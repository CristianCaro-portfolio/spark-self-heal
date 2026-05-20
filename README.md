# spark-self-heal

Self-healing data pipeline on AWS (Spark + Glue + Athena + Airflow) with an
AI agent that diagnoses failures and proposes patches via pull request.

## Status

Work in progress — Acto 1: foundations + bootstrap.

## Stack

- AWS: S3, Glue (Catalog + Jobs), Athena, CloudWatch Logs
- Orchestration: Apache Airflow (self-hosted via docker-compose)
- Infrastructure as Code: Terraform
- Agent: Python + Anthropic Claude API + tool use loop
- CI/CD: GitHub Actions

## Architecture decisions

See `docs/adr/` for the full ADR log.

## License

MIT
