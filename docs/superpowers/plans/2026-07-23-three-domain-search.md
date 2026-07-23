# Three-Domain Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broad Brain MRI splitting with independent Autism+MRI, Depression+MRI, and TMS daily searches.

**Architecture:** Active domains are an explicit ordered allowlist. The shell runner fetches requested domains independently, batches successful files through one IF sync, then finalizes each file independently while accumulating failures.

**Tech Stack:** Bash, Python standard library, PubMed E-utilities, unittest, systemd/launchd.

---

### Task 1: Lock the active domain contract

**Files:**
- Modify: `tests/test_server_domains.py`
- Modify: `scripts/server.py`
- Create: `.agents/skills/academic-search/sources/tms.md`
- Delete: inactive source configs under `.agents/skills/academic-search/sources/`

- [ ] Write a failing server test asserting historical files cannot add domains and the result order is exactly `autism`, `depression`, `tms`.
- [ ] Run `python3 -m unittest tests.test_server_domains -v` and confirm failure.
- [ ] Add the explicit ordered active-domain allowlist and stop data-file discovery from adding domains.
- [ ] Add the bounded TMS PubMed configuration and remove inactive configs.
- [ ] Run the focused test and confirm it passes.

### Task 2: Apply the agreed IF semantics

**Files:**
- Modify: `tests/test_filter_impact_factor.py`
- Modify: `scripts/filter_impact_factor.py`
- Modify: `scripts/validate_data.py` only if final validation must recognize the new removal contract.

- [ ] Change the test to require removal of `not_available_yet` while retaining `unresolved` and `lookup_error`.
- [ ] Run `python3 -m unittest tests.test_filter_impact_factor -v` and confirm failure.
- [ ] Implement the minimal status handling and accurate stats.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Replace the MRI split runner

**Files:**
- Rewrite contract assertions: `tests/test_minimal_if_pipeline.py`
- Modify: `scripts/fetch.sh`
- Modify: `scripts/fetch_config.sh`
- Delete: `scripts/split_brainmri_by_disease.py`
- Delete: `tests/test_split_brainmri_by_disease.py`

- [ ] Write failing contract tests for `ACTIVE_DOMAINS=(autism depression tms)`, shared IF sync on the successful file subset, per-file finalization, explicit rejection of old modes, and offline three-domain `test` mode.
- [ ] Run the focused contract tests and confirm failure.
- [ ] Remove all split-script dependencies and implement the domain batch runner with accumulated failure reporting.
- [ ] Make no-argument execution equivalent to `all`; make a single-domain command run only that domain.
- [ ] Keep `if` argument passthrough unchanged and make `test` avoid PubMed/LetPub.
- [ ] Run `bash -n scripts/fetch.sh scripts/fetch_config.sh` and the focused contract tests.

### Task 4: Update scheduling and documentation

**Files:**
- Modify: `scripts/schedule.sh`
- Modify: `README.md`
- Modify: `docs/huawei-cloud-deployment.md`

- [ ] Replace local `brainmri` label, argument, and log names with `all`.
- [ ] Update user-facing commands and active-domain descriptions without changing unrelated documentation.
- [ ] Run shell syntax checks and `git diff --check`.

### Task 5: Verify, commit, and deploy

**Files:** all files above; no historical `data/YYYY-MM-DD-*.json` deletion or rewrite.

- [ ] Run `python3 -m unittest discover -s tests -q`.
- [ ] Run `python3 -m py_compile scripts/*.py tests/*.py` and `bash -n scripts/*.sh`.
- [ ] Verify `/api/domains` locally returns only the three ordered domains.
- [ ] Commit the implementation.
- [ ] Back up `/projects/daily-insights`, rsync without `--delete`, and run remote tests.
- [ ] After the backup, delete only the explicitly retired remote source configs, split script, and split-script test so no obsolete active code survives; do not delete any historical `data/*.json`.
- [ ] Install/enable `daily-insights-fetch-all.timer`, disable the old Brain MRI timer, and confirm the next 08:30 schedule.
- [ ] Verify the public page and `/api/domains` after deployment.
