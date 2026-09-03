"""Make a small static Boston coastline SVG from a MassGIS GeoJSON export.

Source: https://services1.arcgis.com/hGdibHYSPO59RG1h/ArcGIS/rest/services/Massachusetts_Municipalities_Hosted/FeatureServer/0
Query envelope: -71.40,42.10,-70.85,42.60; inSR/outSR=4326; f=geojson.
Run with the downloaded GeoJSON path as the first argument.
"""
import json
import sys
from pathlib import Path


def project(point):
    lon, lat = point[:2]
    return (12 + (lon + 71.33) / .55 * 296, 12 + (42.46 - lat) / .27 * 196)


def simplify(points, tolerance=.25):
    if len(points) < 3:
        return points
    x, y = points[0]
    dx, dy = points[-1][0] - x, points[-1][1] - y
    length = dx * dx + dy * dy
    distances = []
    for px, py in points[1:-1]:
        t = max(0, min(1, ((px-x)*dx + (py-y)*dy) / length)) if length else 0
        distances.append(((px-x-t*dx)**2 + (py-y-t*dy)**2)**.5)
    furthest = max(range(len(distances)), key=distances.__getitem__)
    if distances[furthest] <= tolerance:
        return [points[0], points[-1]]
    split = furthest + 1
    return simplify(points[:split+1], tolerance)[:-1] + simplify(points[split:], tolerance)


source = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))


def clip_ring(points):
    for axis, edge, sign in [(0, -1, 1), (0, 321, -1), (1, -1, 1), (1, 221, -1)]:
        clipped = []
        for a, b in zip(points, points[1:] + points[:1]):
            inside_a = (a[axis] - edge) * sign >= 0
            inside_b = (b[axis] - edge) * sign >= 0
            if inside_a:
                clipped.append(a)
            if inside_a != inside_b:
                t = (edge - a[axis]) / (b[axis] - a[axis])
                clipped.append(tuple(a[i] + t * (b[i] - a[i]) for i in range(2)))
        points = clipped
    return points + points[:1]


paths = []
for feature in source['features']:
    geometry = feature['geometry']
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    for polygon in polygons:
        rings = []
        for ring in polygon:
            points = simplify(clip_ring([project(point) for point in ring]))
            if len(points) < 4:
                continue
            rings.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x,y in points) + 'Z')
        paths.append('<path d="' + ''.join(rings) + '"/>')
svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 220"><title>Boston Harbor coastline</title><desc>MassGIS (Bureau of Geographic Information), Commonwealth of Massachusetts EOTSS. Generalized municipal coastline, simplified to a quarter pixel.</desc><path fill="#b9ddec" d="M0,0H320V220H0Z"/><g fill="#f1eee3" stroke="#f1eee3" stroke-width="0.35" fill-rule="evenodd">' + ''.join(paths) + '</g></svg>\n'
output = Path(__file__).resolve().parents[1] / 'public/data/boston/coastline.svg'
output.write_text(svg, encoding='utf-8')
print(f'{output}: {output.stat().st_size} bytes')
