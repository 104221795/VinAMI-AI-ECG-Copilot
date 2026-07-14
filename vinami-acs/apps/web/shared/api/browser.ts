"use client";

import { VinamiApiClient } from "@vinami/api-client";

export function createBrowserApiClient() {
  return new VinamiApiClient({
    baseUrl: "/api/backend",
    requestSource: "vinami-next-browser",
  });
}
