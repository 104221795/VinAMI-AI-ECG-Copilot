import { VinamiApiError } from "@vinami/api-client";
import type { IdentityView } from "@web/entities/identity/model";
import { createServerApiClient } from "@web/shared/api/client";
import { parseContract } from "@web/shared/api/parse";
import { identitySchema } from "@web/shared/validation/contracts";

export async function loadIdentity(): Promise<IdentityView> {
  const value = parseContract(
    identitySchema,
    await createServerApiClient().getIdentitySession(),
  );
  return {
    actorId: value.actor_id,
    displayName: value.display_name,
    primaryRole: value.roles[0] ?? "Unknown role",
    roles: value.roles,
    permissions: value.permissions,
    provider: value.identity_provider,
    mode: value.identity_mode,
    developmentOnly: value.development_only,
    expiresAt: value.expires_at,
  };
}

export async function loadIdentitySafe(): Promise<IdentityView | null> {
  try {
    return await loadIdentity();
  } catch (error) {
    console.warn("vinami_identity_session_unavailable", {
      category: error instanceof VinamiApiError ? error.kind : "unknown",
    });
    return null;
  }
}
