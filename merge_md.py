#!/usr/bin/env python3
"""Merge ordered markdown section files into a single markdown file.

Usage:
	python merge_md.py INPUT_DIR OUTPUT_FILE

The script reads files named like Section0001.md, Section0002.md, ... from the
input directory, sorts them by section number, and concatenates them into a
single markdown document. In each source file, only the first markdown level-2
heading (## ...) is promoted to a level-1 heading (# ...) in the merged output.
It also removes leading [TOC] navigation lines and unwraps hard-wrapped prose
paragraphs while preserving common Markdown block structures.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SECTION_FILE_RE = re.compile(r"^Section(\d{4})\.md$", re.IGNORECASE)
FIRST_H2_RE = re.compile(r"^##(\s+.*)$", re.MULTILINE)
TOC_LINE_RE = re.compile(r"^\s*\[TOC\].*$")
LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Merge Section####.md files from a directory into one markdown file."
	)
	parser.add_argument("input_dir", type=Path, help="Directory containing Section####.md files")
	parser.add_argument("output_file", type=Path, help="Merged markdown output path")
	return parser.parse_args()


def section_sort_key(path: Path) -> int:
	match = SECTION_FILE_RE.fullmatch(path.name)
	if match is None:
		raise ValueError(f"Unexpected section filename: {path.name}")
	return int(match.group(1))


def find_section_files(input_dir: Path) -> list[Path]:
	if not input_dir.exists() or not input_dir.is_dir():
		raise ValueError(f"Input must be an existing directory: {input_dir}")

	files = [
		path
		for path in input_dir.iterdir()
		if path.is_file() and SECTION_FILE_RE.fullmatch(path.name)
	]

	if not files:
		raise ValueError(f"No files matching Section####.md found in: {input_dir}")

	return sorted(files, key=section_sort_key)


def promote_first_h2(markdown_text: str, source_path: Path) -> str:
	updated_text, replacements = FIRST_H2_RE.subn(r"#\1", markdown_text, count=1)
	if replacements == 0:
		raise ValueError(f"No level-2 heading found in: {source_path}")
	return updated_text


def is_standalone_markdown_line(line: str) -> bool:
	stripped = line.strip()
	if not stripped:
		return False
	if stripped.startswith("#"):
		return True
	if FENCE_RE.match(stripped):
		return True
	if stripped.startswith(">"):
		return True
	if LIST_MARKER_RE.match(stripped):
		return True
	if stripped.startswith("<"):
		return True
	if stripped.startswith("|"):
		return True
	if set(stripped) <= {"-", "*", "_"} and len(stripped) >= 3:
		return True
	if stripped.startswith("[") and "](" in stripped:
		return True
	return False


def normalize_markdown(markdown_text: str) -> str:
	normalized_lines: list[str] = []
	paragraph_lines: list[str] = []
	in_code_block = False

	def flush_paragraph() -> None:
		if paragraph_lines:
			normalized_lines.append(" ".join(line.strip() for line in paragraph_lines))
			paragraph_lines.clear()

	for raw_line in markdown_text.splitlines():
		line = raw_line.rstrip()
		stripped = line.strip()

		if TOC_LINE_RE.match(line):
			continue

		if FENCE_RE.match(stripped):
			flush_paragraph()
			normalized_lines.append(line)
			in_code_block = not in_code_block
			continue

		if in_code_block:
			normalized_lines.append(line)
			continue

		if not stripped:
			flush_paragraph()
			if normalized_lines and normalized_lines[-1] != "":
				normalized_lines.append("")
			continue

		if is_standalone_markdown_line(line):
			flush_paragraph()
			normalized_lines.append(stripped)
			continue

		paragraph_lines.append(stripped)

	flush_paragraph()

	while normalized_lines and normalized_lines[-1] == "":
		normalized_lines.pop()

	return "\n".join(normalized_lines)


def merge_markdown_files(input_dir: Path, output_file: Path) -> int:
	merged_sections: list[str] = []
	section_files = find_section_files(input_dir)

	for section_file in section_files:
		content = section_file.read_text(encoding="utf-8")
		normalized_content = normalize_markdown(content)
		merged_sections.append(promote_first_h2(normalized_content.strip(), section_file))

	output_file.parent.mkdir(parents=True, exist_ok=True)
	output_file.write_text("\n\n".join(merged_sections).rstrip() + "\n", encoding="utf-8")
	return len(section_files)


def main() -> None:
	args = parse_args()
	merged_count = merge_markdown_files(args.input_dir, args.output_file)
	print(f"Merged {merged_count} files into {args.output_file}")


if __name__ == "__main__":
	main()
