#!/usr/bin/env bash
# =============================================================================
# translate_batch.sh — Translate all or a range of chapters sequentially
#
# USAGE:
#   ./translate_batch.sh                         # all chapters in raw_chapters/
#   ./translate_batch.sh --from 042 --to 045     # filenames containing these strings
#   ./translate_batch.sh --skip-existing         # skip already-translated chapters
#   ./translate_batch.sh --yes                   # auto-accept all updates
#   ./translate_batch.sh 042 045 047             # specific chapter stems
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()   { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()     { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()   { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
err()    { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="$SCRIPT_DIR/raw_chapters"
OUTPUT_DIR="$SCRIPT_DIR/translated_chapters"
TRANSLATE="$SCRIPT_DIR/translate.sh"

SKIP_EXISTING=false
AUTO_YES=false
FROM_CH=""
TO_CH=""
SPECIFIC=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-existing) SKIP_EXISTING=true; shift ;;
        --yes|-y)        AUTO_YES=true;      shift ;;
        --from)          FROM_CH="$2";       shift 2 ;;
        --to)            TO_CH="$2";         shift 2 ;;
        --help|-h)
            sed -n '3,9p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) SPECIFIC+=("$1"); shift ;;
    esac
done

[[ ! -d "$RAW_DIR"   ]] && { err "raw_chapters/ not found at $RAW_DIR"; exit 1; }
[[ ! -f "$TRANSLATE" ]] && { err "translate.sh not found at $TRANSLATE"; exit 1; }
chmod +x "$TRANSLATE"
mkdir -p "$OUTPUT_DIR"

# ── Build chapter list ────────────────────────────────────────────────────────
if [[ ${#SPECIFIC[@]} -gt 0 ]]; then
    CHAPTER_FILES=()
    for stem in "${SPECIFIC[@]}"; do
        mapfile -t matches < <(find "$RAW_DIR" -maxdepth 1 -name "*${stem}*.txt" | sort -V)
        if [[ ${#matches[@]} -gt 0 ]]; then
            CHAPTER_FILES+=("${matches[@]}")
        else
            warn "No file matching '${stem}' in raw_chapters/ — skipping"
        fi
    done
else
    mapfile -t CHAPTER_FILES < <(find "$RAW_DIR" -maxdepth 1 -name "*.txt" | sort -V)
fi

# Apply --from / --to filters
if [[ -n "$FROM_CH" || -n "$TO_CH" ]]; then
    FILTERED=()
    IN_RANGE=false
    [[ -z "$FROM_CH" ]] && IN_RANGE=true
    for f in "${CHAPTER_FILES[@]}"; do
        base="$(basename "$f")"
        [[ -n "$FROM_CH" && "$base" == *"$FROM_CH"* ]] && IN_RANGE=true
        $IN_RANGE && FILTERED+=("$f")
        [[ -n "$TO_CH"   && "$base" == *"$TO_CH"*   ]] && IN_RANGE=false
    done
    CHAPTER_FILES=("${FILTERED[@]}")
fi

if [[ ${#CHAPTER_FILES[@]} -eq 0 ]]; then
    err "No chapter files found to process."
    exit 1
fi

# ── Show plan ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Batch Translation Plan${RESET}"
echo "────────────────────────────────────────"
for f in "${CHAPTER_FILES[@]}"; do
    base="$(basename "$f" .txt)"
    out="$OUTPUT_DIR/${base}.txt"
    if [[ -f "$out" ]]; then
        echo -e "  $base  ${YELLOW}(already translated)${RESET}"
    else
        echo "  $base"
    fi
done
echo ""
read -rp "Proceed? [y/N] " go
[[ "$go" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }

# ── Process chapters ──────────────────────────────────────────────────────────
DONE=0; SKIPPED=0; FAILED=0
FAILED_LIST=()

for CHAPTER_FILE in "${CHAPTER_FILES[@]}"; do
    base="$(basename "$CHAPTER_FILE" .txt)"
    out="$OUTPUT_DIR/${base}.txt"

    echo ""
    echo -e "${BOLD}━━━ $base ━━━${RESET}"

    if [[ -f "$out" && "$SKIP_EXISTING" == true ]]; then
        warn "Already translated, skipping."
        (( SKIPPED++ )) || true
        continue
    fi

    ARGS=("$CHAPTER_FILE")
    [[ "$AUTO_YES" == true ]] && ARGS+=("--yes")

    if bash "$TRANSLATE" "${ARGS[@]}"; then
        ok "Done: $base"
        (( DONE++ )) || true
    else
        err "FAILED: $base"
        (( FAILED++ )) || true
        FAILED_LIST+=("$base")
        echo ""
        read -rp "Continue with remaining chapters? [y/N] " cont
        [[ "$cont" =~ ^[Yy]$ ]] || { info "Batch stopped."; break; }
    fi

    info "Progress: ${DONE} done, ${SKIPPED} skipped, ${FAILED} failed"
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo -e "${BOLD}Batch Complete${RESET}"
echo "────────────────────────────────────────"
ok  "Translated: $DONE"
[[ $SKIPPED -gt 0 ]] && warn "Skipped:    $SKIPPED"
[[ $FAILED  -gt 0 ]] && err  "Failed:     $FAILED"
if [[ ${#FAILED_LIST[@]} -gt 0 ]]; then
    echo ""
    err "Failed chapters:"
    for ch in "${FAILED_LIST[@]}"; do echo "    - $ch"; done
fi
echo "════════════════════════════════════════"
echo ""
