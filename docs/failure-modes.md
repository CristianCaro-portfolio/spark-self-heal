# Failure Modes Catalog

This catalog documents the deliberate failure modes injected into the
transactions ETL pipeline. Each mode is what the self-healing agent
(see Phase 4) is trained to diagnose and propose patches for.

## Reading this catalog

Each entry follows the format:

- **ID**: stable identifier (FM-XX) used across the codebase, tests, and
  the agent's prompts.
- **Class**: `hard` if the Glue Job exits with a non-zero status; `silent`
  if the job commits successfully but the output is contaminated or
  incomplete. The agent must handle both classes, with different signals.
- **Symptom**: what an operator sees in CloudWatch logs / Athena queries.
- **Root cause**: the actual data condition causing it.
- **Detection signal**: the deterministic check the agent uses to confirm
  the diagnosis (vs. guessing).
- **Proposed remediation**: what the agent should suggest in a PR.

## Background: why two failure classes

An early empirical run revealed that several assumptions baked into the
first version of `transactions_etl.py` did not hold:

1. **Spark JSON `.schema(...)` silently drops unexpected fields.** It
   does NOT raise, even with `mode=FAILFAST`. `FAILFAST` only triggers on
   records that violate the declared schema at the type level
   (e.g. a string where an int is required); extra fields are tolerated
   by design.
2. **`StructField(nullable=False)` is informational metadata.** Neither
   the JSON reader nor the Parquet writer enforces it at runtime.
   Records with `null` on a declared non-nullable column are read,
   written, and queried without warnings.

As a result, the first version of the job processed all six broken
datasets successfully (exit code 0), with partial silent data loss. To
make FM-01 and FM-06 reproducible as hard failures — and therefore
usable as end-to-end tests for the agent — the job was hardened with
two explicit guards (see `pipelines/jobs/transactions_etl.py`):

- a **schema-drift probe** that reads JSON without a schema, diffs the
  observed columns against the expected set, and raises if either side
  differs;
- a **non-null guard** that asserts no `null` values exist in columns
  declared `nullable=False`, after the typed read.

The catalog below reflects the behavior of the **hardened** job.

---

## FM-01 · Schema drift (new unexpected field)

| Aspect | Detail |
|---|---|
| Class | `hard` (after hardening; silent in unhardened code) |
| Source file | `data/broken/01_schema_drift.json` |
| Symptom | Glue Job state is `FAILED`. `ErrorMessage` starts with `RuntimeError: Schema drift detected at s3://...` and includes a list of `unexpected` columns. |
| Root cause | The upstream system began emitting a new field (`fraud_score`) not declared in `TRANSACTION_SCHEMA`. Spark's `.schema(...)` would silently drop it; the schema-drift probe in step 3.a of the job catches the divergence by reading once without a schema and diffing columns. |
| Detection signal | Glue `ErrorMessage` contains the literal `Schema drift detected` AND a non-empty `unexpected=[...]` list. The list itself names the new field(s). |
| Proposed remediation | Two options for the agent to evaluate: (a) add the new field to `TRANSACTION_SCHEMA` as `nullable=True` (forward-compatible, recommended default); (b) extend the probe's allow-list to ignore the new field temporarily and quarantine its values for human review. The agent should prefer (a) unless the new field is known to be a leak from a different domain. |

## FM-02 · Invalid currency codes

| Aspect | Detail |
|---|---|
| Class | `silent` |
| Source file | `data/broken/02_invalid_currency.json` |
| Symptom | Job exits `SUCCEEDED`. `count(*)` in silver drops by ~10% vs. raw. Athena queries on `currency` show only valid ISO codes because the allow-list filter silently dropped the bad ones. |
| Root cause | Upstream produced non-ISO-4217 codes (`XX`, `DOLLAR`, `us`, `Bitcoin`, empty string). The `currency.isin(VALID_CURRENCIES)` filter dropped them without surfacing the values. |
| Detection signal | Log line `dropped N invalid records` shows N > 0, AND in a follow-up probe of the raw JSON the agent finds `currency` values outside `VALID_CURRENCIES`. |
| Proposed remediation | (a) Normalize obvious typos (`us` → `USD`) in a pre-filter step; (b) route truly invalid records to a quarantine prefix in S3 for human review; (c) alert the upstream team. Default: implement a normalization function for known typos and quarantine the rest. |

## FM-03 · Negative amounts

| Aspect | Detail |
|---|---|
| Class | `silent` |
| Source file | `data/broken/03_negative_amount.json` |
| Symptom | `count(*)` in silver drops by ~5% vs. raw. Refund-like transactions are missing. |
| Root cause | Upstream encodes refunds with a negative `amount` and `status='refunded'`. The `amount > 0` filter is too strict — it rejects legitimate refunds. |
| Detection signal | Raw probe of the dropped records shows `status='refunded'` correlated with `amount < 0`. |
| Proposed remediation | Soften the filter to `amount != 0`, OR conditionally allow negatives when `status='refunded'`. Default: conditional allow, since negative refunds are legitimate domain data. |

