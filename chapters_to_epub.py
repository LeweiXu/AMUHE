#!/usr/bin/env python3
"""Convert a directory of chapter TXT files into a single EPUB.

Usage:
	python chapters_to_epub.py ./chapters --title "My Book"
	python chapters_to_epub.py ./chapters -o book.epub --author "Author Name"

Dependencies:
	pip install ebooklib markdown
"""

from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from pathlib import Path

from ebooklib import epub
from markdown import markdown as md_to_html


@dataclass
class ChapterSource:
	"""Represents one chapter extracted from .txt or .md source files."""

	title: str
	body: str
	chapter_number: int | None
	source_path: Path
	source_index: int
	is_markdown: bool


def natural_sort_key(path: Path) -> list[object]:
	"""Sort paths by filename using natural ordering (1, 2, 10)."""
	name = path.name.lower()
	return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def extract_chapter_number(text: str) -> int | None:
	"""Best-effort extraction of chapter number from title or filename-like text."""
	match = re.search(r"chapter\s*([0-9]+)", text, flags=re.IGNORECASE)
	if match:
		return int(match.group(1))

	match = re.search(r"\bc\s*([0-9]{1,4})\b", text, flags=re.IGNORECASE)
	if match:
		return int(match.group(1))

	match = re.search(r"\b([0-9]{1,4})\b", text)
	if match:
		return int(match.group(1))

	return None


def split_title_and_body(text: str, fallback_title: str) -> tuple[str, str]:
	"""Use the first non-empty line as chapter title and the rest as body."""
	lines = [line.rstrip() for line in text.splitlines()]

	first_non_empty = None
	for idx, line in enumerate(lines):
		if line.strip():
			first_non_empty = idx
			break

	if first_non_empty is None:
		return fallback_title, ""

	title = lines[first_non_empty].strip()
	body_lines = lines[first_non_empty + 1 :]
	body = "\n".join(body_lines).strip()
	return title or fallback_title, body


def split_markdown_into_chapters(markdown_text: str, fallback_title: str) -> list[tuple[str, str]]:
	"""Split markdown into chapters using level-1 headings (# ...)."""
	heading_re = re.compile(r"^\s*#\s+(.+?)\s*$", flags=re.MULTILINE)
	matches = list(heading_re.finditer(markdown_text))

	if not matches:
		return [(fallback_title, markdown_text.strip())]

	chapters: list[tuple[str, str]] = []
	for idx, match in enumerate(matches):
		title = match.group(1).strip()
		content_start = match.end()
		content_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown_text)
		body = markdown_text[content_start:content_end].strip()
		chapters.append((title or fallback_title, body))

	return chapters


def text_body_to_xhtml(body: str) -> str:
	"""Convert plain text body to simple EPUB-safe XHTML paragraphs."""
	if not body.strip():
		return "<p></p>"

	chunks = re.split(r"\n\s*\n", body.strip())
	paragraphs = []
	for chunk in chunks:
		clean = "\n".join(line.rstrip() for line in chunk.splitlines()).strip()
		if not clean:
			continue
		escaped = html.escape(clean).replace("\n", "<br/>")
		paragraphs.append(f"<p>{escaped}</p>")

	return "\n".join(paragraphs) if paragraphs else "<p></p>"


def markdown_body_to_xhtml(body: str) -> str:
	"""Convert markdown body text into XHTML fragment for EPUB chapter content."""
	if not body.strip():
		return "<p></p>"

	raw_html = md_to_html(body, extensions=["extra", "sane_lists", "nl2br"])
	# ebook readers are sensitive to uppercase/self-closing variants; keep simple HTML5-like tags.
	return raw_html.strip() or "<p></p>"


def find_supported_files(input_dir: Path, recursive: bool = False) -> list[Path]:
	"""Return sorted list of supported chapter source files."""
	pattern = "**/*" if recursive else "*"
	files = [
		p
		for p in input_dir.glob(pattern)
		if p.is_file() and p.suffix.lower() in {".txt", ".md", ".markdown"}
	]
	return sorted(files, key=natural_sort_key)


def read_text_file(path: Path, encoding: str) -> str:
	"""Read text file with a preferred encoding and common fallback."""
	try:
		return path.read_text(encoding=encoding)
	except UnicodeDecodeError:
		return path.read_text(encoding="utf-8", errors="replace")


