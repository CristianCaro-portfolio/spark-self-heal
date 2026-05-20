# ADR-002: Agent autonomy spectrum

## Status
Accepted — 2026-05-20

## Context
When a Glue Job fails, the agent can take actions at different levels of
autonomy. Defining this explicitly is an architectural decision, not an
implementation detail: it determines the agent's blast radius, the IAM
permissions it needs, the design of its control loop, and the project's
narrative.

## Decision
Implement 3 operating modes, controlled by the `AGENT_MODE` environment
variable:

| Mode      | Reads logs | Diagnoses | Proposes patch | Opens PR | Auto-merge |
|-----------|------------|-----------|----------------|----------|------------|
| observe   | yes        | yes       | no             | no       | no         |
| propose   | yes        | yes       | yes            | yes      | no         |
| apply     | yes        | yes       | yes            | yes      | yes (if CI passes) |

- Development default: `propose`.
- CI default: `observe`.
- `apply` additionally requires the `--allow-auto-merge` flag on the
  command line.

## Rationale
1. Human-in-the-loop by default reflects real industry practice.
2. The three modes demonstrate a progression of architectural trust.
3. `propose` produces PRs as public artifacts visible on GitHub.
4. `apply` exists but behind a flag, showing maturity (not "the agent
   does everything and we pray").

## Consequences

### Positive
- Safety by construction.
- Each PR opened by the agent stays in GitHub history as evidence.
- Allows prompt evaluation by observing which PRs are accepted vs.
  rejected.

### Negative
- Less "wow factor" than a fully autonomous agent.
- Requires GitHub API integration (token scoped to a single repo).
