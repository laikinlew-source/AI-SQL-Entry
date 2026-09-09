# Production Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, resumable production coordinator that processes real invoice PDFs through the existing pipeline, assigns exactly one production state, generates read-only evidence and Get File 3 files, and never writes to SQL Account.

**Architecture:** A new `production_validation` module owns configuration, stable-file discovery, duplicate/resume indexes, state publication, exception reports, and dashboard aggregation. It calls existing `process_invoice_pdf` and existing snapshot/package validators through injected interfaces, so business rules remain outside the coordinator. A small CLI wrapper provides one-shot and polling modes; polling repeats the deterministic one-shot operation.

**Tech Stack:** Python 3.10+, standard library, existing `openpyxl` package, `unittest`, `Decimal`, atomic JSON writes, temporary directories, and controlled clocks in tests.

**Spec:** `docs/superpowers/specs/2026-09-09-production-validation-design.md`

## Global Constraints

- Process only physical PDFs from the configured intake folder; never generate demo or fictional invoice data.
- Terminal lifecycle states are exactly `READY`, `FAILED`, `REVIEW`, and `DUPLICATE`.
- Keep the existing OCR, canonical JSON, local snapshot, validation, and Get File 3 contracts backward compatible.
- SQL Account access remains file generation only; no API, database, UI automation, import, or posting path may be added.
- All run and state artifacts are timestamped, append-only, and never overwritten.
- Decimal arithmetic and existing template validation remain authoritative.
- Tests use temporary directories, fake OCR commands, fixed clocks, and local snapshots; no test reads the real OneDrive intake.

---

## Task 1: Production configuration and run layout

**Files:**
- Create: `config/production_validation.json`
- Create: `src/ai_sql_entry/production_validation.py`
- Create: `tests/test_production_validation.py`

**Interfaces:**
- `ProductionConfig` is a frozen dataclass containing `project_root`, `incoming_dir` (`incoming/`), `production_dir` (`production/`), `quarantine_dir` (`quarantine/`), `archive_dir` (`archive/`), `history_dir` (`output/production-history/`), `diagnostics_dir` (`diagnostics/`), `poll_interval_seconds`, `stability_seconds`, `supported_extensions`, `retry_failed`, `snapshot_version`, `validation_version`, and `import_package_version`.
- `load_production_config(path: Path | None, project_root: Path | None = None) -> ProductionConfig` reads JSON and resolves project-relative paths.
- `ensure_production_roots(config: ProductionConfig) -> None` creates only the configured production roots.
- `create_run_id(now: datetime, token: str) -> str` returns `YYYYMMDDTHHMMSSZ-<token>`.
- `discover_invoice_files(config: ProductionConfig) -> tuple[Path, ...]` returns sorted physical PDFs only.

- [ ] **Step 1: Write failing tests for configuration and run layout.** Test default folder names, relative-path resolution, rejection of negative polling/stability values, unsupported extensions, sorted case-insensitive PDF discovery, exclusion of directories/non-PDFs, and collision-safe run IDs with a fixed timestamp.

```python
def test_loads_default_production_roots_and_discovers_only_pdfs(tmp_path: Path) -> None:
    config = load_production_config(None, project_root=tmp_path)
    ensure_production_roots(config)
    (config.incoming_dir / "b.PDF").write_bytes(b"pdf")
    (config.incoming_dir / "a.txt").write_text("ignore", encoding="utf-8")
    (config.incoming_dir / "folder.pdf").mkdir()
    assert [path.name for path in discover_invoice_files(config)] == ["b.PDF"]
```

