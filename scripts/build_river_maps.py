"""Download and simplify OSM river centerlines for the orientation maps.

Run: python scripts/build_river_maps.py [--source cached-overpass.json]
Geometry: OpenStreetMap contributors, ODbL 1.0.
https://www.openstreetmap.org/copyright
The query envelopes extend beyond the padded map viewports. Whole ways are
retained so rivers cross map edges naturally; the SVG viewport clips them.
"""
import argparse
import json
import math
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

REGIONS = {
    'paris': ((48.74, 2.08, 49.00, 2.62), 'Seine|Marne'),
    'london': ((51.27, -.68, 51.73, .40), 'Thames|River Lea|River Lee'),
    'chicago': ((41.60, -88.02, 42.18, -87.42), 'Chicago River|Calumet River|North Shore Channel|Sanitary and Ship Canal'),
    'washington-dc': ((38.64, -77.66, 39.25, -76.68), 'Potomac|Anacostia'),
    'boston': ((42.10, -71.44, 42.56, -70.68), 'Charles River|Mystic River|Neponset River|Chelsea Creek'),
    'berlin': ((52.29, 12.93, 52.78, 13.80), 'Spree|Havel|Landwehrkanal'),
}


def query():
    ways = ''.join(f'way["waterway"~"^(river|canal|stream|tidal_channel)$"]["name"~"{names}"]({",".join(map(str, bounds))});relation["type"="waterway"]["name"~"{names}"]({",".join(map(str, bounds))});'
                   for bounds, names in REGIONS.values())
    return '[out:json][timeout:90];(' + ways + ');(._;way(r););out geom;'


def simplify(points, epsilon=.00008):
    if len(points) < 3:
        return points
    x, y = points[0]
    dx, dy = points[-1][0] - x, points[-1][1] - y
    length = dx * dx + dy * dy
    distances = []
    for px, py in points[1:-1]:
        t = max(0, min(1, ((px-x)*dx + (py-y)*dy) / length)) if length else 0
        distances.append(math.hypot(px-x-t*dx, py-y-t*dy))
    index = max(range(len(distances)), key=distances.__getitem__)
    if distances[index] <= epsilon:
        return [points[0], points[-1]]
    index += 1
    return simplify(points[:index+1], epsilon)[:-1] + simplify(points[index:], epsilon)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--save-source', type=Path)
    args = parser.parse_args()
    if args.source:
        source = json.loads(args.source.read_text(encoding='utf-8'))
    else:
        request = urllib.request.Request('https://overpass-api.de/api/interpreter',
            data=urllib.parse.urlencode({'data': query()}).encode(),
            headers={'User-Agent': 'Chronometro map geometry build'})
        with urllib.request.urlopen(request, timeout=120) as response:
            source = json.load(response)
    if source.get('remark'):
        raise RuntimeError(source['remark'])
    if args.save_source:
        args.save_source.write_text(json.dumps(source), encoding='utf-8')
    root = Path(__file__).resolve().parents[1]
    member_names = {}
    for element in source['elements']:
        if element['type'] == 'relation':
            for member in element.get('members', []):
                if member['type'] == 'way' and member.get('role', '') in ('', 'main_stream', 'side_stream'):
                    member_names[member['ref']] = element.get('tags', {}).get('name', '')
    for city, (bounds, names) in REGIONS.items():
        if not (root / 'config/cities' / f'{city}.json').exists():
            continue
        south, west, north, east = bounds
        features = []
        for element in source['elements']:
            if element['type'] != 'way':
                continue
            name = element.get('tags', {}).get('name') or member_names.get(element['id'], '')
            geometry = element.get('geometry', [])
            if not re.search(names, name) or not any(south <= p['lat'] <= north and west <= p['lon'] <= east for p in geometry):
                continue
            points = simplify([[p['lon'], p['lat']] for p in geometry])
            features.append({'id': element['id'], 'name': name,
                'points': [[round(x, 6), round(y, 6)] for x, y in points]})
        if not features:
            raise RuntimeError(f'No river geometry for {city}')
        output = root / 'public/data' / city / 'rivers.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({'source': 'OpenStreetMap contributors',
            'license': 'ODbL-1.0', 'sourceUrl': 'https://www.openstreetmap.org/copyright',
            'snapshot': source.get('osm3s', {}).get('timestamp_osm_base', str(date.today())),
            'queryBounds': bounds, 'rivers': features}, separators=(',', ':')) + '\n', encoding='utf-8')
        print(f'{city}: {len(features)} segments, {output.stat().st_size} bytes', flush=True)


if __name__ == '__main__':
    main()
