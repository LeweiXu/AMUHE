# A Maiden's Unwanted Heroic Epic

Info here: https://www.novelupdates.com/series/a-maidens-unwanted-heroic-epic/

You may find that this novel is already translated here at [inoveltranslations](https://inoveltranslation.com/novels/a8509c16-0da1-4401-a852-14d3995077a9)
but if you just click on any chapter you'll find the worst translation known to man. I'm not sure how they did it, but they manage to misspell the main character's
name in almost every single chapter, and entire passages are completely incomprehensible. The only way such a shoddy translation is possible is if it was completed 
via some form of basic machine translation with no proofreading, but they claim to have a translator and a proofreader on the translation team, so I'm not sure.

This repo contain's a translated version of this masterpiece of a novel that ticks all my boxes using the latest and strongest AI model: Claude Opus 4.6 as well as some manual 
checking of any passages that sound unnatural.

I actually tried doing this in early 2025 using GPT but found that although the translation itself was passable, it often couldn't even fit a single chapter in it's context 
window and often truncated up to half a chapter. It also didn't like what it was translating, often straight up refusing to translate because it was a "content violation". 
Looks like GPT couldn't handle Krische's personality lol.

## Where To Read

The translated chapters are available in the `translated_chapters` directory where you can view directory on github. You will also find a `.epub` file located in the root 
directory that compiles all the chapters in the `translated_chapters` directory for easy download/reading.

## Methodology

Although Opus 4.6 has a 1 million token context window, it could theoretically fit the whole novel in it's memory, but translation quality will probably degrade as it translates further
and further into the novel. Instead of trying to translate the whole novel at once (which would've taken literal hours even if the translation quality was perfect), I opted to translate
chapters in batches of 5 at a time. To maintain accuracy and consistency of romanization and accuracy of translation, I maintain a `knowledge_base.md` that is updated after every batch. 
`knowledge_base.md` contains condensed information about the novel and what happened in previous chapters and is supplied to the AI at every batch. In addition, a `context.md` file is 
provided with additional information such as the task, the goal, and other information.

Using the prompt that can be found in `prompt.md`, I passed in 7 files (`knowledge_base.md` + `context.md` + 5 chapters in txt format) and had Claude Opus 4.6 output 2 files:
1. A `.md` file containing the translation of the 5 chapters
2. A `.md` file containing additions to the knowledge base

Instead of having Opus 4.6 redo the knowledge base from scratch which takes a lot of time, I simple had it generate any additions necessary, then used the `merge.py` script to merge
the information into the existing knowledge base.

## Translation Quality

I can confidently say that the translation quality is at the very least **on par if not better** than your average translator. One thing that LLMs can guarantee is that there will be no
spelling or grammar issues. A model as powerful as Opus 4.6 also won't miss entire passages or truncate the text or try to shorten the text like GPT did back in 2025. The only things that 
it could potentially mess up is missing some specific references/idioms, but that is easy to forgive considering how fast and accurate it is.

## Copyright Stuff

no copyright, do whatever y'all want with this. 