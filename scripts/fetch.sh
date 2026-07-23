#!/bin/bash
# fetch.sh — Wrapper for codex daily literature fetching
# Usage: ./scripts/fetch.sh [brainmri|all|if|test|{domain-id}]
#   brainmri    — 抓取 Brain MRI，并分流到疾病领域
#   all         — 同 brainmri
#   if          — 仅同步期刊 IF（不抓论文/新闻）
#   test        — 写入测试数据并分流
#   {domain-id} — 指定学术领域；疾病领域会映射到 brainmri 分流

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TODAY=$(date +%Y-%m-%d)
ACADEMIC_SOURCES_DIR="$PROJECT_DIR/.agents/skills/academic-search/sources"
DIGEST_SCRIPT="$PROJECT_DIR/scripts/generate_digest.py"
SYNC_IF_SCRIPT="$PROJECT_DIR/scripts/sync_impact_factors.py"
FILTER_IF_SCRIPT="$PROJECT_DIR/scripts/filter_impact_factor.py"
VALIDATE_DATA_SCRIPT="$PROJECT_DIR/scripts/validate_data.py"
RUN_WITH_TIMEOUT_SCRIPT="$PROJECT_DIR/scripts/run_with_timeout.py"
SPLIT_MRI_SCRIPT="$PROJECT_DIR/scripts/split_brainmri_by_disease.py"
ACADEMIC_SKILL_DIR="$PROJECT_DIR/.agents/skills/academic-search"
ACADEMIC_SKILL_FILE="$ACADEMIC_SKILL_DIR/SKILL.md"
AUTO_GIT_SYNC="${AUTO_GIT_SYNC:-0}"
AUTO_IF_SYNC="${AUTO_IF_SYNC:-1}"

mkdir -p "$PROJECT_DIR/data"

MODE="${1:-brainmri}"
CONFIG_FILE="$PROJECT_DIR/scripts/fetch_config.sh"

export PYTHONUNBUFFERED=1

if [ ! -f "$CONFIG_FILE" ]; then
    echo "[ERROR] Missing config file: $CONFIG_FILE"
    exit 1
fi

# shellcheck source=/dev/null
source "$CONFIG_FILE"

CODEX_TIMEOUT_SECONDS="${CODEX_TIMEOUT_SECONDS:-${OPENCODE_TIMEOUT_SECONDS:-600}}"

if [ -z "${MODEL_ID:-}" ]; then
    echo "[ERROR] MODEL_ID is empty in $CONFIG_FILE"
    exit 1
fi
for required in "$ACADEMIC_SKILL_FILE" "$SPLIT_MRI_SCRIPT"; do
    if [ ! -f "$required" ]; then
        echo "[ERROR] Required file not found: $required"
        exit 1
    fi
done
if ! command -v codex >/dev/null 2>&1; then
    echo "[ERROR] codex CLI not found. Please install Codex CLI first."
    exit 1
fi

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

