# Batch Translation Prompt
#
# Usage: paste everything from the first divider downward into a new claude.ai Project
#        chat, then replace the placeholder blocks at the bottom with your raw chapters.
#
# The project must have context.md and knowledge_base.md attached as project files.
# Recommended batch size: 3–5 chapters per chat session.
#
# After the session, run:
#   python3 merge_kb.py additions.md
# to merge File 2 into your local knowledge_base.md, then re-upload it to the Project.

---

Translate the following chapters of 少女の望まぬ英雄譚 in order.

Follow all rules in context.md and knowledge_base.md exactly.
Treat all chapters as one continuous session — maintain perfect consistency in character
voice, name romanizations, and terminology across all of them.

## Output: two files

---

### File 1 — Translation (Markdown)

Produce a single `.md` file containing all translated chapters in order.

Formatting rules:
- Use `#` for the chapter title (e.g. `# Chapter 42: The Holy War of the Kitchen`)
- Use `---` between chapters as a chapter divider
- Use `* * *` for scene breaks within a chapter
- Use *italics* for internal thoughts, inner monologue, and recalled memories when they
  are typographically distinct in the source (e.g. set off by the `――` em-dash convention,
  indentation, or a change in visual register)
- Use *italics* for meaningful emphasis where the source uses emphasis markers
  (傍点 dots, 《》 brackets, or similar)
- Use **bold** sparingly, only where the source uses explicit strong visual emphasis
- Preserve the author's paragraph rhythm — do not merge or split paragraphs
- Translator notes go inline at the relevant passage as: `(T/N: ...)`
- Author's notes, if present, go at the end of their chapter after a `---` divider
- If there is not an `――` em-dash in the original text, do not use an em-dash in the translation

Do not invent formatting that has no basis in the source text. When in doubt, plain prose
is correct. The goal is a clean reading experience, not aggressive annotation.

---

### File 2 — Knowledge Base Additions

After ALL chapters are translated, produce a second file containing ONLY new information
introduced in this batch. A merge script will apply these additions automatically, so
follow the format rules below exactly — the script depends on them.

**First line of File 2 must always be:**
`*Update coverage line to: Chapters 1–[last chapter number in this batch]*`

**Then include only sections that actually have new content.** Omit any section entirely
if nothing new was introduced in it. If nothing at all is new, write only:
`No updates required.`

**Format rules by section:**

`## NAME ROMANIZATIONS`
New rows only. Use the same 3-column table format as the existing file:
`| Japanese | English | Role |`
Do not repeat the table header. Do not include rows already in knowledge_base.md.

`## CORE CHARACTERS`
New characters only, as full `### Character Name` subsection blocks.
For existing characters, only add genuinely new bullet points not already present —
use the same `### Character Name` heading so the script can locate the entry.

`## SECONDARY CHARACTERS`
Same rules as CORE CHARACTERS.

`## PLACE NAMES AND LOCATIONS`
New rows only, same 2-column table format: `| **Name (Japanese)** | Description |`
Do not repeat the table header.

`## WORLD-BUILDING REFERENCE`
New `### subsection` blocks or new bullet points under existing subsections only.

`## TIMELINE: CHAPTERS X–Y`
Use a fresh heading with the exact chapter range of this batch, e.g.
`## TIMELINE: CHAPTERS 42–45`
This becomes a new standalone section — do not try to modify the existing timeline.
Use the same table format: `| Chapter(s) | Event |`
Include the table header row for this new section.

`## RECURRING THEMES AND MOTIFS`
New items only, as unnumbered lines (the script handles renumbering):
`**Theme name** — Description`

`## TRANSLATOR NOTES FROM ORIGINAL TRANSLATION (C.1–41)`
New bullet points only, using `- ` prefix.
Update the heading's chapter range if needed (e.g. change C.1–41 to C.1–45).

**Any entirely new section** not listed above: include it with its full `## HEADING`
and complete content. The script will append it to the end of knowledge_base.md.