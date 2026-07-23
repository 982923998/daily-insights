# Daily Insights Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Brain MRI daily pipeline self-contained and verifiable, enrich every article with auditable IF state, remove known IF values below 6, and simplify/safeguard the local app.

**Architecture:** A staged daily batch performs one local IF enrichment on the master Brain MRI file, applies a pure IF threshold filter, splits the filtered articles, generates six embedded digests, validates the whole batch, then publishes it. Article JSON becomes the only IF source consumed by the UI. Online unresolved lookup remains an explicit maintenance command, while server/runtime hardening is implemented independently.

**Tech Stack:** Python 3 standard library and `unittest`, Bash, single-file React/Babel frontend, macOS launchd, existing BeautifulSoup LetPub parser.

**Design spec:** `docs/superpowers/specs/2026-07-23-daily-insights-optimization-design.md`

---

## File ownership and execution order

Parallel wave 1 has non-overlapping ownership:

- Worker A: `scripts/sync_impact_factors.py`, `scripts/filter_impact_factor.py`, `scripts/validate_data.py`, and their tests.
- Worker B: `scripts/server.py` and server tests.
- Worker C: `web/index.html` and frontend contract tests.

Wave 2 starts after Worker A is integrated:

- Worker D: `scripts/fetch.sh`, `scripts/fetch_config.sh`, `scripts/split_brainmri_by_disease.py`, `scripts/publish_batch.py`, `scripts/generate_digest.py`, pipeline/split/digest tests.
- Worker E: `install.sh`, `启动.command`, `scripts/schedule.sh`, runtime tests.
- Worker F: `scripts/audit_impact_factor_history.py`, README/IF skill docs, audit tests.

No worker may revert or stage pre-existing user changes. Each worker must inspect `git diff` before editing and touch only owned files.

### Task 1: Repair IF resolution and article writeback

**Files:**

- Create: `tests/test_sync_impact_factors.py`
- Modify: `scripts/sync_impact_factors.py`

- [ ] **Step 1: Write failing resolver tests**

Cover exact ISSN, exact canonical name, exact abbreviation, zero-as-not-available, unresolved, and conflicting same-priority records. Before production edits, also cover source priority, newer comparable year override, invalid catalog JSON/structure, `no_match` versus `lookup_error`, unresolved idempotency, actual writeback/readback, manual override output, and exclusion of `references/*.json` from the fact index. The desired article result is:

```python
{
    "impact_factor": 8.2,
    "impact_factor_year": None,
    "impact_factor_status": "available",
    "impact_factor_source": "letpub",
    "impact_factor_match_method": "issn",
    "impact_factor_matched_journal": "Canonical Journal",
}
```

Use temporary JSON fixtures and real project functions; do not mock the resolver.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.test_sync_impact_factors -v
```

Expected: failures because the resolver/writeback contract does not exist and target article files remain unchanged.

- [ ] **Step 3: Implement deterministic index and resolver**

Add small pure functions with these responsibilities:

```python
def build_letpub_if_index(journals: list[dict]) -> dict[str, dict]: ...
def resolve_article_if(article: dict, index: dict[str, dict]) -> dict: ...
def apply_if_result(article: dict, result: dict) -> bool: ...
```

Source priority is manual override, legacy crawler supplement, unique, raw. Do not choose the largest IF. Same-priority conflicts without comparable years return `unresolved` with reason `conflict`.

- [ ] **Step 4: Implement actual file writeback**

`process_data_file()` must mutate each article, write via a temporary sibling file plus `os.replace`, reread the file, and return the number of articles whose IF fields actually changed. Empty journal names become explicit `unresolved` records.

- [ ] **Step 5: Separate no-match from system failure**

Invalid/missing catalog structures and JSON parse errors raise and fail the command. Local article no-match is `unresolved/no_match`. Explicit online network/parser failures are recorded as `lookup_error`, not `no_match`.

- [ ] **Step 6: Restore authoritative online supplement writes**

Explicit online lookup writes confirmed rows to `data/letpub/letpub_manual_overrides.json` and appends/upserts task audit metadata in `references/<reference>.json`. Reference files are never loaded into the fact index. Add assertions that a reference-only IF cannot enrich an article until it is present in the manual override catalog.

- [ ] **Step 7: Make unresolved updates idempotent**

Migrate legacy `last_file` to a sorted unique `files` list. Reprocessing the same journal/file pair must not increase `seen_count` or rewrite unchanged payloads.

- [ ] **Step 8: Verify GREEN and regression coverage**

Run:

```bash
python3 -m unittest tests.test_sync_impact_factors -v
```

Expected: all IF tests pass, including a second identical run producing byte-identical article and registry files.

### Task 2: Add IF filtering and staged validation

**Files:**

- Create: `scripts/filter_impact_factor.py`
- Create: `tests/test_filter_impact_factor.py`
- Create: `tests/test_validate_data.py`
- Modify: `scripts/validate_data.py`

- [ ] **Step 1: Write failing threshold tests**

Test the pure rule:

```python
5.999 -> removed
6.0 -> retained
6.001 -> retained
available + null -> error
not_available_yet + null -> retained
unresolved + null -> retained
```

Also test idempotent file filtering and removed/kept/unresolved counts.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.test_filter_impact_factor -v
```

