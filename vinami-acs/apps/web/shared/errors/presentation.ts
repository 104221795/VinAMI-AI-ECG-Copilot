import { VinamiApiError } from "@vinami/api-client";

export interface ErrorPresentation {
  title: string;
  description: string;
  correlationId: string | null;
  retryable: boolean;
}

export function presentError(error: unknown): ErrorPresentation {
  if (!(error instanceof VinamiApiError)) {
    return {
      title: "Information unavailable",
      description:
        "The request could not be completed. Retry, or contact the support team if the issue persists.",
      correlationId: null,
      retryable: true,
    };
  }
  const messages: Record<typeof error.kind, [string, string]> = {
    authentication: [
      "Session unavailable",
      "The verified session is missing or expired. Re-establish the approved identity session.",
    ],
    authorization: [
      "Permission required",
      "Your verified role does not permit access to this clinical information.",
    ],
    not_found: [
      "Record not found",
      "This record may have been removed from the active workflow or the reference may be incorrect.",
    ],
    conflict: [
      "Information changed",
      "A newer aggregate version is available. Refresh before continuing.",
    ],
    validation: [
      "Request could not be validated",
      "Review the selected filters and retry with supported values.",
    ],
    timeout: [
      "Service response delayed",
      "The clinical service did not respond within the expected time window.",
    ],
    offline: [
      "Connection unavailable",
      "The clinical service cannot be reached. Check connectivity before relying on displayed information.",
    ],
    server: [
      "Clinical service unavailable",
      "The server could not complete the request. No clinical action was taken.",
    ],
    malformed: [
      "Contract mismatch detected",
      "The received information failed runtime validation and has not been displayed.",
    ],
    unknown: [
      "Request unsuccessful",
      "The request could not be completed safely.",
    ],
  };
  const [title, description] = messages[error.kind];
  return {
    title,
    description,
    correlationId: error.correlationId,
    retryable: error.retryable,
  };
}
