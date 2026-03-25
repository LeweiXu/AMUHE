import sys
import os
import re


def txt_to_md(directory: str, output_file: str):
    txt_files = [f for f in os.listdir(directory) if f.endswith(".txt")]
    txt_files.sort(key=lambda f: re.match(r"^(\d+)", f).group(1))

    sections = []
    for filename in txt_files:
        filepath = os.path.join(directory, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\n") for line in f.readlines()]

        if not lines:
            continue

        heading = f"# {lines[0]}"
        body_lines = [line for line in lines[1:] if line.strip()]

        section = heading + "\n\n" + "\n\n".join(body_lines)
        sections.append(section)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(sections))
        f.write("\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input_directory> <output_file.md>")
        sys.exit(1)

    txt_to_md(sys.argv[1], sys.argv[2])
    print(f"Done. Output written to {sys.argv[2]}")
