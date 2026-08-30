"""Discover recent DNA, RNA, and unified nucleotide-model candidates.

The scanner is deliberately review-first: it writes only to
data/candidates.yaml.  A human must verify scope and metadata before moving an
entry to data/models.yaml.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import time
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODELS_FILE = DATA_DIR / "models.yaml"
EXCLUDED_FILE = DATA_DIR / "excluded.yaml"
CANDIDATES_FILE = DATA_DIR / "candidates.yaml"
USER_AGENT = "Awesome-Nucleotide-Foundation-Models/1.0 (literature discovery)"

BROAD_QUERIES = [
    "DNA foundation model",
    "DNA language model",
    "DNA pretrained model",
    "genome foundation model",
    "genome language model",
    "genomic foundation model",
    "genomic language model",
    "nucleotide foundation model",
    "nucleotide language model",
    "RNA foundation model",
    "RNA language model",
    "RNA pretrained model",
    "mRNA foundation model",
    "mRNA language model",
    "codon language model",
    "UTR language model",
    "metagenomic foundation model",
    "DNA generative language model",
    "RNA generative language model",
    "DNA BERT",
    "RNA BERT",
    "DNA GPT",
    "RNA GPT",
    "DNA Mamba",
    "RNA Mamba",
]

DNA_TERMS = (
    "dna",
    "genome",
    "genomic",
    "pangenome",
    "metagenome",
    "metagenomic",
    "chromosome",
    "regulatory sequence",
)
RNA_TERMS = (
    "rna",
    "mrna",
    "ncrna",
    "lncrna",
    "utr",
    "codon",
    "transcript sequence",
    "transcriptome sequence",
)
NUCLEOTIDE_TERMS = ("nucleotide", "nucleic acid")
MODEL_TERMS = (
    "foundation model",
    "language model",
    "pre-trained",
    "pretrained",
    "pre-training",
    "pretraining",
    "self-supervised",
    "masked language",
    "causal language",
    "generative model",
    "bert",
    "gpt",
    "mamba",
    "state space model",
    "transformer",
    "diffusion model",
)
STRONG_MODEL_TERMS = (
    "foundation model",
    "language model",
    "pre-trained",
    "pretrained",
    "pre-training",
    "pretraining",
    "self-supervised",
    "masked language",
    "causal language",
)
REVIEW_TERMS = ("benchmark", "survey", "review", "perspective", "evaluation of", "evaluating")
PROFILE_TERMS = (
    "single-cell rna-seq",
    "single cell rna-seq",
    "scrna-seq",
    "expression matrix",
    "expression profile",
    "transcript abundance",
    "methylome profile",
    "spatial transcriptomics",
)
DOWNSTREAM_TITLE_TERMS = (
    "binding site prediction",
    "promoter prediction",
    "site predictor",
    "classification using",
    "detection using",
    "prediction using a pre-trained",
    "prediction using pretrained",
)


@dataclass(frozen=True)
class Candidate:
    title: str
    url: str
    source: str
    date: str
    abstract: str
    query: str


def load_yaml(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or []


def write_yaml(path: Path, records: list[dict]) -> None:
    if not records:
        path.write_text("# Newly discovered candidates pending manual review.\n[]\n", encoding="utf-8")
        return
    path.write_text(
        "# Newly discovered candidates pending manual review.\n"
        + yaml.safe_dump(records, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )


def compact(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_text(value: str | None) -> str:
    value = compact(value).casefold()
    value = re.sub(r"https?://(?:dx\.)?doi\.org/", "doi:", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(value: str | None) -> str:
    if not value:
        return ""
    result = value.strip().rstrip("/").casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/"):
        result = result.replace(prefix, "doi:")
    result = re.sub(r"v\d+$", "", result)
    return result


def known_keys(*record_lists: Iterable[dict]) -> tuple[set[str], set[str], set[str]]:
    names: set[str] = set()
    titles: set[str] = set()
    urls: set[str] = set()
    for records in record_lists:
        for record in records:
            if record.get("name"):
                names.add(normalize_text(record["name"]))
            for alias in record.get("aliases") or []:
                names.add(normalize_text(alias))
            if record.get("title"):
                titles.add(normalize_text(record["title"]))
            url = record.get("paper_url") or record.get("url")
            if url:
                urls.add(normalize_url(url))
    return names, titles, urls


def request_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=35) as response:
        return response.read().decode("utf-8")


def request_json(url: str) -> dict:
    return json.loads(request_text(url))


def query_arxiv(query: str, max_results: int) -> list[Candidate]:
    params = urlencode(
        {
            "search_query": f'all:"{query}"',
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    root = ET.fromstring(request_text(f"https://export.arxiv.org/api/query?{params}"))
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    records = []
    for entry in root.findall("atom:entry", namespace):
        title = compact(entry.findtext("atom:title", default="", namespaces=namespace))
        url = compact(entry.findtext("atom:id", default="", namespaces=namespace))
        submitted = compact(entry.findtext("atom:published", default="", namespaces=namespace))[:10]
        abstract = compact(entry.findtext("atom:summary", default="", namespaces=namespace))
        if title and url:
            records.append(Candidate(title, url, "arXiv", submitted, abstract, query))
    return records


def query_biorxiv(from_date: date, to_date: date) -> list[Candidate]:
    records: list[Candidate] = []
    cursor = 0
    while True:
        url = f"https://api.biorxiv.org/details/biorxiv/{from_date.isoformat()}/{to_date.isoformat()}/{cursor}"
        collection = request_json(url).get("collection") or []
        if not collection:
            break
        for item in collection:
            title = compact(item.get("title"))
            doi = compact(item.get("doi"))
            version = item.get("version") or "1"
            paper_url = f"https://www.biorxiv.org/content/{doi}v{version}" if doi else ""
            if title and paper_url:
                records.append(
                    Candidate(
                        title,
                        paper_url,
                        "bioRxiv",
                        compact(item.get("date")),
                        compact(item.get("abstract")),
                        "bioRxiv recent nucleotide/model filter",
                    )
                )
        if len(collection) < 100:
            break
        cursor += 100
        time.sleep(0.2)
    return records


def query_crossref(query: str, from_date: date, max_results: int) -> list[Candidate]:
    params = urlencode(
        {
            "query.title": query,
            "filter": f"from-pub-date:{from_date.isoformat()}",
            "rows": max_results,
            "sort": "published",
            "order": "desc",
        }
    )
    items = request_json(f"https://api.crossref.org/works?{params}").get("message", {}).get("items", [])
    records = []
    for item in items:
        title_values = item.get("title") or []
        title = compact(title_values[0] if title_values else "")
        doi = compact(item.get("DOI"))
        url = f"https://doi.org/{doi}" if doi else compact(item.get("URL"))
        date_parts = (item.get("published-online") or item.get("published-print") or item.get("created") or {}).get("date-parts") or []
        parts = date_parts[0] if date_parts else []
        published = "-".join(f"{part:02d}" for part in parts) if parts else ""
        abstract = compact(re.sub(r"<[^>]+>", " ", item.get("abstract") or ""))
        if title and url:
            records.append(Candidate(title, url, "Crossref", published, abstract, query))
    return records


def parse_date(value: str) -> date | None:
    if not value:
        return None
    normalized = value.replace(".", "-")
    for fmt, length in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try:
            return datetime.strptime(normalized[:length], fmt).date()
        except ValueError:
            pass
    return None


def contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def score_candidate(candidate: Candidate) -> tuple[int, list[str]]:
    title = normalize_text(candidate.title)
    text = normalize_text(f"{candidate.title} {candidate.abstract}")
    evidence: list[str] = []
    score = 0
    for label, terms in (("dna", DNA_TERMS), ("rna", RNA_TERMS), ("nucleotide", NUCLEOTIDE_TERMS)):
        matches = [term for term in terms if term in text]
        if matches:
            score += 3
            evidence.extend(f"{label}:{term}" for term in matches[:3])
    model_matches = [term for term in MODEL_TERMS if term in text]
    score += min(8, len(model_matches) * 2)
    evidence.extend(f"model:{term}" for term in model_matches[:4])
    if contains_any(title, STRONG_MODEL_TERMS):
        score += 4
    if contains_any(title, REVIEW_TERMS):
        score -= 10
        evidence.append("exclude:review-or-benchmark")
    if contains_any(text, PROFILE_TERMS):
        score -= 8
        evidence.append("exclude:profile-data")
    if contains_any(title, DOWNSTREAM_TITLE_TERMS):
        score -= 6
        evidence.append("low-confidence:downstream-title")
    return score, sorted(set(evidence))


def likely_candidate(candidate: Candidate) -> bool:
    title = normalize_text(candidate.title)
    text = normalize_text(f"{candidate.title} {candidate.abstract}")
    has_nucleotide = contains_any(text, (*DNA_TERMS, *RNA_TERMS, *NUCLEOTIDE_TERMS))
    has_model = contains_any(text, MODEL_TERMS)
    if not (has_nucleotide and has_model):
        return False
    if contains_any(title, REVIEW_TERMS) or contains_any(text, PROFILE_TERMS):
        return False
    if "protein language model" in title and not contains_any(title, (*DNA_TERMS, *RNA_TERMS)):
        return False
    return True


def infer_name(title: str) -> str:
    prefix = compact(title.split(":", 1)[0])
    if 1 <= len(prefix.split()) <= 4 and len(prefix) <= 48:
        return prefix
    match = re.search(r"\b([A-Z][A-Za-z0-9.-]*(?:DNA|RNA|BERT|GPT|LM|FM|Mamba)[A-Za-z0-9.-]*)\b", title)
    return match.group(1) if match else "Needs naming"


def infer_domain(text_value: str) -> str:
    text = normalize_text(text_value)
    has_dna = contains_any(text, DNA_TERMS)
    has_rna = contains_any(text, RNA_TERMS)
    if has_dna and has_rna:
        return "dna_rna"
    if has_rna:
        return "rna"
    if has_dna:
        return "dna"
    return "uncertain"


def infer_scope(text_value: str) -> str:
    text = normalize_text(text_value)
    if contains_any(text, ("generate", "generative", "generation", "design", "diffusion", "autoregressive")):
        return "generative"
    if contains_any(text, ("multimodal", "multi modal", "protein", "structure", "epigenomic", "methylation", "text instruction")):
        return "multimodal"
    if contains_any(text, ("plant", "virus", "viral", "microb", "bacter", "variant", "regulatory", "utr", "codon", "mrna", "ncrna")):
        return "specialized"
    if contains_any(text, STRONG_MODEL_TERMS):
        return "general"
    return "uncertain"


def candidate_record(candidate: Candidate, score: int, evidence: list[str]) -> dict:
    combined = f"{candidate.title} {candidate.abstract}"
    parsed = parse_date(candidate.date)
    date_value = parsed.strftime("%Y.%m") if parsed else ""
    return {
        "name": infer_name(candidate.title),
        "title": candidate.title,
        "url": candidate.url,
        "source": candidate.source,
        "date": date_value,
        "abstract": candidate.abstract,
        "status": "pending_review",
        "domain_hint": infer_domain(combined),
        "scope_hint": infer_scope(combined),
        "reason": "Matched nucleotide-sequence and language/foundation-model signals; requires manual scope and metadata review.",
        "matched_terms": evidence,
        "discovery_query": candidate.query,
        "discovered_at": datetime.now(timezone.utc).date().isoformat(),
        "score": score,
    }


def discover(lookback_days: int, max_results: int, min_score: int) -> list[dict]:
    models = load_yaml(MODELS_FILE)
    excluded = load_yaml(EXCLUDED_FILE)
    existing = load_yaml(CANDIDATES_FILE)
    known_names, known_titles, known_urls = known_keys(models, excluded, existing)
    from_date = datetime.now(timezone.utc).date() - timedelta(days=lookback_days)
    to_date = datetime.now(timezone.utc).date()
    raw: list[Candidate] = []

    def extend(label: str, fetch) -> None:
        try:
            raw.extend(fetch())
        except Exception as exc:
            print(f"WARNING: {label} failed: {exc}")

    for query in BROAD_QUERIES:
        extend(f"arXiv query {query!r}", lambda query=query: query_arxiv(query, max_results))
        time.sleep(0.15)
    extend("bioRxiv recent scan", lambda: query_biorxiv(from_date, to_date))
    for query in BROAD_QUERIES[:12]:
        extend(f"Crossref query {query!r}", lambda query=query: query_crossref(query, from_date, max_results))
        time.sleep(0.15)

    discovered = []
    for candidate in raw:
        title_key = normalize_text(candidate.title)
        url_key = normalize_url(candidate.url)
        name_key = normalize_text(infer_name(candidate.title))
        if title_key in known_titles or url_key in known_urls or (name_key != "needs naming" and name_key in known_names):
            continue
        candidate_date = parse_date(candidate.date)
        if candidate_date and candidate_date < from_date:
            continue
        score, evidence = score_candidate(candidate)
        if score < min_score or not likely_candidate(candidate):
            continue
        record = candidate_record(candidate, score, evidence)
        discovered.append(record)
        known_names.add(name_key)
        known_titles.add(title_key)
        known_urls.add(url_key)
    return sorted(discovered, key=lambda item: (item["date"], item["score"], item["title"]), reverse=True)


def merge_candidates(existing: list[dict], discovered: list[dict]) -> list[dict]:
    _, titles, urls = known_keys(existing)
    merged = list(existing)
    for record in discovered:
        title_key = normalize_text(record["title"])
        url_key = normalize_url(record["url"])
        if title_key in titles or url_key in urls:
            continue
        merged.append(record)
        titles.add(title_key)
        urls.add(url_key)
    return sorted(merged, key=lambda item: (item.get("discovered_at", ""), item.get("score", 0), item["title"]), reverse=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lookback-days", type=int, default=60)
    parser.add_argument("--max-results", type=int, default=12)
    parser.add_argument("--min-score", type=int, default=8)
    parser.add_argument("--update", action="store_true", help="Merge results into data/candidates.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = discover(args.lookback_days, args.max_results, args.min_score)
    if records:
        print(f"Found {len(records)} candidate(s) pending human review:")
        for record in records:
            print(f"- [{record['domain_hint']}/{record['scope_hint']}] {record['title']} | {record['url']}")
    else:
        print("No new nucleotide-model candidates found.")
    if args.update and records:
        write_yaml(CANDIDATES_FILE, merge_candidates(load_yaml(CANDIDATES_FILE), records))
        print(f"Updated {CANDIDATES_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
