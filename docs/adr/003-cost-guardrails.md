# ADR-003: Cost guardrails y disciplina operacional

## Status
Accepted — 2026-05-20

## Context
El proyecto corre contra AWS real. Sin salvaguardas, errores honestos
(dejar un cluster idle, un crawler corriendo en loop, leakear access keys)
pueden producir facturas inesperadas de cientos o miles de dólares.

## Decision
Establecer 6 salvaguardas no-negociables como condición de operación.

| # | Salvaguarda | Implementación |
|---|---|---|
| 1 | Budget de $10/mes con 3 alertas | AWS Budgets: 80% actual, 100% actual, 100% forecasted |
| 2 | Tag obligatorio en todo recurso | `default_tags { Project = "spark-self-heal", Environment = "dev", Owner = "cristian" }` en provider Terraform |
| 3 | `terraform destroy` ritualizado | Comando documentado en README al cierre de cada sesión grande |
| 4 | Cero recursos always-on caros | Prohibidos: clusters EMR, EC2 idle, Sagemaker notebooks abiertos. Permitidos always-on: S3 (centavos), Glue Catalog (free tier) |
| 5 | MFA + IAM user separado | Root user con MFA, trabajo diario en `cristian-dev` con least privilege relativo |
| 6 | Región única `us-east-1` | Variable Terraform fija; evita recursos huérfanos en otras regiones |

## Rationale
- Una factura inesperada puede matar el proyecto en una iteración
- La disciplina explícita > confianza en la prudencia personal
- Las salvaguardas se documentan para que cualquiera que clone el repo
  entienda las reglas antes de correr `terraform apply`

## Trade-offs aceptados
Para mantener simplicidad de portfolio, este proyecto NO implementa:
- IAM policies custom por servicio (usa `*FullAccess` AWS-managed)
- Multi-cuenta con AWS Organizations (single account)
- Network isolation con VPC custom (default VPC)
- KMS keys custom (defaults de AWS)
- Auto-shutdown de recursos via Budget Actions

Estas prácticas son apropiadas para producción real pero no agregan
valor pedagógico al proyecto portfolio.

## Consequences

### Positivas
- Riesgo financiero acotado a $10/mes en peor caso típico
- Disciplina industrial demostrable en el código y docs

### Negativas
- Algunas restricciones (tag obligatorio, single region) son fricción
  durante el desarrollo
- Las policies `*FullAccess` no son ejemplo de least privilege estricto
