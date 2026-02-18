#!/bin/bash
# fetch.sh — Wrapper for opencode daily news fetching
# Usage: ./scripts/fetch.sh [ai|autism|all|test]

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TODAY=$(date +%Y-%m-%d)
AI_DATA_FILE="$PROJECT_DIR/data/${TODAY}-ai.json"
AUTISM_DATA_FILE="$PROJECT_DIR/data/${TODAY}-autism.json"

mkdir -p "$PROJECT_DIR/data"

MODE="${1:-ai}"
CONFIG_FILE="$PROJECT_DIR/scripts/fetch_config.sh"

# 强制 Python 无缓冲输出，确保日志实时
export PYTHONUNBUFFERED=1

if [ ! -f "$CONFIG_FILE" ]; then
    echo "[ERROR] Missing config file: $CONFIG_FILE"
    exit 1
fi

# shellcheck source=/dev/null
source "$CONFIG_FILE"

if [ -z "${MODEL_ID:-}" ]; then
    echo "[ERROR] MODEL_ID is empty in $CONFIG_FILE"
    exit 1
fi

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

validate_json_file() {
    local file="$1"
    if [ ! -f "$file" ]; then
        log "[ERROR] Data file was not created: $file"
        return 1
    fi

    if ! python3 -m json.tool "$file" >/dev/null 2>&1; then
        log "[ERROR] Data file is not valid JSON: $file"
        return 1
    fi

    log "[OK] Data file validated: $file"
    return 0
}


run_opencode() {
    local title="$1"
    local prompt="$2"

    log "⚡ [$title] model: $MODEL_ID"
    log "──── PROMPT ────────────────────────"
    while IFS= read -r line; do
        [ -n "$line" ] && echo "  $line"
    done <<< "$prompt"
    log "────────────────────────────────────"

    opencode run "$prompt" \
        --title "$title" \
        --model "$MODEL_ID" \
        --print-logs 2>&1

    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log "[ERROR] opencode exited with code $exit_code ($title)"
        return $exit_code
    fi

    return 0
}

if [ -z "${AI_PROMPT_TEMPLATE:-}" ] || [ -z "${AUTISM_PROMPT_TEMPLATE:-}" ] || [ -z "${TEST_PROMPT_TEMPLATE:-}" ]; then
    echo "[ERROR] Prompt templates are missing in $CONFIG_FILE"
    exit 1
fi

# 从配置模板渲染提示词
AI_PROMPT="${AI_PROMPT_TEMPLATE//__TODAY__/$TODAY}"
AI_PROMPT="${AI_PROMPT//__DATA_FILE__/$AI_DATA_FILE}"

AUTISM_PROMPT="${AUTISM_PROMPT_TEMPLATE//__TODAY__/$TODAY}"
AUTISM_PROMPT="${AUTISM_PROMPT//__DATA_FILE__/$AUTISM_DATA_FILE}"

TEST_PROMPT="${TEST_PROMPT_TEMPLATE//__TODAY__/$TODAY}"
TEST_PROMPT="${TEST_PROMPT//__DATA_FILE__/$AI_DATA_FILE}"

log "🚀 Starting task: $MODE"
log "📂 AI data file: $AI_DATA_FILE"
log "📂 Autism data file: $AUTISM_DATA_FILE"

cd "$PROJECT_DIR"

case "$MODE" in
    ai)
        run_opencode "Fetch AI News" "$AI_PROMPT" || exit $?
        validate_json_file "$AI_DATA_FILE" || exit $?
        ;;
    autism)
        run_opencode "Fetch Autism News" "$AUTISM_PROMPT" || exit $?
        validate_json_file "$AUTISM_DATA_FILE" || exit $?
        ;;
    all)
        run_opencode "Fetch AI News" "$AI_PROMPT" || exit $?
        validate_json_file "$AI_DATA_FILE" || exit $?

        run_opencode "Fetch Autism News" "$AUTISM_PROMPT" || exit $?
        validate_json_file "$AUTISM_DATA_FILE" || exit $?
        ;;
    test)
        run_opencode "Test Write" "$TEST_PROMPT" || exit $?
        validate_json_file "$AI_DATA_FILE" || exit $?
        ;;
    *)
        echo "Usage: $0 {ai|autism|all|test}"
        exit 1
        ;;
esac

log "✅ Task finished."
