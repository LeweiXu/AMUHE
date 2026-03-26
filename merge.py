#!/usr/bin/env python3
"""
merge_kb.py — Merge new knowledge base additions into context.md

USAGE:
    python3 merge_kb.py additions.md
    python3 merge_kb.py additions.md --kb path/to/context.md
    python3 merge_kb.py additions.md --dry-run

The additions file is the second output Claude produces after a translation batch.
It should contain only new/changed content, with section headings matching
context.md exactly.

MERGE BEHAVIOUR BY SECTION:
    NAME ROMANIZATIONS    — append new table rows
    SPEECH PATTERNS       — append new bullet items (- **Name:** ...)
    RECURRING TERMS       — append new table rows
    TRANSLATION DECISIONS — append new bullet items (- ...)
    SECONDARY CHARACTERS  — append new **Name** bold blocks, or update existing ones
    TIMELINE SUMMARY      — replace the matching Arc N line in the existing section
    COVERAGE LINE         — replace the *Current coverage* line at the top
    NEW SECTIONS          — any section not found in the existing file is
                            appended at the end
"""

import re
import sys
import shutil
import argparse
from pathlib import Path

# ── Colour helpers ─────────────────────────────────────────────────────────────
RESET = "\033[0m"; GREEN = "\033[0;32m"; YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"; RED = "\033[0;31m"; BOLD = "\033[1m"

def info(m):  print(f"{CYAN}[INFO]{RESET}  {m}")
def ok(m):    print(f"{GREEN}[OK]{RESET}    {m}")
def warn(m):  print(f"{YELLOW}[WARN]{RESET}  {m}")
def err(m):   print(f"{RED}[ERROR]{RESET} {m}", file=sys.stderr)


# ── Section parsing ────────────────────────────────────────────────────────────

def parse_sections(text: str) -> dict[str, str]:
    """
    Split a markdown file into a dict of {heading: content}.
    Heading is the raw ## line (e.g. '## NAME ROMANIZATIONS').
    Content is everything after the heading up to (but not including) the next ## heading.
    A special key '_preamble' holds any text before the first ## heading.
    """
    sections: dict[str, str] = {}
    current_key = "_preamble"
    current_lines: list[str] = []

    for line in text.splitlines(keepends=True):
        if line.startswith("## "):
            sections[current_key] = "".join(current_lines)
            current_key = line.rstrip("\n")
            current_lines = []
        else:
            current_lines.append(line)

    sections[current_key] = "".join(current_lines)
    return sections


def sections_to_text(sections: dict[str, str]) -> str:
    """Reconstruct the file from a sections dict, in insertion order."""
    parts = []
    for heading, content in sections.items():
        if heading == "_preamble":
            parts.append(content)
        else:
            parts.append(heading + "\n" + content)
    return "".join(parts)


# ── Coverage line update ───────────────────────────────────────────────────────

def update_coverage_line(preamble: str, new_coverage: str) -> str:
    """Replace the *Current coverage: ...* line in the preamble."""
    pattern = r"\*Current coverage:.*?\*"
    replacement = f"*Current coverage: {new_coverage}*"
    updated, n = re.subn(pattern, replacement, preamble)
    if n == 0:
        warn("Coverage line not found in preamble — appending it.")
        updated = preamble.rstrip() + f"\n{replacement}\n"
    return updated


# ── Per-section merge strategies ───────────────────────────────────────────────

def append_table_rows(existing: str, addition: str) -> str:
    """
    For table-based sections (NAME ROMANIZATIONS, RECURRING TERMS).
    Appends new rows, skipping header/separator rows and duplicates.
    Inserts before trailing --- if present.
    """
    new_rows = []
    for line in addition.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("|---|") or stripped == "|---|---|---|":
            continue
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        first_cell = cells[0] if cells else ""
        if first_cell and first_cell not in existing:
            new_rows.append(line.rstrip())

    if not new_rows:
        return existing

    new_block = "\n".join(new_rows) + "\n"

    sep_pos = existing.rfind("\n---\n")
    if sep_pos != -1:
        return existing[:sep_pos + 1] + new_block + existing[sep_pos + 1:]
    return existing.rstrip() + "\n" + new_block


def append_bullet_list(existing: str, addition: str) -> str:
    """
    For SPEECH PATTERNS and TRANSLATION DECISIONS — bullet lists.
    Appends new bullet items that don't already appear in existing.
    """
    new_bullets = []
    for line in addition.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and stripped not in existing:
            new_bullets.append(stripped)

    if not new_bullets:
        return existing

    return existing.rstrip() + "\n" + "\n".join(new_bullets) + "\n"


def append_secondary_characters(existing: str, addition: str) -> str:
    """
    For SECONDARY CHARACTERS — **Name** bold entry lines.

    Format in context.md:
        **Name** — description sentence. More detail.

    New characters are appended at the end.
    Existing characters get additional sentences appended to their line
    if the addition supplies content not already present.
    """
    # Parse addition into {name: full_line} for bold-name entries
    add_blocks: dict[str, str] = {}
    for line in addition.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(r"\*\*([^*]+)\*\*", stripped)
        if m:
            name = m.group(1)
            add_blocks[name] = stripped

    if not add_blocks:
        stripped_add = addition.strip()
        if stripped_add and stripped_add not in existing:
            return existing.rstrip() + "\n\n" + stripped_add + "\n"
        return existing

    result = existing
    new_entries: list[str] = []

    for name, block in add_blocks.items():
        if f"**{name}**" in result:
            # Character exists — append any new trailing content to their line
            pat = re.compile(r"(\*\*" + re.escape(name) + r"\*\*[^\n]*)", re.MULTILINE)
            m2 = pat.search(result)
            if m2:
                existing_line = m2.group(1)
                # Extract what the addition adds beyond the bold name
                add_suffix = block[len(f"**{name}**"):].strip()
                if add_suffix and add_suffix not in existing_line:
                    new_line = existing_line.rstrip() + " " + add_suffix
                    result = result[:m2.start()] + new_line + result[m2.end():]
        else:
            new_entries.append(block)

    if new_entries:
        result = result.rstrip() + "\n\n" + "\n\n".join(new_entries) + "\n"

    return result


def replace_timeline_arc(existing: str, addition: str) -> str:
    """
    For TIMELINE SUMMARY — replace matching Arc line(s).

    The addition should contain one or more lines of the form:
        **Arc N (C.X–Y):** ...summary...

    For each such line, find the matching **Arc N** line in the existing
    content and replace it in-place. If no match is found, append.
    """
    add_arcs: list[tuple[str, str]] = []  # (arc_label e.g. "Arc 6", full replacement line)
    for line in addition.splitlines():
        stripped = line.strip()
        m = re.match(r"\*\*Arc\s+(\d+)", stripped)
        if m:
            add_arcs.append((f"Arc {m.group(1)}", stripped))

    if not add_arcs:
        return existing

    result = existing
    for arc_label, new_line in add_arcs:
        pat = re.compile(r"^\*\*" + re.escape(arc_label) + r"\b.*$", re.MULTILINE)
        m2 = pat.search(result)
        if m2:
            result = result[:m2.start()] + new_line + result[m2.end():]
            info(f"Replaced {arc_label} in TIMELINE SUMMARY")
        else:
            result = result.rstrip() + "\n\n" + new_line + "\n"
            info(f"Appended new {arc_label} to TIMELINE SUMMARY")

    return result


# ── Section routing ────────────────────────────────────────────────────────────

_SECTION_KEYWORDS: list[tuple[str, str]] = [
    ("NAME ROMANIZATIONS",    "table"),
    ("SPEECH PATTERNS",       "bullet_list"),
    ("RECURRING TERMS",       "table"),
    ("TRANSLATION DECISIONS", "bullet_list"),
    ("SECONDARY CHARACTERS",  "secondary_characters"),
    ("TIMELINE SUMMARY",      "timeline_arc"),
]


def classify_heading(heading: str) -> str:
    """Return the merge strategy for a given ## heading."""
    h = heading.upper()
    for keyword, strategy in _SECTION_KEYWORDS:
        if keyword in h:
            return strategy
    return "append"


def fuzzy_find_heading(addition_heading: str, kb_sections: dict[str, str]) -> str | None:
    """
    Find the best matching existing section heading for an additions heading.
    Exact match first, then keyword-based fuzzy match.
    """
    if addition_heading in kb_sections:
        return addition_heading

    add_upper = addition_heading.upper()
    for keyword, _ in _SECTION_KEYWORDS:
        if keyword in add_upper:
            for kb_heading in kb_sections:
                if kb_heading == "_preamble":
                    continue
                if keyword in kb_heading.upper():
                    return kb_heading
    return None


def merge_section(existing: str, addition: str, strategy: str) -> str:
    if strategy == "table":
        return append_table_rows(existing, addition)
    if strategy == "bullet_list":
        return append_bullet_list(existing, addition)
    if strategy == "secondary_characters":
        return append_secondary_characters(existing, addition)
    if strategy == "timeline_arc":
        return replace_timeline_arc(existing, addition)
    # default: append if content not already present
    stripped = addition.strip()
    if stripped and stripped not in existing:
        return existing.rstrip() + "\n\n" + stripped + "\n"
    return existing


# ── Main ───────────────────────────────────────────────────────────────────────

def latest_kb_addition(kb_additions_dir: Path) -> Path | None:
    """Return the most recently modified .md file in kb_additions_dir, or None."""
    candidates = list(kb_additions_dir.glob("*.md"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main():
    parser = argparse.ArgumentParser(
        description="Merge knowledge base additions into context.md"
    )
    parser.add_argument("additions", nargs="?", default=None,
                        help="Path to the additions .md file from Claude "
                             "(default: latest file in kb_additions/)")
    parser.add_argument("--kb", default=None,
                        help="Path to context.md (default: ./context.md)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing anything")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    kb_path = Path(args.kb) if args.kb else script_dir / "context.md"

    if args.additions:
        add_path = Path(args.additions)
    else:
        kb_additions_dir = script_dir / "kb_additions"
        add_path = latest_kb_addition(kb_additions_dir)
        if add_path is None:
            err(f"No .md files found in {kb_additions_dir}")
            sys.exit(1)
        info(f"Using latest additions file: {add_path.name}")

    if not kb_path.exists():
        err(f"context.md not found: {kb_path}")
        sys.exit(1)
    if not add_path.exists():
        err(f"Additions file not found: {add_path}")
        sys.exit(1)

    kb_text  = kb_path.read_text(encoding="utf-8")
    add_text = add_path.read_text(encoding="utf-8")

    # Check for no-op
    stripped_add = add_text.strip()
    if not stripped_add or stripped_add.lower() == "no updates required.":
        ok("Additions file contains no updates. context.md unchanged.")
        return

    kb_sections  = parse_sections(kb_text)
    add_sections = parse_sections(add_text)

    changes: list[str] = []
    new_sections_to_append: list[tuple[str, str]] = []

    # ── Handle coverage line ───────────────────────────────────────────────────
    coverage_match = re.search(
        r"\*Update coverage line to:([^*]+)\*", add_text
    )
    if coverage_match:
        new_coverage = coverage_match.group(1).strip()
        old_preamble = kb_sections.get("_preamble", "")
        new_preamble = update_coverage_line(old_preamble, new_coverage)
        if new_preamble != old_preamble:
            kb_sections["_preamble"] = new_preamble
            changes.append(f"Coverage line → {new_coverage}")

    # ── Process each section in the additions file ─────────────────────────────
    for heading, add_content in add_sections.items():
        if heading == "_preamble":
            continue
        # Skip bare coverage directive lines
        if "Update coverage line to:" in add_content and len(add_content.strip().splitlines()) <= 2:
            continue

        add_content_stripped = add_content.strip()
        if not add_content_stripped or add_content_stripped.lower() == "no updates required.":
            continue

        strategy = classify_heading(heading)
        kb_heading = fuzzy_find_heading(heading, kb_sections)

        if kb_heading is not None:
            original = kb_sections[kb_heading]
            merged   = merge_section(original, add_content, strategy)
            if merged != original:
                kb_sections[kb_heading] = merged
                changes.append(f"Updated: {kb_heading}")
            else:
                info(f"No new content for: {kb_heading}")
        else:
            new_sections_to_append.append((heading, add_content))
            changes.append(f"New section added: {heading}")

    # Append brand-new sections at the end
    for heading, content in new_sections_to_append:
        kb_sections[heading] = "\n" + content.lstrip()

    # ── Output ─────────────────────────────────────────────────────────────────
    new_kb_text = sections_to_text(kb_sections)

    if not changes:
        ok("No changes detected. context.md unchanged.")
        return

    print()
    print(f"{BOLD}Changes to apply:{RESET}")
    for c in changes:
        print(f"  • {c}")
    print()

    if args.dry_run:
        warn("DRY RUN — no files written.")
        return

    # Backup and write
    bak = kb_path.with_suffix(".md.bak")
    shutil.copy2(kb_path, bak)
    kb_path.write_text(new_kb_text, encoding="utf-8")

    ok(f"context.md updated  ({len(changes)} change(s))")
    ok(f"Backup saved: {bak.name}")
    print()


if __name__ == "__main__":
    main()