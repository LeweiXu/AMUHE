#!/usr/bin/env bash
# =============================================================================
# translate_batch.sh — Translate all or a range of chapters sequentially
#
# USAGE:
#   ./translate_batch.sh                        # translate all in raw_chapters/
#   ./translate_batch.sh c42 c43 c44            # specific chapters by name
#   ./translate_batch.sh --from c42             # from chapter onwards
#   ./translate_batch.sh --from c42 --to c45    # inclusive range
#   ./translate_batch.sh --skip-existing        # skip already-translated chapters
#   ./translate_batch.sh --no-confirm           # auto-accept all updates (caution)
#
# Each chapter is translated one at a time. context.md and knowledge_base.md
# are updated between chapters so each translation benefits from the last.
# =============================================================================

set -euo pipefail

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="$SCRIPT_DIR/raw_chapters"
OUTPUT_DIR="$SCRIPT_DIR/translated_chapters"
TRANSLATE_SCRIPT="$SCRIPT_DIR/translate.sh"

SKIP_EXISTING=false
NO_CONFIRM=false
FROM_CHAPTER=""
TO_CHAPTER=""
SPECIFIC_CHAPTERS=()

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-existing) SKIP_EXISTING=true; shift ;;
        --no-confirm)    NO_CONFIRM=true;    shift ;;
        --from)          FROM_CHAPTER="$2";  shift 2 ;;
        --to)            TO_CHAPTER="$2";    shift 2 ;;
        --help|-h)
            sed -n '2,15p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) SPECIFIC_CHAPTERS+=("$1"); shift ;;
    esac
done

# ── Validation ────────────────────────────────────────────────────────────────
[[ ! -d "$RAW_DIR" ]]         && { error "raw_chapters/ not found at $RAW_DIR"; exit 1; }
[[ ! -f "$TRANSLATE_SCRIPT" ]] && { error "translate.sh not found at $TRANSLATE_SCRIPT"; exit 1; }
chmod +x "$TRANSLATE_SCRIPT"
mkdir -p "$OUTPUT_DIR"

# ── Build chapter list ────────────────────────────────────────────────────────
if [[ ${#SPECIFIC_CHAPTERS[@]} -gt 0 ]]; then
    # Specific chapters named on command line
    CHAPTER_FILES=()
    for ch in "${SPECIFIC_CHAPTERS[@]}"; do
        f="$RAW_DIR/${ch}.txt"
        [[ ! -f "$f" ]] && f="$RAW_DIR/${ch}"   # allow with or without .txt
        if [[ -f "$f" ]]; then
            CHAPTER_FILES+=("$f")
        else
            warn "Not found, skipping: $ch"
        fi
    done
else
    # All .txt files in raw_chapters/, sorted naturally
    mapfile -t CHAPTER_FILES < <(find "$RAW_DIR" -maxdepth 1 -name "*.txt" | sort -V)
fi

# Apply --from / --to filters
if [[ -n "$FROM_CHAPTER" || -n "$TO_CHAPTER" ]]; then
    FILTERED=()
    IN_RANGE=false
    [[ -z "$FROM_CHAPTER" ]] && IN_RANGE=true   # no --from means start from beginning
    for f in "${CHAPTER_FILES[@]}"; do
        base="$(basename "$f" .txt)"
        [[ "$base" == "$FROM_CHAPTER" ]] && IN_RANGE=true
        $IN_RANGE && FILTERED+=("$f")
        [[ -n "$TO_CHAPTER" && "$base" == "$TO_CHAPTER" ]] && IN_RANGE=false
    done
    CHAPTER_FILES=("${FILTERED[@]}")
fi

if [[ ${#CHAPTER_FILES[@]} -eq 0 ]]; then
    error "No chapter files found to process."
    exit 1
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Batch Translation${RESET}"
echo "────────────────────────────────────────"
info "Chapters to process: ${#CHAPTER_FILES[@]}"
for f in "${CHAPTER_FILES[@]}"; do
    base="$(basename "$f" .txt)"
    out="$OUTPUT_DIR/${base}.txt"
    if [[ -f "$out" ]]; then
        echo "    $base  ${YELLOW}(already translated)${RESET}"
    else
        echo "    $base"
    fi
done
echo ""

read -rp "Proceed? [y/N] " go
[[ "$go" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }
echo ""

# ── Process each chapter ──────────────────────────────────────────────────────
DONE=0
SKIPPED=0
FAILED=0
FAILED_LIST=()

for CHAPTER_FILE in "${CHAPTER_FILES[@]}"; do
    base="$(basename "$CHAPTER_FILE" .txt)"
    out="$OUTPUT_DIR/${base}.txt"

    echo ""
    echo -e "${BOLD}━━━ Chapter: $base ━━━${RESET}"

    # Skip if exists and --skip-existing
    if [[ -f "$out" && "$SKIP_EXISTING" == true ]]; then
        warn "Already translated, skipping: $base"
        ((SKIPPED++)) || true
        continue
    fi

    # Build translate.sh arguments
    ARGS=("$CHAPTER_FILE")
    if [[ "$NO_CONFIRM" == true ]]; then
        # In no-confirm mode we pipe 'y\ny\ny\n' to auto-accept everything
        # We wrap translate.sh so stdin gets the confirmations
        if printf 'y\ny\ny\n' | bash "$TRANSLATE_SCRIPT" "${ARGS[@]}"; then
            success "Chapter $base done."
            ((DONE++)) || true
        else
            error "Chapter $base FAILED."
            ((FAILED++)) || true
            FAILED_LIST+=("$base")
        fi
    else
        if bash "$TRANSLATE_SCRIPT" "${ARGS[@]}"; then
            success "Chapter $base done."
            ((DONE++)) || true
        else
            error "Chapter $base FAILED."
            ((FAILED++)) || true
            FAILED_LIST+=("$base")
            echo ""
            read -rp "Continue with remaining chapters? [y/N] " cont
            [[ "$cont" =~ ^[Yy]$ ]] || { info "Batch aborted by user."; break; }
        fi
    fi

    echo ""
    info "Progress: ${DONE} translated, ${SKIPPED} skipped, ${FAILED} failed"
done

# ── Final summary ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo -e "${BOLD}Batch Complete${RESET}"
echo "────────────────────────────────────────"
success "Translated:  $DONE"
[[ $SKIPPED -gt 0 ]] && warn    "Skipped:     $SKIPPED"
[[ $FAILED  -gt 0 ]] && error   "Failed:      $FAILED"
if [[ ${#FAILED_LIST[@]} -gt 0 ]]; then
    echo ""
    error "Failed chapters:"
    for ch in "${FAILED_LIST[@]}"; do
        echo "    - $ch"
    done
fi
echo "════════════════════════════════════════"
echo ""
