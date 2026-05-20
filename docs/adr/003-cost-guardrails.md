# ADR-003: Cost guardrails and operational discipline

## Status
Accepted — 2026-05-20

## Context
The project runs against real AWS. Without safeguards, honest mistakes
(leaving an idle cluster, a crawler running in a loop, leaking access
keys) can produce unexpected bills of hundreds or thousands of dollars.

## Decision
Establish 6 non-negotiable safeguards as a precondition for operation.

| # | Safeguard | Implementation |
|---|---|---|
| 1 | $10/month budget with 3 alerts | AWS Budgets: 80% actual, 100% actual, 100% forecasted |
| 2 | Mandatory tag on every resource | `default_tags { Project = "spark-self-heal", Environment = "dev", Owner = "cristian" }` in the Terraform provider |
| 3 | Ritualized `terraform destroy` | Command documented in README for end-of-session teardown |
| 4 | No expensive always-on resources | Forbidden: EMR clusters, idle EC2, open SageMaker notebooks. Allowed always-on: S3 (cents), Glue Catalog (free tier) |
| 5 | MFA + separate IAM user | Root user with MFA; daily work under `cristian-dev` with relative least privilege |
| 6 | Single region `us-east-1` | Fixed Terraform variable; prevents orphan resources in other regions |

## Rationale
- A surprise bill can kill the project in one iteration.
- Explicit discipline beats personal prudence.
- Safeguards are documented so that anyone cloning the repo understands
  the rules before running `terraform apply`.

## Trade-offs accepted
To keep the portfolio simple, this project does NOT implement:
- Custom per-service IAM policies (uses AWS-managed `*FullAccess`).
- Multi-account setups with AWS Organizations (single account).
- Network isolation with a custom VPC (default VPC).
- Custom KMS keys (AWS defaults).
- Auto-shutdown via Budget Actions.

These practices are appropriate for real production environments but
add no pedagogical value to a portfolio project.

## Consequences

### Positive
- Financial risk bounded to ~$10/month in the typical worst case.
- Industrial discipline demonstrable in the code and docs.

### Negative
- Some constraints (mandatory tag, single region) create friction
  during development.
- `*FullAccess` policies are not an example of strict least privilege.