- [ ] **Step 2: Run the focused test and confirm it fails because the module/configuration does not exist.**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_production_validation.ProductionConfigurationTests -v`

Expected: import or attribute failure for `production_validation`.

- [ ] **Step 3: Implement the minimum configuration loader and root/discovery functions.** Use standard-library `json`, `Path`, and `datetime`; reject unknown lifecycle configuration and negative intervals; never create the legacy `invoices` directory implicitly.

- [ ] **Step 4: Run focused tests and the existing suite.**

Run: `$env:PYTHONPATH='src'; python -m unittest tests.test_production_validation.ProductionConfigurationTests -v` and then `python -m unittest discover -s tests -v`.

Expected: new tests and all existing tests pass.

- [ ] **Step 5: Review the diff and commit only Task 1 files after the task is green.**

Commit message: `feat: add production validation configuration`

## Task 2: Atomic history, audit, and duplicate indexes

**Files:**
- Modify: `src/ai_sql_entry/production_validation.py`
- Modify: `tests/test_production_validation.py`

**Interfaces:**
- `atomic_write_json(path: Path, payload: Mapping[str, object]) -> None` writes a UTF-8 JSON file through a sibling temporary file and `os.replace`.
- `load_resume_index(config: ProductionConfig) -> dict[str, object]` returns an empty validated index when no index exists.
- `record_resume_entry(config: ProductionConfig, entry: Mapping[str, object]) -> None` appends/replaces by source SHA-256 through an atomic write.
- `find_duplicate(canonical: Mapping[str, object], index: Mapping[str, object]) -> dict[str, object] | None` returns the prior entry and all matching keys—SHA-256, Invoice Number, Supplier, Invoice Date, and Total Amount—or `None`.
- `build_audit(canonical: Mapping[str, object], config: ProductionConfig, run_id: str, processed_at: str) -> dict[str, object]` returns the required provenance/version fields.

- [ ] **Step 1: Write failing tests for atomicity, duplicate reasons, and audit provenance.** Cover exact SHA matches, composite matches using normalized supplier/invoice/date/Decimal total, missing-key non-matches, deterministic index replacement, and snapshot/validation/package version fields.

```python
def test_duplicate_report_lists_every_matching_key(tmp_path: Path) -> None:
    canonical = canonical_fixture(document_id="new", sha256="a" * 64,
                                   supplier="Acorn Supplies", number="INV-1",
                                   issue_date="2026-09-09", total="106.00")
    index = {"entries": [{"source_sha256": "a" * 64,
                           "supplier": "Acorn Supplies", "invoice_number": "INV-1",
                           "invoice_date": "2026-09-09", "total_amount": "106.00",
                           "document_id": "old", "run_id": "prior"}]}
    duplicate = find_duplicate(canonical, index)
    assert duplicate["matching_keys"] == ["sha256", "invoice_number", "supplier", "invoice_date", "total_amount"]
```

- [ ] **Step 2: Run the focused tests and confirm failure.**

- [ ] **Step 3: Implement normalized comparison and atomic resume-index updates.** Normalize business strings using the same case/punctuation-insensitive convention already used by validation; use `Decimal` for totals; never treat absent values as equal.

- [ ] **Step 4: Run focused and existing tests.**

- [ ] **Step 5: Commit the green task.**

Commit message: `feat: add production duplicate and resume indexes`

## Task 3: Per-invoice outcomes and exception reports

**Files:**
- Modify: `src/ai_sql_entry/production_validation.py`
- Modify: `tests/test_production_validation.py`

**Interfaces:**
- `ProductionState = Literal["READY", "FAILED", "REVIEW", "DUPLICATE"]`.
- `InvoiceOutcome` is a frozen dataclass containing `state` (exactly `READY`, `FAILED`, `REVIEW`, or `DUPLICATE`), `document_id`, `source_path`, `source_sha256`, `run_id`, `artifact_dir`, `manifest_path`, `exception_report_path`, `processing_seconds`, and `review_status`.
- `exception_report(category: str, message: str, *, field_path: str | None, retryable: bool, operator_action: str, report_reference: str | None = None) -> dict[str, object]` returns sanitized structured findings for OCR_FAILURE, MISSING_FIELD, SUPPLIER_MISMATCH, TAX_MISMATCH, GL_MISMATCH, CURRENCY_MISMATCH, ARITHMETIC_MISMATCH, DUPLICATE, and MANUAL_REVIEW_REQUIRED.
- `write_invoice_manifest(path: Path, audit: Mapping[str, object], outcome: InvoiceOutcome, references: Mapping[str, str]) -> None` persists the per-invoice audit/state record.

- [ ] **Step 1: Write failing tests for all four terminal states and every required exception category.** Test that reports contain category, JSON Pointer or null, retryability, operator action, and no stderr/secrets; test one manifest per state and exactly one state directory.

```python
def test_exception_categories_are_structured_without_stderr() -> None:
    report = exception_report("OCR_FAILURE", "OCR did not produce readable text",
                              field_path=None, retryable=True,
                              operator_action="Inspect OCR runtime and retry.")
    assert report["category"] == "OCR_FAILURE"
    assert "stderr" not in report
