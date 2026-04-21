#!/usr/bin/env python3
"""Merge ordered markdown section files into a single markdown file.

Usage:
    python merge_md.py [INPUT_DIR] [OUTPUT_FILE]

The script reads files named like Section0001.md, Section0002.md, ... from the
input directory, sorts them by section number, and concatenates them into a
single markdown document. In each source file, only the first markdown level-2
heading (## ...) is promoted to a level-1 heading (# ...) in the merged output.
It removes leading [TOC] lines and joins wrapped prose lines when the current
line ends with a continuation character such as a letter, digit, comma,
semicolon, colon, or a trailing apostrophe attached to a word such as
"Berys'".
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DEFAULT_INPUT_DIR = Path("UwU")
DEFAULT_OUTPUT_FILE = Path("translated_chapters/c311-364.md")
SECTION_PATTERN = re.compile(r"Section(\d+)\.md$")
CONTINUATION_PUNCTUATION = {",", ";", ":"}
TRAILING_CLOSERS = {'"', "”", ")", "]", "}"}
LIST_MARKER_PATTERN = re.compile(r"^\s*(?:[-+*]\s+|\d+\.\s+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=str(DEFAULT_INPUT_DIR),
        help=f"Directory containing SectionNNNN.md files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        default=str(DEFAULT_OUTPUT_FILE),
        help=f"Merged markdown output path. Default: {DEFAULT_OUTPUT_FILE}",
    )
    return parser.parse_args()


def iter_section_files(input_dir: Path) -> list[Path]:
    section_files: list[tuple[int, Path]] = []

    for path in input_dir.iterdir():
        match = SECTION_PATTERN.fullmatch(path.name)
        if match and path.is_file():
            section_files.append((int(match.group(1)), path))

    return [path for _, path in sorted(section_files)]


def strip_leading_toc(lines: list[str]) -> list[str]:
    start = 0
    while start < len(lines):
        stripped = lines[start].strip()
        if not stripped or stripped.startswith("[TOC]"):
            start += 1
            continue
        break
    return lines[start:]


def promote_first_h2(lines: list[str]) -> list[str]:
    promoted = False
    output: list[str] = []

    for line in lines:
        if not promoted and line.startswith("## "):
            output.append("# " + line[3:])
            promoted = True
        else:
            output.append(line)

    return output


def remove_toc_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if not line.lstrip().startswith("[TOC]")]


def is_block_boundary(line: str) -> bool:
    stripped = line.lstrip()
    if not stripped:
        return True
    if stripped.startswith(("#", ">", "<", "```", "~~~")):
        return True
    if stripped == "---" or stripped == "***":
        return True
    return bool(LIST_MARKER_PATTERN.match(stripped))


def should_join(line: str) -> bool:
    stripped = line.rstrip()
    if not stripped:
        return False

    if len(stripped) >= 2 and stripped[-1] in {"'", "’"} and stripped[-2].isalnum():
        return True

    while stripped and stripped[-1] in TRAILING_CLOSERS:
        stripped = stripped[:-1]

    if not stripped:
        return False

    return stripped[-1].isalnum() or stripped[-1] in CONTINUATION_PUNCTUATION


def join_wrapped_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip()

        if not line:
            if merged and merged[-1] != "":
                merged.append("")
            continue

        if (
            merged
            and merged[-1] != ""
            and should_join(merged[-1])
            and not is_block_boundary(merged[-1])
            and not is_block_boundary(line)
        ):
            merged[-1] = f"{merged[-1]} {line.lstrip()}"
            continue

        merged.append(line)

    return merged


def load_section(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    lines = strip_leading_toc(lines)
    lines = remove_toc_lines(lines)
    lines = promote_first_h2(lines)
    lines = join_wrapped_lines(lines)
    return "\n".join(lines).strip()


def add_blank_line_between_non_empty_lines(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []

    for line in lines:
        if not line.strip():
            continue
        output.append(line.rstrip())
        output.append("")

    return "\n".join(output).rstrip() + "\n"


def merge_sections(input_dir: Path, output_file: Path) -> int:
    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    section_files = iter_section_files(input_dir)
    if not section_files:
        print(f"No section files found in: {input_dir}", file=sys.stderr)
        return 1

    merged_sections = [load_section(path) for path in section_files]
    output_text = "\n\n".join(section for section in merged_sections if section) + "\n"
    output_text = add_blank_line_between_non_empty_lines(output_text)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(output_text, encoding="utf-8")
    return 0


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_file = Path(args.output_file)
    return merge_sections(input_dir, output_file)


if __name__ == "__main__":
    raise SystemExit(main())
