#!/usr/bin/env python3
"""Validate stable normal-format Chinese DOCX documents."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn


FONT_EAST = "宋体"
FONT_WEST = "Times New Roman"
CN_DIGITS = "一二三四五六七八九十"
H1_RE = re.compile(rf"^[{CN_DIGITS}]+、")
H2_RE = re.compile(r"^\d+\.\d+\s+")
H3_RE = re.compile(r"^\d+\.\d+\.\d+\s+")
H4_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+\s+")
H5_RE = re.compile(r"^（\d+）")


def run_props(run):
    r_pr = run._element.find(qn("w:rPr"))
    east = west = None
    size = None
    bold = bool(run.bold)
    color = None
    if r_pr is not None:
        r_fonts = r_pr.find(qn("w:rFonts"))
        if r_fonts is not None:
            east = r_fonts.get(qn("w:eastAsia"))
            west = r_fonts.get(qn("w:ascii")) or r_fonts.get(qn("w:hAnsi"))
        sz = r_pr.find(qn("w:sz"))
        if sz is not None:
            size = int(sz.get(qn("w:val"))) / 2
        b = r_pr.find(qn("w:b"))
        if b is not None:
            val = b.get(qn("w:val"))
            bold = val not in ("0", "false", "False")
        c = r_pr.find(qn("w:color"))
        if c is not None:
            color = c.get(qn("w:val"))
    return east, west, size, bold, color


def outline_level(paragraph):
    p_pr = paragraph._p.find(qn("w:pPr"))
    if p_pr is None:
        return None
    node = p_pr.find(qn("w:outlineLvl"))
    if node is None:
        return None
    return int(node.get(qn("w:val")))


def classify(text: str, idx: int) -> str:
    if idx == 0:
        return "title"
    if H1_RE.match(text):
        return "h1"
    if H4_RE.match(text):
        return "h4"
    if H3_RE.match(text):
        return "h3"
    if H2_RE.match(text):
        return "h2"
    if H5_RE.match(text):
        return "h5"
    if re.match(r"^图\d+：", text):
        return "caption"
    return "body"


def validate(path: Path, verbose: bool = False) -> int:
    doc = Document(path)
    issues = []
    paragraphs = [p for p in doc.paragraphs if p.text.strip()]
    expected_sizes = {"title": 16, "h1": 16, "h2": 14, "h3": 12, "h4": 12, "h5": 12, "body": 12, "caption": 12}
    outline_expected = {"h1": 0, "h2": 1, "h3": 2, "h4": 3, "h5": 4}

    for idx, paragraph in enumerate(paragraphs):
        text = paragraph.text.strip()
        level = classify(text, idx)
        if not paragraph.runs:
            # Picture-only paragraphs are allowed.
            continue
        east, west, size, bold, color = run_props(paragraph.runs[0])
        prefix = f"paragraph {idx + 1} [{level}] {text[:24]!r}"
        if east != FONT_EAST:
            issues.append(f"{prefix}: east font {east!r} != {FONT_EAST!r}")
        if west != FONT_WEST:
            issues.append(f"{prefix}: west font {west!r} != {FONT_WEST!r}")
        if size != expected_sizes[level]:
            issues.append(f"{prefix}: size {size!r} != {expected_sizes[level]}pt")
        if color not in (None, "000000"):
            issues.append(f"{prefix}: color {color!r} is not black")
        if level in {"title", "h1", "h2", "h3", "h4", "h5", "caption"} and not bold:
            issues.append(f"{prefix}: expected bold")
        if level in outline_expected and outline_level(paragraph) != outline_expected[level]:
            issues.append(f"{prefix}: outline level {outline_level(paragraph)!r} != {outline_expected[level]}")
        fmt = paragraph.paragraph_format
        if level == "body":
            if fmt.alignment != WD_ALIGN_PARAGRAPH.JUSTIFY:
                issues.append(f"{prefix}: body alignment is not justified")
            if fmt.line_spacing_rule != WD_LINE_SPACING.ONE_POINT_FIVE:
                issues.append(f"{prefix}: body line spacing is not 1.5")
            indent = fmt.first_line_indent.pt if fmt.first_line_indent else 0
            if abs(indent - 24) > 0.01:
                issues.append(f"{prefix}: body first indent {indent!r} != 24pt")
        if verbose:
            print(f"[CHECK] {idx + 1:02d} {level}: {text}")

    if issues:
        print(f"[FAIL] {path}")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print(f"[OK] normal format validation passed: {path}")
    print(f"[OK] checked paragraphs: {len(paragraphs)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate normal DOCX format")
    parser.add_argument("docx", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    sys.exit(validate(args.docx, args.verbose))


if __name__ == "__main__":
    main()
