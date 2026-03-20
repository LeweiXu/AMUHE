#!/usr/bin/env python3
"""
merge_kb.py — Merge new knowledge base additions into knowledge_base.md

USAGE:
    python3 merge_kb.py additions.md
    python3 merge_kb.py additions.md --kb path/to/knowledge_base.md
    python3 merge_kb.py additions.md --dry-run

The additions file is the second output Claude produces after a translation batch.
It should contain only new/changed content, with section headings matching
knowledge_base.md exactly.

MERGE BEHAVIOUR BY SECTION:
    NAME ROMANIZATIONS          — append new table rows before the closing ---
    CORE CHARACTERS             — append new ### subsections
    SECONDARY CHARACTERS        — append new ### subsections
    PLACE NAMES AND LOCATIONS   — append new table rows before the closing ---
    WORLD-BUILDING REFERENCE    — append new ### subsections or bullet points
    TIMELINE: CHAPTERS *        — new TIMELINE sections are added as entirely new
                                  sections (each batch gets its own heading)
    RECURRING THEMES AND MOTIFS — append new numbered items, renumbering if needed
    TRANSLATOR NOTES *          — append new bullet points
    COVERAGE LINE               — replace the *Current coverage* line at the top
    NEW SECTIONS                — any section not found in the existing file is
                                  appended at the end
"""

import re
import sys
import shutil
import argparse
from pathlib import Path
from datetime import date

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
    For table-based sections (NAME ROMANIZATIONS, PLACE NAMES).
    Appends new rows from the addition, skipping header/separator rows and
    any rows whose first cell already exists in the existing content.
    Inserted before the trailing --- if present, otherwise at the end.
    """
    new_rows = []
    for line in addition.splitlines():
        stripped = line.strip()
        # Skip blank lines, header rows, separator rows
        if not stripped or stripped.startswith("|---|") or stripped == "|---|---|---|":
            continue
        if not stripped.startswith("|"):
            continue
        # Extract first cell to check for duplicates
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        first_cell = cells[0] if cells else ""
        if first_cell and first_cell not in existing:
            new_rows.append(line.rstrip())

    if not new_rows:
        return existing

    new_block = "\n".join(new_rows) + "\n"

    # Insert before the trailing --- separator if it exists
    sep_pos = existing.rfind("\n---\n")
    if sep_pos != -1:
        return existing[:sep_pos + 1] + new_block + existing[sep_pos + 1:]
    return existing.rstrip() + "\n" + new_block


def append_subsections(existing: str, addition: str) -> str:
    """
    For character/world-building sections with ### subsections.
    Appends any ### subsection from addition that doesn't already exist in existing.
    Updates existing ### entries if the addition contains the same heading with new content.
    """
    # Parse ### subsections from addition
    add_subs: dict[str, str] = {}
    current = None
    current_lines: list[str] = []

    for line in addition.splitlines(keepends=True):
        if line.startswith("### "):
            if current is not None:
                add_subs[current] = "".join(current_lines)
            current = line.rstrip("\n")
            current_lines = []
        else:
            if current is not None:
                current_lines.append(line)

    if current is not None:
        add_subs[current] = "".join(current_lines)

    if not add_subs:
        # No ### subsections — treat as plain text to append
        stripped = addition.strip()
        if stripped and stripped not in existing:
            return existing.rstrip() + "\n\n" + stripped + "\n"
        return existing

    result = existing
    for heading, content in add_subs.items():
        if heading in existing:
            # Subsection exists — append any genuinely new bullet/detail lines
            # Find the existing subsection and add new lines after it
            new_lines = []
            for line in content.splitlines():
                line_stripped = line.strip()
                if line_stripped and line_stripped not in existing:
                    new_lines.append(line)
            if new_lines:
                insert_after = heading
                pos = result.find(insert_after)
                if pos != -1:
                    end_pos = result.find("\n### ", pos + 1)
                    if end_pos == -1:
                        end_pos = len(result)
                    block = result[pos:end_pos].rstrip()
                    result = (result[:pos]
                              + block + "\n"
                              + "\n".join(new_lines) + "\n"
                              + result[end_pos:])
        else:
            # New subsection — append to end
            result = result.rstrip() + "\n\n" + heading + "\n" + content

    return result


def append_numbered_list(existing: str, addition: str) -> str:
    """
    For RECURRING THEMES AND MOTIFS — numbered list.
    Appends new items and renumbers the whole list sequentially.
    """
    def extract_items(text: str) -> list[str]:
        items = []
        for line in text.splitlines():
            m = re.match(r"^\d+\.\s+(.+)", line.strip())
            if m:
                items.append(m.group(1))
        return items

    existing_items = extract_items(existing)
    new_items = extract_items(addition)

    added = False
    for item in new_items:
        if item not in existing_items:
            existing_items.append(item)
            added = True

    if not added:
        return existing

    # Rebuild numbered list, keeping surrounding non-list text
    # Find where the list starts and ends in existing
    lines = existing.splitlines(keepends=True)
    list_start = list_end = None
    for i, line in enumerate(lines):
        if re.match(r"^\d+\.", line.strip()):
            if list_start is None:
                list_start = i
            list_end = i

    numbered = "".join(f"{i+1}. {item}\n" for i, item in enumerate(existing_items))

    if list_start is not None:
        return (
            "".join(lines[:list_start])
            + numbered
            + "".join(lines[list_end + 1:])
        )
    return existing.rstrip() + "\n\n" + numbered


def append_bullet_list(existing: str, addition: str) -> str:
    """
    For TRANSLATOR NOTES — bullet list.
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