validate_data_file() {
    local file="$1"
    local domain_id="${2:-}"
    local stage="${3:-}"
    if [ ! -f "$file" ]; then
        log "[ERROR] Data file was not created: $file"
        return 1
    fi
    if ! python3 -m json.tool "$file" >/dev/null 2>&1; then
        log "[ERROR] Data file is not valid JSON: $file"
        return 1
    fi
    if [ ! -f "$VALIDATE_DATA_SCRIPT" ]; then
        log "[ERROR] Data validator script not found: $VALIDATE_DATA_SCRIPT"
        return 1
    fi
    local validate_output validator_args=("$file" "$domain_id")
    if [ -n "$stage" ]; then
        validator_args+=(--stage "$stage")
    fi
    if [ "$stage" = "final" ]; then
        validator_args+=(--minimum-impact-factor 8)
    fi
    if ! validate_output=$(python3 "$VALIDATE_DATA_SCRIPT" "${validator_args[@]}" 2>&1); then
        log "[ERROR] Data quality check failed: $file"
        [ -n "$validate_output" ] && echo "$validate_output"
        return 1
    fi
    [ -n "$validate_output" ] && echo "$validate_output"
    log "[OK] Data file validated (schema + quality): $file"
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

sync_impact_factors() {
    local file="$1"
    local sync_output
    if [ ! -f "$SYNC_IF_SCRIPT" ]; then
        log "[WARN] IF sync script not found: $SYNC_IF_SCRIPT"
        return 0
    fi
    if ! sync_output=$(python3 "$SYNC_IF_SCRIPT" "$file" 2>&1); then
        log "[WARN] IF sync failed (non-blocking): $file"
        [ -n "$sync_output" ] && echo "$sync_output"
        return 0
    fi
    [ -n "$sync_output" ] && echo "$sync_output"
    log "[OK] Impact factors synced: $file"
    return 0
}

filter_impact_factors() {
    local file="$1"
    local filter_output
    if [ ! -f "$FILTER_IF_SCRIPT" ]; then
        log "[ERROR] IF filter script not found: $FILTER_IF_SCRIPT"
        return 1
    fi
    if ! filter_output=$(python3 "$FILTER_IF_SCRIPT" "$file" --minimum 8 2>&1); then
        log "[ERROR] IF filter failed: $file"
        [ -n "$filter_output" ] && echo "$filter_output"
        return 1
    fi
    [ -n "$filter_output" ] && echo "$filter_output"
    log "[OK] Articles below IF 8 filtered: $file"
    return 0
}

run_post_fetch_if_sync() {
    local mode="$1"
    local sync_output

    case "$mode" in
        if|journal-if|impact-factor|brainmri|mri|all|autism|depression|adhd|ad|pd)
            return 0
            ;;
    esac

    if [ "$AUTO_IF_SYNC" != "1" ]; then
        log "[INFO] AUTO_IF_SYNC is disabled; skip post-fetch IF sync."
        return 0
    fi

    if [ ! -f "$SYNC_IF_SCRIPT" ]; then
        log "[WARN] IF sync script not found: $SYNC_IF_SCRIPT"
        return 0
    fi

    log "🔁 Running post-fetch IF sync (reference=auto-unresolved)..."
    if ! sync_output=$(python3 "$SYNC_IF_SCRIPT" --reference auto-unresolved 2>&1); then
        log "[WARN] Post-fetch IF sync failed (non-blocking)."
        [ -n "$sync_output" ] && echo "$sync_output"
        return 0
    fi
    [ -n "$sync_output" ] && echo "$sync_output"
    log "[OK] Post-fetch IF sync finished."
    return 0
}