Expected: module/function missing.

- [ ] **Step 3: Implement the minimal pure filter**

Expose:

```python
def filter_articles_by_if(articles: list[dict], minimum: float = 6.0) -> tuple[list[dict], dict]: ...
def filter_file(path: Path, minimum: float = 6.0) -> dict: ...
```

Use atomic sibling-file replacement. Do not crawl, resolve journals, generate digest, or change unrelated article fields.

- [ ] **Step 4: Write failing staged-validator tests**

Test `raw`, `enriched`, and `final` stages. Assert filename date, top-level date, article date, domain category, IF state/value combinations, and absence of known IF below 6 in final output. The path-aware API is explicit:

```python
def validate_file(path: Path, domain_id: str, stage: str = "raw", minimum_impact_factor: float = 6.0) -> list[str]: ...
def validate_payload(payload: object, domain_id: str, stage: str = "raw", minimum_impact_factor: float = 6.0) -> list[str]: ...
```

`validate_file()` owns filename/top-level/article date consistency; `validate_payload()` owns schema, domain and IF contracts.

- [ ] **Step 5: Verify RED**

Run:

```bash
python3 -m unittest tests.test_validate_data -v
```

Expected: stage/date/IF assertions are missing.

- [ ] **Step 6: Implement staged validation**

Add `stage="raw"` and `minimum_impact_factor=6.0` arguments to `validate_payload()` and matching CLI flags. Preserve existing callers by keeping raw as the default.

- [ ] **Step 7: Verify GREEN**

Run:

```bash
python3 -m unittest tests.test_filter_impact_factor tests.test_validate_data -v
```

Expected: all tests pass.

### Task 3: Secure the local HTTP server

**Files:**

- Create: `tests/test_server_security.py`
- Modify: `scripts/server.py`

- [ ] **Step 1: Write failing traversal and binding tests**

Test normal web/data resolution and rejection of literal `..`, URL-encoded traversal, and symlink escape. Test constants for `127.0.0.1`, allowed fetch modes, and maximum request size. Also create six-file date fixtures proving legacy no-`batch_id` dates remain visible, consistent new batches are visible, and missing/mixed `batch_id` batches are hidden by `/api/dates`.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.test_server_security -v
```

Expected: traversal resolves outside the project, host/mode/body contracts are absent, and mixed batches are incorrectly visible.

- [ ] **Step 3: Implement safe path resolution**

Create a pure helper that URL-decodes, resolves the candidate, and verifies `candidate.is_relative_to(root)` before serving. Return a guaranteed non-existent path or send 404 for rejected requests.

- [ ] **Step 4: Restrict network/API surface**

Bind to `127.0.0.1`, whitelist the current Brain MRI aliases, cap request bodies, reject malformed JSON, replace wildcard CORS with loopback origin handling, and clean completed task state.

- [ ] **Step 5: Implement mixed-batch visibility**

Make `/api/dates` the authoritative selectable-date source. For a new batch date, expose it only when all six expected domain files exist with the same non-empty `batch_id`. Preserve visibility of legacy dates where every existing file lacks `batch_id`; hide partial or mixed new batches.

- [ ] **Step 6: Verify GREEN**

Run:

```bash
python3 -m unittest tests.test_server_domains tests.test_server_security -v
```

Expected: all server tests pass.

### Task 4: Make the frontend consume article IF directly

**Files:**

- Create: `tests/test_frontend_contract.py`
- Modify: `web/index.html`

- [ ] **Step 1: Write failing static contract tests**

Assert the page does not request `/data/letpub/`, does not define browser-side LetPub index builders, and reads `article.impact_factor`, `article.impact_factor_year`, and `article.impact_factor_status`. Also assert selectable dates come only from `/api/dates`; the frontend must not independently discover or display data-file dates that the server has hidden as mixed batches.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.test_frontend_contract -v
```

