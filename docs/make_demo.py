"""Generate the README terminal screenshots (demo.png and diff.png).

These are faithful renderings of real `skillcard` output (captured from actual
runs against DeepSeek), drawn as a terminal window so the README shows the CLI
exactly as a user would see it. Re-run this script after changing the CLI
output to keep the screenshots honest.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

BG = "#1e1e2e"          # terminal background
FG = "#cdd6f4"          # normal text
MUTED = "#6c7086"       # dim text
GREEN = "#a6e3a1"       # grade letter / success
YELLOW = "#f9e2af"      # labels
BLUE = "#89b4fa"        # commands / paths
RED = "#f38ba8"         # warnings
TITLE_BAR = "#313244"
DOT_RED = "#f38ba8"
DOT_YELLOW = "#f9e2af"
DOT_GREEN = "#a6e3a1"

FONT = "DejaVuSansMono.ttf"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSansMono.ttf", "Consolas.ttf", "Menlo.ttc", "monospace.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_terminal(lines: list[tuple[str, str]], title: str, out_path: Path) -> None:
    """Draw a terminal window.

    ``lines`` is a list of ``(color, text)``; color is one of the *_COLOR
    constants above (or any hex string).
    """
    font = _font(18)
    line_h = 26
    pad_x = 24
    pad_top = 56  # title bar + a little air
    pad_bottom = 24

    max_w = 0
    for _color, text in lines:
        w = font.getbbox(text)[2]
        max_w = max(max_w, w)
    width = max(720, max_w + pad_x * 2)
    height = pad_top + len(lines) * line_h + pad_bottom

    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    # Title bar with three macOS-style dots.
    draw.rectangle([0, 0, width, 40], fill=TITLE_BAR)
    title_font = _font(15)
    tw = title_font.getbbox(title)[2]
    draw.text(((width - tw) // 2, 12), title, fill=MUTED, font=title_font)
    for i, color in enumerate((DOT_RED, DOT_YELLOW, DOT_GREEN)):
        x = 16 + i * 24
        draw.ellipse([x, 14, x + 12, 26], fill=color)

    y = pad_top
    for color, text in lines:
        draw.text((pad_x, y), text, fill=color, font=font)
        y += line_h

    img.save(out_path)
    print(f"wrote {out_path}")


def _demo_lines() -> list[tuple[str, str]]:
    """Real output of `skillcard examples/01-excellent.md` (DeepSeek, 2026-10)."""
    return [
        (BLUE, "$ skillcard examples/01-excellent.md"),
        (FG, ""),
        (GREEN, "Grade: A  (91.6/100)"),
        (YELLOW, "  Structure              "), (FG, "100"),
        (YELLOW, "  Trigger accuracy       "), (FG, "88"),
        (YELLOW, "  Boundary robustness    "), (FG, "82"),
        (YELLOW, "  Instruction clarity    "), (FG, "85"),
        (YELLOW, "  Output verifiability   "), (FG, "90"),
        (YELLOW, "  Security               "), (GREEN, "clean"),
        (FG, ""),
        (MUTED, "card:  skillcard-report/card.png"),
        (MUTED, "badge: skillcard-report/badge.svg"),
        (MUTED, "json:  skillcard-report/result.json"),
        (FG, ""),
        (MUTED, "Embed in README:"),
        (MUTED, "  ![skill score](skillcard-report/badge.svg)"),
    ]


def _diff_lines() -> list[tuple[str, str]]:
    """Real output of `skillcard diff before/ after/` after editing a skill."""
    return [
        (BLUE, "$ skillcard diff before/ after/"),
        (FG, ""),
        (FG, "diff: 2 skills (0 added, 0 removed, 2 changed)"),
        (FG, ""),
        (MUTED, "   a/SKILL.md: A  (+0)  failed-checks 0  cost 0 tok"),
        (GREEN, "  +b/SKILL.md: B -> A  (+15)  failed-checks -2  cost 0 tok"),
    ]


def main() -> None:
    _draw_terminal(_demo_lines(), "skillcard", HERE / "demo.png")
    _draw_terminal(_diff_lines(), "skillcard diff", HERE / "diff.png")


if __name__ == "__main__":
    main()