run_codex() {
    local title="$1"
    local prompt="$2"
    local timeout_sec="${CODEX_TIMEOUT_SECONDS:-600}"
    local provider="${CODEX_PROVIDER:-}"
    local provider_args=()
    local trace_file=""

    log "⚡ [$title] model: $MODEL_ID"
    if [ -n "$provider" ]; then
        provider_args=(-c "model_provider=\"$provider\"")
        log "⚡ [$title] provider: $provider"
    fi
    if ! [[ "$timeout_sec" =~ ^[0-9]+$ ]]; then
        log "[WARN] Invalid CODEX_TIMEOUT_SECONDS=$timeout_sec, fallback to 600"
        timeout_sec=600
    fi
    if [ "$timeout_sec" -gt 0 ]; then
        log "⏱️ [$title] timeout: ${timeout_sec}s"
    else
        log "⏱️ [$title] timeout: disabled"
    fi
    log "──── PROMPT ────────────────────────"
    while IFS= read -r line; do
        [ -n "$line" ] && echo "  $line"
    done <<< "$prompt"
    log "────────────────────────────────────"

    trace_file=$(mktemp -t codex-run.XXXXXX)
    if [ -z "$trace_file" ] || [ ! -f "$trace_file" ]; then
        log "[ERROR] Failed to create trace file via mktemp"
        return 1
    fi

    if [ "$timeout_sec" -gt 0 ]; then
        if [ ! -f "$RUN_WITH_TIMEOUT_SCRIPT" ]; then
            log "[ERROR] Timeout runner script not found: $RUN_WITH_TIMEOUT_SCRIPT"
            return 1
        fi
        python3 "$RUN_WITH_TIMEOUT_SCRIPT" \
            --timeout "$timeout_sec" \
            -- \
            codex exec \
            "${provider_args[@]}" \
            --model "$MODEL_ID" \
            --dangerously-bypass-approvals-and-sandbox \
            "$prompt" \
            2>&1 | tee "$trace_file"
        local exit_code=${PIPESTATUS[0]}
    else
        codex exec \
            "${provider_args[@]}" \
            --model "$MODEL_ID" \
            --dangerously-bypass-approvals-and-sandbox \
            "$prompt" \
            2>&1 | tee "$trace_file"
        local exit_code=${PIPESTATUS[0]}
    fi

    if [ $exit_code -eq 124 ]; then
        log "[ERROR] codex timed out after ${timeout_sec}s ($title)"
        if rg -qi "(websearch|webfetch|exec|thinking|curl|esearch|efetch|esummary|api)" "$trace_file" 2>/dev/null; then
            log "[WARN] Timeout reached while Codex was still collecting information."
        else
            log "[WARN] Timeout reached before meaningful collection activity was detected."
        fi
        rm -f "$trace_file"
        return 124
    fi
    if [ $exit_code -ne 0 ]; then
        log "[ERROR] codex exited with code $exit_code ($title)"
        rm -f "$trace_file"
        return $exit_code
    fi
    rm -f "$trace_file"
    return 0
}

git_sync_data() {
    local mode="$1"
    local branch
    local has_data_changes=0
    local ahead_count=0
    local git_output=""

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
    if ! git -C "$PROJECT_DIR" diff --quiet -- data \
        || ! git -C "$PROJECT_DIR" diff --cached --quiet -- data; then
        has_data_changes=1
    fi

    if [ "$has_data_changes" -eq 1 ]; then
        if ! git_output=$(git -C "$PROJECT_DIR" commit -m "data: auto-fetch ${mode} ${TODAY}" -- \
            data \
            2>&1); then
            log "[ERROR] git commit failed; skip push."
            [ -n "$git_output" ] && echo "$git_output"
            return 1
        fi
        [ -n "$git_output" ] && echo "$git_output"
    fi

    if git -C "$PROJECT_DIR" rev-parse --verify "origin/$branch" >/dev/null 2>&1; then
        ahead_count=$(git -C "$PROJECT_DIR" rev-list --count "origin/$branch..$branch" 2>/dev/null || echo "0")
    fi

    if [ "$has_data_changes" -eq 0 ] && [ "$ahead_count" -eq 0 ]; then
        log "[INFO] No data changes to sync."
        return 0
    fi

    if git_output=$(git -C "$PROJECT_DIR" push origin "$branch" 2>&1); then
        [ -n "$git_output" ] && echo "$git_output"
        log "[OK] Data synced to GitHub (branch: $branch)"
        return 0
    fi

    log "[WARN] Direct git push failed; trying pull --rebase and retry."
    [ -n "$git_output" ] && echo "$git_output"
    if ! git_output=$(git -C "$PROJECT_DIR" -c rebase.autoStash=true pull --rebase origin "$branch" 2>&1); then
        log "[ERROR] git pull --rebase failed; push skipped."
        [ -n "$git_output" ] && echo "$git_output"
        return 1
    fi
    [ -n "$git_output" ] && echo "$git_output"

    if ! git_output=$(git -C "$PROJECT_DIR" push origin "$branch" 2>&1); then
        log "[ERROR] git push failed after rebase retry."
        [ -n "$git_output" ] && echo "$git_output"
        return 1
    fi
    [ -n "$git_output" ] && echo "$git_output"

    log "[OK] Data synced to GitHub after rebase retry (branch: $branch)"
    return 0
}

