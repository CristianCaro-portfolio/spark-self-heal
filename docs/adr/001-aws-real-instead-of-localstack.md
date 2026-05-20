# ADR-001: Real AWS account instead of LocalStack

## Status
Accepted — 2026-05-20

## Context
The project requires a working AWS environment (S3, Glue Catalog, Glue Jobs,
Athena, CloudWatch). Three options for the test plane were evaluated:

1. **LocalStack** (local AWS API emulator in Docker)
2. **Real AWS** with a personal account
3. **Local OSS stack** (MinIO + Hive Metastore + DuckDB) — simulates the
   architecture without emulating AWS APIs

Verified research (May 2026):
- LocalStack archived its Community Edition on March 23, 2026.
- Glue and Athena are listed as "Pro image only" in the official coverage
  documentation (docs.localstack.cloud/references/coverage/coverage_glue).
- The free Hobby plan (post March 2026) does NOT include Glue or Athena.
- LocalStack Ultimate costs $89/month or requires applying for the OSS
  license (manual review of days to weeks).

## Decision
Use a **real AWS account** with a controlled spending ceiling
($10/month via AWS Budgets).

## Rationale
1. **Services available without restrictions** — Glue and Athena are
   central to the project and to the target role profile (Senior Data
   Engineer with AWS). Emulating them adds no value.
2. **Low and predictable cost** — Glue Jobs serverless ($0.44/DPU-hr,
   minimum 2 DPU × 1 min ≈ $0.015 per short run) plus S3 (cents) plus
   Catalog (1M-object Always Free tier) add up to $3-5/month during
   active development.
3. **Demonstrable skill in the portfolio** — Terraform pointing at real
   AWS is more credible to a recruiter than the same HCL pointing at an
   emulator.
4. **Services discarded for cost** — MWAA (~$355/month minimum) is
   replaced by self-hosted Airflow in docker-compose; EMR clusters are
   replaced by serverless Glue Jobs.

## Consequences

### Positive
- Zero ambiguity about AWS API fidelity.
- The portfolio reflects real AWS experience, not emulator experience.
- Terraform is 100% portable to any AWS account.

### Negative
- Requires teardown discipline at the end of long sessions.
- A leaked access key on GitHub can produce serious costs.
- Without budgets/alerts configured, an honest mistake can get expensive.

### Mitigations
- AWS Budget of $10/month with alerts at 80% actual, 100% actual, and
  100% forecasted.
- Separate IAM user (`cristian-dev`) with relative least privilege (no
  AdministratorAccess) and mandatory MFA.
- Access keys never committed; `.gitignore` blocks `*.tfvars`,
  `*.tfstate`, `.env*`, and credentials CSVs.
- `terraform destroy` at the end of each long development session.
- Mandatory tag `Project=spark-self-heal` on every resource via the
  provider's `default_tags`.

## Alternatives considered

### LocalStack Ultimate (paid)
- $89/month — disproportionate for a portfolio project.
- Rejected on cost.

### LocalStack OSS license (free for qualifying OSS projects)
- Requires manual review with uncertain timing.
- Makes the project dependent on vendor approval.
- Rejected on external dependency.

### Local OSS stack (MinIO + Hive Metastore + DuckDB)
- Zero indefinite cost.
- The concept is preserved but the README would read as
  "Glue-equivalent, Athena-equivalent" instead of "AWS Glue, AWS Athena".
- Rejected on loss of alignment with the target JD.
