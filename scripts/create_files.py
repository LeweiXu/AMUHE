import sys
import os


def create_files(start: int, end: int, output_dir: str = "translated_chapters"):
    os.makedirs(output_dir, exist_ok=True)

    current = start + 1
    while current <= end:
        # End of group: next multiple of 5
        group_end = min(((current - 1) // 5 + 1) * 5, end)

        filename = f"{current}-{group_end}.md"
        filepath = os.path.join(output_dir, filename)
        open(filepath, "w").close()
        print(f"Created {filepath}")

        current = group_end + 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <start> <end> [output_dir]")
        sys.exit(1)

    start = int(sys.argv[1])
    end = int(sys.argv[2])
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "translated_chapters"

    create_files(start, end, output_dir)
