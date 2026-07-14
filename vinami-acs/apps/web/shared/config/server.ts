import "server-only";
import { z } from "zod";

const schema = z.object({
  VINAMI_API_BASE_URL: z.string().url().default("http://127.0.0.1:8000"),
  VINAMI_WEB_IDENTITY_MODE: z
    .enum(["development", "oidc"])
    .default("development"),
  VINAMI_WEB_DEVELOPMENT_IDENTITY: z
    .enum([
      "physician",
      "nurse",
      "technician",
      "care_coordinator",
      "administrator",
      "auditor",
      "system_service",
      "read_only_reviewer",
    ])
    .default("physician"),
  NEXT_PUBLIC_ENVIRONMENT: z.string().default("Development"),
});

const parsed = schema.parse(process.env);
if (
  parsed.NEXT_PUBLIC_ENVIRONMENT.toLowerCase() === "production" &&
  parsed.VINAMI_WEB_IDENTITY_MODE === "development"
) {
  throw new Error("Development identity mode is prohibited in production");
}

export const serverConfig = {
  apiBaseUrl: parsed.VINAMI_API_BASE_URL,
  identityMode: parsed.VINAMI_WEB_IDENTITY_MODE,
  developmentIdentity: parsed.VINAMI_WEB_DEVELOPMENT_IDENTITY,
} as const;