```

- [ ] **Step 2: Run the focused tests and confirm failure.**

- [ ] **Step 3: Implement immutable outcome directories and sanitized exception/manifest writers.** Publish through a staging directory and atomic rename; do not overwrite a prior state directory.

- [ ] **Step 4: Run focused and existing tests.**

- [ ] **Step 5: Commit the green task.**

Commit message: `feat: add production invoice outcomes and exceptions`

## Task 4: Deterministic one-shot coordinator

**Files:**
- Modify: `src/ai_sql_entry/production_validation.py`
- Modify: `tests/test_production_validation.py`

**Interfaces:**
- `InvoiceProcessor = Callable[[Path, Path, datetime], PipelineResult]`.
- `run_production_once(config: ProductionConfig, *, now: datetime, processor: InvoiceProcessor | None = None) -> dict[str, object]` scans stable PDFs, resumes terminal hashes, invokes the existing pipeline, assigns states, writes reports, and returns the immutable run report.
- `classify_pipeline_artifacts(canonical: Mapping[str, object], package_report: Mapping[str, object]) -> tuple[ProductionState, list[dict[str, object]]]` maps extraction failures to `FAILED`, duplicates to `DUPLICATE`, unresolved review/mapping requirements to `REVIEW`, and fully passing package validation to `READY`.

- [ ] **Step 1: Write failing deterministic tests before implementation.** Use a fake processor that writes controlled canonical/package artifacts. Cover: READY with XLSX files and `ReadyForImport=YES`; FAILED for OCR/missing-field exception; REVIEW for incomplete review or missing mapping; DUPLICATE for exact and composite matches; no reprocessing after a terminal resume entry; changed hash processed as new; and run-specific directories.

```python
def test_run_production_once_assigns_all_four_states_and_resumes(tmp_path: Path) -> None:
    config = test_config(tmp_path)
    seed_ready_pdf(config.incoming_dir / "ready.pdf")
    seed_review_pdf(config.incoming_dir / "review.pdf")
    seed_failed_pdf(config.incoming_dir / "failed.pdf")
    seed_duplicate_pdf(config.incoming_dir / "duplicate.pdf")
    report = run_production_once(config, now=FIXED_NOW, processor=fake_processor)
    assert report["counts"] == {"READY": 1, "REVIEW": 1, "FAILED": 1, "DUPLICATE": 1}
    second = run_production_once(config, now=FIXED_NOW + timedelta(minutes=1), processor=fake_processor)
    assert second["processed"] == 0
