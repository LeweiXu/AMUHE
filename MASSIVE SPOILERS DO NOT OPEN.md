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

Follow all rules in context.md exactly.
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
introduced in this batch. A merge script will apply these additions automatically, so
follow the format rules exactly — the script depends on them.

**First line of File 2 must always be:**
`*Update coverage line to: Chapters 1–[last chapter number in this batch]*`

**Then include only the sections below that actually have new content.**
If nothing at all is new, write only: `No updates required.`

---

`## NAME ROMANIZATIONS`
New rows only. Same 3-column table format — do NOT repeat the header row:
```
| Japanese | English | Role/Notes |
```
One row per new name. Do not include names already in context.md.

---

`## SPEECH PATTERNS`
New characters only. Use the same bullet format as the existing section:
```
- **Name:** Register description. Distinctive features.
```
Do not re-list characters already present.

---

`## RECURRING TERMS`
New rows only. Same 3-column table format — do NOT repeat the header row:
```
| Japanese | English | Notes |
```

---

`## TRANSLATION DECISIONS`
New decisions only. Use the same bullet format as the existing section:
```
- Japanese = "English" (explanation if needed)
```

---

`## SECONDARY CHARACTERS`
New characters only, as bold-name entry lines matching the existing format:
```
**Name** — Role/description. Key facts relevant to translation (speech register, status, relationship to main cast).
```
One line per character. Do not create subsections or headers within this block.
For existing characters, only add a new entry line if there is a genuinely new
fact that affects translation (e.g. a new speech register note, a name change,
a status change that will alter how other characters address them).