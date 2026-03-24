# Auth And Selfstock Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove browser auth, plaintext password caching, and the legacy selfstock protocol while making selfstock detail enrichment non-fatal.

**Architecture:** Simplify authentication to explicit credentials or explicit cookies only, keep cookie caching limited to session cookies, and collapse self-stock support onto the v2 cookie API. Treat selfstock detail enrichment as optional metadata layered on top of the primary group data.

**Tech Stack:** Python, pytest, uv, requests

---

### Task 1: Remove Browser Auth Surface

**Files:**
- Modify: `pyproject.toml`
- Modify: `auth.py`
- Modify: `main.py`
- Delete: `cookie.py`
- Modify: `tests/test_auth_session_manager.py`
- Modify: `tests/test_main_cli_auth_defaults.py`

- [ ] **Step 1: Write the failing tests**

Add tests that assert:
- CLI no longer accepts `--auth-method browser`
- CLI no longer accepts `--browser`
- `SessionManager(auth_method='browser')` is rejected

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_main_cli_auth_defaults.py tests/test_auth_session_manager.py`

- [ ] **Step 3: Write minimal implementation**

Remove browser-specific CLI flags, dependency wiring, and `SessionManager` browser resolution logic.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_main_cli_auth_defaults.py tests/test_auth_session_manager.py`

- [ ] **Step 5: Commit**

Commit message: `refactor: remove browser auth flow`

### Task 2: Remove Plaintext Password Cache And Legacy Selfstock Protocol

**Files:**
- Modify: `auth.py`
- Modify: `storage.py`
- Modify: `api.py`
- Modify: `service.py`
- Modify: `tests/test_auth_session_manager.py`
- Modify: `tests/test_selfstock_protocol.py`

- [ ] **Step 1: Write the failing tests**

Add tests that assert:
- credential login cache entries do not persist `password`
- legacy selfstock helpers are gone and v2 upload path remains intact

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_auth_session_manager.py tests/test_selfstock_protocol.py tests/test_selfstock_service.py`

- [ ] **Step 3: Write minimal implementation**

Delete plaintext password persistence, remove old-protocol helpers, and delete service-layer compatibility that only supported them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_auth_session_manager.py tests/test_selfstock_protocol.py tests/test_selfstock_service.py`

- [ ] **Step 5: Commit**

Commit message: `refactor: drop legacy selfstock protocol`

### Task 3: Decouple Selfstock Detail Enrichment And Refresh Docs

**Files:**
- Modify: `service.py`
- Modify: `README.md`
- Modify: `TUTORIAL.md`
- Modify: `tests/test_selfstock_service.py`

- [ ] **Step 1: Write the failing tests**

Add tests that assert:
- `get_all_groups()` still returns parsed groups when `refresh_selfstock_detail()` fails
- `get_self_stocks()` still returns self-stock items when metadata refresh fails

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_selfstock_service.py`

- [ ] **Step 3: Write minimal implementation**

Wrap enrichment refresh in non-fatal handling and update docs to describe the new auth model and selfstock behavior.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_selfstock_service.py`
Run: `uv run pytest -q`

- [ ] **Step 5: Commit**

Commit message: `fix: make selfstock detail enrichment optional`