# ── Section routing ────────────────────────────────────────────────────────────

def classify_heading(heading: str) -> str:
    """Return the merge strategy for a given ## heading."""
    h = heading.upper()
    if "NAME ROMANIZATIONS" in h:
        return "table"
    if "PLACE NAMES" in h:
        return "table"
    if "CORE CHARACTERS" in h:
        return "subsections"
    if "SECONDARY CHARACTERS" in h:
        return "subsections"
    if "WORLD-BUILDING" in h:
        return "subsections"
    if "TIMELINE" in h:
        return "new_section"   # each batch gets its own timeline block
    if "RECURRING THEMES" in h:
        return "numbered_list"
    if "TRANSLATOR NOTES" in h:
        return "bullet_list"
    return "append"            # default: append non-duplicate content


def merge_section(existing: str, addition: str, strategy: str) -> str:
    if strategy == "table":
        return append_table_rows(existing, addition)
    if strategy == "subsections":
        return append_subsections(existing, addition)
    if strategy == "numbered_list":
        return append_numbered_list(existing, addition)
    if strategy == "bullet_list":
        return append_bullet_list(existing, addition)
    if strategy == "new_section":
        return None   # signal: add as a brand-new section
    # default: append if content not already present
    stripped = addition.strip()
    if stripped and stripped not in existing:
        return existing.rstrip() + "\n\n" + stripped + "\n"
    return existing


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Merge knowledge base additions into knowledge_base.md"
    )
    parser.add_argument("additions", help="Path to the additions .md file from Claude")
    parser.add_argument("--kb", default=None,
                        help="Path to knowledge_base.md (default: ./knowledge_base.md)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing anything")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    kb_path = Path(args.kb) if args.kb else script_dir / "knowledge_base.md"
    add_path = Path(args.additions)

    if not kb_path.exists():
        err(f"knowledge_base.md not found: {kb_path}")
        sys.exit(1)
    if not add_path.exists():
        err(f"Additions file not found: {add_path}")
        sys.exit(1)

    kb_text  = kb_path.read_text(encoding="utf-8")
    add_text = add_path.read_text(encoding="utf-8")

    # Check for no-op
    stripped_add = add_text.strip()
    if not stripped_add or stripped_add.lower() == "no updates required.":
        ok("Additions file contains no updates. knowledge_base.md unchanged.")
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
        if heading in ("_preamble",):
            continue
        # Skip bare coverage directive lines
        if "Update coverage line to:" in add_content and len(add_content.strip().splitlines()) <= 2:
            continue

        add_content_stripped = add_content.strip()
        if not add_content_stripped or add_content_stripped.lower() == "no updates required.":
            continue

        strategy = classify_heading(heading)

        if strategy == "new_section":
            # TIMELINE sections — always add as a new top-level section
            if heading not in kb_sections:
                new_sections_to_append.append((heading, add_content))
                changes.append(f"New section added: {heading}")
            else:
                # Extremely rare: same exact timeline heading — skip
                warn(f"Timeline section already exists, skipping: {heading}")
            continue

        if heading in kb_sections:
            original = kb_sections[heading]
            merged   = merge_section(original, add_content, strategy)
            if merged is None:
                # new_section signal for a known heading — treat as append
                new_sections_to_append.append((heading, add_content))
                changes.append(f"New section added: {heading}")
            elif merged != original:
                kb_sections[heading] = merged
                changes.append(f"Updated: {heading}")
            else:
                info(f"No new content for: {heading}")
        else:
            # Brand new section not in existing KB
            new_sections_to_append.append((heading, add_content))
            changes.append(f"New section added: {heading}")

    # Append brand-new sections at the end
    for heading, content in new_sections_to_append:
        kb_sections[heading] = "\n" + content.lstrip()

    # ── Output ─────────────────────────────────────────────────────────────────
    new_kb_text = sections_to_text(kb_sections)

    if not changes:
        ok("No changes detected. knowledge_base.md unchanged.")
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

    ok(f"knowledge_base.md updated  ({len(changes)} change(s))")
    ok(f"Backup saved: {bak.name}")
    print()


if __name__ == "__main__":
    main()