Expected: current LetPub fetch/index assertions fail.

- [ ] **Step 3: Replace IF lookup with article fields**

Keep a single formatter:

```javascript
const getIfInfoForArticle = (article = {}) => ({
  impactFactor: Number.isFinite(Number(article.impact_factor)) ? Number(article.impact_factor) : null,
  impactFactorYear: article.impact_factor_year ?? null,
  impactFactorStatus: article.impact_factor_status || 'unresolved',
});
```

Map machine status to Chinese only at rendering time. Remove `letpubIndex` state, effect, helpers, and props. Do not change visual styling.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python3 -m unittest tests.test_frontend_contract -v
```

Expected: all frontend contract tests pass and the HTML contains no `/data/letpub/` request.

### Task 5: Rebuild the daily pipeline around one staged enrichment

**Files:**

- Create: `scripts/publish_batch.py`
- Create: `tests/test_publish_batch.py`
- Create: `tests/test_fetch_pipeline.py`
- Create: `tests/test_generate_digest.py`
- Modify: `scripts/fetch.sh`
- Modify: `scripts/fetch_config.sh`
- Modify: `scripts/split_brainmri_by_disease.py`
- Modify: `scripts/generate_digest.py`
- Modify: `tests/test_split_brainmri_by_disease.py`

- [ ] **Step 1: Write all failing pipeline, ISSN, split, and digest contract tests**

Assert the academic output contract includes `journal_issn`. Add a true end-to-end fixture whose master articles contain ISSNs and whose local catalog resolves them to `5.9`, `6.0`, and unknown; run the real local enrichment, filtering, splitting, and digest functions and assert ISSN survives, `5.9` is absent, `6.0` and unknown survive, and each output remains internally consistent. Add a split test proving disease terms in journal/source/category do not cause classification while title/summary terms do.

In `tests/test_generate_digest.py`, assert for every generated file that `stats.total == len(articles)`, every recommendation URL belongs to that file's article URL set, and digest generation preserves all article fields including `journal_issn` and IF provenance. These tests must exist before any production pipeline or digest edit.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.test_split_brainmri_by_disease tests.test_fetch_pipeline tests.test_generate_digest -v
```

Expected: journal metadata still influences split, the prompt does not require ISSN, and the full enrichment/filter/split/digest contract is not implemented.

- [ ] **Step 3: Add batch-directory support**

Make the splitter accept an explicit output directory. In `fetch.sh`, create one `mktemp -d` batch directory with cleanup trap and pass staged paths through fetch, validator, enrichment, filter, split, digest, and final validation.

- [ ] **Step 4: Enforce one fail-closed IF call**

The staged order must be exactly:

```text
fetch -> validate raw -> sync IF --no-crawl once -> filter 6 -> validate final
-> split -> validate six -> digest six -> validate six -> publish -> optional git sync
```

Remove per-domain IF calls and automatic post-fetch unresolved sync. IF/filter failures return non-zero and block downstream steps.

- [ ] **Step 5: Implement batch publish and rollback tests**

`publish_batch.py` assigns one `batch_id` to all six JSON payloads, validates required filenames, backs up existing targets, and uses `os.replace`. Ordinary exceptions restore backups. A dry-run/mocked mid-publish failure must leave the old six files intact.

- [ ] **Step 6: Implement and verify digest contracts**

Keep digest generation local to one staged file. If the existing implementation violates the tests, make only the changes required to ensure totals are computed from the final article list, recommendation URLs are a subset of that list, and article/IF/ISSN fields are never rewritten or dropped.

- [ ] **Step 7: Test shell orchestration with stubs**

Run `fetch.sh` in a temporary project fixture with stub commands/scripts that append their invocation to a trace. Assert one IF call, correct order, no digest/Git after IF failure, and no real Codex/network access.

- [ ] **Step 8: Verify GREEN**

Run:

```bash
python3 -m unittest tests.test_publish_batch tests.test_fetch_pipeline tests.test_split_brainmri_by_disease tests.test_generate_digest -v
bash -n scripts/fetch.sh scripts/fetch_config.sh
```

Expected: all tests and shell syntax checks pass.

### Task 6: Align install and launchd runtime behavior

**Files:**

- Create: `tests/test_runtime_scripts.py`
- Modify: `install.sh`
- Modify: `启动.command`
- Modify: `scripts/schedule.sh`

- [ ] **Step 1: Write failing runtime contract tests**

