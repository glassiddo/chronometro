#!/usr/bin/env python3
"""Verify Boston scope, topology, normalization, transfers, and release bounds."""
import json
from collections import defaultdict, deque
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / "public/data/boston/network.json"
DAILY = ROOT / "public/data/boston/daily"
EXPECTED = {"Red","Orange","Blue","Green-B","Green-C","Green-D","Green-E","Mattapan"}
def require(value, message):
    if not value: raise AssertionError(message)
def main():
    data=json.loads(NETWORK.read_text(encoding="utf-8")); require(set(data["routes"])==EXPECTED,"route scope"); require(len(data["stations"])==124,"station count")
    by_route,graph=defaultdict(list),defaultdict(set)
    for d in data["directions"].values():
        by_route[d["routeId"]].append(d)
        for a,b in zip(d["stations"],d["stations"][1:]): graph[a].add(b); graph[b].add(a)
    for a,dests in data.get("transfers",{}).items():
        for b in dests: graph[a].add(b); graph[b].add(a)
    start=next(iter(data["stations"])); seen={start}; queue=deque([start])
    while queue:
        for item in graph[queue.popleft()]:
            if item not in seen: seen.add(item); queue.append(item)
    require(seen==set(data["stations"]),f"disconnected {set(data['stations'])-seen}")
    labels=lambda rid:{d["label"] for d in by_route[rid]}
    require(labels("Red")=={"Alewife","Ashmont","Braintree"},"Red branches"); require(labels("Mattapan")=={"Ashmont","Mattapan"},"Mattapan")
    require(labels("Green-B")=={"Boston College","Government Center"},"Green B"); require(labels("Green-C")=={"Cleveland Circle","Government Center"},"Green C")
    require(labels("Green-D")=={"Riverside","Union Square"},"Green D"); require(labels("Green-E")=={"Heath Street","Medford/Tufts"},"Green E")
    names={s["name"]:sid for sid,s in data["stations"].items()}
    for pair in [("Longwood","Longwood Medical Area"),("Chestnut Hill","Chestnut Hill Avenue")]: require(all(n in names for n in pair) and names[pair[0]]!=names[pair[1]],f"collapsed {pair}")
    cross={(a,b,sec) for a,dests in data.get("transfers",{}).items() for b,sec in dests.items() if a!=b}; require(cross=={("place-pktrm","place-dwnxg",300),("place-dwnxg","place-pktrm",300)},f"walks {cross}")
    dates=json.loads((DAILY/"index.json").read_text(encoding="utf-8"))["dates"]
    require(dates[0]=="2026-08-30" and dates[-1]=="2026-10-31" and len(dates)==63,"daily bounds")
    require({p.stem for p in DAILY.glob("????-??-??.json")}==set(dates),"daily files differ from calendar")
    print("Boston verification passed: 8 services, 124 stations, connected, 63 days through October 31")
if __name__=="__main__": main()
