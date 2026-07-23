#!/bin/bash
# fetch.sh — Wrapper for codex daily literature fetching
# Usage: ./scripts/fetch.sh [all|autism|depression|tms|if|test]
#   all         — 抓取 Autism + MRI、Depression + MRI 和全部 TMS 研究
#   if          — 仅同步期刊 IF（不抓论文/新闻）
#   test        — 离线写入并验证三个领域的测试数据

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TODAY=$(date +%Y-%m-%d)
ACADEMIC_SOURCES_DIR="$PROJECT_DIR/.agents/skills/academic-search/sources"
DIGEST_SCRIPT="$PROJECT_DIR/scripts/generate_digest.py"
SYNC_IF_SCRIPT="$PROJECT_DIR/scripts/sync_impact_factors.py"
FILTER_IF_SCRIPT="$PROJECT_DIR/scripts/filter_impact_factor.py"
VALIDATE_DATA_SCRIPT="$PROJECT_DIR/scripts/validate_data.py"
RUN_WITH_TIMEOUT_SCRIPT="$PROJECT_DIR/scripts/run_with_timeout.py"
ACADEMIC_SKILL_DIR="$PROJECT_DIR/.agents/skills/academic-search"
ACADEMIC_SKILL_FILE="$ACADEMIC_SKILL_DIR/SKILL.md"
ACTIVE_DOMAINS=(autism depression tms)
AUTO_GIT_SYNC="${AUTO_GIT_SYNC:-0}"

mkdir -p "$PROJECT_DIR/data"

MODE="${1:-all}"
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
for required in "$ACADEMIC_SKILL_FILE" "$SYNC_IF_SCRIPT" "$FILTER_IF_SCRIPT"; do
    if [ ! -f "$required" ]; then
        echo "[ERROR] Required file not found: $required"
        exit 1
    fi
done

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

run_codex() {
    local title="$1"
    local prompt="$2"
    local timeout_sec="${CODEX_TIMEOUT_SECONDS:-600}"
    local provider="${CODEX_PROVIDER:-}"
    local provider_args=()
    local trace_file=""

    if ! command -v codex >/dev/null 2>&1; then
        log "[ERROR] codex CLI not found. Please install Codex CLI first."
        return 1
    fi

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
}

run_domain_batch() {
    local requested_domains=("$@")
    local successful_domains=()
    local successful_files=()
    local failed_stages=()
    local domain_id data_file sync_output

    for domain_id in "${requested_domains[@]}"; do
        data_file="$PROJECT_DIR/data/${TODAY}-${domain_id}.json"
        if run_academic_domain "$domain_id"; then
            successful_domains+=("$domain_id")
            successful_files+=("$data_file")
        else
            failed_stages+=("${domain_id}:fetch")
            log "[ERROR] Fetch failed for $domain_id; continuing."
        fi
    done

    if [ "${#successful_files[@]}" -eq 0 ]; then
        log "[ERROR] No domain produced a valid raw data file."
        log "[ERROR] Failed stages: ${failed_stages[*]}"
        return 1
    fi

    if ! sync_output=$(python3 "$SYNC_IF_SCRIPT" "${successful_files[@]}" --reference auto-unresolved 2>&1); then
        failed_stages+=("if-sync")
        log "[ERROR] Shared IF sync failed; final files were not generated."
        [ -n "$sync_output" ] && echo "$sync_output"
        log "[ERROR] Failed stages: ${failed_stages[*]}"
        return 1
    fi
    [ -n "$sync_output" ] && echo "$sync_output"
    log "[OK] Shared impact-factor lookup finished."

    for domain_id in "${successful_domains[@]}"; do
        data_file="$PROJECT_DIR/data/${TODAY}-${domain_id}.json"
        if ! filter_impact_factors "$data_file"; then
            failed_stages+=("${domain_id}:filter")
            continue
        fi
        if ! generate_digest "$data_file" "$domain_id"; then
            failed_stages+=("${domain_id}:digest")
            continue
        fi
        if ! validate_data_file "$data_file" "$domain_id" "final"; then
            failed_stages+=("${domain_id}:validate")
        fi
    done

    if [ "${#failed_stages[@]}" -gt 0 ]; then
        log "[ERROR] Failed stages: ${failed_stages[*]}"
        return 1
    fi
    return 0
}

