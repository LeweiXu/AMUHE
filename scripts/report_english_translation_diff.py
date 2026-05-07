#!/usr/bin/env python3
"""
Compare two English translation files and report likely missing/additional lines.

Usage:
    python report_english_translation_diff.py translator_a.md translator_b.md [-o report.md]

The input files may contain one chapter or many chapters.  When "# Chapter N"
headers are present, each chapter is compared separately.  Otherwise the entire
file is compared as a single section.
"""

import argparse
import difflib
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path


CHAPTER_RE = re.compile(
    r"^\s*#{1,6}\s*(?:chapter|ch\.?)\s*(\d+)\b[:.\-\s]*(.*)$",
    re.IGNORECASE,
)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
WORD_RE = re.compile(r"[a-z0-9']+")
HORIZONTAL_RULE_RE = re.compile(r"^\s{0,3}(?:[-*_]\s*){3,}$")
BR_ONLY_RE = re.compile(r"^\s*(?:<br\s*/?>\s*)+$", re.IGNORECASE)
REFLOW_CONTEXT_THRESHOLD = 0.38

STOPWORDS = {
    "a",
    "about",
    "after",
    "again",
    "all",
    "also",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "been",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "even",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "hers",
    "him",
    "his",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "like",
    "me",
    "my",
    "no",
    "not",
    "of",
    "on",
    "one",
    "or",
    "our",
    "out",
    "she",
    "so",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "they",
    "this",
    "to",
    "up",
    "was",
    "we",
    "were",
    "what",
    "when",
    "with",
    "would",
    "you",
    "your",
}


@dataclass(frozen=True)
class Line:
    number: int
    text: str
    norm: str
    tokens: frozenset[str]


@dataclass
class Chapter:
    key: int | str
    title: str
    order: int
    lines: list[Line]


@dataclass
class ChapterResult:
    key: int | str
    title_a: str
    title_b: str
    a_count: int
    b_count: int
    a_only_count: int
    b_only_count: int
    likely_missing_from_b: int
    likely_added_in_b: int
    blocks: list[dict]
    warning: str | None = None


def strip_html_comments(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text)


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = text.lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"[*_`~]", "", text)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-z0-9'\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def line_tokens(norm: str) -> frozenset[str]:
    return frozenset(
        token for token in WORD_RE.findall(norm) if len(token) > 2 and token not in STOPWORDS
    )


def make_line(number: int, text: str) -> Line:
    norm = normalize_text(text)
    return Line(number=number, text=text, norm=norm, tokens=line_tokens(norm))


def is_ignored_line(text: str) -> bool:
    stripped = text.strip()
    return not stripped or bool(HORIZONTAL_RULE_RE.match(stripped)) or bool(BR_ONLY_RE.match(stripped))


def parse_chapters(path: Path) -> list[Chapter]:
    text = strip_html_comments(path.read_text(encoding="utf-8"))
    raw_lines = text.splitlines()

    chapters: list[Chapter] = []
    current: Chapter | None = None
    current_line_num = 0
    found_header = False

    for raw in raw_lines:
        header = CHAPTER_RE.match(raw)
        if header:
            found_header = True
            chapter_num = int(header.group(1))
            title = header.group(2).strip() or f"Chapter {chapter_num}"
            current = Chapter(
                key=chapter_num,
                title=f"Chapter {chapter_num}: {title}",
                order=len(chapters),
                lines=[],
            )
            chapters.append(current)
            current_line_num = 0
            continue

        if is_ignored_line(raw):
            continue

        if current is None:
            current = Chapter(
                key="preamble" if found_header else "file",
                title="Preamble" if found_header else path.name,
                order=len(chapters),
                lines=[],
            )
            chapters.append(current)
            current_line_num = 0

        current_line_num += 1
        current.lines.append(make_line(current_line_num, raw.strip()))

    if not chapters:
        chapters.append(Chapter(key="file", title=path.name, order=0, lines=[]))

    return chapters


def chapter_map(chapters: list[Chapter]) -> dict[int | str, Chapter]:
    return {chapter.key: chapter for chapter in chapters}


def sorted_chapter_keys(a_chapters: list[Chapter], b_chapters: list[Chapter]) -> list[int | str]:
    order: dict[int | str, int] = {}
    for chapter in a_chapters + b_chapters:
        order.setdefault(chapter.key, len(order))

    def sort_key(key: int | str):
        if isinstance(key, int):
            return (0, key)
        return (1, order[key])

    return sorted(order, key=sort_key)


