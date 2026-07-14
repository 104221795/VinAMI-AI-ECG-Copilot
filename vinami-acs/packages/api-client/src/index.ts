import createClient from "openapi-fetch";
import type { components, paths } from "@vinami/contracts";

export type ProblemDetail = components["schemas"]["ProblemDetail"];
export type ClinicalCasePage =
  components["schemas"]["PaginatedClinicalCasesResponse"];
export type ClinicalCase = components["schemas"]["ClinicalCaseResponse"];
export type Patient = components["schemas"]["PatientResponse"];
export type Encounter = components["schemas"]["EncounterResponse"];
export type TimelineEvent = components["schemas"]["TimelineEventResponse"];
export type AuditEntry = components["schemas"]["AuditEntryResponse"];
export type IdentitySession = components["schemas"]["IdentitySessionResponse"];
export type TriageAssessment =
  components["schemas"]["TriageAssessmentResponse"];
export type TriageHistory = components["schemas"]["TriageHistoryResponse"];
export type TriageVitalsSummary =
  components["schemas"]["TriageVitalsSummaryResponse"];
export type VitalObservationSet =
  components["schemas"]["VitalObservationSetResponse"];
export type VitalObservationHistory =
  components["schemas"]["VitalObservationHistoryResponse"];
export type RecordTriageInput =
  components["schemas"]["RecordTriageAssessmentRequest"];
export type CorrectTriageInput =
  components["schemas"]["CorrectTriageAssessmentRequest"];
export type RecordVitalsInput =
  components["schemas"]["RecordVitalObservationSetRequest"];
export type CorrectVitalsInput =
  components["schemas"]["CorrectVitalObservationSetRequest"];
export type ECGWorkspace = components["schemas"]["ECGWorkspaceResponse"];
export type ECGWaveform = components["schemas"]["WaveformResponse"];
export type ECGIngestionJob = components["schemas"]["IngestionJobResponse"];
export type ECGAnalysis = components["schemas"]["AnalysisResponse"];
export type ECGInterpretation = components["schemas"]["InterpretationResponse"];
export type ECGAnalysisInput = components["schemas"]["RequestAnalysisBody"];
export type ECGInterpretationInput =
  components["schemas"]["InterpretationBody"];

export type ApiErrorKind =
  | "authentication"
  | "authorization"
  | "not_found"
  | "conflict"
  | "validation"
  | "timeout"
  | "offline"
  | "server"
  | "malformed"
  | "unknown";

export class VinamiApiError extends Error {
  readonly occurredAt = new Date().toISOString();

  constructor(
    readonly kind: ApiErrorKind,
    message: string,
    readonly status: number | null,
    readonly correlationId: string | null,
    readonly retryable: boolean,
  ) {
    super(message);
    this.name = "VinamiApiError";
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  developmentIdentity?: string;
  requestSource?: string;
  timeoutMs?: number;
  onResponse?: (observation: {
    status: number;
    correlationId: string | null;
  }) => void;
}

export interface CaseListQuery {
  page?: number;
  page_size?: number;
  status?: "open" | "under_review" | "closed";
  priority?: "routine" | "urgent" | "critical";
  location?: string;
}

export class VinamiApiClient {
  private readonly client: ReturnType<typeof createClient<paths>>;
  private readonly baseUrl: string;
  private readonly defaultHeaders: Record<string, string>;
  private readonly safeFetch: typeof fetch;

  constructor(options: ApiClientOptions) {
    const headers: Record<string, string> = {
      Accept: "application/json",
      "X-Request-Source": options.requestSource ?? "vinami-web",
    };
    if (options.developmentIdentity) {
      headers["X-Development-Identity"] = options.developmentIdentity;
    }
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.defaultHeaders = headers;
    this.safeFetch = createSafeFetch(
      options.timeoutMs ?? 8_000,
      options.onResponse,
    );
    this.client = createClient<paths>({
      baseUrl: this.baseUrl,
      headers,
      fetch: this.safeFetch,
    });
  }

  async listClinicalCases(
    query: CaseListQuery = {},
  ): Promise<ClinicalCasePage> {
    const result = await this.client.GET("/api/v1/clinical-cases", {
      params: { query },
    });
    return unwrap(result);
  }

  async getClinicalCase(caseId: string): Promise<ClinicalCase> {
    return unwrap(
      await this.client.GET("/api/v1/clinical-cases/{case_id}", {
        params: { path: { case_id: caseId } },
      }),
    );
  }

  async getPatient(patientId: string): Promise<Patient> {
    return unwrap(
      await this.client.GET("/api/v1/patients/{patient_id}", {
        params: { path: { patient_id: patientId } },
      }),
    );
  }

