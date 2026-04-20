#!/usr/bin/env python3
"""
Report line count differences between raw Japanese chapters and English translations.

Usage:
    python report_translation_diff.py <start> [end] [-o output.md]

Each raw chapter file: raw_chapters/NNN_title.txt  (NNN = zero-padded chapter number)
Each translated file:  translated_chapters/c[start]-[end].md  (chapters separated by # headers)
"""

import argparse
import difflib
import re
import sys
from pathlib import Path

RAW_DIR = Path("raw_chapters")
TRANS_DIR = Path("translated_chapters")


def get_raw_lines(chapter_num):
    matches = list(RAW_DIR.glob(f"{chapter_num:03d}_*.txt"))
    if not matches:
        return None, None
    path = matches[0]
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return lines, path


def find_translated_file(chapter_num):
    for f in sorted(TRANS_DIR.glob("c*.md")):
        m = re.match(r"c(\d+)[-–](\d+)$", f.stem)
        if m and int(m.group(1)) <= chapter_num <= int(m.group(2)):
            return f, int(m.group(1)), int(m.group(2))
        m = re.match(r"c(\d+)$", f.stem)
        if m and int(m.group(1)) == chapter_num:
            return f, chapter_num, chapter_num
    return None, None, None


def extract_chapter_lines(trans_file, chapter_num):
    """Return non-blank lines for the given chapter, including its header line."""
    text = trans_file.read_text(encoding="utf-8")
    lines = text.splitlines()

    chapter_pat = re.compile(r"^#\s+Chapter\s+" + str(chapter_num) + r"\b", re.IGNORECASE)
    next_chapter_pat = re.compile(r"^#\s+Chapter\s+\d+", re.IGNORECASE)

    start_idx = None
    end_idx = len(lines)

    for i, line in enumerate(lines):
        if start_idx is None:
            if chapter_pat.match(line):
                start_idx = i
        elif next_chapter_pat.match(line):
            end_idx = i
            break

    if start_idx is None:
        return None

    return [l for l in lines[start_idx:end_idx] if l.strip()]


def is_dialogue(line):
    """True if the line is dialogue (JP: starts with 「/『; EN: starts with " or ")."""
    s = line.strip()
    return s[:1] in ('「', '『', '"', '\u201c', "'")


def line_features(line):
    """
    Return a feature tuple used as a structural proxy for aligning JP↔EN lines.
    Since CJK chars are ~2-3x more info-dense than ASCII, we normalise lengths
    by counting CJK chars as 2.5 ASCII chars so buckets are comparable.
    """
    s = line.strip()
    cjk_count = sum(1 for c in s if '\u3000' <= c <= '\u9fff' or '\uff00' <= c <= '\uffef')
    ascii_count = len(s) - cjk_count
    norm_len = cjk_count * 2.5 + ascii_count
    if norm_len < 20:
        bucket = 0
    elif norm_len < 60:
        bucket = 1
    elif norm_len < 130:
        bucket = 2
    else:
        bucket = 3
    return (int(is_dialogue(line)), bucket)


def find_diff_location(raw_lines, trans_lines):
    """
    Use structural features (dialogue flag + normalised length bucket) to find
    where lines are missing or extra.  Returns (missing, extra) as lists of
    (line_number, content) tuples.
    """
    raw_feats = [line_features(l) for l in raw_lines]
    trans_feats = [line_features(l) for l in trans_lines]

    sm = difflib.SequenceMatcher(None, raw_feats, trans_feats, autojunk=False)
    missing = []
    extra = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "delete":
            for i in range(i1, i2):
                missing.append((i + 1, raw_lines[i]))
        elif tag == "insert":
            for j in range(j1, j2):
                extra.append((j + 1, trans_lines[j]))
        elif tag == "replace":
            raw_block = list(range(i1, i2))
            trans_block = list(range(j1, j2))
            paired = min(len(raw_block), len(trans_block))
            for i in raw_block[paired:]:
                missing.append((i + 1, raw_lines[i]))
            for j in trans_block[paired:]:
                extra.append((j + 1, trans_lines[j]))

    return missing, extra


def md_escape(s):
    return s.replace("|", "\\|").replace("\n", " ")


LARGE_DIFF_THRESHOLD = 0.10  # flag as severe if |delta| / raw_count >= 10%
LARGE_DIFF_ABS = 15           # or if |delta| >= 15 lines (whichever triggers first)


def delta_cell(delta, raw_count):
    """Format the delta column; bold + label for large differences."""
    if delta == 0:
        return "OK"
    sign = "+" if delta > 0 else ""
    label = f"{sign}{delta}"
    severe = abs(delta) >= LARGE_DIFF_ABS or (raw_count and abs(delta) / raw_count >= LARGE_DIFF_THRESHOLD)
    if severe:
        direction = "EXTRA" if delta > 0 else "MISSING"
        return f"**{label} ({direction})**"
    direction = "extra" if delta > 0 else "missing"
    return f"{label} ({direction})"


