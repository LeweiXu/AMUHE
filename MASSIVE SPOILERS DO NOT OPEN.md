## UwU

Aight if you're looking at this file the the cat's out of the bag. You may or may not have noticed the translation quality was a bit *too* good with some slightly unnatural sounding 
passages. Well, that is because I did the translation using the latest and strongest LLM model: Claude Opus 4.6.

## Methodology

I actually tried doing this in early 2025 using GPT but found that although the translation itself was passable, it often couldn't even fit a single chapter in it's context 
window and often truncated up to half a chapter. It also didn't like what it was translating, often straight up refusing to translate because it was a "content violation". 
Looks like GPT couldn't handle Krische's personality lol.

Opus 4.6 has a 1 million token context window, it could theoretically fit the whole novel in it's memory, but translation quality will probably degrade as it translates further
and further into the novel. Instead of trying to translate the whole novel at once (which would've taken literal hours even if the translation quality was perfect), I opted to translate
chapters in batches of 5 at a time. To maintain accuracy and consistency of romanization and accuracy of translation, I maintain a `knowledge_base.md` that is updated after every batch. 
`knowledge_base.md` contains condensed information about the novel and what happened in previous chapters and is supplied to the AI at every batch. In addition, a `context.md` file is 
provided with additional information such as the task, the goal, and other information.

I passed in 7 files (`knowledge_base.md` + `context.md` + 5 chapters in txt format) + the prompt which is available below and had Claude Opus 4.6 output 2 files:
1. A `.md` file containing the translation of the 5 chapters
2. A `.md` file containing additions to the knowledge base

Instead of having Opus 4.6 redo the knowledge base from scratch which takes a lot of time, I simple had it generate any additions necessary, then used the `merge.py` script to merge
the information into the existing knowledge base.

## Translation Quality

I can confidently say that the translation quality is at the very least **on par if not better** than your average translator. One thing that LLMs can guarantee is that there will be no
spelling or grammar issues. A model as powerful as Opus 4.6 also won't miss entire passages or truncate the text or try to shorten the text like GPT did back in 2025. The only things that 
it could potentially mess up is missing some specific references/idioms, but that is easy to forgive considering how fast and accurate it is.

I also did some quality testing by having Opus 4.6 translate the first few chapters and compared it against HecateHonryuu's translation and obviously, while HecateHonryuu's translation 
was great, the LLM translation didn't fall far behind. If HecateHonryuu's translation is a 10/10, then I would say that Opus 4.6's translation is a solid 9/10 (while inoveltranslations' 
would be like a 4/10).

## Prompt

Translate the following chapters of 少女の望まぬ英雄譚 in order.

Follow all rules in context.md and knowledge_base.md exactly.
Treat all chapters as one continuous session — maintain perfect consistency in character
voice, name romanizations, and terminology across all of them.

### Output: two files

---

#### File 1 — Translation (Markdown)

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

Do not invent formatting that has no basis in the source text. When in doubt, plain prose
is correct. The goal is a clean reading experience, not aggressive annotation.

---

#### File 2 — Knowledge Base Additions

After ALL chapters are translated, produce a second file containing ONLY new information
introduced in this batch. The new information should be concise and condensed. Only add
information necessary for translation accuracy. A merge script will apply these additions 
automatically, so follow the format rules below exactly — the script depends on them.

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