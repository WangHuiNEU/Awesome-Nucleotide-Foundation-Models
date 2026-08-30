"""Validate catalog metadata and cross-file invariants."""
from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

MODEL_FIELDS = {
    "name",
    "title",
    "paper_url",
    "first_public_date",
    "first_public_url",
    "publication_date",
    "publication_status",
    "domain",
    "scope",
    "focus",
    "code_url",
    "weights_url",
    "architecture",
    "tokenization",
    "objective",
    "parameters",
    "context_length",
    "pretraining_data",
    "summary",
}
RESOURCE_FIELDS = {"name", "title", "url", "date", "domains", "summary"}
EXCLUDED_FIELDS = {"name", "title", "paper_url", "date", "reason"}
CANDIDATE_FIELDS = {
    "title",
    "url",
    "source",
    "date",
    "status",
    "domain_hint",
    "scope_hint",
    "reason",
    "matched_terms",
    "discovery_query",
    "discovered_at",
}

ALLOWED_DOMAINS = {"dna", "rna", "dna_rna"}
ALLOWED_SCOPES = {"general", "specialized", "generative", "multimodal"}
ALLOWED_STATUSES = {"peer_reviewed", "preprint", "model_release"}
DATE_RE = re.compile(r"^(\d{4})\.(\d{2})$")
ULTRAGEN_CLAIM = "The first RNA language model pre-trained on in vitro-synthesized RNA libraries."


def load_yaml(name: str):
    with (DATA_DIR / name).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or ([] if name != "catalog.yaml" else {})


