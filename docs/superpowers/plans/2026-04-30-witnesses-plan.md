# Plan 1.2.5 — Witnesses as First-Class Entities

**Status:** SHIPPED — 2026-04-30 on branch `ux-witnesses-help-snippet`

## Summary

Witnesses and WitnessStatements are now first-class entities in CasePulse. Previously, `Argument.argument_type = Witness` existed but witness *identity* lived only in the reasoning text. This plan promotes witnesses to their own schema, models, repository, and UI page.

## Entities added

### witnesses
- `id, case_id, name, relationship, witness_type, contact_info, status, notes, created_at, updated_at`
- `witness_type`: character / fact / both
- `status`: initial / contacted / willing / hostile / subpoenaed / unavailable

### witness_statements
- `id, witness_id, statement_text, statement_date, contradiction_id, argument_id, status, created_at`
- `status`: draft / reviewed / locked
- FK to `contradictions(id)` ON DELETE SET NULL
- FK to `arguments(id)` ON DELETE SET NULL

## Files added/modified

| File | Change |
|---|---|
| `casepulse/storage/database.py` | Appended two tables + 6 indices to `SCHEMA` |
| `casepulse/case_theory/models.py` | Added `WitnessType`, `WitnessStatus`, `WitnessStatementStatus`, `Witness`, `WitnessStatement` |
| `casepulse/case_theory/repository.py` | Added 10 CRUD functions for witnesses + statements |
| `pages/4A_Witnesses.py` | New page (alphanumeric position between Cases and Documents) |
| `casepulse/case_theory/ui/argument_editor.py` | Shows "Linked witness statements" section for Witness-type arguments |
| `tests/storage/test_schema_migrations.py` | `test_witnesses_schema`, `test_witness_statements_schema` |
| `tests/case_theory/test_models.py` | `test_witness_model`, `test_witness_statement_model` + coercion tests |
| `tests/case_theory/test_repository.py` | 8 new tests covering full CRUD + case scoping + cascade delete |
| `tests/case_theory_ui/test_witnesses_smoke.py` | 4 AppTest smoke tests for the Witnesses page |
| `tests/case_theory_ui/test_workbench_smoke.py` | `test_argument_witness_statement_link` |

## Test count
- Before: 119 passing, 2 skipped
- After: 140 passing, 2 skipped (+21 tests)

## Plan 1.3 notes
- The brief renderer (`brief_renderer.py`) should call `list_statements_for_argument(db, argument_id)` when rendering Witness-type arguments, attributing each statement to the witness by name and relationship.
- Witness status (willing / hostile / subpoenaed) should drive risk flags in trial-preparation exports.
- `active_case_id` is written back to `st.session_state` from the Witnesses page picker (this was a bug in Plans 1.1/1.2 on Search + Documents).
