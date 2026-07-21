# AI-SQL-Entry Development Workflow

## Purpose

This document defines how AI-SQL-Entry is changed. It applies to documentation, application code, tests, configuration, schemas, and migration utilities. Version 1 development must preserve the scope and architectural boundaries in `001-Project-Vision.md` and `002-System-Architecture.md`.

## Authority and change order

When requirements conflict, use this order:

1. Explicitly approved Version 1 scope and exclusions.
2. System architecture and safety boundaries.
3. Feature-specific design and acceptance criteria.
4. Implementation plan.
5. Source code and tests.

Do not implement a feature until its behavior, inputs, outputs, failure modes, and acceptance criteria are documented and reviewed. A scope change requires updating the relevant documentation before or with the implementation.

## Coding standards

### Python baseline

- Support Python 3.10 or later, consistent with `pyproject.toml`.
- Use UTF-8 text files and platform-independent paths through `pathlib`.
- Use four spaces for indentation and follow PEP 8 naming conventions.
- Add type annotations to public functions, methods, and data structures.
- Prefer small modules with one clear responsibility and explicit interfaces.
- Keep filesystem, AI/OCR provider, clock, and user-interface dependencies behind replaceable boundaries.
- Prefer standard-library features unless a dependency provides clear, documented value.
- Do not hide failures with broad exception handling. Catch expected exceptions at the boundary that can handle them.

### Models and data

- Use explicit models for manifests, extraction results, validation findings, review decisions, and audit events.
- Version persisted JSON schemas from their first committed implementation.
- Represent money with decimal-safe types, never binary floating point.
- Preserve source values separately from normalized and human-corrected values.
- Store persisted timestamps and audit-log timestamps in UTC with timezone information; convert them to local time only for display.
- Treat original file bytes as immutable.

### Logging

- Prefer structured events with a timestamp, event type, document identifier, stage, and outcome.
- Do not log full document contents, secrets, or unnecessary personal/accounting data.
- Never rely on logs as the only record of document state.
- Include actionable context while preserving the original exception chain for maintainers.

### Tooling

The implementation phase should standardize formatting and linting with Ruff, type checking with mypy, and testing with pytest. Tool versions and configuration must be pinned or bounded in project metadata before they become required in continuous integration. The documentation phase does not install these tools or add application dependencies.

## Testing standards

- Use test-driven development for behavior changes: demonstrate the missing behavior with a failing test, implement the smallest correct change, then refactor with tests passing.
- Unit-test pure parsing, normalization, validation, hashing, and state-transition logic.
- Integration-test filesystem moves, interrupted-copy handling, PDF rendering, multi-page ordering, and artifact grouping in temporary directories.
- Contract-test each AI/OCR adapter with sanitized, stored responses so routine tests do not require network access or nondeterministic inference.
- Use non-sensitive sample documents. Never commit real supplier, customer, financial, email, or WhatsApp data.
- Test success, low-confidence output, missing fields, corrupt files, unsupported formats, duplicate files, locked files, partial copies, name collisions, interrupted runs, and recovery.
- A test must assert externally meaningful behavior, not private implementation detail, unless the detail is a safety invariant.

## Git workflow

### Branches

- `main` contains reviewed, coherent work and must remain in a usable state.
- Create short-lived branches from the latest `main`.
- Use descriptive names such as `docs/review-workflow`, `feature/intake-stability`, or `fix/duplicate-collision`.
- Keep one logical change per branch. Do not mix unrelated cleanup with feature work.

### Commits

- Make small, reviewable commits that each leave the repository consistent.
- Use an imperative Conventional Commit-style subject, for example `docs: define review workflow`, `feat: add file stability guard`, or `fix: preserve duplicate originals`.
- Explain safety-sensitive or non-obvious decisions in the commit body.
- Do not commit generated runtime data, logs, secrets, local documents, model weights, virtual environments, or editor state.
- Do not rewrite shared history without explicit agreement.

### Review and integration

Before integration:

1. Rebase or merge the current `main` according to the team's chosen policy.
2. Run all required formatting, linting, type-checking, and test commands.
3. Review the diff for scope, sensitive data, generated artifacts, and accidental dependency changes.
4. Confirm documentation and acceptance criteria still match the implementation.
5. Obtain review for changes affecting lifecycle transitions, originals, duplicate detection, financial calculations, schemas, or security boundaries.
6. Merge only when checks pass and review comments are resolved.

## Implementation rules

All Version 1 implementation must follow these rules:

1. **No SQL Account integration:** Do not automate its UI, write to its database, or claim that approved JSON has been entered.
2. **Local-only operation:** Do not send documents, extracted data, or derived images to external services.
3. **Manual external intake:** Email and WhatsApp files arrive only through user download or save actions.
4. **Preserve originals:** Never edit or overwrite the original file.
5. **Verify stable input:** Do not claim a file until copying/downloading has completed and it can be read safely.
6. **Use explicit lifecycle transitions:** Do not infer completion only from file presence or create two authoritative copies in different state folders.
7. **Never overwrite silently:** Use unique document identifiers, collision checks, and safe destination creation.
8. **Make processing restart-safe:** Repeated detection or restart must not create duplicate approvals or lose the current state.
9. **Hash original bytes:** Use SHA-256 as the exact-duplicate key and retain enough metadata to explain duplicate decisions.
10. **Preserve page order:** Multi-page inputs and rendered pages must remain deterministically ordered.
11. **Version JSON:** Schema changes require an explicit version and compatibility or migration decision.
12. **Expose uncertainty:** Retain confidence and validation findings; do not turn uncertain AI/OCR output into an asserted fact.
13. **Require human approval:** No document enters `completed/` merely because extraction or validation succeeded.
14. **Record corrections:** Preserve the extracted value and the reviewed value when a human changes a field.
15. **Fail safely:** Retain the original, record the stage and reason, and state whether retry is possible.
16. **Keep errors actionable:** User-facing errors explain what the operator can do; technical details remain available locally for diagnosis.
17. **Treat HEIC as conditional:** Enable it only with a tested local decoder and provide a clear conversion instruction otherwise.
18. **Protect sensitive data:** Use sanitized fixtures and avoid sensitive payloads in logs, tests, commits, and screenshots.
19. **Avoid premature scope:** Do not add alias learning, mailbox access, WhatsApp access, mobile upload, cloud deployment, or parallel-processing complexity in Version 1.
20. **Document irreversible decisions:** Persistence formats, schema contracts, state-transition semantics, and retention behavior require design review before implementation.

## Dependency rules

- Every runtime dependency must have a documented purpose and compatible license.
- Prefer maintained libraries with Windows support and deterministic local behavior.
- Pin or constrain versions so a fresh environment can be reproduced.
- AI/OCR models and HEIC/PDF codecs require explicit installation, licensing, storage, and offline-operation notes.
- A dependency must not introduce undeclared network calls or cloud fallbacks.
- Remove unused dependencies promptly.

## Feature development sequence

For each feature:

1. Confirm it belongs to Version 1.
2. Write or update the feature design and acceptance criteria.
3. Identify data-preservation, privacy, lifecycle, and recovery risks.
4. Create an implementation plan with exact files and verification commands.
5. Add a failing automated test where behavior can be tested.
6. Implement the smallest complete behavior.
7. Run focused tests, then the full required verification suite.
8. Review documentation, logs, error messages, and generated artifacts.
9. Commit the coherent change with a descriptive subject.
10. Obtain review and integrate according to the Git workflow.

## Definition of done

A Version 1 change is done only when:

- It satisfies documented acceptance criteria and remains within scope.
- New and existing tests pass.
- Formatting, linting, and type checks pass once those tools are configured.
- Failure and recovery paths have been exercised in proportion to risk.
- Original-file preservation and state-transition invariants remain intact.
- No sensitive or generated runtime data is staged in Git.
- Relevant documentation is consistent with the behavior.
- The working tree is clean after the intended commit.

## Documentation-only phase

At the end of the initial documentation phase, `src/` and `tests/` contain no application or test code. The only intended repository change is the approved documentation commit. Feature implementation begins only through a later, separately approved task.
