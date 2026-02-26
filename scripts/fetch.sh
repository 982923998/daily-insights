#!/bin/bash
# fetch.sh — Wrapper for opencode daily news fetching
# Usage: ./scripts/fetch.sh [ai|all|test|{domain-id}]
#   ai          — 抓取 AI 新闻（daily-ai-news 技能）
#   all         — 抓取 AI 新闻 + 全部学术领域
#   test        — 写入测试数据
#   {domain-id} — 抓取指定学术领域（如 autism）

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TODAY=$(date +%Y-%m-%d)
AI_DATA_FILE="$PROJECT_DIR/data/${TODAY}-ai.json"
ACADEMIC_SOURCES_DIR="$PROJECT_DIR/.agents/skills/academic-search/sources"
DIGEST_SCRIPT="$PROJECT_DIR/scripts/generate_digest.py"
ENRICH_JOURNAL_SCRIPT="$PROJECT_DIR/scripts/enrich_journal.py"
AUTO_GIT_SYNC="${AUTO_GIT_SYNC:-0}"

mkdir -p "$PROJECT_DIR/data"

MODE="${1:-ai}"
CONFIG_FILE="$PROJECT_DIR/scripts/fetch_config.sh"

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

generate_digest() {
    local file="$1"
    local domain_id="$2"
    local digest_output
    if [ ! -f "$DIGEST_SCRIPT" ]; then
        log "[ERROR] Digest script not found: $DIGEST_SCRIPT"
        return 1
    fi
    if ! digest_output=$(python3 "$DIGEST_SCRIPT" "$file" "$domain_id" 2>&1); then
        log "[ERROR] Failed to generate digest for: $file"
        [ -n "$digest_output" ] && echo "$digest_output"
        return 1
    fi
    [ -n "$digest_output" ] && echo "$digest_output"
    log "[OK] Digest generated: $file"
    return 0
}

enrich_journal() {
    local file="$1"
    local enrich_output
    if [ ! -f "$ENRICH_JOURNAL_SCRIPT" ]; then
        log "[WARN] Journal enrich script not found: $ENRICH_JOURNAL_SCRIPT"
        return 0
    fi
    if ! enrich_output=$(python3 "$ENRICH_JOURNAL_SCRIPT" "$file" 2>&1); then
        log "[ERROR] Failed to enrich journal names for: $file"
        [ -n "$enrich_output" ] && echo "$enrich_output"
        return 1
    fi
    [ -n "$enrich_output" ] && echo "$enrich_output"
    log "[OK] Journal names enriched: $file"
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
        --model "$MODEL_ID" 2>&1

    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log "[ERROR] opencode exited with code $exit_code ($title)"
        return $exit_code
    fi
    return 0
}

git_sync_data() {
    local mode="$1"
    local branch

    if ! command -v git >/dev/null 2>&1; then
        log "[WARN] git not found; skip auto sync."
        return 0
    fi

    if [ "$AUTO_GIT_SYNC" != "1" ]; then
        log "[INFO] AUTO_GIT_SYNC is disabled; skip git push."
        return 0
    fi

    if ! git -C "$PROJECT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        log "[WARN] Not a git repository: $PROJECT_DIR"
        return 0
    fi

    branch=$(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || true)
    if [ -z "$branch" ]; then
        log "[WARN] Cannot detect current git branch; skip sync."
        return 0
    fi

    # Commit only generated data files; avoid accidental code commits.
    git -C "$PROJECT_DIR" add -A -- \
        data \
        >/dev/null 2>&1 || true

    # Need to check both unstaged and staged changes in data/.
    if git -C "$PROJECT_DIR" diff --quiet -- data \
        && git -C "$PROJECT_DIR" diff --cached --quiet -- data; then
        log "[INFO] No data changes to sync."
        return 0
    fi

    if ! git -C "$PROJECT_DIR" commit -m "data: auto-fetch ${mode} ${TODAY}" -- \
        data \
        >/dev/null 2>&1; then
        log "[ERROR] git commit failed; skip push."
        return 1
    fi

    if ! git -C "$PROJECT_DIR" pull --rebase origin "$branch" >/dev/null 2>&1; then
        log "[ERROR] git pull --rebase failed; push skipped."
        return 1
    fi

    if ! git -C "$PROJECT_DIR" push origin "$branch" >/dev/null 2>&1; then
        log "[ERROR] git push failed."
        return 1
    fi

    log "[OK] Data synced to GitHub (branch: $branch)"
    return 0
}