def main():
    parser = argparse.ArgumentParser(
        description="Report translation line count differences per chapter."
    )
    parser.add_argument("start", type=int, help="First chapter to check")
    parser.add_argument("end", type=int, nargs="?", help="Last chapter to check (inclusive)")
    parser.add_argument(
        "-o", "--output", default="translation_diff_report.md", help="Output .md file"
    )
    args = parser.parse_args()

    end = args.end if args.end is not None else args.start
    if end < args.start:
        print(f"Error: end chapter ({end}) must be >= start chapter ({args.start})", file=sys.stderr)
        sys.exit(1)

    # --- First pass: collect data for every chapter ---
    # Each entry: dict with keys ch, raw_count, trans_count, delta,
    #             raw_path, trans_file, raw_lines, trans_lines, warning
    rows = []
    for ch in range(args.start, end + 1):
        row = {"ch": ch}
        raw_lines, raw_path = get_raw_lines(ch)
        if raw_lines is None:
            row["warning"] = f"no raw file found in `{RAW_DIR}/`"
            rows.append(row)
            continue

        trans_file, _, _ = find_translated_file(ch)
        if trans_file is None:
            row["warning"] = f"no translated file found in `{TRANS_DIR}/`"
            rows.append(row)
            continue

        trans_lines = extract_chapter_lines(trans_file, ch)
        if trans_lines is None:
            row["warning"] = f"header `# Chapter {ch}` not found in `{trans_file.name}`"
            rows.append(row)
            continue

        row.update(
            raw_count=len(raw_lines),
            trans_count=len(trans_lines),
            delta=len(trans_lines) - len(raw_lines),
            raw_path=raw_path,
            trans_file=trans_file,
            raw_lines=raw_lines,
            trans_lines=trans_lines,
            warning=None,
        )
        rows.append(row)

    # --- Build summary table ---
    issues = sum(1 for r in rows if not r.get("warning") and r.get("delta", 0) != 0)
    warn_rows = [r for r in rows if r.get("warning")]

    summary_lines = []
    summary_lines.append("## Summary\n\n")

    counts = [r for r in rows if not r.get("warning")]
    severe_count = sum(
        1 for r in counts
        if r["delta"] != 0 and (
            abs(r["delta"]) >= LARGE_DIFF_ABS
            or (r["raw_count"] and abs(r["delta"]) / r["raw_count"] >= LARGE_DIFF_THRESHOLD)
        )
    )

    stat_parts = []
    if issues == 0:
        stat_parts.append("All checked chapters match line counts.")
    else:
        stat_parts.append(f"**{issues}** chapter(s) have line count differences")
        if severe_count:
            stat_parts.append(f"**{severe_count}** flagged as severe (bold)")
    if warn_rows:
        stat_parts.append(f"**{len(warn_rows)}** warning(s) — see below")
    summary_lines.append("  ".join(stat_parts) + "\n\n")

    summary_lines.append("| Ch | Raw | EN | Delta | Trans file |\n")
    summary_lines.append("|---:|---:|---:|---|---|\n")
    for r in rows:
        ch = r["ch"]
        if r.get("warning"):
            summary_lines.append(f"| {ch} | — | — | ⚠ {r['warning']} | — |\n")
            continue
        dc = delta_cell(r["delta"], r["raw_count"])
        anchor = f"#chapter-{ch}" if r["delta"] != 0 else ""
        ch_cell = f"[{ch}]({anchor})" if anchor else str(ch)
        summary_lines.append(
            f"| {ch_cell} | {r['raw_count']} | {r['trans_count']} | {dc} | `{r['trans_file'].name}` |\n"
        )
    summary_lines.append("\n")

    # --- Build per-chapter detail sections (only chapters with differences) ---
    detail_lines = []
    for r in rows:
        if r.get("warning") or r.get("delta", 0) == 0:
            continue
        ch = r["ch"]
        delta = r["delta"]
        detail_lines.append(f"## Chapter {ch}\n\n")
        detail_lines.append(f"| | |\n|---|---|\n")
        detail_lines.append(f"| Raw file | `{r['raw_path'].name}` |\n")
        detail_lines.append(f"| Translated file | `{r['trans_file'].name}` |\n")
        detail_lines.append(f"| Raw line count | {r['raw_count']} |\n")
        detail_lines.append(f"| Translated line count | {r['trans_count']} |\n")
        if delta < 0:
            detail_lines.append(f"| **Verdict** | **{abs(delta)} line(s) MISSING from translation** |\n\n")
        else:
            detail_lines.append(f"| **Verdict** | **{delta} line(s) EXTRA in translation** |\n\n")

        missing, extra = find_diff_location(r["raw_lines"], r["trans_lines"])

        if missing:
            detail_lines.append("### Likely Missing Lines (raw Japanese)\n\n")
            detail_lines.append("*These raw lines appear to have no corresponding translation.*\n\n")
            detail_lines.append("| Raw Line # | Japanese Content |\n|---:|---|\n")
            for ln, content in missing:
                detail_lines.append(f"| {ln} | {md_escape(content)} |\n")
            detail_lines.append("\n")

        if extra:
            detail_lines.append("### Likely Extra Lines (English translation)\n\n")
            detail_lines.append("*These translated lines appear to have no corresponding source.*\n\n")
            detail_lines.append("| Trans Line # | English Content |\n|---:|---|\n")
            for ln, content in extra:
                detail_lines.append(f"| {ln} | {md_escape(content)} |\n")
            detail_lines.append("\n")

        detail_lines.append("---\n\n")

    # --- Assemble output ---
    out = []
    out.append(f"# Translation Diff Report: Chapters {args.start}–{end}\n\n")
    out.extend(summary_lines)
    if detail_lines:
        out.append("---\n\n")
        out.extend(detail_lines)

    output_path = Path(args.output)
    output_path.write_text("".join(out), encoding="utf-8")

    status = f"Report written to `{output_path}`"
    if issues:
        status += f" — {issues} chapter(s) with differences"
        if severe_count:
            status += f" ({severe_count} severe)"
    if warn_rows:
        status += f", {len(warn_rows)} warning(s)"
    print(status)


if __name__ == "__main__":
    main()
