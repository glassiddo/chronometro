"""Build the NYC coastline SVG from local NYC Planning and US Census sources."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "gouv_new_york_basemap-export/borough-boundaries.geojson"
SURROUNDING_SOURCE = ROOT / "gouv_new_york_basemap-export/surrounding-land.geojson"
OUTPUT = ROOT / "public/data/new-york/coastline.svg"
NETWORK_OUTPUT = ROOT / "public/data/new-york/network-context.svg"
NETWORK_SOURCE = ROOT / "public/data/new-york/network.json"
MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = -74.26, 40.49, -73.68, 40.94
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


def simplify(points, tolerance=.28):
    if len(points) <= 3:
        return points
    distances = [segment_distance(point, points[0], points[-1]) for point in points[1:-1]]
    furthest = max(distances, default=0)
    if furthest <= tolerance:
        return [points[0], points[-1]]
    index = distances.index(furthest) + 1
    return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def ring_path(ring):
    points = simplify([project(point) for point in ring])
    if len(points) < 3:
        return ""
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in points) + "Z"


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    paths = []
    for feature in data["features"]:
        for polygon in feature["geometry"]["coordinates"]:
            path = "".join(filter(None, (ring_path(ring) for ring in polygon)))
            if path:
                paths.append(f'<path d="{path}"/>')
    surrounding = json.loads(SURROUNDING_SOURCE.read_text(encoding="utf-8"))
    nyc_counties = {"Bronx", "Kings", "New York", "Queens", "Richmond"}
    surrounding_paths = []
    for feature in surrounding["features"]:
        if feature["properties"].get("NAME") in nyc_counties:
            continue
        coordinates = feature["geometry"]["coordinates"]
        polygons = coordinates if feature["geometry"]["type"] == "MultiPolygon" else [coordinates]
        for polygon in polygons:
            path = "".join(filter(None, (ring_path(ring) for ring in polygon)))
            if path:
                surrounding_paths.append(f'<path d="{path}"/>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220">'
        '<style>path{vector-effect:non-scaling-stroke}</style>'
        '<title>New York City borough coastline</title>'
        '<desc>NYC Department of City Planning borough boundaries with surrounding US Census geography.</desc>'
        '<path fill="#78c4e4" d="M0,0H320V220H0Z"/>'
        '<g fill="#ece9df" stroke="#8fb7c8" stroke-width="0.55" fill-rule="evenodd">'
        + "".join(surrounding_paths) + '</g>'
        '<g fill="#f7f2e7" stroke="#72a9c1" stroke-width="0.75" fill-rule="evenodd">'
        + "".join(paths) + '</g></svg>\n'
    )
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(paths)} polygons, {len(svg):,} bytes)")

    network = json.loads(NETWORK_SOURCE.read_text(encoding="utf-8"))
    seen = set()
    segments = []
    for direction in network["directions"].values():
        for left_id, right_id in zip(direction["stations"], direction["stations"][1:]):
            key = tuple(sorted((left_id, right_id)))
            if key in seen:
                continue
            seen.add(key)
            left, right = network["stations"][left_id], network["stations"][right_id]
            x1, y1 = project((left["lon"], left["lat"]))
            x2, y2 = project((right["lon"], right["lat"]))
            segments.append(f"M{x1:.1f},{y1:.1f}L{x2:.1f},{y2:.1f}")
    land_paths = "".join(paths)
    overlay = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220">'
        '<style>path{vector-effect:non-scaling-stroke}</style>'
        f'<defs><clipPath id="land">{land_paths}</clipPath></defs>'
        f'<path d="{"".join(segments)}" clip-path="url(#land)" fill="none" stroke="#59656b" '
        'stroke-width="0.65" stroke-linecap="round" stroke-linejoin="round" opacity="0.22"/>'
        '</svg>\n'
    )
    NETWORK_OUTPUT.write_text(overlay, encoding="utf-8")
    print(f"Wrote {NETWORK_OUTPUT} ({len(segments)} segments, {len(overlay):,} bytes)")


if __name__ == "__main__":
    main()