# Retry codex execution and allow validated-file fallback on failures.
# Retry codex execution without model fallback.
run_codex_with_fallback_base() {
    local title="$1"
    local prompt="$2"
    local file="$3"
    local domain_id="$4"
    local retry_attempts="${CODEX_RETRY_ATTEMPTS:-3}"
    local retry_delay="${CODEX_RETRY_DELAY_SECONDS:-20}"
    local attempt=1
    local rc=1

    if ! [[ "$retry_attempts" =~ ^[0-9]+$ ]] || [ "$retry_attempts" -lt 1 ]; then
        log "[WARN] Invalid CODEX_RETRY_ATTEMPTS=$retry_attempts, fallback to 3"
        retry_attempts=3
    fi
    if ! [[ "$retry_delay" =~ ^[0-9]+$ ]] || [ "$retry_delay" -lt 0 ]; then
        log "[WARN] Invalid CODEX_RETRY_DELAY_SECONDS=$retry_delay, fallback to 20"
        retry_delay=20
    fi

    while [ "$attempt" -le "$retry_attempts" ]; do
        if [ "$attempt" -gt 1 ]; then
            log "🔁 Retry attempt ${attempt}/${retry_attempts}: $title"
        fi

        run_codex "$title" "$prompt"
        rc=$?
        if [ $rc -eq 0 ]; then
            return 0
        fi

        if [ $rc -eq 124 ]; then
            log "[WARN] codex timeout detected. Checking whether a valid data file was already written: $file"
            if validate_data_file "$file" "$domain_id"; then
                log "[WARN] Timeout fallback accepted: continue with validated file."
                return 0
            fi
            log "[WARN] Timeout fallback unavailable: no valid data file yet."
        else
            log "[WARN] codex exited with code $rc. Checking whether a valid data file was already written: $file"
            if validate_data_file "$file" "$domain_id"; then
                log "[WARN] Non-timeout fallback accepted: continue with validated file."
                return 0
            fi
            log "[WARN] No valid data file available after exit code $rc."
        fi

        if [ "$attempt" -lt "$retry_attempts" ] && [ "$retry_delay" -gt 0 ]; then
            log "[WARN] Sleeping ${retry_delay}s before retry..."
            sleep "$retry_delay"
        fi
        attempt=$((attempt + 1))
    done

    log "[ERROR] Exhausted retries for $title (last exit code: $rc)"
    return $rc
}

# Retry codex execution and allow validated-file fallback on failures.
run_codex_with_fallback() {
    local title="$1"
    local prompt="$2"
    local file="$3"
    local domain_id="$4"
    local rc=1

    run_codex_with_fallback_base "$title" "$prompt" "$file" "$domain_id"
    rc=$?
    if [ $rc -eq 0 ]; then
        return 0
    fi

    if [ -n "${FALLBACK_MODEL_ID:-}" ] && [ "$FALLBACK_MODEL_ID" != "$MODEL_ID" ]; then
        log "[WARN] Primary model failed; retrying with fallback model: $FALLBACK_MODEL_ID"
        local original_model="$MODEL_ID"
        MODEL_ID="$FALLBACK_MODEL_ID"
        run_codex_with_fallback_base "$title" "$prompt" "$file" "$domain_id"
        rc=$?
        MODEL_ID="$original_model"
        if [ $rc -eq 0 ]; then
            return 0
        fi
        log "[ERROR] Fallback model failed (model=$FALLBACK_MODEL_ID)."
    fi

    return $rc
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
    local post_process="${2:-1}"
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
    prompt="${prompt//__ACADEMIC_SKILL_PATH__/$ACADEMIC_SKILL_FILE}"

    run_codex_with_fallback "Fetch $label" "$prompt" "$data_file" "$domain_id" || return $?
    validate_data_file "$data_file" "$domain_id" || return $?
    if [ "$post_process" != "1" ]; then
        return 0
    fi
    sync_impact_factors "$data_file" || return $?
    generate_digest "$data_file" "$domain_id" || return $?
}