Using a temporary HOME and stub tools, assert: install uses the health endpoint rather than port-only detection; temporary assets use one unique directory and cleanup trap; launchd plist contains the resolved absolute Codex executable.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.test_runtime_scripts -v
```

Expected: existing install/schedule behavior violates these contracts.

- [ ] **Step 3: Implement minimal runtime fixes**

Reuse the health-check behavior from `启动.command`; use `mktemp -d` and trap cleanup in install; resolve `command -v codex` during schedule installation and place that absolute path in `ProgramArguments` or the generated environment.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
python3 -m unittest tests.test_runtime_scripts -v
bash -n install.sh scripts/schedule.sh 启动.command
```

Expected: tests and syntax checks pass.

### Task 7: Add safe historical IF audit and update contracts

**Files:**

- Create: `scripts/audit_impact_factor_history.py`
- Create: `tests/test_if_history_audit.py`
- Modify: `README.md`
- Modify: `.agents/skills/journal-impact-factor/SKILL.md`
- Modify: `.agents/skills/journal-impact-factor/references/unresolved-auto.md`
- Modify: `.agents/skills/journal-impact-factor/references/manual-journal-input.md`
- Modify: `.agents/skills/journal-impact-factor/references/reference-naming.md`

- [ ] **Step 1: Write failing audit tests**

In a temporary data directory, include valid domain files, unrelated JSON, duplicate disease copies, IF below/equal/above 6, unknown, and conflict. Assert only the exact `YYYY-MM-DD-(brainmri|autism|depression|adhd|ad|pd).json` filename patterns are scanned, no file bytes change, and output reports both file occurrences and URL-deduplicated counts.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.test_if_history_audit -v
```

Expected: audit module missing.

- [ ] **Step 3: Implement dry-run-only audit**

Reuse the IF resolver and filter classification functions. The command must have no apply/delete option in this iteration. Emit JSON and human-readable summaries with matched, below-threshold, retained-unknown, conflict, and source provenance counts.

- [ ] **Step 4: Update documentation and skill contract**

Document the new daily order, `IF >= 6` rule, unknown retention, machine status fields, explicit online `fetch.sh if` workflow, authoritative file responsibilities, local-only server binding, and test commands. Remove statements claiming raw/reference files are the article IF source.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
python3 -m unittest tests.test_if_history_audit -v
```

Expected: audit tests pass and fixture files remain byte-identical.

### Task 8: Full integration verification

**Files:**

- Review only: all changed files

- [ ] **Step 1: Run the complete offline test suite**

```bash
python3 -m unittest discover -s tests -v
```

Expected: zero failures and zero errors.

- [ ] **Step 2: Run syntax and compile checks**

```bash
python3 -m py_compile scripts/*.py tests/*.py
bash -n install.sh scripts/*.sh 启动.command
```

Expected: exit 0.

- [ ] **Step 3: Run the historical dry-run audit**

```bash
if_audit_before="$(mktemp)"
if_audit_after="$(mktemp)"
find data -maxdepth 1 -type f \
  | rg '/[0-9]{4}-[0-9]{2}-[0-9]{2}-(brainmri|autism|depression|adhd|ad|pd)\.json$' \
  | sort \
  | while IFS= read -r file; do shasum -a 256 "$file"; done > "$if_audit_before"
python3 scripts/audit_impact_factor_history.py --project-dir . --minimum 6 --json
find data -maxdepth 1 -type f \
  | rg '/[0-9]{4}-[0-9]{2}-[0-9]{2}-(brainmri|autism|depression|adhd|ad|pd)\.json$' \
  | sort \
  | while IFS= read -r file; do shasum -a 256 "$file"; done > "$if_audit_after"
diff -u "$if_audit_before" "$if_audit_after"
rm -f "$if_audit_before" "$if_audit_after"
```

Expected: report only; before/after SHA-256 manifests are identical.

- [ ] **Step 4: Verify frontend/server smoke behavior**

Start the local server, request `/`, `/api/domains`, and one normal data file; assert HTTP 200. Request literal and encoded traversal paths; assert 404. Confirm no listener exists on non-loopback interfaces.

- [ ] **Step 5: Inspect the final diff**

Confirm every changed line maps to the approved design, no historical data was deleted, and pre-existing user modifications were neither reverted nor accidentally staged.

- [ ] **Step 6: Do not run the live daily fetch automatically**

The production fetch performs external PubMed/Codex calls and writes current data. After offline verification, report readiness and ask before running a new live fetch under the new `IF >= 6` gate.
