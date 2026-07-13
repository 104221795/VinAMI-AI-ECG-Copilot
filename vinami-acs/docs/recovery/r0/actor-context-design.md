# Actor Context Design

`ActorContext` is an immutable value object containing actor ID, normalized role, correlation ID, and optional causation ID. Consequential commands require it structurally.

For R0, accepted physician authority is explicit: `physician`. The role supplied by a command is not trusted alone. `SQLAlchemyActorAuthorizationRepository` resolves the actor from `clinical_users`, and handlers reject missing users, role mismatches, and non-physician roles before persistence or transition.

This is an authorization placeholder, not authentication. R1 must bind actor context to a verified API identity and permission policy. Until then, direct internal callers still need trusted composition-root access, and the system must not be exposed as a clinical service.

Audit records capture actor ID and role for accepted and rejected consequential commands, with correlation and causation linkage.
