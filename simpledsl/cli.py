from __future__ import annotations

import sys
from pathlib import Path

from .musicxml import MusicXmlExporter
from .parser import DslParser
from .sheet_svg import SheetSvgExporter


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    input_path = Path(args[0]) if len(args) > 0 else Path("input.dsl")
    musicxml_path = Path(args[1]) if len(args) > 1 else Path("output.musicxml")
    svg_path = Path(args[2]) if len(args) > 2 else musicxml_path.with_suffix(".svg")

    try:
        score = DslParser.parse(input_path.read_text(encoding="utf-8"))
        musicxml_path.write_text(MusicXmlExporter.export(score), encoding="utf-8")
        svg_path.write_text(SheetSvgExporter.export(score), encoding="utf-8")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote MusicXML to {musicxml_path}")
    print(f"Wrote sheet SVG to {svg_path}")
    return 0
