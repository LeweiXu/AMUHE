#!/usr/bin/env python3
"""Convert an EPUB file into one TXT file per chapter.

Usage:
	python convert.py /path/to/book.epub
	python convert.py /path/to/book.epub --output-dir ./chapters

Dependencies:
	pip install ebooklib beautifulsoup4
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub


def sanitize_filename(name: str, fallback: str) -> str:
	"""Return a filesystem-safe filename stem."""
	cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name).strip()
	cleaned = re.sub(r"\s+", " ", cleaned)
	cleaned = cleaned.strip(". ")
	return cleaned or fallback


def chapter_text_and_title(html_bytes: bytes, fallback_title: str) -> tuple[str, str]:
	"""Extract human-readable text and a chapter title from XHTML/HTML bytes."""
	soup = BeautifulSoup(html_bytes, "html.parser")

	for tag in soup(["script", "style", "noscript"]):
		tag.decompose()

	title = fallback_title
	heading = soup.find(["h1", "h2", "h3"])
	if heading and heading.get_text(strip=True):
		title = heading.get_text(strip=True)
	elif soup.title and soup.title.get_text(strip=True):
		title = soup.title.get_text(strip=True)

	lines = [line.strip() for line in soup.get_text("\n").splitlines()]
	text = "\n".join(line for line in lines if line)
	return text, title


def iter_spine_documents(book: epub.EpubBook):
	"""Yield document items in reading order according to the spine."""
	id_map = {item.get_id(): item for item in book.get_items()}
	for entry in book.spine:
		item_id = entry[0] if isinstance(entry, tuple) else entry
		item = id_map.get(item_id)
		if item and item.get_type() == ITEM_DOCUMENT:
			yield item


def convert_epub_to_chapter_txt(
	epub_path: Path,
	output_dir: Path | None = None,
	skip_first_chapters: int = 0,
) -> int:
	"""Convert chapters from EPUB to individual TXT files.

	Returns the number of chapter files written.
	"""
	if not epub_path.exists() or epub_path.suffix.lower() != ".epub":
		raise ValueError(f"Input must be an existing .epub file: {epub_path}")
	if skip_first_chapters < 0:
		raise ValueError("skip_first_chapters must be >= 0")

	book = epub.read_epub(str(epub_path))

	target_dir = output_dir or epub_path.with_name(f"{epub_path.stem}_chapters")
	target_dir.mkdir(parents=True, exist_ok=True)

	chapter_count = 0
	for source_idx, doc in enumerate(iter_spine_documents(book), start=1):
		if source_idx <= skip_first_chapters:
			continue

		output_idx = chapter_count + 1
		fallback_title = f"chapter_{output_idx:03d}"
		text, title = chapter_text_and_title(doc.get_content(), fallback_title)

		if not text.strip():
			continue

		safe_stem = sanitize_filename(title, fallback_title)
		out_path = target_dir / f"{output_idx:03d}_{safe_stem}.txt"
		out_path.write_text(text + "\n", encoding="utf-8")
		chapter_count += 1

	return chapter_count


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Convert an EPUB file into one TXT file per chapter.",
	)
	parser.add_argument("epub_file", type=Path, help="Path to the input .epub file")
	parser.add_argument(
		"-o",
		"--output-dir",
		type=Path,
		default=None,
		help="Output directory for chapter txt files (default: <bookname>_chapters next to EPUB)",
	)
	parser.add_argument(
		"--skip-first-chapters",
		type=int,
		default=0,
		help="Number of chapters to skip before writing files (default: 0)",
	)
	return parser


def main() -> None:
	args = build_parser().parse_args()
	if args.skip_first_chapters < 0:
		raise ValueError("--skip-first-chapters must be >= 0")

	count = convert_epub_to_chapter_txt(
		args.epub_file,
		args.output_dir,
		skip_first_chapters=args.skip_first_chapters,
	)
	print(f"Done. Wrote {count} chapter file(s).")


if __name__ == "__main__":
	main()
