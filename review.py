#!/usr/bin/env python3
"""
review_edits.py — Interactively review proposed edits and apply them to the chapter file.

DIRECTORY LAYOUT (relative to this script):
    review/               — edits files produced by Sonnet (e.g. c40-45_edits.md)
    translated_chapters/  — chapter files to be edited in-place (e.g. c40-45.md)

USAGE:
    python3 review_edits.py                        # interactive review, newest edits file
    python3 review_edits.py review/c40-45_edits.md # interactive review, specific file
    python3 review_edits.py --auto-approve         # approve all edits without prompting
    python3 review_edits.py --undo                 # undo all APPROVED edits

BEHAVIOUR:
    - Finds the corresponding chapter file by stripping "_edits" from the edits filename.
    - Presents each ORIGINAL/EDIT pair and prompts y/n/q.
    - Approved edits are applied to the chapter file in-place by exact string match.
    - Each block in the edits file is annotated with APPROVED or REJECTED.
    - q saves progress so far; remaining edits are marked REJECTED.
    - --undo reverses all APPROVED edits, restoring originals, and clears annotations.
    - --undo and --auto-approve are mutually exclusive.
"""

import re
import sys
import argparse
import textwrap
from pathlib import Path

# ── Terminal helpers ───────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[0;31m"
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
DIM    = "\033[2m"

def wrap(text: str, width: int = 68, indent: str = "  ") -> str:
    lines = []
    for para in text.split("\n"):
        if para.strip():
            lines.extend(textwrap.wrap(para, width=width,
                                       initial_indent=indent,
                                       subsequent_indent=indent))
        else:
            lines.append("")
    return "\n".join(lines)

def divider(char: str = "─", width: int = 72):
    print(DIM + char * width + RESET)


# ── Parsing ────────────────────────────────────────────────────────────────────

def parse_edits(text: str) -> list[dict]:
    """
    Parse all ORIGINAL/EDIT pairs from the edits file.
    Returns a list of dicts with 'original' and 'edit' keys.
    """
    results = []
    pattern = re.compile(
        r'^ORIGINAL:\s*(.+?)\n'
        r'^EDIT:\s*(.+?)$',
        re.MULTILINE
    )
    for m in pattern.finditer(text):
        results.append({
            'original': m.group(1).strip(),
            'edit':     m.group(2).strip(),
        })
    return results


# ── Review loop ────────────────────────────────────────────────────────────────

