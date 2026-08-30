"""Backward-compatible entry point for catalog validation."""

from validate_data import validate


if __name__ == "__main__":
    raise SystemExit(validate())
