#!/usr/bin/env bash
# =============================================================================
# translate.sh — Translate a chapter of 少女の望まぬ英雄譚 using Claude Code
#
# USAGE:
#   ./translate.sh <chapter_file>
#   ./translate.sh raw_chapters/c42.txt
#   ./translate.sh raw_chapters/c42.txt --dry-run    # print prompt only, no API call
#
# REQUIREMENTS:
#   - Claude Code CLI installed and authenticated (claude command available)
#   - Directory structure:
#       ./raw_chapters/       — source Japanese .txt files
#       ./translated_chapters/ — output directory (created if missing)
#       ./context.md          — translation rules and quick reference
#       ./knowledge_base.md   — full lore/character reference
#
# OUTPUT:
#   - translated_chapters/<chapter_name>.txt   — translated chapter
#   - context.md and knowledge_base.md updated in-place if new information found
# =============================================================================

set -euo pipefail

# ── Colour helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

# ── Argument parsing ─────────────────────────────────────────────────────────
DRY_RUN=false
CHAPTER_FILE=""

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --help|-h)
            sed -n '2,20p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) CHAPTER_FILE="$arg" ;;
    esac
done

if [[ -z "$CHAPTER_FILE" ]]; then
    error "No chapter file specified."
    echo "Usage: $0 <chapter_file> [--dry-run]"
    exit 1
fi

# ── Path setup ───────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT_FILE="$SCRIPT_DIR/context.md"
KB_FILE="$SCRIPT_DIR/knowledge_base.md"
OUTPUT_DIR="$SCRIPT_DIR/translated_chapters"

# Resolve chapter file path
if [[ ! -f "$CHAPTER_FILE" ]]; then
    # Try relative to script dir
    if [[ -f "$SCRIPT_DIR/$CHAPTER_FILE" ]]; then
        CHAPTER_FILE="$SCRIPT_DIR/$CHAPTER_FILE"
    else
        error "Chapter file not found: $CHAPTER_FILE"
        exit 1
    fi
fi

CHAPTER_BASENAME="$(basename "$CHAPTER_FILE" .txt)"
OUTPUT_FILE="$OUTPUT_DIR/${CHAPTER_BASENAME}.txt"

# ── Pre-flight checks ─────────────────────────────────────────────────────────
info "Pre-flight checks..."

if [[ ! -f "$CONTEXT_FILE" ]]; then
    error "context.md not found at: $CONTEXT_FILE"
    exit 1
fi

if [[ ! -f "$KB_FILE" ]]; then
    error "knowledge_base.md not found at: $KB_FILE"
    exit 1
fi

if ! command -v claude &>/dev/null; then
    error "'claude' command not found. Is Claude Code installed and in your PATH?"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

if [[ -f "$OUTPUT_FILE" ]]; then
    warn "Output file already exists: $OUTPUT_FILE"
    read -rp "Overwrite? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }
fi

success "All checks passed."
info "Chapter:    $CHAPTER_FILE"
info "Output:     $OUTPUT_FILE"
echo ""

# ── Build the prompt ──────────────────────────────────────────────────────────
# We pass everything inline so Claude has full context in one shot.

CHAPTER_TEXT="$(cat "$CHAPTER_FILE")"
CONTEXT_TEXT="$(cat "$CONTEXT_FILE")"
KB_TEXT="$(cat "$KB_FILE")"

read -r -d '' PROMPT << 'PROMPT_EOF'
You are a professional Japanese-to-English literary translator specialising in web novels.

You have been given three inputs:
1. CONTEXT — translation rules, character speech patterns, established name romanizations, and tone guide
2. KNOWLEDGE BASE — full lore, character details, world-building, and chapter timeline
3. CHAPTER — the raw Japanese source text to translate

Your job is to produce THREE outputs, each clearly delimited:

═══════════════════════════════════════
OUTPUT 1: TRANSLATION
═══════════════════════════════════════
Translate the chapter completely. Rules:
- Follow every instruction in CONTEXT exactly
- Krische always refers to herself in third person ("Krische" not "I/me")
- Preserve all "……" ellipses exactly as written
- Keep "Ehehe" as-is
- Keep "the floofy thing"/"floof" for Krische's casual mana references
- Keep Japanese honorifics (kaa-sama, ojou-sama, onee-sama, etc.)
- Translate scene breaks (※ or ＊＊＊) as:   * * *
- Do NOT add drama or emotion that is not in the source text
- Translate author/translator notes if present, marking them (T/N: ...)
- Preserve paragraph spacing

═══════════════════════════════════════
OUTPUT 2: CONTEXT_UPDATES
═══════════════════════════════════════
List ONLY genuine new information from this chapter that should be added to context.md.
This means: new characters with distinct speech patterns, new recurring expressions,
new translation decisions made in this chapter, corrections to existing entries.
Format as a markdown patch — show the section heading and the new/changed lines only.
If there is nothing new to add, write: NONE

═══════════════════════════════════════
OUTPUT 3: KNOWLEDGE_BASE_UPDATES
═══════════════════════════════════════
List ONLY genuine new information from this chapter that should be added to knowledge_base.md.
This means: new named characters, new place names, new events in the timeline,
new world-building details, new political developments, new relationships revealed.
Format as a markdown patch — show the section heading and the new/changed lines only.
If there is nothing new to add, write: NONE

PROMPT_EOF

FULL_PROMPT="${PROMPT}

---
## CONTEXT
${CONTEXT_TEXT}