def review(edits: list[dict], chapter_text: str,
           auto_approve: bool = False) -> tuple[str, list[tuple[dict, str]]]:
    """
    Walk through edits interactively or approve all automatically.
    Returns (updated_chapter_text, [(edit_dict, decision), ...]).
    Decisions are 'APPROVED' or 'REJECTED'.
    """
    decisions: list[tuple[dict, str]] = []
    total = len(edits)

    if auto_approve:
        print(f"\n{YELLOW}Auto-approving all {total} edit(s).{RESET}")

    for i, ed in enumerate(edits):
        print()
        divider("═")
        print(f"{BOLD}  Edit {i + 1} of {total}{RESET}")
        divider()
        print(f"\n{YELLOW}{BOLD}  ORIGINAL{RESET}")
        print(wrap(ed['original']))
        print()
        print(f"{GREEN}{BOLD}  PROPOSED EDIT{RESET}")
        print(wrap(ed['edit']))
        print()
        divider()

        if ed['original'] not in chapter_text:
            print(f"  {YELLOW}⚠ Original paragraph not found in chapter file — "
                  f"edit cannot be applied if accepted.{RESET}\n")

        if auto_approve:
            print(f"  {GREEN}✓ Auto-approved{RESET}")
            decisions.append((ed, "APPROVED"))
            continue

        while True:
            try:
                choice = input(
                    f"  {BOLD}[y]{RESET} accept  "
                    f"{BOLD}[n]{RESET} reject  "
                    f"{BOLD}[q]{RESET} quit & save → "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "q"

            if choice in ("y", "n", "q"):
                break
            print(f"  {RED}Please enter y, n, or q.{RESET}")

        if choice == "q":
            print(f"\n{YELLOW}Quitting — saving progress so far.{RESET}")
            decisions.append((ed, "REJECTED"))
            for remaining in edits[i + 1:]:
                decisions.append((remaining, "REJECTED"))
            break

        decision = "APPROVED" if choice == "y" else "REJECTED"
        decisions.append((ed, decision))
        label = f"  {GREEN}✓ Approved{RESET}" if choice == "y" else f"  {RED}✗ Rejected{RESET}"
        print(label)

    updated = chapter_text
    for ed, decision in decisions:
        if decision == "APPROVED" and ed['original'] in updated:
            updated = updated.replace(ed['original'], ed['edit'], 1)

    return updated, decisions


# ── Undo ──────────────────────────────────────────────────────────────────────

def undo(edits_text: str, chapter_text: str) -> tuple[str, int]:
    """
    Reverse all APPROVED edits found in the edits file.
    Returns (updated_chapter_text, undo_count).
    """
    pattern = re.compile(
        r'^ORIGINAL:\s*(.+?)\n'
        r'^EDIT:\s*(.+?)\n'
        r'^APPROVED\s*$',
        re.MULTILINE
    )
    updated = chapter_text
    count = 0
    for m in pattern.finditer(edits_text):
        original = m.group(1).strip()
        edit     = m.group(2).strip()
        if edit in updated:
            updated = updated.replace(edit, original, 1)
            count += 1
    return updated, count


def strip_annotations(edits_text: str) -> str:
    """Remove all APPROVED and REJECTED lines from the edits file."""
    lines = edits_text.splitlines(keepends=True)
    return "".join(l for l in lines if l.strip() not in ("APPROVED", "REJECTED"))


# ── Annotate edits file ────────────────────────────────────────────────────────

def annotate_edits_file(edits_text: str, decisions: list[tuple[dict, str]]) -> str:
    """Append APPROVED or REJECTED after each EDIT: line. Processes in reverse order."""
    result = edits_text
    for ed, decision in reversed(decisions):
        block = f"ORIGINAL: {ed['original']}\nEDIT: {ed['edit']}"
        pos = result.find(block)
        if pos == -1:
            continue
        end = pos + len(block)
        result = result[:end] + f"\n{decision}" + result[end:]
    return result


# ── Directory helpers ──────────────────────────────────────────────────────────

def find_newest_edits_file(review_dir: Path) -> Path:
    candidates = sorted(review_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        print(f"{RED}[ERROR]{RESET} No .md files found in {review_dir}/", file=sys.stderr)
        sys.exit(1)
    return candidates[-1]


def find_chapter_file(edits_path: Path, chapters_dir: Path) -> Path:
    stem = edits_path.stem
    chapter_stem = re.sub(r'_edits?$', '', stem, flags=re.IGNORECASE)
    chapter_path = chapters_dir / f"{chapter_stem}.md"
    if not chapter_path.exists():
        print(f"{RED}[ERROR]{RESET} Chapter file not found: {chapter_path}", file=sys.stderr)
        sys.exit(1)
    return chapter_path


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Review proposed edits and apply them to chapter files."
    )
    parser.add_argument("edits_file", nargs="?", default=None,
                        help="Path to the edits .md file (default: newest in review/)")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--auto-approve", action="store_true",
                      help="Approve all edits without prompting")
    mode.add_argument("--undo", action="store_true",
                      help="Undo all APPROVED edits, restoring chapter originals")
    args = parser.parse_args()

    script_dir   = Path(__file__).resolve().parent
    review_dir   = script_dir / "review"
    chapters_dir = script_dir / "translated_chapters"

    if args.edits_file:
        edits_path = Path(args.edits_file)
    else:
        edits_path = find_newest_edits_file(review_dir)
        print(f"{DIM}Using newest edits file: {edits_path.name}{RESET}")

    chapter_path = find_chapter_file(edits_path, chapters_dir)
    edits_text   = edits_path.read_text(encoding="utf-8")
    chapter_text = chapter_path.read_text(encoding="utf-8")

    # ── Undo mode ─────────────────────────────────────────────────────────────
    if args.undo:
        print(f"\n{BOLD}Undo Mode{RESET}")
        print(f"{DIM}Edits:   {edits_path.name}{RESET}")
        print(f"{DIM}Chapter: {chapter_path.name}{RESET}")

        updated_chapter, count = undo(edits_text, chapter_text)
        chapter_path.write_text(updated_chapter, encoding="utf-8")
        edits_path.write_text(strip_annotations(edits_text), encoding="utf-8")

        print()
        divider("═")
        print(f"\n  {YELLOW}↩ Reverted:{RESET} {count} edit(s)")
        print(f"\n  {BOLD}Chapter restored:{RESET} {chapter_path}")
        print(f"  {BOLD}Annotations cleared:{RESET} {edits_path}\n")
        return

    # ── Review / auto-approve mode ────────────────────────────────────────────
    edits = parse_edits(edits_text)
    if not edits:
        print(f"{YELLOW}No ORIGINAL/EDIT pairs found in {edits_path.name}.{RESET}")
        sys.exit(0)

    print(f"\n{BOLD}Translation Edit Review{RESET}")
    print(f"{DIM}Edits:   {edits_path.name}{RESET}")
    print(f"{DIM}Chapter: {chapter_path.name}  |  {len(edits)} proposed edit(s){RESET}")

    updated_chapter, decisions = review(edits, chapter_text, args.auto_approve)

    chapter_path.write_text(updated_chapter, encoding="utf-8")
    edits_path.write_text(annotate_edits_file(edits_text, decisions), encoding="utf-8")

    approved = sum(1 for _, d in decisions if d == "APPROVED")
    rejected = sum(1 for _, d in decisions if d == "REJECTED")
    print()
    divider("═")
    print(f"\n  {GREEN}✓ Approved:{RESET} {approved}")
    print(f"  {RED}✗ Rejected:{RESET} {rejected}")
    print(f"\n  {BOLD}Chapter saved:{RESET} {chapter_path}")
    print(f"  {BOLD}Edits annotated:{RESET} {edits_path}\n")


if __name__ == "__main__":
    main()