def normalized(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def valid_url(value: str | None) -> bool:
    if value is None:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def check_date(value: str | None, label: str, errors: list[str], *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        errors.append(f"{label}: expected YYYY.MM, got {value!r}")
        return
    year, month = map(int, value.split("."))
    if not 1 <= month <= 12:
        errors.append(f"{label}: invalid month {month}")
    if (year, month) > (date.today().year, date.today().month):
        errors.append(f"{label}: date is in the future")


def duplicate_values(records: list[dict], field: str) -> list[str]:
    values = [normalized(record.get(field)) for record in records if record.get(field)]
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if value and count > 1)


def validate_models(models: list[dict], errors: list[str]) -> None:
    for index, record in enumerate(models, 1):
        name = record.get("name") or f"record #{index}"
        missing = sorted(MODEL_FIELDS - set(record))
        if missing:
            errors.append(f"{name}: missing fields: {', '.join(missing)}")
        if record.get("name") in {None, "", "-"}:
            errors.append(f"{name}: placeholder or empty model name")
        if record.get("domain") not in ALLOWED_DOMAINS:
            errors.append(f"{name}: invalid domain {record.get('domain')!r}")
        if record.get("scope") not in ALLOWED_SCOPES:
            errors.append(f"{name}: invalid scope {record.get('scope')!r}")
        if record.get("publication_status") not in ALLOWED_STATUSES:
            errors.append(f"{name}: invalid publication_status {record.get('publication_status')!r}")
        check_date(record.get("first_public_date"), f"{name}.first_public_date", errors)
        check_date(record.get("publication_date"), f"{name}.publication_date", errors, nullable=True)
        for field in ("paper_url", "first_public_url", "code_url", "weights_url"):
            if not valid_url(record.get(field)):
                errors.append(f"{name}: invalid {field}: {record.get(field)!r}")
        for field in ("architecture", "tokenization", "objective"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f"{name}: {field} must be a non-empty string")
        for field in ("parameters", "context_length", "pretraining_data"):
            if record.get(field) == "-":
                errors.append(f"{name}: use null rather than '-' for unknown {field}")
        if len(record.get("summary", "")) < 40:
            errors.append(f"{name}: summary is too short")
        aliases = record.get("aliases", [])
        if aliases is not None and (not isinstance(aliases, list) or not all(isinstance(item, str) for item in aliases)):
            errors.append(f"{name}: aliases must be a list of strings")

    for field in ("name", "title", "paper_url"):
        duplicates = duplicate_values(models, field)
        if duplicates:
            errors.append(f"models: duplicate normalized {field}: {', '.join(duplicates)}")

    name_index = {record["name"]: record for record in models if record.get("name")}
    ultragen = name_index.get("UltraGen")
    if not ultragen:
        errors.append("UltraGen: required catalog record is missing")
    elif ultragen.get("notable_claim") != ULTRAGEN_CLAIM:
        errors.append("UltraGen: protected in-vitro-synthesized RNA priority claim changed or missing")

    counts = Counter(record.get("domain") for record in models)
    if len(models) < 100:
        errors.append(f"catalog regression: expected at least 100 models, found {len(models)}")
    if counts["dna"] < 40 or counts["rna"] < 40 or counts["dna_rna"] < 5:
        errors.append(f"domain coverage regression: {dict(counts)}")


def validate_resources(records: list[dict], kind: str, errors: list[str]) -> None:
    for index, record in enumerate(records, 1):
        name = record.get("name") or f"{kind} #{index}"
        missing = sorted(RESOURCE_FIELDS - set(record))
        if missing:
            errors.append(f"{kind} {name}: missing fields: {', '.join(missing)}")
        check_date(record.get("date"), f"{kind} {name}.date", errors)
        if not valid_url(record.get("url")) or not valid_url(record.get("code_url")):
            errors.append(f"{kind} {name}: invalid URL")
        domains = record.get("domains")
        if not isinstance(domains, list) or not domains or not set(domains) <= ALLOWED_DOMAINS:
            errors.append(f"{kind} {name}: invalid domains {domains!r}")
        if len(record.get("summary", "")) < 30:
            errors.append(f"{kind} {name}: summary is too short")
    if duplicate_values(records, "name"):
        errors.append(f"{kind}: duplicate names")


def validate_excluded(excluded: list[dict], model_names: set[str], errors: list[str]) -> None:
    for index, record in enumerate(excluded, 1):
        name = record.get("name") or f"excluded #{index}"
        missing = sorted(EXCLUDED_FIELDS - set(record))
        if missing:
            errors.append(f"{name}: missing excluded fields: {', '.join(missing)}")
        check_date(record.get("date"), f"{name}.date", errors)
        if not valid_url(record.get("paper_url")):
            errors.append(f"{name}: invalid paper_url")
        if record.get("name") in model_names:
            errors.append(f"{name}: present in both models.yaml and excluded.yaml")


def validate_candidates(candidates: list[dict], known_titles: set[str], known_urls: set[str], errors: list[str]) -> None:
    for index, record in enumerate(candidates, 1):
        name = record.get("title") or f"candidate #{index}"
        missing = sorted(CANDIDATE_FIELDS - set(record))
        if missing:
            errors.append(f"{name}: missing candidate fields: {', '.join(missing)}")
        if record.get("domain_hint") not in {*ALLOWED_DOMAINS, "uncertain"}:
            errors.append(f"{name}: invalid domain_hint {record.get('domain_hint')!r}")
        if record.get("scope_hint") not in {*ALLOWED_SCOPES, "uncertain"}:
            errors.append(f"{name}: invalid scope_hint {record.get('scope_hint')!r}")
        if normalized(record.get("title")) in known_titles:
            errors.append(f"{name}: candidate title is already known")
        if normalized(record.get("url")) in known_urls:
            errors.append(f"{name}: candidate URL is already known")


def validate() -> int:
    catalog = load_yaml("catalog.yaml")
    models = load_yaml("models.yaml")
    benchmarks = load_yaml("benchmarks.yaml")
    surveys = load_yaml("surveys.yaml")
    excluded = load_yaml("excluded.yaml")
    candidates = load_yaml("candidates.yaml")
    errors: list[str] = []

    for key in ("title", "repository", "last_reviewed", "scope_version", "description"):
        if not catalog.get(key):
            errors.append(f"catalog.yaml: missing {key}")
    try:
        date.fromisoformat(catalog.get("last_reviewed", ""))
    except ValueError:
        errors.append("catalog.yaml: last_reviewed must be YYYY-MM-DD")

    validate_models(models, errors)
    validate_resources(benchmarks, "benchmark", errors)
    validate_resources(surveys, "survey", errors)

    model_names = {record.get("name") for record in models}
    validate_excluded(excluded, model_names, errors)
    known_titles = {normalized(record.get("title")) for record in [*models, *excluded]}
    known_urls = {normalized(record.get("paper_url")) for record in [*models, *excluded]}
    validate_candidates(candidates, known_titles, known_urls, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    counts = Counter(record["domain"] for record in models)
    print(
        f"Validated {len(models)} models "
        f"(DNA {counts['dna']}, RNA {counts['rna']}, DNA+RNA {counts['dna_rna']}), "
        f"{len(benchmarks)} benchmarks, {len(surveys)} surveys, "
        f"{len(excluded)} exclusions, and {len(candidates)} candidates."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(validate())
