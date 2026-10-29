"""Static SVG badge with shields.io-style visuals."""

from __future__ import annotations

from pathlib import Path

from skillcard.models import EvalResult, grade_color

SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img"
  aria-label="skillcard: {message}">
  <title>skillcard: {message}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{width}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{msg_w}" height="20" fill="{color}"/>
    <rect width="{width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif"
     font-size="110">
    <text x="{label_x}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)"
          textLength="{label_len}">skillcard</text>
    <text x="{label_x}" y="140" transform="scale(.1)"
          textLength="{label_len}">skillcard</text>
    <text x="{msg_x}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)"
          textLength="{msg_len}">{message}</text>
    <text x="{msg_x}" y="140" transform="scale(.1)" textLength="{msg_len}">{message}</text>
  </g>
</svg>
"""

CHAR_W = 6.5  # approx width per char at font-size 11


def render_badge(result: EvalResult, out_path: str | Path) -> Path:
    message = f"{result.grade} | {result.total_score:.0f}/100"
    label_w = int(CHAR_W * len("skillcard")) + 12
    msg_w = int(CHAR_W * len(message)) + 12
    svg = SVG_TEMPLATE.replace("{width}", str(label_w + msg_w))
    svg = svg.replace("{label_w}", str(label_w))
    svg = svg.replace("{msg_w}", str(msg_w))
    svg = svg.replace("{label_x}", str(label_w * 5))
    svg = svg.replace("{msg_x}", str(label_w * 10 + msg_w * 5))
    svg = svg.replace("{label_len}", str((label_w - 10) * 10))
    svg = svg.replace("{msg_len}", str((msg_w - 10) * 10))
    svg = svg.replace("{color}", grade_color(result.grade))
    svg = svg.replace("{message}", message)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    return out
