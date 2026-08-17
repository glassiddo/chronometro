# Chronométro

Chronométro is a daily route puzzle based on the Paris transport network. Each day has five journeys. Pick the lines, directions, stops, and walking connections that get you from one station to another in the least time.

Play at [chronometro.cc](https://chronometro.cc/).

## How it works

The game represents stations and connections as a weighted graph. It uses Dijkstra's algorithm to find the route with the lowest estimated travel time.

Travel time includes:

- time on the train or tram
- estimated waiting time
- transfers and walking links included in the source data

Waiting times use half the median scheduled gap between departures from 7:00-10:00 AM. The model does not include the time needed to enter the first station or reach the initial platform.

An exact match with the stored fastest route scores 100 points. Other successful routes score from 10 to 99 based on their extra travel time. Giving up scores 0. The five daily puzzles add up to a maximum of 500 points.

## Network data

The current game data comes from an ITO World modified GTFS export based on Île-de-France Mobilités data:

- version `20260630_200738`
- valid from 27 June to 29 July 2026

The game includes the Metro, RER A to E, and tram lines T1 to T14. Buses, ORLYVAL, and CDG VAL are not included.

This is a fixed timetable snapshot. It does not account for current delays, closures, disruptions, accessibility, fares, or later network changes.

## Privacy

Chronométro has no accounts or cookies and does not save progress in the browser. Routes and scores disappear when the page is reloaded or closed.

## Credits

Route data: Île-de-France Mobilités and ITO World.

Chronométro is not affiliated with or endorsed by RATP or Île-de-France Mobilités.
