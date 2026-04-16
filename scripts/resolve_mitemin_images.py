#!/usr/bin/env python3
"""Resolve mitemin page links into local image embeds.

This script scans chapter files, finds URLs that point to mitemin image pages
(e.g. https://26997.mitemin.net/i409700/), fetches each page, extracts the real
image URL from img1.mitemin.net, downloads the image into /public, and rewrites
chapter files to use the downloaded image.

For markdown files, standalone page-link lines are converted to markdown image
syntax so the image is displayed directly.

Usage examples:
    python scripts/resolve_mitemin_images.py
    python scripts/resolve_mitemin_images.py --dry-run
    python scripts/resolve_mitemin_images.py --overwrite
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PAGE_URL_RE = re.compile(r"https?://[^\s<>'\"\)\]]*mitemin\.net/[^\s<>'\"\)\]]*", re.IGNORECASE)
IMG_URL_RE = re.compile(
    r"https?://img1\.mitemin\.net/[^\s<>'\"]+?\.(?:jpg|jpeg|png)(?:\?[^\s<>'\"]*)?",
    re.IGNORECASE,
)
IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png)$", re.IGNORECASE)
PAGE_ID_RE = re.compile(r"/i([0-9]+)/?", re.IGNORECASE)
SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown"}
MARKDOWN_SUFFIXES = {".md", ".markdown"}


class ResolveError(RuntimeError):
    """Raised when a mitemin page cannot be resolved to a direct image URL."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve mitemin page URLs to local image files.")
    parser.add_argument(
        "--chapters-dir",
        type=Path,
        default=Path("translated_chapters"),
        help="Directory containing chapter files (default: translated_chapters)",
    )
    parser.add_argument(
        "--public-dir",
        type=Path,
        default=Path("public"),
        help="Directory where downloaded images are saved (default: public)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Recursively scan chapters directory (default: true)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Network timeout in seconds for page/image requests (default: 20)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Redownload images even if destination files already exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files or download images; print planned actions",
    )
    return parser.parse_args()


