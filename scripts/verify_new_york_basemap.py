"""Keep coarse NYC county land from filling the detailed coastline's water."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

import build_new_york_basemap as builder


def feature(name, lon):
    ring = [[lon, 40.7], [lon + .04, 40.7], [lon + .04, 40.74],
            [lon, 40.74], [lon, 40.7]]
    return {"properties": {"NAME": name},
            "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]}}


with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
    folder = Path(temporary)
    boroughs, counties, output = (folder / name for name in ("boroughs.json", "counties.json", "map.svg"))
    boroughs.write_text(json.dumps({"features": [feature("Queens", -73.9)]}), encoding="utf-8")
    counties.write_text(json.dumps({"features": [feature("Queens County", -73.95),
                                                feature("Hudson County", -74.1)]}), encoding="utf-8")
    with patch.multiple(builder, SOURCE=boroughs, SURROUNDING_SOURCE=counties, OUTPUT=output):
        builder.main()
    svg = ET.parse(output).getroot()
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    groups = svg.findall("svg:g", namespace)
    assert len(groups[0]) == 1, "NYC county polygons must not overwrite bays and rivers"
    assert len(groups[1]) == 1, "Detailed borough land must remain visible"
    assert groups[0][0].get("d") == builder.ring_path(feature("Hudson", -74.1)["geometry"]["coordinates"][0][0])
    assert svg.find("svg:path", namespace).get("fill") == "#b9ddec", "Use the shared muted water palette"
print("NYC basemap county exclusion and palette checks passed.")
