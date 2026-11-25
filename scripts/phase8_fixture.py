"""Seed, serve, and verify synthetic Phase 8 data in dedicated PostgreSQL databases."""

import argparse
import json
import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import uvicorn
from cloudinary.exceptions import Error
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Department, Organization, Role, ServiceArea
from app.db.session import create_database_engine
from app.main import create_app
from app.schemas.auth import StaffInput
from app.services import evidence, gemini
from app.services.access import provision_staff
from app.services.auth import add_user


def load_settings() -> Settings:
    settings = Settings(app_env="test")
    database = settings.database_url.path or ""
    if re.fullmatch(r"/civicfix_ai_test_phase8(?:_[a-z0-9_]+)?", database) is None:
        raise SystemExit("Set DATABASE_URL to a dedicated Phase 8 test database.")
    return settings


def seed(settings: Settings, path: Path) -> None:
    tag = uuid4().hex[:8]
    password = "synthetic phase eight passphrase"
    latitude = round(12.013579 + (int(tag, 16) % 50000) / 100000, 6)
    longitude = 77.432198

    def account(role: str) -> dict:
        return {"full_name": f"Phase 8 {role} {tag}", "email": f"phase8-{role}-{tag}@example.com", "password": password}

    fixture = {role: account(role) for role in ("citizen", "other", "admin", "staff", "outside")}
    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as db:
            admin = add_user(db, **fixture["admin"], role=Role.ADMIN)
            add_user(db, **fixture["other"], role=Role.CITIZEN)
            organization = Organization(name=f"Phase 8 water authority {tag}")
            db.add(organization)
            db.flush()
            department = Department(organization_id=organization.id, code=f"WATER-{tag.upper()}", name="Water repairs")
            db.add(department)
            areas = []
            for index, lat in enumerate((latitude, latitude + 0.02)):
                lng = longitude
                ring = [
                    [lng - .0004, lat - .0004], [lng + .0004, lat - .0004], [lng + .0004, lat + .0004],
                    [lng - .0004, lat + .0004], [lng - .0004, lat - .0004],
                ]
                area = ServiceArea(
                    organization_id=organization.id, name=f"Synthetic service area {index + 1}",
                    boundary_geojson={"type": "Polygon", "coordinates": [ring]},
                )
                db.add(area)
                areas.append(area)
            db.commit()
            for role, area in zip(("staff", "outside"), areas):
                person = provision_staff(db, admin, StaffInput(
                    **fixture[role], organization_id=organization.id, department_ids={department.id}, service_area_ids={area.id},
                ))
                fixture[role]["id"] = str(person.user.id)
            fixture.update(
                tag=tag, latitude=latitude, longitude=longitude, department_id=str(department.id),
                department_code=department.code, organization_id=str(organization.id),
            )
    finally:
        engine.dispose()
    path.write_text(json.dumps(fixture), encoding="utf-8")
    print("Seeded synthetic admin, two area-scoped staff accounts, and the second citizen.")


def serve(settings: Settings, fixture: dict, port: int) -> None:
    config = settings.model_copy(update={
        "gemini_model": "phase8-fixture", "gemini_api_key": SecretStr("fixture"),
        "gemini_timeout_seconds": 0.25, "cors_origins": "http://localhost:5188",
        "cloudinary_cloud_name": "fixture", "cloudinary_api_key": SecretStr("fixture"), "cloudinary_api_secret": SecretStr("fixture"),
    })

    def gemini_reply(request, *, timeout):
        payload = json.loads(request.data)
        text = json.loads(payload["contents"][0]["parts"][0]["text"])
        if text["title"].startswith("Gemini timeout"):
            raise TimeoutError("Synthetic timeout")
        result = {
            "category": "WATER_LEAKAGE", "summary": "Water pooling around a broken supply pipe.",
            "priority": "HIGH", "priority_reason": "The issue affects water service near a road.",
            "recommended_department_code": fixture["department_code"], "confidence": .88,
            "needs_human_review": False, "safety_flags": [],
        }
        return BytesIO(json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(result)}]}}]}).encode())

    def fail_upload(*args, **kwargs):
        raise Error("Synthetic Cloudinary outage")

    gemini.urlopen = gemini_reply
    evidence.uploader.upload = fail_upload
    uvicorn.run(create_app(config), host="127.0.0.1", port=port, access_log=False)


def snapshot(settings: Settings, fixture: dict, report: dict) -> None:
    prefix = settings.api_v1_prefix
    with TestClient(create_app(settings)) as client:
        def get(path, *, method="GET", headers=None, body=None):
            response = client.request(method, prefix + path, headers=headers, json=body)
            if response.status_code != 200:
                raise RuntimeError(f"{method} {path} returned HTTP {response.status_code}")
            return response.json()["data"]

        def sign_in(role):
            account = fixture[role]
            result = get("/auth/login", method="POST", headers={"X-CivicFix-CSRF": "1"},
                         body={"email": account["email"], "password": account["password"]})
            return {"Authorization": "Bearer " + result["access_token"]}

        citizen, admin = sign_in("citizen"), sign_in("admin")
        complaint = get(f"/complaints/{report['id']}", headers=citizen)
        history = get(f"/complaints/{report['id']}/updates?page_size=100", headers=citizen)
        audit = get(f"/admin/audit-logs?entity_id={report['id']}&page_size=100", headers=admin)
        feedback = get(f"/complaints/{report['id']}/feedback", headers=citizen)
    if complaint["public_reference"] != report["reference"] or complaint["status"] != "RESOLVED":
        raise RuntimeError("The restored report reference or status differs.")
    if not {"COMPLAINT_ASSIGNED", "COMPLAINT_STATUS_CHANGED", "COMPLAINT_NOTE_ADDED"}.issubset(
        {entry["action"] for entry in audit}
    ):
        raise RuntimeError("The report's audited staff actions are incomplete.")
    print(json.dumps({
        "reference": complaint["public_reference"], "status": complaint["status"], "history": history,
        "audit": audit, "feedback": feedback,
    }, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seed", "serve", "snapshot"))
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--port", type=int, default=8004)
    options = parser.parse_args()
    settings = load_settings()
    if options.mode == "seed":
        seed(settings, options.fixture)
        return
    fixture = json.loads(options.fixture.read_text(encoding="utf-8"))
    if options.mode == "serve":
        serve(settings, fixture, options.port)
        return
    if options.report is None:
        parser.error("snapshot requires --report")
    snapshot(settings, fixture, json.loads(options.report.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
