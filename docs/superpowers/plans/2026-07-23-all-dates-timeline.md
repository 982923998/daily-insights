# All-Dates Article Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the date picker and display all available articles as a newest-first timeline.

**Architecture:** Keep the single-file React frontend. Add small pure timeline helpers inside `web/index.html`, load `/api/dates` after domains, fetch every date/domain file with per-file isolation, then deduplicate and sort once. Add one focused Python test file that executes the pure helper block with Node and statically checks the page wiring.

**Tech Stack:** React 18 in browser, JavaScript, Python `unittest`, Node.js.

---

### Task 1: Lock the timeline behavior with failing tests

**Files:**
- Create: `tests/test_frontend_timeline.py`
- Test: `web/index.html`

- [ ] **Step 1: Add helper behavior tests**

Extract the JavaScript between `// --- Timeline Helpers Start ---` and `// --- Timeline Helpers End ---`, execute it with Node, and assert:

- valid date fallback is `published_date → article.date → payload.date → request date`;
- invalid dates are ignored;
- domain + normalized URL deduplication keeps the newest record;
- missing-URL records deduplicate by domain + normalized title;
- records with different valid dates are returned in strict newest-first order;
- equal-date input remains stable;
- different domains may retain the same URL;
- the newest non-empty object Digest wins per domain, with fallback to an older valid Digest.
- a pure view-state helper distinguishes `/api/dates` failure, an empty dates list, one failed file among successful files, and dates whose files all failed.
- invalid JSON resolves to a skipped file, and a parsed payload without the required object/`articles` array structure is rejected without affecting valid sibling files.

- [ ] **Step 2: Add page contract tests**

Assert that `type="date"`, `currentDate`, and `onDateChange` are absent. Assert that `/api/dates`, all-date file requests, `Newest first`, and `saved_at` descending order remain present. The four loading-state branches are verified by executing the pure view-state helper rather than only matching source strings.

- [ ] **Step 3: Run the new test and verify RED**

Run: `python3 -m unittest tests.test_frontend_timeline -v`

Expected: FAIL because the timeline helper block and all-date loader do not exist yet.

### Task 2: Implement the all-date timeline

**Files:**
- Modify: `web/index.html:90-220`
- Modify: `web/index.html:730-1000`
- Test: `tests/test_frontend_timeline.py`

- [ ] **Step 1: Add pure timeline helpers**

Add helpers for strict `YYYY-MM-DD` validation, payload structure validation, date fallback, valid Digest detection, domain-scoped URL/title deduplication, stable newest-first sorting, newest-valid Digest selection, and final view-state resolution. Preserve `_domainId`, add the effective timeline date only as an internal field, and keep existing anchor generation.

- [ ] **Step 2: Remove date UI and state**

Reduce `Sidebar` props to domain/favorite navigation only. Delete the date input, Saved date notice, `today/currentDate` state, and date-specific header/error copy. Show `Newest first` below the ordinary-view title.

- [ ] **Step 3: Load all dates and files**

After domains are ready, request `/api/dates`. Validate and sort the returned dates, fetch every date/domain combination with `safeFetch`, convert HTTP/JSON failures to skipped files, reject parsed payloads without an object top level and `articles` array, merge valid payloads, select Digests, and expose generic unavailable/empty states. Keep the existing domain, search, saved, Digest and card render paths.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python3 -m unittest tests.test_frontend_timeline tests.test_frontend_if_contract -v`

Expected: all tests pass.

### Task 3: Verify, commit, and deploy

**Files:**
- Modify: `web/index.html`
- Create: `tests/test_frontend_timeline.py`

- [ ] **Step 1: Run full verification**

Run:

```bash
python3 -m unittest discover -s tests -q
python3 -m py_compile tests/*.py scripts/*.py
bash -n scripts/*.sh
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 2: Parse the JSX**

Use the installed Node/Acorn JSX runtime to parse the Babel script from `web/index.html`.

Expected: `JSX parse OK`.

- [ ] **Step 3: Commit**

```bash
git add web/index.html tests/test_frontend_timeline.py
git commit -m "feat: show articles as an all-date timeline"
```

- [ ] **Step 4: Deploy only the changed frontend and tests**

Back up `/projects/daily-insights`, rsync `web/index.html` and `tests/test_frontend_timeline.py`, run the remote full test suite, restart `daily-insights.service`, and verify the public page plus `/api/domains`. Do not modify or delete historical `data/`.
