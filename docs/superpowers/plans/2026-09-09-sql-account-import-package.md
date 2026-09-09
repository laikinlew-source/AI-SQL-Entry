# SQL Account Import Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a fail-closed, read-only Purchase Invoice package for SQLAccXLSnMDBImp Get File 3 using approved canonical JSON and local master-data snapshots.

**Architecture:** Extend the existing source-independent master-data validator into a mapping and readiness report, then pass only successful mappings to a focused XLSX package writer. A separate template validator reads the generated workbooks back and verifies their fixed contract before the package receives `ReadyForImport = YES`.

**Tech Stack:** Python 3.10+, standard library, `decimal.Decimal`, `openpyxl`, `unittest`/pytest.

**Spec:** User-approved requirements in the 2026-09-09 task conversation; no parallel architecture document.

## Global Constraints

- Target only SQLAccXLSnMDBImp `Get File 3` with separate Header and Detail XLSX files.
- Never access the SQL Account database, automate its UI, or post accounting data.
- Never fabricate missing business values or master-data mappings.
- Preserve source provenance in reports and in non-mapped workbook columns.
- Generate a package only from existing canonical JSON and editable local snapshots.

---

### Task 1: Mapping and readiness validation

**Files:**
- Modify: `src/ai_sql_entry/sql_account_validation.py`
- Modify: `tests/test_sql_account_validation.py`

**Interfaces:**
- Consumes: canonical JSON and `SqlAccountMasterData`.
- Produces: a detailed mapping report and arithmetic/readiness component results.

- [ ] Write failing tests for effective reviewed values, complete missing mappings, totals, SST, line totals, and OCR score.
- [ ] Run the focused tests and confirm they fail because the new report fields do not exist.
- [ ] Implement the smallest source-independent mapping/readiness functions.
- [ ] Run the focused tests and the existing validation tests.

### Task 2: Fixed Get File 3 workbook contract and validator

**Files:**
- Create: `src/ai_sql_entry/sql_account_template.py`
- Create: `tests/test_sql_account_template.py`

**Interfaces:**
- Consumes: two workbook paths and the fixed header/detail contract.
- Produces: structured checks for sheet name, columns, order, required values, `dd/mm/yyyy`, numeric cells, and common keys.

- [ ] Write failing tests for valid workbooks and each required validation failure.
- [ ] Run the focused tests and confirm the module is missing.
- [ ] Implement the fixed contract and workbook validator using `openpyxl` read-only mode.
- [ ] Run the focused tests.

### Task 3: Import package writer and reports

**Files:**
- Replace: `src/ai_sql_entry/sql_account_export.py`
- Modify: `tests/test_sql_account_export.py`

**Interfaces:**
- Consumes: canonical JSON, mapping report, validation timestamp, and output directory.
- Produces: `Purchase Invoice Header.xlsx`, `Purchase Invoice Detail.xlsx`, `Mapping_Report.json`, `Validation_Report.json`, `Import_Checklist.md`, and `Import_Summary.md`.

- [ ] Write failing tests for exact filenames, sheets, columns, key consistency, provenance, decimal cells, and fail-closed output.
- [ ] Run focused tests and confirm failure against the legacy CSV preview writer.
- [ ] Implement the package writer without fallbacks or placeholder business values.
- [ ] Read both workbooks back through the template validator before setting readiness.
- [ ] Run focused tests.

### Task 4: Pipeline integration

**Files:**
- Modify: `src/ai_sql_entry/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: the existing canonical artifact and local snapshot provider.
- Produces: the import package under the document artifact directory, including a non-ready report when mappings fail.

- [ ] Write a failing pipeline test for the six required package files and `ReadyForImport = NO` with empty snapshots.
- [ ] Run the focused test and confirm failure against legacy filenames.
- [ ] Integrate mapping, validation, and package writing while preserving existing result fields.
- [ ] Run pipeline tests.

### Task 5: Full verification and delivery

**Files:**
- Verify only the files listed above and this plan.

- [ ] Run the complete automated test suite.
- [ ] Generate a package from the test canonical invoice with controlled local snapshots.
- [ ] Parse every JSON report and read back both XLSX files.
- [ ] Confirm no SQL/database/UI code or generated business data was added.
- [ ] Review `git diff` and stage only milestone files, leaving pre-existing dirty files untouched.
- [ ] Commit and push only after every verification succeeds.
