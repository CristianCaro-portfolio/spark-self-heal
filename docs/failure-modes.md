# Failure Modes Catalog

This catalog documents the deliberate failure modes injected into the
transactions ETL pipeline. Each mode is what the self-healing agent
(see Phase 4) is trained to diagnose and propose patches for.

## Reading this catalog

Each entry follows the format:

- **ID**: stable identifier (FM-XX) used across the codebase, tests, and
  the agent's prompts.
- **Symptom**: what an operator sees in CloudWatch logs / Athena queries.
- **Root cause**: the actual data condition causing it.
- **Detection signal**: the deterministic check the agent uses to confirm
  the diagnosis (vs. guessing).
- **Proposed remediation**: what the agent should suggest in a PR.

---

## FM-01 · Schema drift (new unexpected field)

| Aspect | Detail |
|---|---|
| Source file | `data/broken/01_schema_drift.json` |
| Symptom | Job fails at read time. CloudWatch shows `org.apache.spark.SparkException: Malformed records ... fields: [fraud_score]`. |
| Root cause | The upstream system began emitting a new field (`fraud_score`) not declared in the explicit `TRANSACTION_SCHEMA`. With `mode=FAILFAST`, Spark refuses to parse records that have unexpected fields. |
| Detection signal | Logs contain the literal substring `Malformed records detected` AND the offending field name. |
| Proposed remediation | Two options for the agent to evaluate: (a) add the new field to the schema as `nullable=True` (forward-compatible); (b) switch mode to `PERMISSIVE` and route bad records to a quarantine bucket. Default recommendation: option (a). |

## FM-02 · Invalid currency codes

| Aspect | Detail |
|---|---|
| Source file | `data/broken/02_invalid_currency.json` |
| Symptom | Job succeeds but `count(*)` drops by ~10%. Athena queries on currency show no surprise (the allow-list filter worked). Dropped records are silent. |
| Root cause | Upstream produced non-ISO-4217 codes (`XX`, `DOLLAR`, `us`, `Bitcoin`, empty string). The `currency.isin(VALID_CURRENCIES)` filter dropped them. |
| Detection signal | The job log line `dropped N invalid records` shows N > 0 AND a sample of the dropped records' currency values lies outside `VALID_CURRENCIES`. |
| Proposed remediation | (a) Normalize obvious typos (`us` → `USD`) in a pre-filter step; (b) route truly invalid records to quarantine for human review; (c) alert the upstream team. Default: implement a normalization function for known typos and quarantine the rest. |

## FM-03 · Negative amounts

| Aspect | Detail |
|---|---|
| Source file | `data/broken/03_negative_amount.json` |
| Symptom | `count(*)` drops by ~5%. Refund-like transactions are missing from silver. |
| Root cause | Upstream encodes refunds with a negative `amount` and `status='refunded'`. The `amount > 0` filter is too strict — it rejects legitimate refunds. |
| Detection signal | Logs show dropped records with `status='refunded'` AND `amount < 0`. |
| Proposed remediation | Soften the filter to `amount != 0`, OR conditionally allow negatives when `status='refunded'`. Default: conditional allow, since negative refunds are legitimate domain data. |

## FM-04 · Malformed timestamps

| Aspect | Detail |
|---|---|
| Source file | `data/broken/04_malformed_timestamps.json` |
| Symptom | `count(*)` drops by ~15%. No errors logged at parse time (silently NULL). |
| Root cause | Upstream emits multiple timestamp formats: ISO, `dd/mm/yyyy`, compact `YYYYMMDDTHHMMSS`. The single-format `to_timestamp` returns NULL for non-matching strings, and the NULL filter then drops them. |
| Detection signal | Compare raw count vs. count after timestamp parsing; if the delta exceeds 5%, suspect format drift. Sample raw `created_at` strings and check them against known patterns. |
| Proposed remediation | Add a multi-format parser using `coalesce` over several `to_timestamp` calls. Default: implement multi-format parsing for the 3 known variants. |

## FM-05 · Duplicate transaction_id

| Aspect | Detail |
|---|---|
| Source file | `data/broken/05_duplicate_ids.json` |
| Symptom | `count(*)` is lower than the input by a small number (5 in our test). |
| Root cause | Upstream re-emitted records (network retries, double-publish). `dropDuplicates(["transaction_id"])` correctly removed them but silently. |
| Detection signal | Log line `removed N duplicate transaction_id(s)` with N > 0. |
| Proposed remediation | This is correct behavior, NOT a failure. The agent's job here is to confirm the dedup is intentional and document it. If the duplicate count spikes (>1% of input), escalate as an upstream incident. |

## FM-06 · Null required fields

| Aspect | Detail |
|---|---|
| Source file | `data/broken/06_null_required_fields.json` |
| Symptom | Silent record drop after filtering. If `amount` is the null field, `amount > 0` evaluates to NULL → record dropped. If `currency` is null, `isin()` returns NULL → dropped. |
| Root cause | Upstream produced records with missing values on `merchant_id`, `customer_id`, `amount`, or `currency`. The `nullable=False` schema hint does not enforce — it only documents. |
| Detection signal | Compare raw count vs. clean count; sample raw records and check which required fields are null. |
| Proposed remediation | Add an explicit null-check stage that quarantines records with nulls on required fields and logs the field name(s). Default: implement a `validate_required_fields()` function with explicit per-field logging. |

---

## Failure modes NOT covered (future work)

These are realistic failure modes the project does NOT currently exercise.
They would be valuable additions in extended iterations:

- **Timezone confusion** — the same event with `created_at` in local time
  vs. UTC, leading to ambiguous reconciliation.
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

1. The agent reads CloudWatch logs of the failed run.
2. It searches each FM's "Detection signal" against the logs.
3. The first FM that matches is hypothesized as the root cause.
4. The agent reads the corresponding "Proposed remediation".
5. It generates a code patch (PySpark diff) and opens a PR on GitHub.
6. The PR description includes: identified FM, evidence from logs,
   proposed change, and reasoning.

This catalog is therefore both documentation AND the agent's grounding
data.