def iter_supported_files(root: Path, recursive: bool) -> Iterable[Path]:
    pattern = "**/*" if recursive else "*"
    for path in sorted(root.glob(pattern)):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def is_direct_mitemin_image(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.netloc.lower().startswith("img1.mitemin.net"):
        return False
    return IMAGE_EXT_RE.search(parsed.path) is not None


def is_mitemin_page_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return "mitemin.net" in host and not is_direct_mitemin_image(url)


def fetch_text(url: str, timeout: float) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (AMUHE mitemin resolver)"})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def fetch_bytes(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (AMUHE mitemin resolver)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def resolve_image_url_from_page(page_url: str, timeout: float) -> str:
    html_text = fetch_text(page_url, timeout=timeout)
    matches = list(dict.fromkeys(IMG_URL_RE.findall(html_text)))
    if not matches:
        raise ResolveError(f"No direct img1.mitemin.net image URL found in page: {page_url}")
    return matches[0]


def filename_for_page_image(page_url: str, image_url: str) -> str:
    page_match = PAGE_ID_RE.search(urlparse(page_url).path)
    page_part = f"i{page_match.group(1)}" if page_match else "unknown"
    image_path = urlparse(image_url).path
    ext = Path(image_path).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png"}:
        ext = ".jpg"
    return f"mitemin_{page_part}{ext}"


def download_image(image_url: str, destination: Path, timeout: float, overwrite: bool, dry_run: bool) -> None:
    if destination.exists() and not overwrite:
        return
    if dry_run:
        return
    content = fetch_bytes(image_url, timeout=timeout)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def replace_urls_in_text(file_path: Path, text: str, url_to_rel_path: dict[str, str]) -> tuple[str, int]:
    """Replace page URLs in one file and return updated text + replacement count."""
    if not url_to_rel_path:
        return text, 0

    replaced_count = 0
    lines = text.splitlines(keepends=True)
    is_markdown = file_path.suffix.lower() in MARKDOWN_SUFFIXES
    out_lines: list[str] = []

    for line in lines:
        new_line = line
        stripped = line.strip()

        if is_markdown and stripped in url_to_rel_path:
            target = url_to_rel_path[stripped]
            line_ending = "\n" if line.endswith("\n") else ""
            indent = line[: len(line) - len(line.lstrip())]
            alt = Path(target).name
            new_line = f"{indent}![{alt}]({target}){line_ending}"
            replaced_count += 1
        else:
            for old_url, new_target in url_to_rel_path.items():
                if old_url in new_line:
                    new_line = new_line.replace(old_url, new_target)
                    replaced_count += 1

        out_lines.append(new_line)

    return "".join(out_lines), replaced_count


def main() -> int:
    args = parse_args()
    chapters_dir = args.chapters_dir.resolve()
    public_dir = args.public_dir.resolve()

    if not chapters_dir.is_dir():
        print(f"[error] Chapters directory does not exist: {chapters_dir}")
        return 2

    all_files = list(iter_supported_files(chapters_dir, recursive=args.recursive))
    if not all_files:
        print(f"[warn] No supported files found in: {chapters_dir}")
        return 0

    file_to_urls: dict[Path, set[str]] = {}
    all_page_urls: set[str] = set()

    for file_path in all_files:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        urls = set(PAGE_URL_RE.findall(text))
        page_urls = {u for u in urls if is_mitemin_page_url(u)}
        if page_urls:
            file_to_urls[file_path] = page_urls
            all_page_urls.update(page_urls)

    if not all_page_urls:
        print("[ok] No mitemin page URLs found.")
        return 0

    print(f"[info] Found {len(all_page_urls)} unique mitemin page URL(s) across {len(file_to_urls)} file(s).")

    page_to_local_abs: dict[str, Path] = {}
    failed_pages: dict[str, str] = {}

    for page_url in sorted(all_page_urls):
        try:
            image_url = resolve_image_url_from_page(page_url, timeout=args.timeout)
            filename = filename_for_page_image(page_url, image_url)
            destination = public_dir / filename
            download_image(
                image_url=image_url,
                destination=destination,
                timeout=args.timeout,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
            )
            page_to_local_abs[page_url] = destination
            print(f"[ok] {page_url} -> {destination}")
        except (ResolveError, HTTPError, URLError, TimeoutError) as exc:
            failed_pages[page_url] = str(exc)
            print(f"[warn] Failed to resolve {page_url}: {exc}")

    changed_files = 0
    total_replacements = 0

    for file_path, page_urls in file_to_urls.items():
        url_to_rel_path: dict[str, str] = {}
        for page_url in page_urls:
            local_abs = page_to_local_abs.get(page_url)
            if local_abs is None:
                continue
            rel = os.path.relpath(local_abs, start=file_path.parent)
            rel_posix = rel.replace(os.sep, "/")
            url_to_rel_path[page_url] = rel_posix

        if not url_to_rel_path:
            continue

        original_text = file_path.read_text(encoding="utf-8", errors="replace")
        updated_text, replacements = replace_urls_in_text(file_path, original_text, url_to_rel_path)

        if replacements > 0 and updated_text != original_text:
            if not args.dry_run:
                file_path.write_text(updated_text, encoding="utf-8")
            changed_files += 1
            total_replacements += replacements
            action = "would update" if args.dry_run else "updated"
            print(f"[ok] {action} {file_path} ({replacements} replacement(s))")

    print(
        "[done] "
        f"resolved={len(page_to_local_abs)} failed={len(failed_pages)} "
        f"files_changed={changed_files} replacements={total_replacements}"
    )

    if failed_pages:
        print("[warn] Unresolved page URLs:")
        for page_url, reason in failed_pages.items():
            print(f"  - {page_url}: {reason}")

    return 0 if page_to_local_abs else 1


if __name__ == "__main__":
    sys.exit(main())