def dialogue_prefix(line: str) -> str:
    stripped = line.lstrip()
    return stripped[:1] if stripped[:1] in {'"', "'", "\u201c", "\u2018"} else ""


def line_similarity(a: Line, b: Line) -> float:
    if not a.norm or not b.norm:
        return 0.0
    if a.norm == b.norm:
        return 1.0

    char_ratio = difflib.SequenceMatcher(None, a.norm, b.norm, autojunk=False).ratio()

    if a.tokens and b.tokens:
        shared = len(a.tokens & b.tokens)
        union = len(a.tokens | b.tokens)
        token_jaccard = shared / union if union else 0.0
        token_overlap = shared / min(len(a.tokens), len(b.tokens))
    else:
        token_jaccard = 0.0
        token_overlap = 0.0

    len_ratio = min(len(a.norm), len(b.norm)) / max(len(a.norm), len(b.norm), 1)
    dialogue_bonus = 0.04 if dialogue_prefix(a.text) == dialogue_prefix(b.text) else -0.04
    number_bonus = 0.05 if re.findall(r"\d+", a.norm) == re.findall(r"\d+", b.norm) else 0.0

    score = max(
        char_ratio,
        (0.52 * token_overlap) + (0.22 * token_jaccard) + (0.18 * char_ratio) + (0.08 * len_ratio),
    )
    return max(0.0, min(1.0, score + dialogue_bonus + number_bonus))