# Split Brain MRI output into disease domain files and finish each generated file.
process_mri_split_outputs() {
    local brainmri_file="$PROJECT_DIR/data/${TODAY}-brainmri.json"
    local domain_id data_file

    if ! python3 "$SPLIT_MRI_SCRIPT" "$brainmri_file"; then
        log "[ERROR] Failed to split Brain MRI output."
        return 1
    fi

    for domain_id in brainmri autism depression adhd ad pd; do
        data_file="$PROJECT_DIR/data/${TODAY}-${domain_id}.json"
        validate_data_file "$data_file" "$domain_id" "final" || return $?
        generate_digest "$data_file" "$domain_id" || return $?
    done
}

# Run the single MRI retrieval and derive disease files locally.
run_mri_pipeline() {
    local brainmri_file="$PROJECT_DIR/data/${TODAY}-brainmri.json"
    local sync_output

    run_academic_domain "brainmri" "0" || return $?
    if [ ! -f "$SYNC_IF_SCRIPT" ]; then
        log "[ERROR] IF sync script not found: $SYNC_IF_SCRIPT"
        return 1
    fi
    if ! sync_output=$(python3 "$SYNC_IF_SCRIPT" "$brainmri_file" --no-crawl 2>&1); then
        log "[ERROR] IF sync failed: $brainmri_file"
        [ -n "$sync_output" ] && echo "$sync_output"
        return 1
    fi
    [ -n "$sync_output" ] && echo "$sync_output"
    log "[OK] Impact factors synced locally: $brainmri_file"
    filter_impact_factors "$brainmri_file" || return $?
    validate_data_file "$brainmri_file" "brainmri" "final" || return $?
    process_mri_split_outputs || return $?
}

# Historical helper: all academic disease views now come from Brain MRI split.
run_all_academic_domains() {
    run_mri_pipeline
}

if [ -z "${ACADEMIC_PROMPT_TEMPLATE:-}" ] || [ -z "${TEST_PROMPT_TEMPLATE:-}" ]; then
    echo "[ERROR] Prompt templates are missing in $CONFIG_FILE"
    exit 1
fi

TEST_DATA_FILE="$PROJECT_DIR/data/${TODAY}-brainmri.json"
TEST_PROMPT="${TEST_PROMPT_TEMPLATE//__TODAY__/$TODAY}"
TEST_PROMPT="${TEST_PROMPT//__DATA_FILE__/$TEST_DATA_FILE}"

log "🚀 Starting task: $MODE"

cd "$PROJECT_DIR"

case "$MODE" in
    ai)
        log "[ERROR] AI fetch is disabled for this project."
        exit 1
        ;;
    brainmri|mri|all|autism|depression|adhd|ad|pd)
        run_mri_pipeline || exit $?
        ;;
    test)
        run_codex_with_fallback "Test Write" "$TEST_PROMPT" "$TEST_DATA_FILE" "brainmri" || exit $?
        validate_data_file "$TEST_DATA_FILE" "brainmri" || exit $?
        process_mri_split_outputs || exit $?
        ;;
    if|journal-if|impact-factor)
        if [ ! -f "$SYNC_IF_SCRIPT" ]; then
            log "[ERROR] IF sync script not found: $SYNC_IF_SCRIPT"
            exit 1
        fi
        shift || true
        if ! python3 "$SYNC_IF_SCRIPT" "$@"; then
            exit 1
        fi
        ;;
    *)
        # Treat all positional args as academic domain IDs
        needs_mri=0
        for domain_id in "$@"; do
            case "$domain_id" in
                ai)
                    log "[ERROR] AI fetch is disabled for this project."
                    exit 1
                    ;;
                brainmri|mri|autism|depression|adhd|ad|pd)
                    needs_mri=1
                    ;;
                *)
                    run_academic_domain "$domain_id" || exit $?
                    ;;
            esac
        done
        if [ "$needs_mri" -eq 1 ]; then
            run_mri_pipeline || exit $?
        fi
        ;;
esac

log "✅ Task finished."
if ! git_sync_data "$MODE"; then
    log "[WARN] Git sync failed, but local fetch artifacts are already generated."
fi
