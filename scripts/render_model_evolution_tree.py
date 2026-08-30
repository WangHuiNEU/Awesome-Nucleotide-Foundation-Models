"""Render a conceptual radial evolution tree from data/models.yaml.

The hierarchy is a catalog taxonomy rather than an inferred phylogeny:
nucleotide models branch by sequence domain, then by catalog scope, with model
families shown as chronologically ordered leaves.
"""
from __future__ import annotations

from collections import Counter
from math import cos, pi, sin
from pathlib import Path
from xml.sax.saxutils import escape

import yaml


ROOT = Path(__file__).resolve().parents[1]
MODELS_FILE = ROOT / "data" / "models.yaml"
OUTPUT_FILE = ROOT / "assets" / "model_evolution_tree.svg"

DOMAIN_ORDER = ("dna", "rna", "dna_rna")
SCOPE_ORDER = ("general", "specialized", "generative", "multimodal")
DOMAIN_LABELS = {
    "dna": "DNA",
    "rna": "RNA",
    "dna_rna": "DNA + RNA",
}
SCOPE_LABELS = {
    "general": "General",
    "specialized": "Specialized",
    "generative": "Generative",
    "multimodal": "Multimodal",
}
DOMAIN_COLORS = {
    "dna": "#2563eb",
    "rna": "#16a34a",
    "dna_rna": "#9333ea",
}
SCOPE_COLORS = {
    "general": "#64748b",
    "specialized": "#d97706",
    "generative": "#dc2626",
    "multimodal": "#7c3aed",
}


def load_models(path: Path = MODELS_FILE) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or []


def svg_text(x, y, value, size=16, weight=400, fill="#111827", anchor="middle", css_class="") -> str:
    class_attribute = f' class="{css_class}"' if css_class else ""
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-family="Inter,Segoe UI,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}"{class_attribute}>{escape(str(value))}</text>'
    )


def polar(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    radians = (angle - 90) * pi / 180
    return cx + radius * cos(radians), cy + radius * sin(radians)


def radial_path(
    cx: float,
    cy: float,
    parent_radius: float,
    parent_angle: float,
    child_radius: float,
    child_angle: float,
) -> str:
    start_x, start_y = polar(cx, cy, parent_radius, parent_angle)
    end_x, end_y = polar(cx, cy, child_radius, child_angle)
    control_radius = parent_radius + (child_radius - parent_radius) * 0.52
    control_1_x, control_1_y = polar(cx, cy, control_radius, parent_angle)
    control_2_x, control_2_y = polar(cx, cy, control_radius, child_angle)
    return (
        f"M {start_x:.2f},{start_y:.2f} "
        f"C {control_1_x:.2f},{control_1_y:.2f} "
        f"{control_2_x:.2f},{control_2_y:.2f} {end_x:.2f},{end_y:.2f}"
    )


def arc_path(cx: float, cy: float, radius: float, start_angle: float, end_angle: float) -> str:
    start_x, start_y = polar(cx, cy, radius, start_angle)
    end_x, end_y = polar(cx, cy, radius, end_angle)
    large_arc = 1 if end_angle - start_angle > 180 else 0
    return (
        f"M {start_x:.2f},{start_y:.2f} "
        f"A {radius:.2f},{radius:.2f} 0 {large_arc} 1 {end_x:.2f},{end_y:.2f}"
    )


def radial_text(
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    value: str,
    *,
    size: int,
    weight: int,
    fill: str,
    css_class: str = "",
) -> str:
    x, y = polar(cx, cy, radius, angle)
    rotation = angle - 90
    anchor = "start"
    if 180 < angle < 360:
        rotation += 180
        anchor = "end"
    class_attribute = f' class="{css_class}"' if css_class else ""
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" transform="rotate({rotation:.2f} {x:.2f} {y:.2f})" '
        f'font-family="Inter,Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" dominant-baseline="middle"{class_attribute}>'
        f"{escape(value)}</text>"
    )