run_if_maintenance() {
    local unresolved_file="$PROJECT_DIR/data/if_unresolved_journals.json"
    local unresolved_files=()
    local file domain_id sync_output unresolved_file_list

    if [ ! -f "$unresolved_file" ]; then
        log "[INFO] No unresolved journal file; IF maintenance skipped."
        return 0
    fi

    if ! unresolved_file_list=$(python3 - "$unresolved_file" "$PROJECT_DIR/data" <<'PY'
import json
import re
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
journals = payload.get("journals", payload) if isinstance(payload, dict) else payload
entries = journals.values() if isinstance(journals, dict) else journals
data_dir = Path(sys.argv[2])
active = re.compile(r"^\d{4}-\d{2}-\d{2}-(autism|depression|tms)\.json$")
files = set()
for entry in entries:
    if not isinstance(entry, dict):
        continue
    names = list(entry.get("files") or [])
    if entry.get("last_file"):
        names.append(entry["last_file"])
    for name in names:
        path = data_dir / Path(str(name)).name
        if active.match(path.name) and path.is_file():
            files.add(path)
for path in sorted(files):
    print(path)
PY
); then
        log "[ERROR] Failed to read unresolved journal files."
        return 1
    fi
    while IFS= read -r file; do
        [ -n "$file" ] && unresolved_files+=("$file")
    done <<< "$unresolved_file_list"

    if [ "${#unresolved_files[@]}" -eq 0 ]; then
        log "[INFO] No unresolved active-domain files; IF maintenance skipped."
        return 0
    fi

    log "[INFO] Daily IF maintenance: ${#unresolved_files[@]} active-domain files."
    if ! sync_output=$(python3 "$SYNC_IF_SCRIPT" \
        --reference auto-unresolved-daily \
        "${unresolved_files[@]}" 2>&1); then
        [ -n "$sync_output" ] && echo "$sync_output"
        log "[ERROR] Daily unresolved IF lookup failed."
        return 1
    fi
    [ -n "$sync_output" ] && echo "$sync_output"

    for file in "${unresolved_files[@]}"; do
        domain_id="${file##*-}"
        domain_id="${domain_id%.json}"
        filter_impact_factors "$file" || return 1
        generate_digest "$file" "$domain_id" || return 1
        validate_data_file "$file" "$domain_id" "final" || return 1
    done
    log "[OK] Daily unresolved IF maintenance finished."
}

run_test_mode() {
    local domain_id data_file category test_dir rc=0

    test_dir=$(mktemp -d "${TMPDIR:-/tmp}/daily-insights-test.XXXXXX") || return 1

    for domain_id in "${ACTIVE_DOMAINS[@]}"; do
        category=$(get_fm "$ACADEMIC_SOURCES_DIR/${domain_id}.md" "category")
        data_file="$test_dir/${TODAY}-${domain_id}.json"
        python3 - "$data_file" "$TODAY" "$domain_id" "$category" <<'PY'
import json
import sys
from pathlib import Path

path, today, domain_id, category = sys.argv[1:]
payload = {
    "date": today,
    "articles": [{
        "title": f"{category} pipeline test",
        "summary": "Offline test entry for pipeline validation.",
        "url": f"https://example.com/{domain_id}-pipeline-test",
        "category": category,
        "source": "test",
        "journal": "Test Journal",
        "published_date": today,
        "date": today,
        "impact_factor": 8.0,
        "impact_factor_year": 2024,
        "impact_factor_status": "available",
        "impact_factor_source": "test",
        "impact_factor_match_method": "test",
        "impact_factor_matched_journal": "Test Journal",
    }],
}
Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
        if ! generate_digest "$data_file" "$domain_id" \
            || ! validate_data_file "$data_file" "$domain_id" "final"; then
            rc=1
            break
        fi
    done
    rm -rf -- "$test_dir"
    return "$rc"
}

if [ -z "${ACADEMIC_PROMPT_TEMPLATE:-}" ]; then
    echo "[ERROR] Prompt templates are missing in $CONFIG_FILE"
    exit 1
fi

log "🚀 Starting task: $MODE"

cd "$PROJECT_DIR"

case "$MODE" in
    all)
        run_domain_batch "${ACTIVE_DOMAINS[@]}" || exit $?
        ;;
    autism|depression|tms)
        run_domain_batch "$MODE" || exit $?
        ;;
    test)
        AUTO_GIT_SYNC=0
        run_test_mode || exit $?
        ;;
    if)
        if [ ! -f "$SYNC_IF_SCRIPT" ]; then
            log "[ERROR] IF sync script not found: $SYNC_IF_SCRIPT"
            exit 1
        fi
        shift || true
        if [ "$#" -eq 0 ]; then
            run_if_maintenance || exit $?
        elif ! python3 "$SYNC_IF_SCRIPT" "$@"; then
            exit 1
        fi
        ;;
    brainmri|mri|adhd|ad|pd|mefmri|ai)
        log "[ERROR] Retired mode: $MODE. Use all, autism, depression, or tms."
        exit 1
        ;;
    *)
        log "[ERROR] Unsupported mode: $MODE"
        exit 1
        ;;
esac

log "✅ Task finished."
if ! git_sync_data "$MODE"; then
    log "[WARN] Git sync failed, but local fetch artifacts are already generated."
fi
