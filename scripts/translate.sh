#!/usr/bin/env bash
# =============================================================================
# translate.sh — Translate a chapter using Claude Code's headless mode
#
# USAGE:
#   ./translate.sh raw_chapters/042_厨房の聖戦.txt
#   ./translate.sh raw_chapters/042_厨房の聖戦.txt --dry-run
#   ./translate.sh raw_chapters/042_厨房の聖戦.txt --yes
#
# REQUIREMENTS:
#   - Claude Code installed:  npm install -g @anthropic-ai/claude-code
#   - Logged in:              claude login
#
# HOW IT WORKS:
#   The translation rules + knowledge base are loaded via --system-prompt-file
#   (bypasses the known Claude CLI bug with large stdin input).
#   The chapter text is passed as the -p prompt argument.
#   Claude is told to write its output directly to files, which we then read.
# =============================================================================

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()   { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()     { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()   { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
err()    { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
header() { echo -e "\n${BOLD}$*${RESET}"; }

# ── Arguments ─────────────────────────────────────────────────────────────────
DRY_RUN=false
AUTO_YES=false
CHAPTER_FILE=""

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --yes|-y)  AUTO_YES=true ;;
        --help|-h)
            echo "Usage: $0 <chapter_file> [--dry-run] [--yes]"
            echo "  --dry-run  Show the system prompt and task prompt without calling Claude"
            echo "  --yes      Auto-accept all proposed updates to context.md / knowledge_base.md"
            exit 0 ;;
        *)  CHAPTER_FILE="$arg" ;;
    esac
done

if [[ -z "$CHAPTER_FILE" ]]; then
    err "No chapter file specified."
    echo "Usage: $0 <chapter_file> [--dry-run] [--yes]"
    exit 1
fi

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT_FILE="$SCRIPT_DIR/context.md"
KB_FILE="$SCRIPT_DIR/knowledge_base.md"
OUTPUT_DIR="$SCRIPT_DIR/translated_chapters"
UPDATES_DIR="$SCRIPT_DIR/updates"
TMP_DIR="$SCRIPT_DIR/.tmp_translate"

[[ "$CHAPTER_FILE" != /* ]] && CHAPTER_FILE="$(pwd)/$CHAPTER_FILE"
CHAPTER_FILE="$(realpath "$CHAPTER_FILE")"
CHAPTER_STEM="$(basename "$CHAPTER_FILE" .txt)"
OUTPUT_FILE="$OUTPUT_DIR/${CHAPTER_STEM}.txt"

# ── Pre-flight ────────────────────────────────────────────────────────────────
info "Pre-flight checks..."

[[ ! -f "$CHAPTER_FILE" ]] && { err "Chapter not found: $CHAPTER_FILE"; exit 1; }
[[ ! -f "$CONTEXT_FILE" ]] && { err "context.md not found"; exit 1; }
[[ ! -f "$KB_FILE"      ]] && { err "knowledge_base.md not found"; exit 1; }

if ! command -v claude &>/dev/null; then
    err "'claude' command not found."
    err "Install: npm install -g @anthropic-ai/claude-code"
    err "Login:   claude login"
    exit 1
fi

mkdir -p "$OUTPUT_DIR" "$UPDATES_DIR" "$TMP_DIR"

if [[ -f "$OUTPUT_FILE" && "$AUTO_YES" == false ]]; then
    warn "Output already exists: $OUTPUT_FILE"
    read -rp "Overwrite? [y/N] " c
    [[ "$c" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }
fi

ok "All checks passed."
info "Chapter:  $CHAPTER_STEM"
info "Output:   $OUTPUT_FILE"

# ── Build system prompt file ───────────────────────────────────────────────────
# This goes in --system-prompt-file, bypassing the stdin size bug.
# It contains: role + translation rules + knowledge base.
SYS_PROMPT_FILE="$TMP_DIR/sysprompt_${CHAPTER_STEM}.txt"

# Paths where Claude will write its output (inside the project dir)
TRANSLATION_OUT="$TMP_DIR/translation_${CHAPTER_STEM}.txt"
CTX_UPDATE_OUT="$TMP_DIR/ctx_update_${CHAPTER_STEM}.txt"
KB_UPDATE_OUT="$TMP_DIR/kb_update_${CHAPTER_STEM}.txt"

# Clean up any leftover output files from a previous run
rm -f "$TRANSLATION_OUT" "$CTX_UPDATE_OUT" "$KB_UPDATE_OUT"

cat > "$SYS_PROMPT_FILE" << SYSEOF
You are a professional Japanese-to-English literary translator specialising in web novels.
You are meticulous, consistent, and faithful to the source text's tone.
You never add emotion or drama that is not present in the original.

== TRANSLATION RULES (from context.md) ==

$(cat "$CONTEXT_FILE")

== LORE AND CHARACTER REFERENCE (from knowledge_base.md) ==

$(cat "$KB_FILE")

== OUTPUT INSTRUCTIONS ==

You must write your output to three files using the Write tool. Do not print the translation
to the terminal — write it to the files below.

1. Write the full English translation to:
   ${TRANSLATION_OUT}

2. Write proposed additions to context.md to:
   ${CTX_UPDATE_OUT}
   - Include ONLY genuinely new info: new speech patterns, new expressions, new translation
     decisions, corrections to existing entries.
   - Format as a markdown patch (section heading + new/changed lines only).
   - If nothing new, write the single word: NONE

3. Write proposed additions to knowledge_base.md to:
   ${KB_UPDATE_OUT}
   - Include ONLY genuinely new info: new characters, places, timeline events,
     world-building, political developments, relationships revealed.
   - Format as a markdown patch (section heading + new/changed lines only).
   - If nothing new, write the single word: NONE

Translation rules reminder:
- Krische always refers to herself in third person ("Krische", never "I" or "me")
- Preserve all "……" ellipses exactly as written
- Keep "Ehehe" as-is
- Use "the floofy thing" / "floof" for Krische's casual mana references
- Keep honorifics: kaa-sama, tou-sama, ojii-sama, ojou-sama, onee-sama, oba-san
- Translate scene breaks (※ or ＊＊＊) as:   * * *
- Do NOT add drama or emotion not present in the source
- Preserve paragraph spacing and chapter structure exactly
- Mark any author/translator notes as (T/N: ...)
SYSEOF

info "System prompt: $(wc -c < "$SYS_PROMPT_FILE") bytes"

# ── Build the task prompt (passed as -p argument) ─────────────────────────────
# This is intentionally short — just the chapter text.
# Keeping -p small avoids the CLI large-input bug.
CHAPTER_TEXT="$(cat "$CHAPTER_FILE")"
TASK_PROMPT="Translate the following Japanese web novel chapter according to your system prompt instructions. Write the outputs to the three files specified.

== CHAPTER SOURCE TEXT ==

${CHAPTER_TEXT}"

info "Chapter text: $(wc -c < "$CHAPTER_FILE") bytes"

# ── Dry run ────────────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == true ]]; then
    warn "DRY RUN — not calling Claude."
    echo ""
    header "── System prompt (first 60 lines) ──"
    head -60 "$SYS_PROMPT_FILE"
    echo "..."
    header "── Task prompt (first 20 lines) ──"
    echo "$TASK_PROMPT" | head -20
    echo "..."
    echo ""
    info "Full system prompt: $SYS_PROMPT_FILE"
    info "Output files would be written to: $TMP_DIR/"
    exit 0
fi

# ── Call Claude ────────────────────────────────────────────────────────────────
info "Calling Claude... (this will take a few minutes)"
echo ""

# Use --system-prompt-file to load context (avoids large stdin bug)
# Use -p for the task prompt (chapter text)
# Allow only the Write tool — Claude only needs to write the three output files
# --dangerously-skip-permissions required for non-interactive mode
CLAUDE_LOG="$TMP_DIR/claude_log_${CHAPTER_STEM}.txt"

if ! claude -p "$TASK_PROMPT" \
        --system-prompt-file "$SYS_PROMPT_FILE" \
        --allowedTools "Write" \
        --dangerously-skip-permissions \
        --output-format text \
        2>&1 | tee "$CLAUDE_LOG"; then
    err "Claude exited with an error. See log: $CLAUDE_LOG"
    exit 1
fi

echo ""

# ── Verify output files were written ──────────────────────────────────────────
if [[ ! -s "$TRANSLATION_OUT" ]]; then
    err "Claude did not write the translation file: $TRANSLATION_OUT"
    err "Claude's output was:"
    cat "$CLAUDE_LOG"
    exit 1
fi

ok "Translation file written ($(wc -c < "$TRANSLATION_OUT") bytes)"

# ── Copy translation to output directory ──────────────────────────────────────
cp "$TRANSLATION_OUT" "$OUTPUT_FILE"
ok "Translation saved: $OUTPUT_FILE"

# ── Helper: review and apply an update ────────────────────────────────────────
apply_update() {
    local label="$1"
    local target="$2"
    local update_file="$3"
    local tag="$4"

    if [[ ! -f "$update_file" ]]; then
        info "No $label update file found — skipping."
        return
    fi

    local content
    content="$(cat "$update_file")"
    local trimmed
    trimmed="$(echo "$content" | tr -d '[:space:]')"

    if [[ -z "$trimmed" || "${trimmed^^}" == "NONE" ]]; then
        info "No $label updates needed."
        return
    fi

    echo ""
    header "═══ PROPOSED ${label} UPDATES ═══"
    cat "$update_file"
    header "═════════════════════════════════════════"
    echo ""

    local do_apply=false
    if [[ "$AUTO_YES" == true ]]; then
        info "Auto-accepting $label updates."
        do_apply=true
    else
        read -rp "Apply these updates to $label? [y/N] " c
        [[ "$c" =~ ^[Yy]$ ]] && do_apply=true
    fi

    if [[ "$do_apply" == true ]]; then
        cp "$target" "${target}.bak"
        {
            printf '\n\n---\n## Updates from %s (%s)\n\n' \
                "$CHAPTER_STEM" "$(date +%Y-%m-%d)"
            cat "$update_file"
        } >> "$target"
        ok "$label updated  (backup: $(basename "$target").bak)"
    else
        local sidecar="$UPDATES_DIR/${CHAPTER_STEM}_${tag}_update.md"
        cp "$update_file" "$sidecar"
        info "Proposal saved: $sidecar"
    fi
}

apply_update "context.md"        "$CONTEXT_FILE" "$CTX_UPDATE_OUT" "context"
apply_update "knowledge_base.md" "$KB_FILE"      "$KB_UPDATE_OUT"  "kb"

# ── Cleanup temp files ─────────────────────────────────────────────────────────
rm -f "$SYS_PROMPT_FILE" "$TRANSLATION_OUT" "$CTX_UPDATE_OUT" "$KB_UPDATE_OUT" "$CLAUDE_LOG"

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
ok "Chapter '${CHAPTER_STEM}' complete."
echo ""
echo "  Translation:    $OUTPUT_FILE"
echo "  Context:        $CONTEXT_FILE"
echo "  Knowledge base: $KB_FILE"
echo ""