def align_lines(
    a_lines: list[Line],
    b_lines: list[Line],
    match_threshold: float,
    min_similarity: float,
    gap_penalty: float,
) -> list[tuple[str, int | None, int | None, float | None]]:
    """Fast chapter alignment.

    Most translation revisions keep many lines identical.  We anchor on exact
    normalized matches first, then fuzzy-align only the changed spans.  This
    avoids building a chapter-sized dynamic-programming matrix.
    """
    a_norms = [line.norm for line in a_lines]
    b_norms = [line.norm for line in b_lines]
    sm = difflib.SequenceMatcher(None, a_norms, b_norms, autojunk=False)

    operations: list[tuple[str, int | None, int | None, float | None]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                operations.append(("match", i1 + offset, j1 + offset, 1.0))
        elif tag == "delete":
            operations.extend(("delete", i, None, None) for i in range(i1, i2))
        elif tag == "insert":
            operations.extend(("insert", None, j, None) for j in range(j1, j2))
        elif tag == "replace":
            operations.extend(
                align_changed_span(
                    a_lines,
                    b_lines,
                    i1,
                    i2,
                    j1,
                    j2,
                    match_threshold,
                    min_similarity,
                    gap_penalty,
                )
            )

    return operations


def align_changed_span(
    a_lines: list[Line],
    b_lines: list[Line],
    i1: int,
    i2: int,
    j1: int,
    j2: int,
    match_threshold: float,
    min_similarity: float,
    gap_penalty: float,
) -> list[tuple[str, int | None, int | None, float | None]]:
    span_cells = (i2 - i1) * (j2 - j1)
    if span_cells <= 20000:
        return align_lines_dp(
            a_lines[i1:i2],
            b_lines[j1:j2],
            i1,
            j1,
            match_threshold,
            min_similarity,
            gap_penalty,
        )
    return align_lines_greedy(a_lines, b_lines, i1, i2, j1, j2, min_similarity)


def align_lines_dp(
    a_lines: list[Line],
    b_lines: list[Line],
    a_offset: int,
    b_offset: int,
    match_threshold: float,
    min_similarity: float,
    gap_penalty: float,
) -> list[tuple[str, int | None, int | None, float | None]]:
    n = len(a_lines)
    m = len(b_lines)
    scores = [[float("-inf")] * (m + 1) for _ in range(n + 1)]
    back = [[""] * (m + 1) for _ in range(n + 1)]
    sim_cache: dict[tuple[int, int], float] = {}

    scores[0][0] = 0.0
    for i in range(1, n + 1):
        scores[i][0] = scores[i - 1][0] - gap_penalty
        back[i][0] = "delete"
    for j in range(1, m + 1):
        scores[0][j] = scores[0][j - 1] - gap_penalty
        back[0][j] = "insert"

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            key = (i - 1, j - 1)
            sim = sim_cache.get(key)
            if sim is None:
                sim = line_similarity(a_lines[i - 1], b_lines[j - 1])
                sim_cache[key] = sim

            candidates = [
                (scores[i - 1][j] - gap_penalty, "delete"),
                (scores[i][j - 1] - gap_penalty, "insert"),
            ]
            if sim >= min_similarity:
                candidates.append((scores[i - 1][j - 1] + sim - match_threshold, "match"))

            best_score, best_action = max(candidates, key=lambda item: item[0])
            scores[i][j] = best_score
            back[i][j] = best_action

    operations: list[tuple[str, int | None, int | None, float | None]] = []
    i = n
    j = m
    while i > 0 or j > 0:
        action = back[i][j]
        if action == "match":
            sim = sim_cache[(i - 1, j - 1)]
            operations.append(("match", a_offset + i - 1, b_offset + j - 1, sim))
            i -= 1
            j -= 1
        elif action == "delete":
            operations.append(("delete", a_offset + i - 1, None, None))
            i -= 1
        elif action == "insert":
            operations.append(("insert", None, b_offset + j - 1, None))
            j -= 1
        else:
            raise RuntimeError("alignment failed")

    operations.reverse()
    return operations


def align_lines_greedy(
    a_lines: list[Line],
    b_lines: list[Line],
    i1: int,
    i2: int,
    j1: int,
    j2: int,
    min_similarity: float,
) -> list[tuple[str, int | None, int | None, float | None]]:
    operations: list[tuple[str, int | None, int | None, float | None]] = []
    i = i1
    j = j1
    lookahead = 45
    anchor_threshold = max(0.62, min_similarity + 0.12)

    while i < i2 and j < j2:
        current_sim = line_similarity(a_lines[i], b_lines[j])
        if current_sim >= min_similarity:
            operations.append(("match", i, j, current_sim))
            i += 1
            j += 1
            continue

        best: tuple[float, int, int] | None = None
        max_i = min(i2, i + lookahead + 1)
        max_j = min(j2, j + lookahead + 1)
        for ii in range(i, max_i):
            for jj in range(j, max_j):
                sim = line_similarity(a_lines[ii], b_lines[jj])
                distance_penalty = 0.01 * ((ii - i) + (jj - j))
                score = sim - distance_penalty
                if best is None or score > best[0]:
                    best = (score, ii, jj)

        if best is None or best[0] < anchor_threshold:
            operations.append(("delete", i, None, None))
            operations.append(("insert", None, j, None))
            i += 1
            j += 1
            continue

        _, anchor_i, anchor_j = best
        operations.extend(("delete", idx, None, None) for idx in range(i, anchor_i))
        operations.extend(("insert", None, idx, None) for idx in range(j, anchor_j))
        operations.append(("match", anchor_i, anchor_j, line_similarity(a_lines[anchor_i], b_lines[anchor_j])))
        i = anchor_i + 1
        j = anchor_j + 1

    operations.extend(("delete", idx, None, None) for idx in range(i, i2))
    operations.extend(("insert", None, idx, None) for idx in range(j, j2))
    return operations


def context_match(
    operations: list[tuple[str, int | None, int | None, float | None]], start: int, step: int
) -> tuple[int | None, int | None, float | None]:
    i = start
    while 0 <= i < len(operations):
        op, a_idx, b_idx, sim = operations[i]
        if op == "match":
            return a_idx, b_idx, sim
        i += step
    return None, None, None


def combined_line(lines: list[Line]) -> Line | None:
    if not lines:
        return None
    text = " ".join(line.text for line in lines)
    return make_line(lines[0].number, text)


def best_context_similarity(lines: list[Line], context_lines: list[Line | None]) -> float:
    merged = combined_line(lines)
    usable_context = [context for context in context_lines if context is not None]
    if merged is None or not usable_context:
        return 0.0
    best = 0.0
    for context in usable_context:
        best = max(best, line_similarity(merged, context))
        for line in lines:
            best = max(best, line_similarity(line, context))
    return best


def classify_block(
    a_only: list[Line],
    b_only: list[Line],
    prev_a: Line | None,
    prev_b: Line | None,
    next_a: Line | None,
    next_b: Line | None,
) -> str:
    if a_only and b_only:
        return "changed_or_reflowed"
    if a_only:
        context_sim = best_context_similarity(a_only, [prev_b, next_b])
        return (
            "changed_or_reflowed"
            if context_sim >= REFLOW_CONTEXT_THRESHOLD
            else "likely_missing_from_b"
        )
    if b_only:
        context_sim = best_context_similarity(b_only, [prev_a, next_a])
        return "changed_or_reflowed" if context_sim >= REFLOW_CONTEXT_THRESHOLD else "likely_added_in_b"
    return "unchanged"


def block_likely_counts(block: dict) -> tuple[int, int]:
    if block.get("kind") == "likely_missing_from_b":
        return len(block["a_only"]), 0
    if block.get("kind") == "likely_added_in_b":
        return 0, len(block["b_only"])
    return 0, 0


def build_blocks(
    operations: list[tuple[str, int | None, int | None, float | None]],
    a_lines: list[Line],
    b_lines: list[Line],
) -> list[dict]:
    blocks = []
    idx = 0
    while idx < len(operations):
        op, _, _, _ = operations[idx]
        if op == "match":
            idx += 1
            continue

        start = idx
        a_only = []
        b_only = []
        while idx < len(operations) and operations[idx][0] != "match":
            cur_op, a_idx, b_idx, _ = operations[idx]
            if cur_op == "delete" and a_idx is not None:
                a_only.append(a_lines[a_idx])
            elif cur_op == "insert" and b_idx is not None:
                b_only.append(b_lines[b_idx])
            idx += 1

        prev_a, prev_b, prev_sim = context_match(operations, start - 1, -1)
        next_a, next_b, next_sim = context_match(operations, idx, 1)
        prev_a_line = a_lines[prev_a] if prev_a is not None else None
        prev_b_line = b_lines[prev_b] if prev_b is not None else None
        next_a_line = a_lines[next_a] if next_a is not None else None
        next_b_line = b_lines[next_b] if next_b is not None else None
        blocks.append(
            {
                "a_only": a_only,
                "b_only": b_only,
                "kind": classify_block(a_only, b_only, prev_a_line, prev_b_line, next_a_line, next_b_line),
                "prev": (prev_a_line, prev_b_line, prev_sim),
                "next": (next_a_line, next_b_line, next_sim),
            }
        )

    return blocks


def compare_chapter(
    key: int | str,
    a: Chapter | None,
    b: Chapter | None,
    match_threshold: float,
    min_similarity: float,
    gap_penalty: float,
) -> ChapterResult:
    title_a = a.title if a else ""
    title_b = b.title if b else ""

    if a is None:
        b_lines = b.lines if b else []
        return ChapterResult(
            key=key,
            title_a=title_a,
            title_b=title_b,
            a_count=0,
            b_count=len(b_lines),
            a_only_count=0,
            b_only_count=len(b_lines),
            likely_missing_from_b=0,
            likely_added_in_b=len(b_lines),
            blocks=[
                {
                    "a_only": [],
                    "b_only": b_lines,
                    "kind": "likely_added_in_b",
                    "prev": (None, None, None),
                    "next": (None, None, None),
                }
            ]
            if b_lines
            else [],
            warning="chapter missing from file A",
        )

    if b is None:
        a_lines = a.lines
        return ChapterResult(
            key=key,
            title_a=title_a,
            title_b=title_b,
            a_count=len(a_lines),
            b_count=0,
            a_only_count=len(a_lines),
            b_only_count=0,
            likely_missing_from_b=len(a_lines),
            likely_added_in_b=0,
            blocks=[
                {
                    "a_only": a_lines,
                    "b_only": [],
                    "kind": "likely_missing_from_b",
                    "prev": (None, None, None),
                    "next": (None, None, None),
                }
            ]
            if a_lines
            else [],
            warning="chapter missing from file B",
        )

    operations = align_lines(a.lines, b.lines, match_threshold, min_similarity, gap_penalty)
    blocks = build_blocks(operations, a.lines, b.lines)
    likely_missing_from_b = 0
    likely_added_in_b = 0
    for block in blocks:
        missing_count, added_count = block_likely_counts(block)
        likely_missing_from_b += missing_count
        likely_added_in_b += added_count
    return ChapterResult(
        key=key,
        title_a=title_a,
        title_b=title_b,
        a_count=len(a.lines),
        b_count=len(b.lines),
        a_only_count=sum(len(block["a_only"]) for block in blocks),
        b_only_count=sum(len(block["b_only"]) for block in blocks),
        likely_missing_from_b=likely_missing_from_b,
        likely_added_in_b=likely_added_in_b,
        blocks=blocks,
    )


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def chapter_label(key: int | str) -> str:
    return f"Chapter {key}" if isinstance(key, int) else str(key).title()


def anchor_for(key: int | str) -> str:
    return "chapter-" + re.sub(r"[^a-z0-9-]+", "-", str(key).lower()).strip("-")


def format_context_line(line: Line | None) -> str:
    if line is None:
        return "—"
    return f"L{line.number}: {md_escape(line.text)}"


def write_report(
    output_path: Path,
    file_a: Path,
    file_b: Path,
    label_a: str,
    label_b: str,
    results: list[ChapterResult],
    match_threshold: float,
    min_similarity: float,
) -> None:
    out = []
    out.append("# English Translation Comparison Report\n\n")
    out.append(f"- File A: `{file_a}` ({label_a})\n")
    out.append(f"- File B: `{file_b}` ({label_b})\n")
    out.append(f"- Match threshold: `{match_threshold:.2f}`\n")
    out.append(f"- Minimum similarity: `{min_similarity:.2f}`\n\n")
    out.append(
        "Lines listed as A-only are present in file A but did not align to file B; "
        "B-only lines are the reverse. The likely columns exclude blocks that look "
        "like wording changes or line split/merge differences.\n\n"
    )

    changed = [result for result in results if result.a_only_count or result.b_only_count]
    warnings = [result for result in results if result.warning]
    out.append("## Summary\n\n")
    out.append(
        f"Checked {len(results)} section(s). "
        f"{len(changed)} section(s) have unmatched lines. "
        f"{len(warnings)} warning(s).\n\n"
    )
    out.append(
        f"| Section | {label_a} lines | {label_b} lines | Delta | "
        "Likely missing from B | Likely added in B | A-only candidates | B-only candidates |\n"
    )
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|\n")
    for result in results:
        delta = result.b_count - result.a_count
        label = chapter_label(result.key)
        if result.a_only_count or result.b_only_count:
            label = f"[{label}](#{anchor_for(result.key)})"
        out.append(
            f"| {label} | {result.a_count} | {result.b_count} | {delta:+d} | "
            f"{result.likely_missing_from_b} | {result.likely_added_in_b} | "
            f"{result.a_only_count} | {result.b_only_count} |\n"
        )
    out.append("\n")

    if warnings:
        out.append("## Warnings\n\n")
        for result in warnings:
            out.append(f"- {chapter_label(result.key)}: {result.warning}\n")
        out.append("\n")

    for result in changed:
        out.append(f"## {chapter_label(result.key)}\n\n")
        out.append(f"<a id=\"{anchor_for(result.key)}\"></a>\n\n")
        out.append("| | |\n|---|---|\n")
        out.append(f"| File A title | {md_escape(result.title_a) or '—'} |\n")
        out.append(f"| File B title | {md_escape(result.title_b) or '—'} |\n")
        out.append(f"| File A line count | {result.a_count} |\n")
        out.append(f"| File B line count | {result.b_count} |\n")
        out.append(f"| Likely missing from B | {result.likely_missing_from_b} |\n")
        out.append(f"| Likely added in B | {result.likely_added_in_b} |\n")
        out.append(f"| A-only unmatched lines | {result.a_only_count} |\n")
        out.append(f"| B-only unmatched lines | {result.b_only_count} |\n\n")

        for block_num, block in enumerate(result.blocks, start=1):
            out.append(f"### Difference Block {block_num}\n\n")
            out.append(f"Classification: **{block['kind'].replace('_', ' ')}**\n\n")
            prev_a, prev_b, prev_sim = block["prev"]
            next_a, next_b, next_sim = block["next"]
            out.append("**Nearest aligned context**\n\n")
            out.append(f"| Context | {label_a} | {label_b} | Similarity |\n")
            out.append("|---|---|---|---:|\n")
            out.append(
                f"| Before | {format_context_line(prev_a)} | {format_context_line(prev_b)} | "
                f"{prev_sim:.2f} |\n"
                if prev_sim is not None
                else f"| Before | {format_context_line(prev_a)} | {format_context_line(prev_b)} | — |\n"
            )
            out.append(
                f"| After | {format_context_line(next_a)} | {format_context_line(next_b)} | "
                f"{next_sim:.2f} |\n\n"
                if next_sim is not None
                else f"| After | {format_context_line(next_a)} | {format_context_line(next_b)} | — |\n\n"
            )

            if block["a_only"]:
                out.append(f"**A-only lines ({label_a})**\n\n")
                out.append("| Line | Text |\n|---:|---|\n")
                for line in block["a_only"]:
                    out.append(f"| {line.number} | {md_escape(line.text)} |\n")
                out.append("\n")

            if block["b_only"]:
                out.append(f"**B-only lines ({label_b})**\n\n")
                out.append("| Line | Text |\n|---:|---|\n")
                for line in block["b_only"]:
                    out.append(f"| {line.number} | {md_escape(line.text)} |\n")
                out.append("\n")

        out.append("---\n\n")

    output_path.write_text("".join(out), encoding="utf-8")


def print_terminal_summary(label_a: str, label_b: str, results: list[ChapterResult], output: Path) -> None:
    changed = [result for result in results if result.a_only_count or result.b_only_count]
    total_a_only = sum(result.a_only_count for result in results)
    total_b_only = sum(result.b_only_count for result in results)
    likely_missing = sum(result.likely_missing_from_b for result in results)
    likely_added = sum(result.likely_added_in_b for result in results)
    warnings = [result for result in results if result.warning]

    print(f"Report written to `{output}`")
    print(
        f"Checked {len(results)} section(s): {len(changed)} with unmatched lines, "
        f"{total_a_only} A-only, {total_b_only} B-only"
    )
    print(f"Likely content differences: {likely_missing} missing from B, {likely_added} added in B")
    if warnings:
        print(f"Warnings: {len(warnings)}")

    if not changed:
        print("No likely missing/additional lines found.")
        return

    print()
    print(
        f"| Section | {label_a} lines | {label_b} lines | Delta | "
        "Likely missing from B | Likely added in B | A-only | B-only |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for result in changed:
        delta = result.b_count - result.a_count
        print(
            f"| {chapter_label(result.key)} | {result.a_count} | {result.b_count} | "
            f"{delta:+d} | {result.likely_missing_from_b} | {result.likely_added_in_b} | "
            f"{result.a_only_count} | {result.b_only_count} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two English translations and report likely missing/additional lines."
    )
    parser.add_argument("file_a", type=Path, help="First English translation file")
    parser.add_argument("file_b", type=Path, help="Second English translation file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("report.md"),
        help="Comprehensive Markdown report path (default: report.md)",
    )
    parser.add_argument("--label-a", default="A", help="Display label for the first file")
    parser.add_argument("--label-b", default="B", help="Display label for the second file")
    parser.add_argument(
        "--match-threshold",
        type=float,
        default=0.55,
        help="Similarity score treated as a neutral alignment match (default: 0.55)",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.48,
        help="Minimum similarity allowed for two lines to align (default: 0.48)",
    )
    parser.add_argument(
        "--gap-penalty",
        type=float,
        default=0.35,
        help="Penalty for an unmatched line during alignment (default: 0.35)",
    )
    args = parser.parse_args()

    for path in (args.file_a, args.file_b):
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        if not path.is_file():
            print(f"Error: not a file: {path}", file=sys.stderr)
            sys.exit(1)

    if not 0 <= args.min_similarity <= 1:
        print("Error: --min-similarity must be between 0 and 1", file=sys.stderr)
        sys.exit(1)
    if not 0 <= args.match_threshold <= 1:
        print("Error: --match-threshold must be between 0 and 1", file=sys.stderr)
        sys.exit(1)
    if args.gap_penalty <= 0:
        print("Error: --gap-penalty must be greater than 0", file=sys.stderr)
        sys.exit(1)

    a_chapters = parse_chapters(args.file_a)
    b_chapters = parse_chapters(args.file_b)
    a_by_key = chapter_map(a_chapters)
    b_by_key = chapter_map(b_chapters)

    results = [
        compare_chapter(
            key,
            a_by_key.get(key),
            b_by_key.get(key),
            args.match_threshold,
            args.min_similarity,
            args.gap_penalty,
        )
        for key in sorted_chapter_keys(a_chapters, b_chapters)
    ]

    write_report(
        args.output,
        args.file_a,
        args.file_b,
        args.label_a,
        args.label_b,
        results,
        args.match_threshold,
        args.min_similarity,
    )
    print_terminal_summary(args.label_a, args.label_b, results, args.output)


if __name__ == "__main__":
    main()