  async getEncounter(encounterId: string): Promise<Encounter> {
    return unwrap(
      await this.client.GET("/api/v1/encounters/{encounter_id}", {
        params: { path: { encounter_id: encounterId } },
      }),
    );
  }

  async getTimeline(caseId: string): Promise<TimelineEvent[]> {
    return unwrap(
      await this.client.GET("/api/v1/clinical-cases/{case_id}/timeline", {
        params: { path: { case_id: caseId } },
      }),
    );
  }

  async getAudit(caseId: string): Promise<AuditEntry[]> {
    return unwrap(
      await this.client.GET("/api/v1/clinical-cases/{case_id}/audit", {
        params: { path: { case_id: caseId } },
      }),
    );
  }

  async getCurrentTriage(caseId: string): Promise<TriageAssessment | null> {
    return unwrap(
      await this.client.GET("/api/v1/clinical-cases/{case_id}/triage", {
        params: { path: { case_id: caseId } },
      }),
    );
  }

  async getTriageHistory(caseId: string): Promise<TriageHistory> {
    return unwrap(
      await this.client.GET("/api/v1/clinical-cases/{case_id}/triage/history", {
        params: { path: { case_id: caseId } },
      }),
    );
  }

  async getVitalHistory(caseId: string): Promise<VitalObservationHistory> {
    return unwrap(
      await this.client.GET("/api/v1/clinical-cases/{case_id}/vitals", {
        params: { path: { case_id: caseId } },
      }),
    );
  }

  async getLatestVitals(caseId: string): Promise<VitalObservationSet | null> {
    return unwrap(
      await this.client.GET("/api/v1/clinical-cases/{case_id}/vitals/latest", {
        params: { path: { case_id: caseId } },
      }),
    );
  }

  async getTriageVitalsSummary(caseId: string): Promise<TriageVitalsSummary> {
    return unwrap(
      await this.client.GET(
        "/api/v1/clinical-cases/{case_id}/triage-vitals-summary",
        { params: { path: { case_id: caseId } } },
      ),
    );
  }

  async recordTriage(
    caseId: string,
    body: RecordTriageInput,
    idempotencyKey: string,
  ): Promise<TriageAssessment> {
    return unwrap(
      await this.client.POST(
        "/api/v1/clinical-cases/{case_id}/triage-assessments",
        {
          params: {
            path: { case_id: caseId },
            header: { "Idempotency-Key": idempotencyKey },
          },
          body,
        },
      ),
    );
  }

  async correctTriage(
    caseId: string,
    assessmentId: string,
    body: CorrectTriageInput,
    idempotencyKey: string,
  ): Promise<TriageAssessment> {
    return unwrap(
      await this.client.POST(
        "/api/v1/clinical-cases/{case_id}/triage-assessments/{assessment_id}/corrections",
        {
          params: {
            path: { case_id: caseId, assessment_id: assessmentId },
            header: { "Idempotency-Key": idempotencyKey },
          },
          body,
        },
      ),
    );
  }

  async recordVitals(
    caseId: string,
    body: RecordVitalsInput,
    idempotencyKey: string,
  ): Promise<VitalObservationSet> {
    return unwrap(
      await this.client.POST(
        "/api/v1/clinical-cases/{case_id}/vital-observation-sets",
        {
          params: {
            path: { case_id: caseId },
            header: { "Idempotency-Key": idempotencyKey },
          },
          body,
        },
      ),
    );
  }

  async correctVitals(
    caseId: string,
    vitalSetId: string,
    body: CorrectVitalsInput,
    idempotencyKey: string,
  ): Promise<VitalObservationSet> {
    return unwrap(
      await this.client.POST(
        "/api/v1/clinical-cases/{case_id}/vital-observation-sets/{vital_set_id}/corrections",
        {
          params: {
            path: { case_id: caseId, vital_set_id: vitalSetId },
            header: { "Idempotency-Key": idempotencyKey },
          },
          body,
        },
      ),
    );
  }

  async getIdentitySession(): Promise<IdentitySession> {
    return unwrap(await this.client.GET("/api/v1/identity/session"));
  }

  async getECGWorkspace(caseId: string): Promise<ECGWorkspace> {
    return unwrap(
      await this.client.GET("/api/v1/clinical-cases/{case_id}/ecg-workspace", {
        params: { path: { case_id: caseId } },
      }),
    );
  }

  async getECGWaveform(studyId: string): Promise<ECGWaveform> {
    return unwrap(
      await this.client.GET("/api/v1/ecg-studies/{study_id}/waveform", {
        params: { path: { study_id: studyId } },
      }),
    );
  }