```

- [ ] **Step 2: Run the focused tests and confirm failure.**

- [ ] **Step 3: Implement the coordinator against existing `process_invoice_pdf`, `JsonSnapshotProvider`, and `write_import_package`.** The default adapter must pass the configured timestamp and optional OCR commands without changing existing function signatures. Classify mapping mismatches and review gates as `REVIEW`; classify OCR, missing required extraction, arithmetic, template, and unexpected runtime failures as `FAILED`; do not produce workbooks for `DUPLICATE`.

- [ ] **Step 4: Run focused production tests plus all pre-existing tests.**

- [ ] **Step 5: Commit the green task.**

Commit message: `feat: add deterministic production coordinator`

## Task 5: Dashboard, metrics, and immutable run history

**Files:**
- Modify: `src/ai_sql_entry/production_validation.py`
- Modify: `tests/test_production_validation.py`

**Interfaces:**
- `calculate_production_metrics(outcomes: Sequence[InvoiceOutcome], reports: Sequence[Mapping[str, object]]) -> dict[str, object]` returns counts, coverage, missing mappings, processing-time average, and `not_measurable` accuracy fields when no ground truth exists. Audit reports include source filename, SHA-256, processing timestamp, parser version, snapshot version, validation version, import-package version, and review status.
- `write_production_reports(config: ProductionConfig, run_report: Mapping[str, object]) -> dict[str, Path]` writes timestamped JSON/Markdown reports and a current `production_dashboard.md` projection without replacing timestamped history.

- [ ] **Step 1: Write failing tests for dashboard counts and metrics.** Assert all four state counts, supplier/tax/GL/currency coverage, missing-mapping counts, average processing time, explicit non-measurable accuracy, current dashboard content, and preservation of two distinct history directories across two runs.

- [ ] **Step 2: Run focused tests and confirm failure.**

- [ ] **Step 3: Implement metrics and reports with denominator-zero `null` plus reason.** Preserve provenance and audit fields in run reports; use stable ordering for deterministic output.

- [ ] **Step 4: Run focused and existing tests.**

- [ ] **Step 5: Commit the green task.**

Commit message: `feat: add production validation dashboards`

## Task 6: Polling CLI and configuration documentation

**Files:**
- Create: `src/ai_sql_entry/production_cli.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `docs/001-Project-Vision.md`
- Modify: `docs/002-System-Architecture.md`
- Modify: `docs/003-Development-Workflow.md`
- Create: `docs/010-Production-Validation-Guide.md`
- Create: `docs/roadmap.md`
- Modify: `tests/test_production_cli.py`

**Interfaces:**
- `ai-sql-production [--config PATH] [--once] [--watch] [--poll-seconds N]` runs one deterministic pass or repeats it; default is `--once`.
- `production_cli.main(argv: Sequence[str] | None = None, *, runner=run_production_once, sleeper=time.sleep) -> int` is testable without sleeping or touching real paths.

- [ ] **Step 1: Write failing CLI and documentation-contract tests.** Test `--once`, rejection of both `--once` and `--watch`, fixed injected runner invocation, nonzero status for configuration errors, and required documentation terms: four states, production folders, resume, duplicate keys, dashboard, no SQL Account writes.

- [ ] **Step 2: Run focused tests and confirm failure.**

- [ ] **Step 3: Implement the CLI entry point and add `ai-sql-production` to `pyproject.toml`.** Polling must call the same one-shot function, sleep only after a completed pass, and stop cleanly on `KeyboardInterrupt` without changing invoice state.

- [ ] **Step 4: Update documentation without contradicting Version 1 exclusions.** Describe the production coordinator as local file orchestration; retain SQL Account UI/database/API exclusions and document the exact output/state layout and operator review boundary.

- [ ] **Step 5: Run focused tests and all existing tests.**

- [ ] **Step 6: Commit the green task.**

Commit message: `docs: document production validation operation`

## Task 7: Full verification and delivery

**Files:**
- Modify only milestone files listed in Tasks 1–6.
- Do not stage unrelated pre-existing changes in documentation, archive, or diagnostics folders.

- [ ] **Step 1: Run unit and integration tests.**

Run: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v`

Expected: all tests pass with no unexpected failures.

- [ ] **Step 2: Run deterministic repeatability checks.** Execute the production runner twice against the same temporary fixture with the same fixed clock; compare normalized JSON reports and confirm terminal hashes are skipped on the second run.

- [ ] **Step 3: Run compilation and documentation validation.**

Run: `$env:PYTHONPATH='src'; python -m compileall -q src`; parse every JSON configuration/example/report fixture; verify documentation references existing paths and contains no contradictory state or SQL-write claims.

- [ ] **Step 4: Run repository integrity checks.** Verify `git diff --check`, `git status --short`, current branch, remote, and that no SQL Account database/UI/API/write code was added. Inspect the staged diff and ensure no real invoice or secret is staged.

- [ ] **Step 5: Commit the complete verified milestone and push `main`.**

Commit message: `feat: add production validation framework`

- [ ] **Step 6: Report completion.** Include implementation summary, test summary, performance metrics from the deterministic run, remaining risks, generated report locations, commit hash, push result, and recommended next milestone.
