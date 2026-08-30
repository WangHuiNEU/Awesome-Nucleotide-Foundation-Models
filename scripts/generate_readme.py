"""Generate README.md from the structured nucleotide-model catalog."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

import yaml

try:
    from scripts.render_model_evolution_tree import render_evolution_tree_svg
    from scripts.render_model_timeline import render_timeline_svg
except ModuleNotFoundError:  # Allows `python scripts/generate_readme.py`.
    from render_model_evolution_tree import render_evolution_tree_svg
    from render_model_timeline import render_timeline_svg


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
README_FILE = ROOT / "README.md"

DOMAIN_LABELS = {
    "dna": "DNA",
    "rna": "RNA",
    "dna_rna": "DNA + RNA",
}
DOMAIN_ANCHORS = {
    "dna": "dna-models",
    "rna": "rna-models",
    "dna_rna": "dna--rna-models",
}
SCOPE_LABELS = {
    "general": "General",
    "specialized": "Specialized",
    "generative": "Generative",
    "multimodal": "Multimodal",
}
STATUS_LABELS = {
    "peer_reviewed": "published",
    "preprint": "preprint",
    "model_release": "release",
}


def load_yaml(name: str):
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or ([] if name != "catalog.yaml" else {})


def compact(value) -> str:
    if value is None or value == "":
        return "—"
    return re.sub(r"\s+", " ", str(value)).strip()


def cell(value) -> str:
    return compact(value).replace("|", "\\|")


def link(label: str, url: str | None) -> str:
    if not url:
        return ""
    return f"[{label}]({url})"


def domain_list(domains: list[str]) -> str:
    return " / ".join(DOMAIN_LABELS[value] for value in domains)


def resource_links(record: dict) -> str:
    resources = [link("paper", record["paper_url"])]
    if record.get("code_url"):
        resources.append(link("code", record["code_url"]))
    if record.get("weights_url"):
        resources.append(link("weights", record["weights_url"]))
    return " · ".join(resources)


def render_model_table(records: list[dict]) -> str:
    lines = [
        "| Model | First public | Scope | Focus | Architecture | Tokenization | Params | Context | Resources |",
        "|---|---:|---|---|---|---|---:|---:|---|",
    ]
    for record in sorted(records, key=lambda item: (item["first_public_date"], item["name"].lower()), reverse=True):
        marker = " ⭐" if record.get("notable_claim") else ""
        name = f"[{cell(record['name'])}]({record['paper_url']}){marker}"
        date = link(record["first_public_date"], record.get("first_public_url"))
        date += f"<br><sub>{STATUS_LABELS[record['publication_status']]}</sub>"
        lines.append(
            "| "
            + " | ".join(
                [
                    name,
                    date,
                    SCOPE_LABELS[record["scope"]],
                    cell(record["focus"]),
                    cell(record["architecture"]),
                    cell(record["tokenization"]),
                    cell(record.get("parameters")),
                    cell(record.get("context_length")),
                    resource_links(record),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_model_notes(records: list[dict], domain: str) -> str:
    label = DOMAIN_LABELS[domain]
    lines = [f"<details>", f"<summary><strong>{label} model notes ({len(records)})</strong></summary>", ""]
    for record in sorted(records, key=lambda item: (item["first_public_date"], item["name"].lower())):
        details = []
        if record.get("pretraining_data"):
            details.append(f"data: {compact(record['pretraining_data'])}")
        if record.get("objective"):
            details.append(f"objective: {compact(record['objective'])}")
        suffix = f" _({' · '.join(details)})_" if details else ""
        lines.append(f"- **[{record['name']}]({record['paper_url']})** — {compact(record['summary'])}{suffix}")
    lines.extend(["", "</details>"])
    return "\n".join(lines)


def render_resource_table(records: list[dict]) -> str:
    lines = ["| Resource | Domain | Date | Description | Links |", "|---|---|---:|---|---|"]
    for record in sorted(records, key=lambda item: (item["date"], item["name"].lower()), reverse=True):
        resources = link("paper", record["url"])
        if record.get("code_url"):
            resources += " · " + link("code", record["code_url"])
        lines.append(
            f"| **{cell(record['name'])}** | {domain_list(record['domains'])} | {record['date']} | "
            f"{cell(record['summary'])} | {resources} |"
        )
    return "\n".join(lines)


def build_readme() -> str:
    catalog = load_yaml("catalog.yaml")
    models = load_yaml("models.yaml")
    benchmarks = load_yaml("benchmarks.yaml")
    surveys = load_yaml("surveys.yaml")

    by_domain = {domain: [model for model in models if model["domain"] == domain] for domain in DOMAIN_LABELS}
    scope_counts = Counter(model["scope"] for model in models)
    repository = catalog["repository"]
    reviewed = catalog["last_reviewed"]
    reviewed_badge = reviewed.replace("-", "--")

    parts = [
        "# Awesome Nucleotide Foundation Models",
        "",
        f"[![Awesome](https://awesome.re/badge.svg)](https://awesome.re) "
        f"[![CI](https://github.com/{repository}/actions/workflows/validate.yml/badge.svg)](https://github.com/{repository}/actions/workflows/validate.yml) "
        "[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) "
        f"![Last reviewed](https://img.shields.io/badge/last_reviewed-{reviewed_badge}-2563eb)",
        "",
        "A curated, continuously maintained catalog of **DNA, RNA, and unified DNA+RNA sequence language and foundation models**—with structured metadata for papers, code, checkpoints, architectures, tokenization, objectives, training data, scale, and context length.",
        "",
        f"> **Coverage snapshot ({reviewed}):** **{len(models)} models** — {len(by_domain['dna'])} DNA, {len(by_domain['rna'])} RNA, and {len(by_domain['dna_rna'])} DNA+RNA — plus {len(benchmarks)} benchmarks and {len(surveys)} surveys. This is a living catalog: “comprehensive” describes the systematic scope, not a claim that no model can be missing.",
        "",
        "> **UltraGen priority claim.** [UltraGen](https://doi.org/10.21203/rs.3.rs-4461517/v1) is **the first RNA language model pre-trained on in vitro-synthesized RNA libraries**, using 10 million experimentally generated UltraSelex sequences.",
        "",
        "## Scope",
        "",
        "Included entries learn directly from raw nucleotide sequences through self-supervised, autoregressive, diffusion, contrastive, or comparable large-scale pre-training and introduce a reusable representation or generation model. The catalog intentionally includes general models, domain- or organism-specialized models, generative models, and multimodal models in which nucleotide sequence remains a learned modality.",
        "",
        "Excluded are ordinary downstream predictors, systems that only consume embeddings from another nucleotide model, RNA-seq or methylation matrices without raw-sequence pre-training, single-cell expression foundation models, protein-only models, and structure systems that do not introduce a reusable nucleotide sequence model. Borderline decisions are documented in [`data/excluded.yaml`](data/excluded.yaml); the exact schema is in [`docs/SCHEMA.md`](docs/SCHEMA.md).",
        "",
        "## Contents",
        "",
        "- [At a glance](#at-a-glance)",
        "- [Timeline](#timeline)",
        "- [Model evolution tree](#model-evolution-tree)",
        "- [DNA models](#dna-models)",
        "- [RNA models](#rna-models)",
        "- [DNA + RNA models](#dna--rna-models)",
        "- [Model notes](#model-notes)",
        "- [Benchmarks](#benchmarks)",
        "- [Surveys](#surveys)",
        "- [Contributing](#contributing)",
        "",
        "## At a glance",
        "",
        "| View | Count | What it covers |",
        "|---|---:|---|",
        f"| DNA | {len(by_domain['dna'])} | Genomes, regulatory DNA, variants, metagenomes, plants, microbes and DNA generation |",
        f"| RNA | {len(by_domain['rna'])} | ncRNA, mRNA/CDS, UTRs, structure-aware representation and RNA generation/design |",
        f"| DNA + RNA | {len(by_domain['dna_rna'])} | Unified nucleotide or cross-central-dogma models with explicit DNA and RNA sequence signal |",
        f"| General | {scope_counts['general']} | Broad reusable nucleotide representations |",
        f"| Specialized | {scope_counts['specialized']} | Organism-, region-, process- or task-family-focused pre-training |",
        f"| Generative | {scope_counts['generative']} | Autoregressive, diffusion or conditional sequence design |",
        f"| Multimodal | {scope_counts['multimodal']} | Nucleotide sequence jointly modeled with structure, function, protein, text or epigenomic information |",
        "",
        "Dates in the catalog use the earliest public preprint, model release, or paper that we have verified. A later peer-reviewed publication date is stored separately in the YAML metadata.",
        "",
        "## Timeline",
        "",
        f"[![Timeline of {len(models)} nucleotide models](assets/model_timeline.svg)](assets/model_timeline.svg)",
        "",
        "## Model evolution tree",
        "",
        "This radial tree is a **conceptual catalog taxonomy**, not a biological phylogeny or a claim of direct ancestry between models. It branches by sequence domain and research scope; model leaves are ordered by earliest verified public date within each branch.",
        "",
        "[Open the full-size interactive SVG](assets/model_evolution_tree.svg); each model leaf links to its primary paper.",
        "",
        f"[![Conceptual evolution tree of {len(models)} nucleotide models](assets/model_evolution_tree.svg)](assets/model_evolution_tree.svg)",
        "",
    ]

    for domain in DOMAIN_LABELS:
        parts.extend(
            [
                f"## {DOMAIN_LABELS[domain]} models",
                "",
                render_model_table(by_domain[domain]),
                "",
            ]
        )

    parts.extend(["## Model notes", ""])
    for domain in DOMAIN_LABELS:
        parts.extend([render_model_notes(by_domain[domain], domain), ""])

    parts.extend(
        [
            "## Benchmarks",
            "",
            render_resource_table(benchmarks),
            "",
            "## Surveys",
            "",
            render_resource_table(surveys),
            "",
            "## Contributing",
            "",
            "Missing a model or found incorrect metadata? Contributions are welcome.",
            "",
            "1. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and the [`data/models.yaml`](data/models.yaml) schema.",
            "2. Add or correct the structured YAML record; do not hand-edit generated catalog tables.",
            "3. Run `python generate_paper_list.py` and `python scripts/validate_data.py`.",
            "4. Submit the metadata, generated README and timeline in one pull request.",
            "",
            "Automated discovery places possible papers in `data/candidates.yaml` for human review. It never promotes a candidate directly into the confirmed catalog.",
            "",
            "## Acknowledgements",
            "",
            "This catalog grew from [COLA-Laboratory/Awesome-RNA-Foundation-Models](https://github.com/COLA-Laboratory/Awesome-RNA-Foundation-Models) and draws seed references from primary papers and major genome/RNA language-model surveys. Model descriptions should always be checked against the linked primary sources.",
            "",
            "## License",
            "",
            "[MIT](LICENSE)",
            "",
        ]
    )
    return "\n".join(parts)


def main() -> int:
    render_timeline_svg()
    render_evolution_tree_svg()
    README_FILE.write_text(build_readme(), encoding="utf-8")
    print(
        f"Wrote {README_FILE.relative_to(ROOT)}, assets/model_timeline.svg, "
        "and assets/model_evolution_tree.svg"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
