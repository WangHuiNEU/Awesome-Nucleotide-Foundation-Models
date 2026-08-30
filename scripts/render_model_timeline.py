"""Render an SVG timeline from data/models.yaml."""
from __future__ import annotations

from math import ceil
from pathlib import Path
from xml.sax.saxutils import escape

import yaml


ROOT = Path(__file__).resolve().parents[1]
MODELS_FILE = ROOT / "data" / "models.yaml"
OUTPUT_FILE = ROOT / "assets" / "model_timeline.svg"

DOMAIN_LABELS = {
    "dna": "DNA",
    "rna": "RNA",
    "dna_rna": "DNA + RNA",
}
DOMAIN_COLORS = {
    "dna": "#2563eb",
    "rna": "#16a34a",
    "dna_rna": "#9333ea",
}


def load_models(path: Path = MODELS_FILE) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or []


def svg_text(x, y, value, size=16, weight=400, fill="#111827", anchor="middle") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Inter,Segoe UI,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def short_name(value: str, limit: int = 17) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def position(index: int, columns: int, left: float, step_x: float, row_y: list[int]):
    row = index // columns
    col = index % columns
    if row % 2:
        col = columns - 1 - col
    return left + col * step_x, row_y[row], row


def render_timeline_svg(input_file: Path = MODELS_FILE, output_file: Path = OUTPUT_FILE) -> None:
    models = sorted(load_models(input_file), key=lambda item: (item["first_public_date"], item["name"].lower()))
    columns = 10
    rows = ceil(len(models) / columns)
    width = 1600
    left = 92
    right = width - 92
    step_x = (right - left) / (columns - 1)
    top = 212
    row_gap = 126
    row_y = [top + index * row_gap for index in range(rows)]
    height = row_y[-1] + 96
    points = [position(i, columns, left, step_x, row_y)[:2] for i in range(len(models))]

    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfbfd"/>',
        svg_text(38, 43, "Nucleotide Language Model Timeline", 30, 800, "#111827", "start"),
        svg_text(38, 72, f"{len(models)} DNA, RNA, and unified DNA+RNA model families • first public release dates", 15, 400, "#6b7280", "start"),
        '<rect x="38" y="91" width="990" height="42" rx="8" fill="#eff6ff" stroke="#bfdbfe"/>',
        svg_text(56, 116, "Read each row in the arrow direction. Select a model label to open its primary paper.", 13, 650, "#1d4ed8", "start"),
    ]

    legend_x = width - 430
    for offset, domain in enumerate(DOMAIN_LABELS):
        x = legend_x + offset * 132
        svg.append(f'<circle cx="{x}" cy="52" r="7" fill="{DOMAIN_COLORS[domain]}"/>')
        svg.append(svg_text(x + 14, 57, DOMAIN_LABELS[domain], 13, 600, "#374151", "start"))

    for row in range(rows):
        indices = [i for i in range(len(models)) if i // columns == row]
        xs = [position(i, columns, left, step_x, row_y)[0] for i in indices]
        y = row_y[row]
        svg.append(f'<line x1="{min(xs)}" y1="{y}" x2="{max(xs)}" y2="{y}" stroke="#d4d4d8" stroke-width="2"/>')
        arrow = "→" if row % 2 == 0 else "←"
        arrow_x = min(xs) - 42 if row % 2 == 0 else max(xs) + 42
        svg.append(svg_text(arrow_x, y + 7, arrow, 24, 800, "#52525b"))

    svg.append(
        '<polyline points="'
        + " ".join(f"{x},{y}" for x, y in points)
        + '" fill="none" stroke="#3f3f46" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
    )

    box_width = 142
    box_height = 42
    for index, model in enumerate(models):
        x, y, row = position(index, columns, left, step_x, row_y)
        color = DOMAIN_COLORS[model["domain"]]
        box_y = y - 66 if row % 2 == 0 else y + 24
        connector_end = box_y + box_height if row % 2 == 0 else box_y
        url = escape(model.get("first_public_url") or model["paper_url"])

        svg.append(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{connector_end}" stroke="{color}" stroke-width="2"/>')
        svg.append(f'<circle cx="{x}" cy="{y}" r="9" fill="{color}" stroke="#ffffff" stroke-width="3"/>')
        svg.append(f'<a href="{url}" xlink:href="{url}">')
        svg.append(
            f'<rect x="{x - box_width / 2}" y="{box_y}" width="{box_width}" height="{box_height}" '
            f'rx="8" fill="#ffffff" stroke="{color}" stroke-width="1.4"/>'
        )
        svg.append(svg_text(x, box_y + 16, model["first_public_date"], 11, 500, "#71717a"))
        svg.append(svg_text(x, box_y + 32, short_name(model["name"]), 12, 700, "#18181b"))
        svg.append("</a>")

    svg.append("</svg>")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    render_timeline_svg()
    print(f"Wrote {OUTPUT_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
