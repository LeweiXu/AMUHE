#!/usr/bin/env python3
"""Re-batch translated markdown chapters into custom chapter ranges.

Usage:
	python batch_chapters.py <start_chapter> <end_chapter> <batch_size>

Example:
	python batch_chapters.py 311 364 5
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


HEADING_RE = re.compile(r"^#\s+Chapter\s+(\d+)\b.*$", re.MULTILINE)


def natural_sort_key(path: Path) -> list[object]:
	"""Sort file names naturally so c2 appears before c10."""
	name = path.name.lower()
	parts = re.split(r"(\d+)", name)
	return [int(part) if part.isdigit() else part for part in parts]


def extract_chapter_blocks(markdown_text: str) -> list[tuple[int, str]]:
	"""Extract complete chapter blocks keyed by chapter number."""
	matches = list(HEADING_RE.finditer(markdown_text))
	blocks: list[tuple[int, str]] = []

	for idx, match in enumerate(matches):
		chapter_num = int(match.group(1))
		start = match.start()
		end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown_text)
		block = markdown_text[start:end].strip()
		if block:
			blocks.append((chapter_num, block))

	return blocks


def collect_chapters(translated_dir: Path) -> dict[int, str]:
	"""Load all chapter blocks from markdown files in translated_chapters."""
	chapters: dict[int, str] = {}
	chapter_sources: dict[int, Path] = {}

	for md_file in sorted(translated_dir.glob("*.md"), key=natural_sort_key):
		content = md_file.read_text(encoding="utf-8")
		for chapter_num, chapter_block in extract_chapter_blocks(content):
			if chapter_num in chapters:
				raise ValueError(
					"Duplicate chapter "
					f"{chapter_num} found in {chapter_sources[chapter_num].name} and {md_file.name}."
				)
			chapters[chapter_num] = chapter_block
			chapter_sources[chapter_num] = md_file

	return chapters


def batch_write_chapters(
	chapters: dict[int, str],
	start_chapter: int,
	end_chapter: int,
	batch_size: int,
	output_dir: Path,
) -> list[Path]:
	"""Write chapter range into batch files and return generated paths."""
	missing = [str(num) for num in range(start_chapter, end_chapter + 1) if num not in chapters]
	if missing:
		raise ValueError(
			"Missing chapters in requested range: " + ", ".join(missing)
		)

	output_paths: list[Path] = []
	for batch_start in range(start_chapter, end_chapter + 1, batch_size):
		batch_end = min(batch_start + batch_size - 1, end_chapter)
		out_file = output_dir / f"c{batch_start}-{batch_end}.md"

		batch_parts = [chapters[num].strip() for num in range(batch_start, batch_end + 1)]
		out_file.write_text("\n\n".join(batch_parts).strip() + "\n", encoding="utf-8")
		output_paths.append(out_file)

	return output_paths


def parse_args() -> argparse.Namespace:
	"""Parse command-line arguments."""
	parser = argparse.ArgumentParser(
		description=(
			"Re-batch chapters from translated_chapters by extracting # Chapter NNN headings "
			"and writing cSTART-END.md files."
		)
	)
	parser.add_argument("start_chapter", type=int, help="Starting chapter number (inclusive)")
	parser.add_argument("end_chapter", type=int, help="Ending chapter number (inclusive)")
	parser.add_argument("batch_size", type=int, help="Number of chapters per output file")
	return parser.parse_args()


def main() -> int:
	"""Entrypoint for chapter re-batching."""
	args = parse_args()

	if args.start_chapter <= 0 or args.end_chapter <= 0:
		print("start_chapter and end_chapter must be positive integers.", file=sys.stderr)
		return 2

	if args.start_chapter > args.end_chapter:
		print("start_chapter must be less than or equal to end_chapter.", file=sys.stderr)
		return 2

	if args.batch_size <= 0:
		print("batch_size must be a positive integer.", file=sys.stderr)
		return 2

	root_dir = Path(__file__).resolve().parent
	translated_dir = root_dir / "translated_chapters"

	if not translated_dir.exists() or not translated_dir.is_dir():
		print(f"Directory not found: {translated_dir}", file=sys.stderr)
		return 2

	try:
		chapters = collect_chapters(translated_dir)
		output_paths = batch_write_chapters(
			chapters=chapters,
			start_chapter=args.start_chapter,
			end_chapter=args.end_chapter,
			batch_size=args.batch_size,
			output_dir=translated_dir,
		)
	except ValueError as exc:
		print(f"Error: {exc}", file=sys.stderr)
		return 1

	for path in output_paths:
		print(f"Wrote {path.name}")

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
