#!/usr/bin/env python3
"""City-neutral entry point for building a Chronométro data bundle."""

from __future__ import annotations

import argparse

import build_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a configured Chronométro city.")
    parser.add_argument("city", nargs="?", default="paris")
    args, remaining = parser.parse_known_args()
    build_data.configure_city(args.city)
    build_data.main(remaining)


if __name__ == "__main__":
    main()