## FM-04 · Malformed timestamps

| Aspect | Detail |
|---|---|
| Class | `silent` |
| Source file | `data/broken/04_malformed_timestamps.json` |
| Symptom | `count(*)` in silver drops by ~15% vs. raw. No errors at parse time — the values become `NULL` and the null filter drops them. |
| Root cause | Upstream emits multiple timestamp formats: ISO, `dd/mm/yyyy`, compact `YYYYMMDDTHHMMSS`. The single-format `to_timestamp` returns `NULL` for non-matching strings; the null filter then drops them. |
| Detection signal | Compare raw count vs. count after timestamp parsing; if the delta exceeds ~5%, suspect format drift. Sampling raw `created_at` strings reveals non-ISO patterns. |
| Proposed remediation | Add a multi-format parser using `coalesce` over several `to_timestamp` calls. Default: implement multi-format parsing for the 3 known variants. |

## FM-05 · Duplicate transaction_id

| Aspect | Detail |
|---|---|
| Class | `silent` (this is correct behavior, not a defect) |
| Source file | `data/broken/05_duplicate_ids.json` |
| Symptom | `count(*)` in silver is slightly lower than raw (5 in the canonical test). |
| Root cause | Upstream re-emitted records (network retries, double-publish). `dropDuplicates(["transaction_id"])` correctly removed them but silently. |
| Detection signal | Log line `removed N duplicate transaction_id(s)` with N > 0. |
| Proposed remediation | This is correct behavior. The agent's job here is to confirm the dedup is intentional and document it. If the duplicate count spikes (>1% of input), escalate as an upstream incident. |

## FM-06 · Null required fields

| Aspect | Detail |
|---|---|
| Class | `hard` (after hardening; partially silent in unhardened code) |
| Source file | `data/broken/06_null_required_fields.json` |
| Symptom | Glue Job state is `FAILED`. `ErrorMessage` starts with `RuntimeError: Non-null constraint violated on required columns:` followed by a dictionary mapping each violating column to its null count, e.g. `{'merchant_id': 4, 'customer_id': 10, 'amount': 3, 'currency': 3}`. |
| Root cause | Upstream produced records with missing values on declared non-nullable columns (`merchant_id`, `customer_id`, `amount`, `currency`). Spark's `nullable=False` is metadata only; the non-null guard in step 3.c of the job converts the violation into a hard, attributable failure. |
| Detection signal | Glue `ErrorMessage` contains the literal `Non-null constraint violated` AND a dictionary listing the offending columns with their null counts. The dictionary directly identifies which fields to quarantine or repair. |
| Proposed remediation | (a) Quarantine records with nulls on required fields to a `_rejected/` prefix and continue processing the rest; (b) repair the upstream contract so the source never emits nulls on those columns; (c) re-classify the columns as `nullable=True` if business rules actually permit nulls (rare). Default: (a), since it preserves data lineage and is reversible. |

---

## Failure modes NOT covered (future work)

These are realistic failure modes the project does NOT currently
exercise. They would be valuable additions in extended iterations:

- **Timezone confusion** — the same event with `created_at` in local
  time vs. UTC, leading to ambiguous reconciliation.
- **Floating-point amount precision** — sums of many `Double` amounts
  losing cents. Should use `Decimal(18, 2)` in production.
- **Late-arriving data** — records arriving days after their
  `created_at`, breaking partition assumptions.
- **Skew on `country_code`** — one country dominates 90% of volume,
  causing Spark partition skew.
- **OOM on large partitions** — single-partition operations exceeding
  executor memory.

These could be added to the dataset generator and catalog in later
iterations.

---

## How the agent uses this catalog (preview of Phase 4)

When the Glue Job fails or produces anomalous output:

1. The agent reads the failure record JSON captured by Airflow's
   `on_failure_callback` (in `airflow/logs/failures/`) and uses
   `glue_job_run_id` to fetch the matching CloudWatch logs.
2. It classifies the failure:
   - if Glue state is `FAILED`, the failure is `hard` → match the
     `ErrorMessage` against the **Detection signal** of each
     `class: hard` FM.
   - if Glue state is `SUCCEEDED` but downstream signals (row counts,
     Athena assertions) indicate data loss, the failure is `silent` →
     match log counters against the `class: silent` FMs.
3. The first FM whose detection signal matches is hypothesized as the
   root cause.
4. The agent reads the corresponding **Proposed remediation**.
5. It generates a code patch (PySpark diff) and opens a PR on GitHub.
6. The PR description includes: identified FM, evidence from logs and
   the captured failure record, proposed change, and reasoning.

This catalog is therefore both documentation AND the agent's grounding
data.
