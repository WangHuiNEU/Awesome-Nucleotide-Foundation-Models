"""Refresh candidate domain/scope hints without promoting confirmed models."""
from __future__ import annotations

import argparse

from discover_candidates import (
    CANDIDATES_FILE,
    infer_domain,
    infer_scope,
    load_yaml,
    write_yaml,
)


def classify(update: bool) -> int:
    records = load_yaml(CANDIDATES_FILE)
    if not records:
        print("No pending candidate records to classify.")
        return 0

    changed = 0
    for record in records:
        text = f"{record.get('title', '')} {record.get('abstract', '')}"
        domain = infer_domain(text)
        scope = infer_scope(text)
        if record.get("domain_hint") != domain or record.get("scope_hint") != scope:
            record["domain_hint"] = domain
            record["scope_hint"] = scope
            changed += 1
        print(f"- [{domain}/{scope}] {record.get('title', '<untitled>')}")

    if update and changed:
        write_yaml(CANDIDATES_FILE, records)
        print(f"Updated hints for {changed} candidate(s); no confirmed model records were changed.")
    else:
        print(f"Reviewed {len(records)} candidate hint(s); no confirmed model records were changed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="Write refreshed hints to data/candidates.yaml")
    return parser.parse_args()


def main() -> int:
    return classify(parse_args().update)


if __name__ == "__main__":
    raise SystemExit(main())
