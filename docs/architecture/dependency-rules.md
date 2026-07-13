# Dependency Rules

## Allowed Direction

```text
delivery (FastAPI, Streamlit) -> application -> domain
infrastructure -> application ports and domain contracts
tests -> any layer through public contracts
```

## Mandatory Rules

1. The domain layer imports only Python standard library and domain-local code.
2. Application services depend on ports, not SQLAlchemy sessions, FastAPI request objects, Streamlit, or model frameworks.
3. Infrastructure implements ports and may depend on SQLAlchemy, storage SDKs, `torch`, `timm`, or ONNX Runtime only inside the relevant adapter package.
4. Routers have one job: schema validation, inbound-port invocation, and response/error mapping.
5. Streamlit calls `/api/v1` only. It contains no rules, aggregate imports, ORM imports, direct database calls, or provider calls.
6. Contexts share only IDs, value-object primitives, event envelopes, and published application DTOs.
7. ORM classes are persistence mappings; they have no clinical behavior or policy.
8. Every aggregate mutation occurs in an explicit UoW and writes corresponding outbox messages before commit.
9. Query handlers do not mutate command aggregates.
10. An adapter failure maps to a structured application error/event; it is never swallowed.

## Explicitly Forbidden Imports

| Import location | Forbidden imports |
|---|---|
| `domain/` | `fastapi`, `sqlalchemy`, `streamlit`, `torch`, `timm`, `onnxruntime`, infrastructure packages |
| `application/` | concrete repositories, ORM models, `streamlit`, model implementation packages |
| `delivery/streamlit/` | SQLAlchemy, repositories, domain aggregates, clinical policies, `torch` |
| `delivery/api/routers/` | SQLAlchemy session, concrete provider, clinical rule implementation |
| Clinical Reasoning | any model library, checkpoint access, guideline threshold literals not supplied by a reviewed demonstration ruleset |

