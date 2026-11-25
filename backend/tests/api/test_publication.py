from decimal import Decimal
from io import BytesIO
from uuid import UUID

from cloudinary.exceptions import Error
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import func, select

from app.api.public_map import _approximate
from app.db.complaint_models import Complaint
from app.db.evidence_models import ComplaintImage
from app.services import evidence
from test_complaints import API, QUEUE, REPORTS, _admin, _citizen, _data, _report, _site, _staff


def test_approximate_marker_does_not_repeat_exact_grid_centers():
    original = (Decimal("89.995"), Decimal("-179.995"))
    public = _approximate(*original, Decimal("0.01"))
    assert public == (Decimal("89.985"), Decimal("-179.985"))


def test_map_only_returns_approved_fields_and_approximate_coordinates(client, db):
    site = _site(db)
    other_area = _site(db, organization=site.organization, department=site.department)
    admin = _admin(client, db)
    _, staff = _staff(client, admin, site)
    _, outsider = _staff(client, admin, other_area)
    reporter, citizen = _citizen(client)
    _, other_citizen = _citizen(client)
    title = "Synthetic private leaking pipe"
    exact = (site.latitude + 0.000031, site.longitude + 0.000043)
    private, approximate = [
        _data(client.post(REPORTS, headers=citizen, json=_report(site, title=title, latitude=exact[0], longitude=exact[1])), 201)
        for _ in range(2)
    ]
    complaint_id = approximate["id"]
    endpoint = f"{QUEUE}/{complaint_id}/visibility"
    note = "Private maintenance notes for fixture."
    _data(client.post(f"{QUEUE}/{complaint_id}/updates", headers=staff, json={"message": note, "visibility": "INTERNAL"}), 201)
    settings = {"visibility": "APPROXIMATE", "approved_public_summary": "Water leak near the junction", "reason": "Approved for public display."}
    assert client.patch(endpoint, headers=outsider, json=settings).status_code == 404
    assert client.patch(endpoint, headers=citizen, json=settings).status_code == 403
    assert client.patch(endpoint, headers=staff, json={
        **settings, "approved_public_summary": f"Reported by {reporter['full_name']} at {reporter['email']}",
    }).status_code == 422
    assert client.get(f"{REPORTS}/{complaint_id}", headers=other_citizen).status_code == 404
    assert client.get(f"{REPORTS}/{complaint_id}/updates", headers=outsider).status_code == 404
    _data(client.patch(endpoint, headers=staff, json=settings))

    maps = f"{API}/public/complaints/map"
    response = client.get(maps)
    markers = {item["public_reference"]: item for item in _data(response)}
    assert private["public_reference"] not in markers
    marker = markers[approximate["public_reference"]]
    assert set(marker) == {
        "public_reference", "title", "category", "status", "latitude", "longitude",
        "location_precision", "created_on", "updated_on",
    }
    assert marker["location_precision"] == "approximate" and marker["title"] == settings["approved_public_summary"]
    assert all(marker[key] != approximate[key] for key in ("latitude", "longitude"))
    assert all(abs(marker[key] - approximate[key]) <= 0.01 for key in ("latitude", "longitude"))
    for secret in [note, reporter["email"], reporter["full_name"], reporter["id"], title, "Synthetic private address"]:
        assert secret not in response.text
    assert client.get(f"{API}/public/complaints/{private['public_reference']}").status_code == 404
    assert approximate["public_reference"] not in client.get(maps + "?status=CLOSED").text
    audit = _data(client.get(f"{API}/admin/audit-logs?entity_id={complaint_id}&action=COMPLAINT_VISIBILITY_CHANGED", headers=admin))
    assert audit[0]["event_metadata"]["new_visibility"] == "APPROXIMATE"

    # A malformed legacy publication with raw coordinates still gets coarsened.
    row = db.get(Complaint, UUID(complaint_id))
    row.public_latitude, row.public_longitude = row.latitude, row.longitude
    db.commit()
    repaired = next(item for item in _data(client.get(maps)) if item["public_reference"] == row.public_reference)
    assert (repaired["latitude"], repaired["longitude"]) == (marker["latitude"], marker["longitude"])
    _data(client.patch(endpoint, headers=staff, json={"visibility": "PRIVATE", "reason": "Marker hidden by staff."}))
    assert row.public_reference not in client.get(maps).text


def test_optional_evidence_validates_content_and_survives_storage_failure(client, db, monkeypatch):
    site = _site(db)
    _, citizen = _citizen(client)
    _, outsider = _citizen(client)
    case = _data(client.post(REPORTS, headers=citizen, json=_report(site)), 201)
    path = f"{REPORTS}/{case['id']}/images"
    config = client.app.state.settings.model_copy(update={
        "cloudinary_cloud_name": "synthetic-fixture", "cloudinary_api_key": SecretStr("synthetic-key"),
        "cloudinary_api_secret": SecretStr("synthetic-secret"), "max_upload_size_mb": 1, "max_images_per_complaint": 1,
    })
    client.app.state.settings = config
    client.app.state.evidence = evidence.CloudinaryEvidence(config)
    png = BytesIO()
    Image.new("RGB", (8, 8), "orange").save(png, format="PNG")
    payload = {"file": ("synthetic.png", png.getvalue(), "image/png")}
    assert client.post(path, headers=outsider, files=payload).status_code == 404
    assert client.post(path + "?kind=RESOLUTION", headers=citizen, files=payload).status_code == 403
    assert client.post(path, headers=citizen, files={"file": ("bad.png", b"<svg />", "image/png")}).status_code == 422
    assert client.post(path, headers=citizen, files={"file": ("big.png", bytes(1048577), "image/png")}).status_code == 413

    def fail(*args, **options):
        raise Error("Synthetic provider detail")

    monkeypatch.setattr(evidence.uploader, "upload", fail)
    response = client.post(path, headers=citizen, files=payload)
    assert response.status_code == 503 and "Synthetic provider detail" not in response.text
    assert db.scalar(select(func.count()).select_from(ComplaintImage).where(
        ComplaintImage.complaint_id == UUID(case["id"]),
    )) == 0
    assert _data(client.get(f"{REPORTS}/{case['id']}", headers=citizen))["public_reference"] == case["public_reference"]

    def store(file, **options):
        key = options["public_id"]
        assert "synthetic.png" not in key and options["type"] == "authenticated" and options["overwrite"] is False
        with Image.open(file) as sanitized:
            assert sanitized.format == "JPEG" and not sanitized.getexif()
        return {
            "public_id": key, "secure_url": f"https://res.cloudinary.com/synthetic-fixture/image/authenticated/{key}.jpg",
            "resource_type": "image", "type": "authenticated",
        }

    monkeypatch.setattr(evidence.uploader, "upload", store)
    result = _data(client.post(path, headers=citizen, files=payload), 201)
    assert set(result) == {"id", "created_at", "mime_type", "image_kind"} and result["mime_type"] == "image/jpeg"
    assert client.post(path, headers=citizen, files=payload).status_code == 409
