import { createServerApiClient } from "@web/shared/api/client";
import { parseContract } from "@web/shared/api/parse";
import { healthSchema } from "@web/shared/validation/contracts";

export interface SystemHealthView {
  apiStatus: string;
  readiness: string;
  dependency: string;
  revision: string;
  identityMode: string;
  identityStatus: string;
  identityProvider: string;
  developmentOnly: boolean;
  checkedAt: string;
}

export async function loadSystemHealth(): Promise<SystemHealthView> {
  const api = createServerApiClient();
  const [healthValue, readyValue] = await Promise.all([
    api.getHealth(),
    api.getReadiness(),
  ]);
  const health = parseContract(healthSchema, healthValue);
  const ready = parseContract(healthSchema, readyValue);
  return {
    apiStatus: health.status,
    readiness: ready.status,
    dependency: ready.dependency ?? "Not exposed",
    revision: ready.revision ?? "Not exposed",
    identityMode: ready.identity?.mode ?? "Not exposed",
    identityStatus: ready.identity?.status ?? "Not exposed",
    identityProvider: ready.identity?.provider ?? "Not exposed",
    developmentOnly: ready.identity?.development_only ?? false,
    checkedAt: new Date().toISOString(),
  };
}