def load_chapter_sources(input_dir: Path, encoding: str, recursive: bool) -> list[ChapterSource]:
	"""Load chapter entries from supported source files."""
	files = find_supported_files(input_dir, recursive=recursive)
	if not files:
		return []

	chapters: list[ChapterSource] = []
	source_index = 0

	for file_path in files:
		content = read_text_file(file_path, encoding=encoding)
		if not content.strip():
			continue
		suffix = file_path.suffix.lower()

		if suffix == ".txt":
			fallback_title = file_path.stem
			title, body = split_title_and_body(content, fallback_title)
			chapters.append(
				ChapterSource(
					title=title,
					body=body,
					chapter_number=extract_chapter_number(title) or extract_chapter_number(file_path.stem),
					source_path=file_path,
					source_index=source_index,
					is_markdown=False,
				)
			)
			source_index += 1
			continue

		# Markdown files can contain multiple chapters.
		fallback_title = file_path.stem
		sections = split_markdown_into_chapters(content, fallback_title)
		for title, body in sections:
			chapters.append(
				ChapterSource(
					title=title,
					body=body,
					chapter_number=extract_chapter_number(title),
					source_path=file_path,
					source_index=source_index,
					is_markdown=True,
				)
			)
			source_index += 1

	def sort_key(ch: ChapterSource):
		if ch.chapter_number is None:
			return (1, 10**9, ch.source_index)
		return (0, ch.chapter_number, ch.source_index)

	return sorted(chapters, key=sort_key)


def directory_txt_to_epub(
	input_dir: Path,
	output_epub: Path,
	title: str,
	author: str,
	language: str,
	identifier: str,
	encoding: str,
	recursive: bool,
) -> int:
	"""Build a single EPUB from chapter TXT files.

	Returns number of chapters written to EPUB.
	"""
	if not input_dir.exists() or not input_dir.is_dir():
		raise ValueError(f"Input must be an existing directory: {input_dir}")

	chapter_sources = load_chapter_sources(input_dir, encoding=encoding, recursive=recursive)
	if not chapter_sources:
		raise ValueError(f"No .txt/.md files found in: {input_dir}")

	book = epub.EpubBook()
	book.set_identifier(identifier)
	book.set_title(title)
	book.set_language(language)
	if author.strip():
		book.add_author(author)

	style = """
	body { font-family: serif; line-height: 1.5; }
	h1 { text-align: center; margin-top: 1.2em; margin-bottom: 1.2em; }
	p { text-indent: 1.5em; margin: 0.35em 0; white-space: normal; }
	""".strip()
	nav_css = epub.EpubItem(
		uid="style_nav",
		file_name="style/nav.css",
		media_type="text/css",
		content=style,
	)
	book.add_item(nav_css)

	chapters: list[epub.EpubHtml] = []
	for idx, source in enumerate(chapter_sources, start=1):
		chapter_title = source.title
		body_xhtml = markdown_body_to_xhtml(source.body) if source.is_markdown else text_body_to_xhtml(source.body)

		chapter = epub.EpubHtml(
			title=chapter_title,
			file_name=f"chap_{idx:03d}.xhtml",
			lang=language,
		)
		chapter.content = (
			f"<h1>{html.escape(chapter_title)}</h1>\n"
			f"{body_xhtml}"
		)
		chapter.add_item(nav_css)
		book.add_item(chapter)
		chapters.append(chapter)

	book.toc = tuple(chapters)
	book.spine = ["nav", *chapters]
	book.add_item(epub.EpubNcx())
	book.add_item(epub.EpubNav())

	output_epub.parent.mkdir(parents=True, exist_ok=True)
	epub.write_epub(str(output_epub), book, {})
	return len(chapters)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Convert a directory of TXT chapter files into a single EPUB.",
	)
	parser.add_argument("input_dir", type=Path, nargs="?", default=Path("translated_chapters"), help="Directory containing chapter .txt files (default: translated_chapters)")
	parser.add_argument(
		"-o",
		"--output",
		type=Path,
		default=Path("AMUHE.epub"),
		help="Output EPUB path (default: <input_dir_name>.epub next to directory)",
	)
	parser.add_argument("--title", type=str, default="AMUHE.epub", help="Book title")
	parser.add_argument("--author", type=str, default="", help="Author name")
	parser.add_argument("--language", type=str, default="en", help="Language code (default: en)")
	parser.add_argument(
		"--identifier",
		type=str,
		default="txt-chapters-book",
		help="Unique EPUB identifier",
	)
	parser.add_argument(
		"--encoding",
		type=str,
		default="utf-8",
		help="Preferred input text encoding (default: utf-8)",
	)
	parser.add_argument(
		"--recursive",
		action="store_true",
		help="Include .txt files in subdirectories",
	)
	return parser


def main() -> None:
	args = build_parser().parse_args()

	input_dir = args.input_dir
	output_epub = args.output or input_dir.with_name(f"{input_dir.name}.epub")
	title = args.title or input_dir.name

	count = directory_txt_to_epub(
		input_dir=input_dir,
		output_epub=output_epub,
		title=title,
		author=args.author,
		language=args.language,
		identifier=args.identifier,
		encoding=args.encoding,
		recursive=args.recursive,
	)
	print(f"Done. Wrote EPUB with {count} chapter(s): {output_epub}")


if __name__ == "__main__":
	main()
