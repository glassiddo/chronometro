#!/usr/bin/env python3
"""Download a reproducible raw snapshot of selected TfL rail API data."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "gouv_london_tfl-export"
BASE_URL = "https://api.tfl.gov.uk"
DEFAULT_MODES = ("tube", "elizabeth-line")


def read_local_env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env.local"
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip("'\"")
    return values


class TflDownloader:
    def __init__(self, output: Path, app_key: str, refresh: bool) -> None:
        self.output = output
        self.app_key = app_key
        self.refresh = refresh
        self.request_count = 0
        self.cached_count = 0

    def get(self, endpoint: str, destination: Path, allow_not_found: bool = False):
        missing_marker = destination.with_suffix(destination.suffix + ".missing")
        if allow_not_found and missing_marker.exists() and not self.refresh:
            self.cached_count += 1
            return None
        if destination.exists() and not self.refresh:
            self.cached_count += 1
            return json.loads(destination.read_text(encoding="utf-8"))

        separator = "&" if "?" in endpoint else "?"
        url = f"{BASE_URL}{endpoint}"
        if self.app_key:
            url += f"{separator}app_key={urllib.parse.quote(self.app_key)}"

        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "Chronometro-data-builder/1.0"},
        )
        payload = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = json.load(response)
                break
            except urllib.error.HTTPError as error:
                # Do not print the requested URL because it contains the API key.
                if error.code == 404 and allow_not_found:
                    missing_marker.parent.mkdir(parents=True, exist_ok=True)
                    missing_marker.write_text("404\n", encoding="ascii")
                    return None
                if error.code not in {429, 500, 502, 503, 504} or attempt == 4:
                    raise RuntimeError(f"TfL returned HTTP {error.code} for {endpoint}") from None
                delay = 2 ** (attempt + 1)
                print(f"TfL HTTP {error.code}; retrying in {delay}s.", flush=True)
                time.sleep(delay)
            except urllib.error.URLError as error:
                if attempt == 4:
                    raise RuntimeError(
                        f"Could not reach TfL for {endpoint}: {error.reason}"
                    ) from None
                delay = 2 ** (attempt + 1)
                print(f"TfL connection error; retrying in {delay}s.", flush=True)
                time.sleep(delay)

        if payload is None:
            raise RuntimeError(f"TfL returned no data for {endpoint}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(destination)
        if missing_marker.exists():
            missing_marker.unlink()
        self.request_count += 1
        return payload


def timetable_options(payload: dict | None) -> list[tuple[str, str]]:
    """Return direction/endpoint pairs from a TfL timetable disambiguation."""
    options = (payload or {}).get("disambiguation", {}).get("disambiguationOptions", [])
    found = []
    for option in options:
        endpoint = option.get("uri") or ""
        parsed = urllib.parse.urlparse(endpoint)
        direction = urllib.parse.parse_qs(parsed.query).get("direction", [""])[0]
        if endpoint and direction:
            found.append((direction, endpoint))
    return sorted(set(found))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stop_ids(stop_points: list[dict]) -> list[str]:
    return sorted({stop["id"] for stop in stop_points if stop.get("id")})


def ordered_segments(sequence_payloads: list[dict]) -> list[tuple[str, str]]:
    segments = set()
    for payload in sequence_payloads:
        for route in payload.get("orderedLineRoutes", []):
            ids = route.get("naptanIds", [])
            segments.update(zip(ids, ids[1:]))
    return sorted(segments)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--skip-timetables", action="store_true")
    parser.add_argument("--skip-journeys", action="store_true")
    parser.add_argument("--modes", nargs="+", default=list(DEFAULT_MODES))
    parser.add_argument("--journey-date", default="20260825", help="YYYYMMDD representative weekday.")
    parser.add_argument("--journey-time", default="0800", help="HHMM representative departure time.")
    args = parser.parse_args()

    app_key = read_local_env().get("TFL_APP_KEY", "")
    downloader = TflDownloader(args.output, app_key, args.refresh)
    credential = "configured API key" if app_key else "anonymous access"
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"Downloading TfL {', '.join(args.modes)} snapshot using {credential}.", flush=True)

    lines_by_id: dict[str, dict] = {}
    for mode in args.modes:
        encoded_mode = urllib.parse.quote(mode, safe="")
        mode_lines = downloader.get(
            f"/Line/Mode/{encoded_mode}", args.output / "modes" / f"{mode}.json"
        )
        for line in mode_lines:
            lines_by_id[line["id"]] = line
    lines = [lines_by_id[line_id] for line_id in sorted(lines_by_id)]
    (args.output / "lines.json").write_text(
        json.dumps(lines, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    line_ids = sorted(line["id"] for line in lines)
    all_station_ids: set[str] = set()
    missing_timetables: list[dict[str, str]] = []

    for index, line_id in enumerate(line_ids, start=1):
        encoded_line = urllib.parse.quote(line_id, safe="")
        print(f"[{index}/{len(line_ids)}] {line_id}", flush=True)
        stops = downloader.get(
            f"/Line/{encoded_line}/StopPoints",
            args.output / "lines" / line_id / "stop-points.json",
        )
        ids = stop_ids(stops)
        all_station_ids.update(ids)

        sequences = []
        for direction in ("inbound", "outbound"):
            sequences.append(downloader.get(
                f"/Line/{encoded_line}/Route/Sequence/{direction}?serviceTypes=Regular",
                args.output / "lines" / line_id / f"sequence-{direction}.json",
            ))

        if not args.skip_journeys and lines_by_id[line_id].get("modeName") == "elizabeth-line":
            for from_id, to_id in ordered_segments(sequences):
                encoded_from = urllib.parse.quote(from_id, safe="")
                encoded_to = urllib.parse.quote(to_id, safe="")
                downloader.get(
                    f"/Journey/JourneyResults/{encoded_from}/to/{encoded_to}"
                    f"?mode=elizabeth-line&date={args.journey_date}&time={args.journey_time}"
                    "&timeIs=Departing&journeyPreference=LeastTime",
                    args.output / "lines" / line_id / "journeys" / f"{from_id}--{to_id}.json",
                )

        if args.skip_timetables:
            continue
        for stop_id in ids:
            encoded_stop = urllib.parse.quote(stop_id, safe="")
            timetable_path = args.output / "lines" / line_id / "timetables" / f"{stop_id}.json"
            timetable = downloader.get(
                f"/Line/{encoded_line}/Timetable/{encoded_stop}",
                timetable_path,
                allow_not_found=True,
            )
            if timetable is None:
                missing_timetables.append({"lineId": line_id, "stopPointId": stop_id})
                continue
            for direction, endpoint in timetable_options(timetable):
                directional = downloader.get(
                    endpoint,
                    args.output / "lines" / line_id / "timetables" / f"{stop_id}-{direction}.json",
                    allow_not_found=True,
                )
                if directional is None:
                    missing_timetables.append(
                        {"lineId": line_id, "stopPointId": stop_id, "direction": direction}
                    )

    # Preserve the full StopPoint records independently of their line responses.
    for index, station_id in enumerate(sorted(all_station_ids), start=1):
        if index == 1 or index % 50 == 0:
            print(f"Stations: {index}/{len(all_station_ids)}", flush=True)
        encoded_station = urllib.parse.quote(station_id, safe="")
        downloader.get(
            f"/StopPoint/{encoded_station}",
            args.output / "stop-points" / f"{station_id}.json",
        )

    data_files = sorted(
        path for path in args.output.rglob("*.json") if path.name not in {"metadata.json", "manifest.json"}
    )
    modified_times = [datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) for path in data_files]
    manifest = {
        "algorithm": "sha256",
        "files": [
            {"path": path.relative_to(args.output).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in data_files
        ],
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    metadata = {
        "source": "Transport for London Unified API",
        "baseUrl": BASE_URL,
        "snapshotStartedAt": started_at,
        "snapshotCompletedAt": datetime.now(timezone.utc).isoformat(),
        "fileModifiedFrom": min(modified_times).isoformat() if modified_times else None,
        "fileModifiedTo": max(modified_times).isoformat() if modified_times else None,
        "modes": args.modes,
        "lineIds": line_ids,
        "stationCount": len(all_station_ids),
        "timetablesIncluded": not args.skip_timetables,
        "journeysIncluded": not args.skip_journeys,
        "journeyReference": {"date": args.journey_date, "time": args.journey_time, "timeIs": "Departing"},
        "missingTimetables": missing_timetables,
        "fileCount": len(data_files),
        "manifest": "manifest.json",
        "refreshed": args.refresh,
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"Done: {downloader.request_count} downloaded, {downloader.cached_count} cached, "
        f"{len(all_station_ids)} stations.",
        flush=True,
    )


if __name__ == "__main__":
    main()