# Extract a single value from YAML frontmatter (between --- markers)
get_fm() {
    local file="$1" key="$2"
    awk -v k="$key" '
        /^---/ { count++; next }
        count == 1 && $0 ~ ("^" k ":") {
            sub(/^[^:]+:[[:space:]]*/, "")
            gsub(/"/, "")
            print
            exit
        }
        count >= 2 { exit }
    ' "$file"
}

# Run a single academic domain by ID
run_academic_domain() {
    local domain_id="$1"
    local config_file="$ACADEMIC_SOURCES_DIR/${domain_id}.md"

    if [ ! -f "$config_file" ]; then
        log "[ERROR] Domain config not found: $config_file"
        return 1
    fi

    local label category data_file prompt
    label=$(get_fm "$config_file" "label")
    category=$(get_fm "$config_file" "category")
    data_file="$PROJECT_DIR/data/${TODAY}-${domain_id}.json"

    log "📚 Academic domain: $domain_id ($label)"
    log "📂 Data file: $data_file"

    prompt="${ACADEMIC_PROMPT_TEMPLATE//__TODAY__/$TODAY}"
    prompt="${prompt//__DOMAIN_ID__/$domain_id}"
    prompt="${prompt//__DOMAIN_LABEL__/$label}"
    prompt="${prompt//__CATEGORY__/$category}"
    prompt="${prompt//__DATA_FILE__/$data_file}"
    prompt="${prompt//__DOMAIN_CONFIG_PATH__/$config_file}"

    run_opencode "Fetch $label" "$prompt" || return $?
    validate_json_file "$data_file" || return $?
    enrich_journal "$data_file" || return $?
    generate_digest "$data_file" "$domain_id" || return $?
}

# Run all academic domains (skip domains with skill: daily-ai-news)
run_all_academic_domains() {
    if [ ! -d "$ACADEMIC_SOURCES_DIR" ]; then
        log "[WARN] Academic sources directory not found: $ACADEMIC_SOURCES_DIR"
        return 0
    fi

    local ran=0
    for config_file in "$ACADEMIC_SOURCES_DIR"/*.md; do
        [ -f "$config_file" ] || continue
        local skill domain_id
        skill=$(get_fm "$config_file" "skill")
        domain_id=$(get_fm "$config_file" "id")
        [ "$skill" = "daily-ai-news" ] && continue
        [ -z "$domain_id" ] && continue
        run_academic_domain "$domain_id" || return $?
        ran=$((ran + 1))
    done

    [ "$ran" -eq 0 ] && log "[WARN] No academic domains found in $ACADEMIC_SOURCES_DIR"
    return 0
}

if [ -z "${AI_PROMPT_TEMPLATE:-}" ] || [ -z "${ACADEMIC_PROMPT_TEMPLATE:-}" ] || [ -z "${TEST_PROMPT_TEMPLATE:-}" ]; then
    echo "[ERROR] Prompt templates are missing in $CONFIG_FILE"
    exit 1
fi

# Render AI prompt
AI_PROMPT="${AI_PROMPT_TEMPLATE//__TODAY__/$TODAY}"
AI_PROMPT="${AI_PROMPT//__DATA_FILE__/$AI_DATA_FILE}"

TEST_PROMPT="${TEST_PROMPT_TEMPLATE//__TODAY__/$TODAY}"
TEST_PROMPT="${TEST_PROMPT//__DATA_FILE__/$AI_DATA_FILE}"

log "🚀 Starting task: $MODE"

cd "$PROJECT_DIR"

case "$MODE" in
    ai)
        log "📂 AI data file: $AI_DATA_FILE"
        run_opencode "Fetch AI News" "$AI_PROMPT" || exit $?
        validate_json_file "$AI_DATA_FILE" || exit $?
        generate_digest "$AI_DATA_FILE" "ai" || exit $?
        ;;
    all)
        log "📂 AI data file: $AI_DATA_FILE"
        run_opencode "Fetch AI News" "$AI_PROMPT" || exit $?
        validate_json_file "$AI_DATA_FILE" || exit $?
        generate_digest "$AI_DATA_FILE" "ai" || exit $?
        run_all_academic_domains || exit $?
        ;;
    test)
        run_opencode "Test Write" "$TEST_PROMPT" || exit $?
        validate_json_file "$AI_DATA_FILE" || exit $?
        generate_digest "$AI_DATA_FILE" "ai" || exit $?
        ;;
    *)
        # Treat all positional args as academic domain IDs
        for domain_id in "$@"; do
            run_academic_domain "$domain_id" || exit $?
        done
        ;;
esac

log "✅ Task finished."
git_sync_data "$MODE" || exit $?
