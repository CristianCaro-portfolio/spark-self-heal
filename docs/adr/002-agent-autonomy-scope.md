# ADR-002: Espectro de autonomía del agente

## Status
Accepted — 2026-05-20

## Context
Cuando un job de Glue falla, el agente puede tomar acciones con distintos
niveles de autonomía. Definir esto explícitamente es decisión arquitectónica,
no detalle de implementación: determina el blast radius del agente, los
permisos IAM que necesita, el diseño del loop, y la narrativa del proyecto.

## Decision
Implementar 3 modos de operación controlados por la variable de entorno
`AGENT_MODE`:

| Modo      | Lee logs | Diagnostica | Propone parche | Abre PR | Auto-merge |
|-----------|----------|-------------|----------------|---------|------------|
| observe   | sí       | sí          | no             | no      | no         |
| propose   | sí       | sí          | sí             | sí      | no         |
| apply     | sí       | sí          | sí             | sí      | sí (si CI pasa) |

- Default en desarrollo: `propose`
- Default en CI: `observe`
- `apply` requiere además flag `--allow-auto-merge` en línea de comando

## Rationale
1. Human-in-the-loop por defecto refleja la práctica industrial real
2. Los 3 modos demuestran progresión de confianza arquitectónica
3. `propose` produce PRs como artefactos públicos visibles en GitHub
4. `apply` existe pero detrás de flag, demostrando madurez (no es
   "el agente hace todo y rezamos")

## Consequences

### Positivas
- Safety por construcción
- Cada PR del agente queda en el historial de GitHub como prueba
- Permite evaluar prompts viendo qué PRs son aceptados vs rechazados

### Negativas
- Menos "wow factor" automático que un agente 100% autónomo
- Requiere integración con GitHub API (token scoped a un repo)
