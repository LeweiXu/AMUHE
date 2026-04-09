#!/usr/bin/env python3
"""
cleaup.py — Deduplicate markdown table rows in a file.

For every markdown table in the file, finds rows where the first field
matches exactly, removes all but the last occurrence, and writes the
result back to the file.

Usage:
    python cleaup.py [file]        (default: context.md)
"""

import sys
import re


def get_first_field(line: str) -> str:
    """Extract and normalize the first field from a markdown table row."""
    # Strip leading/trailing whitespace, split on '|', skip blank first element
    parts = line.strip().split("|")
    # parts[0] is empty (before the leading |), parts[1] is first field
    if len(parts) >= 2:
        return parts[1].strip()
    return ""


def is_table_row(line: str) -> bool:
    return line.strip().startswith("|")


def is_separator_row(line: str) -> bool:
    """Detect a markdown table separator row like |---|---|"""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    return bool(re.match(r"^\|[-| :]+\|$", stripped))


def process_table(table_lines: list[tuple[int, str]]) -> tuple[list[tuple[int, str]], int]:
    """
    Process a block of table lines (list of (original_lineno, text)).
    Returns (deduplicated lines, number of duplicates removed).
    """
    # Separate header + separator from data rows
    # The separator row is the one matching |---|---| pattern
    sep_idx = None
    for i, (_, line) in enumerate(table_lines):
        if is_separator_row(line):
            sep_idx = i
            break

    if sep_idx is None:
        # No separator found — not a proper table, leave unchanged
        return table_lines, 0

    header_lines = table_lines[: sep_idx + 1]  # header row(s) + separator
    data_lines = table_lines[sep_idx + 1 :]

    # Deduplicate data rows: keep last occurrence of each first-field value
    # We iterate in reverse, collect first-field values seen, then reverse back
    seen: set[str] = set()
    kept_reversed: list[tuple[int, str]] = []
    removed_count = 0

    for lineno, line in reversed(data_lines):
        field = get_first_field(line)
        if field in seen:
            print(
                f"  [DUPLICATE] Line {lineno + 1}: first field = {field!r} — removing earlier occurrence"
            )
            removed_count += 1
        else:
            seen.add(field)
            kept_reversed.append((lineno, line))

    kept_data = list(reversed(kept_reversed))
    return header_lines + kept_data, removed_count


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "context.md"

    print(f"Reading file: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    # Strip trailing newlines for processing, we'll re-add them on write
    lines = [line.rstrip("\n") for line in raw_lines]

    print(f"Total lines: {len(lines)}")

    # Group lines into table blocks and non-table regions
    # We'll build a new list of lines after processing each table
    result_lines: list[str] = []
    i = 0
    total_tables = 0
    total_duplicates = 0

    while i < len(lines):
        if is_table_row(lines[i]):
            # Collect contiguous table lines
            table_start = i
            table_block: list[tuple[int, str]] = []
            while i < len(lines) and is_table_row(lines[i]):
                table_block.append((i, lines[i]))
                i += 1

            total_tables += 1
            first_field = get_first_field(table_block[0][1])
            print(
                f"\nTable #{total_tables} found at line {table_start + 1}–{i} "
                f"({len(table_block)} rows, header first field: {first_field!r})"
            )

            processed, removed = process_table(table_block)
            total_duplicates += removed

            if removed == 0:
                print(f"  No duplicates found.")
            else:
                print(f"  Removed {removed} duplicate row(s).")

            result_lines.extend(row for _, row in processed)
        else:
            result_lines.append(lines[i])
            i += 1

    print(f"\n{'=' * 60}")
    print(f"Summary: {total_tables} table(s) scanned, {total_duplicates} duplicate row(s) removed.")

    if total_duplicates == 0:
        print("No changes made.")
        return

    # Write back
    output = "\n".join(result_lines)
    # Preserve trailing newline if original file had one
    if raw_lines and raw_lines[-1].endswith("\n"):
        output += "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"File written: {filepath}")


if __name__ == "__main__":
    main()