def layout(models: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    grouped = {
        (domain, scope): sorted(
            (model for model in models if model["domain"] == domain and model["scope"] == scope),
            key=lambda item: (item["first_public_date"], item["name"].casefold()),
        )
        for domain in DOMAIN_ORDER
        for scope in SCOPE_ORDER
    }
    nonempty_scopes = {
        domain: [scope for scope in SCOPE_ORDER if grouped[(domain, scope)]]
        for domain in DOMAIN_ORDER
    }

    start_angle = 20.0
    end_angle = 340.0
    domain_gap = 8.0
    scope_gap = 3.5
    domain_gap_count = len(DOMAIN_ORDER) - 1
    scope_gap_count = sum(max(0, len(scopes) - 1) for scopes in nonempty_scopes.values())
    available = end_angle - start_angle - domain_gap * domain_gap_count - scope_gap * scope_gap_count
    leaf_step = available / len(models)

    cursor = start_angle
    leaves: list[dict] = []
    scope_nodes: list[dict] = []
    domain_nodes: list[dict] = []
    for domain_index, domain in enumerate(DOMAIN_ORDER):
        if domain_index:
            cursor += domain_gap
        domain_start = cursor
        for scope_index, scope in enumerate(nonempty_scopes[domain]):
            if scope_index:
                cursor += scope_gap
            scope_start = cursor
            records = grouped[(domain, scope)]
            for record in records:
                leaves.append({"model": record, "angle": cursor + leaf_step / 2})
                cursor += leaf_step
            scope_nodes.append(
                {
                    "domain": domain,
                    "scope": scope,
                    "count": len(records),
                    "start": scope_start,
                    "end": cursor,
                    "angle": (scope_start + cursor) / 2,
                }
            )
        domain_nodes.append(
            {
                "domain": domain,
                "count": sum(len(grouped[(domain, scope)]) for scope in nonempty_scopes[domain]),
                "start": domain_start,
                "end": cursor,
                "angle": (domain_start + cursor) / 2,
            }
        )
    return leaves, scope_nodes, domain_nodes


def render_evolution_tree_svg(input_file: Path = MODELS_FILE, output_file: Path = OUTPUT_FILE) -> None:
    models = load_models(input_file)
    leaves, scope_nodes, domain_nodes = layout(models)
    counts = Counter(model["domain"] for model in models)

    width = 3000
    height = 3000
    cx = width / 2
    cy = 1550
    root_radius = 116
    domain_radius = 255
    scope_radius = 500
    leaf_radius = 985
    label_radius = 1012

    svg = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        ".model-leaf text { transition: fill 120ms ease, font-weight 120ms ease; }",
        ".model-leaf:hover text { fill: #020617; font-weight: 800; }",
        ".model-leaf:hover circle { stroke-width: 4; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fbfbfe"/>',
        svg_text(60, 58, "Nucleotide Foundation Model Evolution Tree", 32, 800, "#0f172a", "start"),
        svg_text(
            60,
            91,
            f"{len(models)} model families • domain → research scope → chronologically ordered model leaves",
            15,
            450,
            "#64748b",
            "start",
        ),
        '<rect x="60" y="112" width="1510" height="48" rx="10" fill="#fff7ed" stroke="#fed7aa"/>',
        svg_text(
            82,
            142,
            "Conceptual taxonomy—not a biological phylogeny or a claim of direct model-to-model ancestry. Select a leaf to open its paper.",
            14,
            600,
            "#9a3412",
            "start",
        ),
    ]

    legend_x = 1770
    svg.append(svg_text(legend_x, 55, "Sequence domain", 13, 700, "#475569", "start"))
    for index, domain in enumerate(DOMAIN_ORDER):
        x = legend_x + index * 190
        svg.append(f'<line x1="{x}" y1="80" x2="{x + 28}" y2="80" stroke="{DOMAIN_COLORS[domain]}" stroke-width="6" stroke-linecap="round"/>')
        svg.append(svg_text(x + 38, 85, f"{DOMAIN_LABELS[domain]} · {counts[domain]}", 13, 650, "#334155", "start"))

    scope_legend_x = 1770
    svg.append(svg_text(scope_legend_x, 126, "Research scope", 13, 700, "#475569", "start"))
    for index, scope in enumerate(SCOPE_ORDER):
        x = scope_legend_x + index * 180
        svg.append(f'<circle cx="{x + 6}" cy="151" r="6" fill="{SCOPE_COLORS[scope]}"/>')
        svg.append(svg_text(x + 20, 156, SCOPE_LABELS[scope], 12, 600, "#475569", "start"))

    for radius, dash in ((domain_radius, "4 10"), (scope_radius, "5 13"), (leaf_radius, "2 10")):
        svg.append(
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#e2e8f0" '
            f'stroke-width="1.2" stroke-dasharray="{dash}"/>'
        )

    domain_by_name = {node["domain"]: node for node in domain_nodes}
    for node in domain_nodes:
        domain = node["domain"]
        color = DOMAIN_COLORS[domain]
        svg.append(
            f'<path d="{arc_path(cx, cy, leaf_radius - 22, node["start"], node["end"])}" '
            f'fill="none" stroke="{color}" stroke-width="8" stroke-linecap="round" opacity="0.22"/>'
        )
        start_x, start_y = polar(cx, cy, root_radius, node["angle"])
        end_x, end_y = polar(cx, cy, domain_radius, node["angle"])
        svg.append(
            f'<path d="M {start_x:.2f},{start_y:.2f} L {end_x:.2f},{end_y:.2f}" '
            f'fill="none" stroke="{color}" stroke-width="9" stroke-linecap="round"/>'
        )

    for node in scope_nodes:
        domain = node["domain"]
        domain_node = domain_by_name[domain]
        color = DOMAIN_COLORS[domain]
        svg.append(
            f'<path d="{radial_path(cx, cy, domain_radius, domain_node["angle"], scope_radius, node["angle"])}" '
            f'fill="none" stroke="{color}" stroke-width="4.2" stroke-linecap="round" opacity="0.76"/>'
        )

    scope_by_key = {(node["domain"], node["scope"]): node for node in scope_nodes}
    for leaf in leaves:
        model = leaf["model"]
        scope_node = scope_by_key[(model["domain"], model["scope"])]
        color = DOMAIN_COLORS[model["domain"]]
        svg.append(
            f'<path d="{radial_path(cx, cy, scope_radius, scope_node["angle"], leaf_radius, leaf["angle"])}" '
            f'fill="none" stroke="{color}" stroke-width="1.55" stroke-linecap="round" opacity="0.36"/>'
        )

    for node in domain_nodes:
        x, y = polar(cx, cy, domain_radius, node["angle"])
        color = DOMAIN_COLORS[node["domain"]]
        label = f'{DOMAIN_LABELS[node["domain"]]} · {node["count"]}'
        box_width = 124 if node["domain"] != "dna_rna" else 170
        svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="18" fill="{color}" stroke="#ffffff" stroke-width="5"/>')
        label_x, label_y = polar(cx, cy, domain_radius + 48, node["angle"])
        svg.append(
            f'<rect x="{label_x - box_width / 2:.2f}" y="{label_y - 17:.2f}" width="{box_width}" height="34" '
            f'rx="17" fill="#ffffff" stroke="{color}" stroke-width="1.6"/>'
        )
        svg.append(svg_text(label_x, label_y + 5, label, 13, 750, color))

    for node in scope_nodes:
        x, y = polar(cx, cy, scope_radius, node["angle"])
        scope_color = SCOPE_COLORS[node["scope"]]
        svg.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="9" fill="{scope_color}" '
            f'stroke="#ffffff" stroke-width="3"/>'
        )
        svg.append(
            radial_text(
                cx,
                cy,
                scope_radius + 22,
                node["angle"],
                f'{SCOPE_LABELS[node["scope"]]} · {node["count"]}',
                size=11,
                weight=700,
                fill=scope_color,
            )
        )

    for leaf in leaves:
        model = leaf["model"]
        angle = leaf["angle"]
        x, y = polar(cx, cy, leaf_radius, angle)
        scope_color = SCOPE_COLORS[model["scope"]]
        url = escape(model.get("first_public_url") or model["paper_url"])
        label = f'{model["first_public_date"]} · {model["name"]}'
        svg.append(f'<a class="model-leaf" href="{url}" xlink:href="{url}">')
        svg.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5.2" fill="{scope_color}" '
            f'stroke="#ffffff" stroke-width="2"/>'
        )
        svg.append(
            radial_text(
                cx,
                cy,
                label_radius,
                angle,
                label,
                size=12,
                weight=550,
                fill="#334155",
                css_class="leaf-label",
            )
        )
        svg.append("</a>")

    svg.extend(
        [
            f'<circle cx="{cx}" cy="{cy}" r="{root_radius}" fill="#ffffff" stroke="#0f172a" stroke-width="4"/>',
            svg_text(cx, cy - 26, "NUCLEOTIDE", 17, 800, "#0f172a"),
            svg_text(cx, cy - 2, "FOUNDATION MODELS", 15, 750, "#0f172a"),
            svg_text(cx, cy + 28, f"{len(models)} families", 14, 600, "#64748b"),
            svg_text(
                60,
                height - 46,
                "Branch hierarchy: sequence domain → catalog scope. Leaf order within each scope follows the earliest verified public date.",
                13,
                500,
                "#64748b",
                "start",
            ),
            "</svg>",
        ]
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    render_evolution_tree_svg()
    print(f"Wrote {OUTPUT_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
