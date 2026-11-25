from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Organization, ServiceArea


def _ring_contains(ring: object, x: Decimal, y: Decimal) -> bool | None:
    if not isinstance(ring, list) or len(ring) < 4:
        return None
    vertices = []
    for point in ring:
        if (
            not isinstance(point, list)
            or len(point) < 2
            or type(point[0]) not in (int, float)
            or type(point[1]) not in (int, float)
            or not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90)
        ):
            return None
        vertices.append((Decimal(str(point[0])), Decimal(str(point[1]))))
    if vertices[0] != vertices[-1] or len(set(vertices)) < 3:
        return None
    edges = list(zip(vertices, vertices[1:]))
    if any(abs(a[0] - b[0]) > 180 for a, b in edges):
        return None

    inside = False
    for (ax, ay), (bx, by) in edges:
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if cross == 0 and min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by):
            return True
        if (ay > y) != (by > y) and (cross > 0) == (by > ay):
            inside = not inside
    return inside


def _contains(geometry: object, longitude: Decimal, latitude: Decimal) -> bool:
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        return False
    coordinates = geometry.get("coordinates")
    polygons = [coordinates] if geometry["type"] == "Polygon" else coordinates
    if not isinstance(polygons, list) or not polygons:
        return False
    matches = []
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            return False
        rings = [_ring_contains(ring, longitude, latitude) for ring in polygon]
        if None in rings:
            return False
        matches.append(rings[0] and not any(rings[1:]))
    return any(matches)


def find_intake_area(db: Session, longitude: Decimal, latitude: Decimal) -> ServiceArea | None:
    areas = db.scalars(
        select(ServiceArea)
        .join(Organization, Organization.id == ServiceArea.organization_id)
        .where(ServiceArea.is_active, Organization.is_active, ServiceArea.boundary_geojson.is_not(None))
    )
    match = None
    for area in areas:
        if _contains(area.boundary_geojson, longitude, latitude):
            if match is not None:
                return None
            match = area
    return match
