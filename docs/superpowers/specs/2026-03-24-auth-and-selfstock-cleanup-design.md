# THS Auth And Selfstock Cleanup Design

**Context**

The current project mixes three authentication strategies (`browser`, `credentials`, `none`), persists plaintext passwords in the local cookie cache, and still carries the deprecated `selfstock.php` protocol alongside the newer cookie-based self-stock API. Group listing also treats `selfstock_detail` enrichment as a hard dependency, which can break the primary listing flow.

**Goals**

- Remove browser-based cookie loading entirely.
- Keep only explicit credentials login and explicit cookie injection.
- Stop persisting plaintext passwords locally.
- Delete the deprecated `selfstock.php` protocol and related compatibility code.
- Make `selfstock_detail` enrichment best-effort so group listing still works when enrichment fails.
- Update CLI, tests, and Chinese documentation to match the simplified model.

**Non-Goals**

- No new authentication mode or background login refresh logic.
- No attempt to preserve browser-based workflows.
- No large refactor outside the touched authentication, self-stock, and documentation boundaries.

**Design**

## Authentication Surface

`SessionManager` will support only:

- `auth_method='credentials'`: perform explicit username/password login and cache only cookies.
- `auth_method='none'`: skip login resolution and rely on provided cookies or later manual injection.

The implicit `auto` path and `browser` path will be removed. CLI callers must now explicitly provide credentials for login-based flows.

## Cookie Cache

The cookie cache remains useful for storing reusable session cookies, but it will no longer store plaintext passwords. Cache reads and writes will operate only on cookie payload plus timestamp.

## Self-Stock Protocol

The codebase will keep only the newer cookie-based v2 self-stock API. Deprecated old-protocol helpers and any service-layer code that exists only to support them will be deleted.

## Group Enrichment Failure Handling

`PortfolioManager.get_all_groups()` should always treat group query as the primary source of truth. After groups are fetched, `selfstock_detail` enrichment should run as a best-effort step:

- success: attach price and added-time metadata as before
- failure: log and continue returning the fetched groups without enrichment

The same rule applies when refreshing self-stock items: enrichment must not block the core result.

## Documentation

README and tutorial content will be updated to describe only:

- explicit credentials login
- explicit cookie injection
- optional cookie reuse through cached session cookies

All browser-installation and browser-auth examples will be removed. Legacy old-protocol references will also be removed.

**Implementation Sequence**

1. Remove browser auth flags, config, optional dependency, tests, and docs references.
2. Remove plaintext password caching and deprecated `selfstock.php` helpers.
3. Decouple `selfstock_detail` enrichment from the primary listing path and update related docs/tests.

**Verification**

- Add or update targeted tests before each behavior change.
- Run focused tests during each step.
- Run the full test suite at the end.