---
## KNOWLEDGE BASE
${KB_TEXT}

---
## CHAPTER SOURCE TEXT
${CHAPTER_TEXT}"

# ── Dry run mode ──────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN — printing prompt only, not calling Claude."
    echo ""
    echo "════════════════════════════════════════"
    echo "$FULL_PROMPT"
    echo "════════════════════════════════════════"
    echo ""
    info "Prompt length: $(echo "$FULL_PROMPT" | wc -c) characters"
    exit 0
fi

# ── Call Claude ───────────────────────────────────────────────────────────────
info "Calling Claude... (this may take a minute)"
echo ""

# Use claude -p (print mode) to get a single non-interactive response
RESPONSE="$(echo "$FULL_PROMPT" | claude -p --dangerously-skip-permissions 2>&1)"

if [[ $? -ne 0 ]]; then
    error "Claude returned a non-zero exit code."
    error "Response was:"
    echo "$RESPONSE"
    exit 1
fi

# ── Parse the three output blocks ─────────────────────────────────────────────
# Extract content between delimiters using awk

extract_block() {
    local label="$1"
    local text="$2"
    # Match from "OUTPUT N: LABEL" line to the next "OUTPUT" delimiter or end of string
    echo "$text" | awk -v lbl="$label" '
        /^OUTPUT [0-9]+: / { in_block = ($0 ~ lbl); next }
        in_block && /^═+$/ { in_block = 0; next }
        in_block { print }
    ' | sed '/^[[:space:]]*$/{ /./!d }' | sed '1{/^[[:space:]]*$/d}'
}

TRANSLATION="$(extract_block "TRANSLATION" "$RESPONSE")"
CTX_UPDATES="$(extract_block "CONTEXT_UPDATES" "$RESPONSE")"
KB_UPDATES="$(extract_block "KNOWLEDGE_BASE_UPDATES" "$RESPONSE")"

# Fallback: if delimiter parsing failed, dump full response to output
if [[ -z "$TRANSLATION" ]]; then
    warn "Could not parse structured output. Saving raw response as translation."
    TRANSLATION="$RESPONSE"
    CTX_UPDATES="NONE"
    KB_UPDATES="NONE"
fi

# ── Write translation ─────────────────────────────────────────────────────────
echo "$TRANSLATION" > "$OUTPUT_FILE"
success "Translation saved: $OUTPUT_FILE"

# ── Apply context updates ─────────────────────────────────────────────────────
if [[ "$CTX_UPDATES" == "NONE" || -z "$(echo "$CTX_UPDATES" | tr -d '[:space:]')" ]]; then
    info "No context.md updates needed."
else
    echo ""
    echo -e "${BOLD}═══ PROPOSED context.md UPDATES ═══${RESET}"
    echo "$CTX_UPDATES"
    echo -e "${BOLD}════════════════════════════════════${RESET}"
    echo ""
    read -rp "Apply these updates to context.md? [y/N] " confirm_ctx
    if [[ "$confirm_ctx" =~ ^[Yy]$ ]]; then
        # Back up first
        cp "$CONTEXT_FILE" "${CONTEXT_FILE}.bak"
        # Append a chapter-stamped update block
        {
            echo ""
            echo "---"
            echo "## Updates from ${CHAPTER_BASENAME}"
            echo ""
            echo "$CTX_UPDATES"
        } >> "$CONTEXT_FILE"
        success "context.md updated (backup: context.md.bak)"
    else
        info "context.md unchanged."
        # Save the proposed updates to a sidecar file so they aren't lost
        SIDECAR="${SCRIPT_DIR}/updates/${CHAPTER_BASENAME}_context_update.md"
        mkdir -p "${SCRIPT_DIR}/updates"
        echo "$CTX_UPDATES" > "$SIDECAR"
        info "Proposed updates saved to: $SIDECAR"
    fi
fi

# ── Apply knowledge base updates ─────────────────────────────────────────────
if [[ "$KB_UPDATES" == "NONE" || -z "$(echo "$KB_UPDATES" | tr -d '[:space:]')" ]]; then
    info "No knowledge_base.md updates needed."
else
    echo ""
    echo -e "${BOLD}═══ PROPOSED knowledge_base.md UPDATES ═══${RESET}"
    echo "$KB_UPDATES"
    echo -e "${BOLD}══════════════════════════════════════════${RESET}"
    echo ""
    read -rp "Apply these updates to knowledge_base.md? [y/N] " confirm_kb
    if [[ "$confirm_kb" =~ ^[Yy]$ ]]; then
        cp "$KB_FILE" "${KB_FILE}.bak"
        {
            echo ""
            echo "---"
            echo "## Updates from ${CHAPTER_BASENAME}"
            echo ""
            echo "$KB_UPDATES"
        } >> "$KB_FILE"
        success "knowledge_base.md updated (backup: knowledge_base.md.bak)"
    else
        info "knowledge_base.md unchanged."
        SIDECAR="${SCRIPT_DIR}/updates/${CHAPTER_BASENAME}_kb_update.md"
        mkdir -p "${SCRIPT_DIR}/updates"
        echo "$KB_UPDATES" > "$SIDECAR"
        info "Proposed updates saved to: $SIDECAR"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
success "Done. Chapter ${CHAPTER_BASENAME} complete."
echo ""
echo "  Translation:  $OUTPUT_FILE"
echo "  Context:      $CONTEXT_FILE"
echo "  Knowledge:    $KB_FILE"
echo ""
