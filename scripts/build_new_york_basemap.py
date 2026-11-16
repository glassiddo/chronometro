"""Build the NYC coastline SVG from local NYC Planning and US Census sources."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "gouv_new_york_basemap-export/borough-boundaries.geojson"
SURROUNDING_SOURCE = ROOT / "gouv_new_york_basemap-export/surrounding-land.geojson"
OUTPUT = ROOT / "public/data/new-york/coastline.svg"
MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = -74.50, 40.30, -73.30, 41.20
WIDTH, HEIGHT = 320, 220
PAD = 12


def project(point):
    lon, lat = point
    return (PAD + (lon - MIN_LON) / (MAX_LON - MIN_LON) * (WIDTH - PAD * 2),
            PAD + (MAX_LAT - lat) / (MAX_LAT - MIN_LAT) * (HEIGHT - PAD * 2))


def segment_distance(point, start, end):
    px, py = point; ax, ay = start; bx, by = end
    dx, dy = bx - ax, by - ay
    if not dx and not dy:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** .5
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** .5


def simplify(points, tolerance=.8):
    if len(points) <= 3:
        return points
    distances = [segment_distance(point, points[0], points[-1]) for point in points[1:-1]]
    furthest = max(distances, default=0)
    if furthest <= tolerance:
        return [points[0], points[-1]]
    index = distances.index(furthest) + 1
    return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def ring_path(ring):
    projected = [project(point) for point in ring]
    # Tiny islands and shoreline fragments add noise at orientation-map scale.
    area = abs(sum(a[0] * b[1] - b[0] * a[1]
                   for a, b in zip(projected, projected[1:]))) / 2
    if area < 3:
        return ""
    points = simplify(projected)
    if len(points) < 3:
        return ""
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in points) + "Z"


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    paths = []
    for feature in data["features"]:
        for polygon in feature["geometry"]["coordinates"]:
            path = ring_path(polygon[0])
            if path:
                paths.append(f'<path d="{path}"/>')
    surrounding = json.loads(SURROUNDING_SOURCE.read_text(encoding="utf-8"))
    nyc_counties = {"Bronx", "Kings", "New York", "Queens", "Richmond"}
    surrounding_paths = []
    for feature in surrounding["features"]:
        if feature["properties"].get("NAME", "").removesuffix(" County") in nyc_counties:
            continue
        coordinates = feature["geometry"]["coordinates"]
        polygons = coordinates if feature["geometry"]["type"] == "MultiPolygon" else [coordinates]
        for polygon in polygons:
            path = ring_path(polygon[0])
            if path:
                surrounding_paths.append(f'<path d="{path}"/>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220">'
        '<style>path{vector-effect:non-scaling-stroke}</style>'
        '<title>New York City borough coastline</title>'
        '<desc>NYC Department of City Planning borough boundaries with surrounding US Census geography.</desc>'
        '<path fill="#b9ddec" d="M0,0H320V220H0Z"/>'
        '<g fill="#ece9df" stroke="none" fill-rule="evenodd">'
        + "".join(surrounding_paths) + '</g>'
        '<g fill="#f1eee3" stroke="#9c9588" stroke-width="0.45" fill-rule="evenodd">'
        + "".join(paths) + '</g></svg>\n'
    )
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(paths)} polygons, {len(svg):,} bytes)")



if __name__ == "__main__":
    main()
