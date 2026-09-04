"""Convert the GLA's downloaded gla.zip to an unsimplified WGS84 GeoJSON.

One-off data preparation; requires geopandas/pyogrio/pyproj. Normal builds do not.
Usage: py scripts/convert_london_boundary.py path/to/gla.zip
"""

import json
import sys
from pathlib import Path

import geopandas as gpd


def main():
    archive = Path(sys.argv[1]).resolve().as_posix()
    frame = gpd.read_file(f"/vsizip/{archive}/gla/London_GLA_Boundary.shp")
    assert len(frame) == 1 and frame.geometry.is_valid.all()
    assert frame.crs.to_epsg() == 27700, frame.crs
    frame = frame.to_crs(4326)
    assert frame.geometry.is_valid.all()
    data = json.loads(frame.to_json())
    output = Path(__file__).resolve().parents[1] / "config/london-city-boundary.geojson"
    output.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Saved {len(frame)} valid feature, EPSG:27700 -> EPSG:4326: {output}")


if __name__ == "__main__":
    main()