  async requestECGAnalysis(
    studyId: string,
    body: ECGAnalysisInput,
    idempotencyKey: string,
  ): Promise<ECGAnalysis> {
    return unwrap(
      await this.client.POST("/api/v1/ecg-studies/{study_id}/analyses", {
        params: {
          path: { study_id: studyId },
          header: { "Idempotency-Key": idempotencyKey },
        },
        body,
      }),
    );
  }

  async recordECGInterpretation(
    studyId: string,
    body: ECGInterpretationInput,
    idempotencyKey: string,
  ): Promise<ECGInterpretation> {
    return unwrap(
      await this.client.POST(
        "/api/v1/ecg-studies/{study_id}/physician-interpretations",
        {
          params: {
            path: { study_id: studyId },
            header: { "Idempotency-Key": idempotencyKey },
          },
          body,
        },
      ),
    );
  }

  async uploadECGStudy(
    caseId: string,
    form: FormData,
    idempotencyKey: string,
  ): Promise<ECGIngestionJob> {
    const headers = new Headers(this.defaultHeaders);
    headers.set("Idempotency-Key", idempotencyKey);
    const response = await this.safeFetch(
      `${this.baseUrl}/api/v1/clinical-cases/${encodeURIComponent(caseId)}/ecg-studies`,
      { method: "POST", headers, body: form },
    );
    const payload: unknown = await response.json().catch(() => undefined);
    if (!response.ok) {
      throw mapApiError(
        response.status,
        payload,
        response.headers.get("x-correlation-id"),
      );
    }
    return payload as ECGIngestionJob;
  }

  async getHealth(): Promise<Record<string, unknown>> {
    return recordResponse(unwrap(await this.client.GET("/health")));
  }

  async getReadiness(): Promise<Record<string, unknown>> {
    return recordResponse(unwrap(await this.client.GET("/ready")));
  }
}

function recordResponse(value: unknown): Record<string, unknown> {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  throw new VinamiApiError(
    "malformed",
    "The platform status response is malformed.",
    null,
    null,
    false,
  );
}

interface OpenApiResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

function unwrap<T>(result: OpenApiResult<T>): T {
  const correlationId = result.response.headers.get("x-correlation-id");
  if (result.data !== undefined) return result.data;
  throw mapApiError(result.response.status, result.error, correlationId);
}

export function mapApiError(
  status: number,
  payload: unknown,
  headerCorrelationId: string | null = null,
): VinamiApiError {
  const problem = isProblem(payload) ? payload : null;
  const correlationId = problem?.correlation_id ?? headerCorrelationId;
  const details: Record<number, [ApiErrorKind, string, boolean]> = {
    401: [
      "authentication",
      "Your verified session is unavailable or has expired.",
      false,
    ],
    403: [
      "authorization",
      "Your verified identity does not have permission to view this information.",
      false,
    ],
    404: [
      "not_found",
      "The requested clinical record is no longer available.",
      false,
    ],
    409: [
      "conflict",
      "The record changed while it was being read. Refresh before continuing.",
      true,
    ],
    422: [
      "validation",
      "The request could not be validated against the current API contract.",
      false,
    ],
  };
  const [kind, message, retryable] =
    details[status] ??
    (status >= 500
      ? ([
          "server",
          "The clinical service is temporarily unavailable.",
          true,
        ] as const)
      : (["unknown", "The request could not be completed.", false] as const));
  return new VinamiApiError(
    kind,
    problem?.detail ?? message,
    status,
    correlationId,
    retryable,
  );
}

function isProblem(value: unknown): value is ProblemDetail {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.title === "string" &&
    typeof candidate.status === "number" &&
    typeof candidate.detail === "string" &&
    typeof candidate.correlation_id === "string"
  );
}

function createSafeFetch(
  timeoutMs: number,
  onResponse?: ApiClientOptions["onResponse"],
): typeof fetch {
  return async (input, init) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const attempts = method === "GET" ? 2 : 1;
    let lastError: unknown;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(input, {
          ...init,
          signal: controller.signal,
        });
        onResponse?.({
          status: response.status,
          correlationId: response.headers.get("x-correlation-id"),
        });
        if (
          method === "GET" &&
          attempt === 0 &&
          [502, 503, 504].includes(response.status)
        ) {
          continue;
        }
        return response;
      } catch (error) {
        lastError = error;
        if (attempt + 1 === attempts) {
          const aborted =
            error instanceof DOMException && error.name === "AbortError";
          throw new VinamiApiError(
            aborted ? "timeout" : "offline",
            aborted
              ? "The clinical service did not respond in time."
              : "The clinical service could not be reached.",
            null,
            null,
            true,
          );
        }
      } finally {
        clearTimeout(timeout);
      }
    }
    throw lastError;
  };
}
