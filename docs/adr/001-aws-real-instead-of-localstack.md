# ADR-001: AWS real en lugar de LocalStack

## Status
Accepted — 2026-05-20

## Context
El proyecto necesita un entorno AWS funcional (S3, Glue Catalog, Glue Jobs,
Athena, CloudWatch). Se evaluaron tres opciones de plano de pruebas:

1. **LocalStack** (emulador de AWS local en Docker)
2. **AWS real** con cuenta personal
3. **Stack OSS local** (MinIO + Hive Metastore + DuckDB) que simula la
   arquitectura sin emular APIs AWS

Investigación verificada (mayo 2026):
- LocalStack archivó la Community Edition el 23 de marzo de 2026
- Glue y Athena están listados como "Pro image only" en la doc oficial
  de cobertura (docs.localstack.cloud/references/coverage/coverage_glue)
- El plan Hobby gratuito (post-marzo 2026) NO incluye Glue ni Athena
- LocalStack Ultimate cuesta $89/mes o requiere aplicar a la licencia
  OSS gratuita (review manual de días a semanas)

## Decision
Se elige **AWS real con cuenta personal** y techo de gasto controlado
($10/mes vía AWS Budget).

## Rationale
1. **Servicios disponibles sin restricciones** — Glue y Athena son
   centrales al proyecto y al perfil del rol target (Data Engineer Sr
   con AWS). No tiene sentido emularlos.
2. **Costo bajo y predecible** — Glue Jobs serverless ($0.44/DPU-hr,
   mín. 2 DPU × 1 min ≈ $0.015 por ejecución corta) más S3 (centavos)
   más Catalog (free tier de 1M objetos siempre vigente) suman $3-5/mes
   en desarrollo activo.
3. **Skill demostrable en el portfolio** — Terraform apuntando a AWS
   real es más creíble para un reclutador que el mismo HCL apuntando a
   un emulador.
4. **Servicios descartados por costo** — MWAA (~$355/mes mínimo) se
   reemplaza por Airflow autohospedado en docker-compose; EMR cluster
   se reemplaza por Glue Jobs serverless.

## Consequences

### Positivas
- Cero ambigüedad sobre la fidelidad de APIs AWS
- Portfolio refleja experiencia real con AWS, no con emulador
- Terraform 100% portable a cualquier cuenta AWS

### Negativas
- Requiere disciplina de teardown al terminar sesiones largas
- Una access key leaked en GitHub puede generar costos graves
- Sin alertas/budget configurados, una negligencia puede salir cara

### Mitigaciones
- AWS Budget de $10/mes con alertas en 80% actual, 100% actual y
  100% forecasted
- IAM user separado (`cristian-dev`) con least privilege relativo
  (no AdministratorAccess) y MFA obligatorio
- Access keys nunca commiteadas; `.gitignore` blindea `*.tfvars`,
  `*.tfstate`, archivos `.env`, CSVs de credenciales
- `terraform destroy` al cierre de cada sesión de desarrollo larga
- Tag obligatorio `Project=spark-self-heal` en todos los recursos
  vía `default_tags` del provider de Terraform

## Alternatives considered

### LocalStack Ultimate (paid)
- $89/mes — desproporcionado para portfolio
- Descartado por costo

### LocalStack OSS license (free para proyectos OSS calificados)
- Requiere review manual con tiempos inciertos
- Hace al proyecto dependiente de la aprobación de un vendor
- Descartado por dependencia externa

### Stack OSS local (MinIO + Hive Metastore + DuckDB)
- Cero costo indefinido
- Concepto del proyecto se preserva pero el README quedaría como
  "Glue-equivalent, Athena-equivalent" en vez de "AWS Glue, AWS Athena"
- Descartado por pérdida de alineación con el JD target
