import "server-only";
import { VinamiApiClient } from "@vinami/api-client";
import { serverConfig } from "@web/shared/config/server";

export function createServerApiClient() {
  return new VinamiApiClient({
    baseUrl: serverConfig.apiBaseUrl,
    developmentIdentity:
      serverConfig.identityMode === "development"
        ? serverConfig.developmentIdentity
        : undefined,
    requestSource: "vinami-next-server",
  });
}
