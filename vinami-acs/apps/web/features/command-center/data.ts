import type { CaseListQuery, VinamiApiClient } from "@vinami/api-client";
import type {
  CaseQueueRowView,
  CaseQueueView,
} from "@web/entities/clinical-case/model";
import { parseContract } from "@web/shared/api/parse";
import { safeDemographics, shortReference } from "@web/shared/formatting";
import {
  casePageSchema,
  encounterSchema,
  patientSchema,
} from "@web/shared/validation/contracts";

export async function loadCaseQueueWith(
  api: VinamiApiClient,
  query: CaseListQuery,
): Promise<CaseQueueView> {
  const page = parseContract(
    casePageSchema,
    await api.listClinicalCases(query),
  );
  const results = await Promise.allSettled(
    page.items.map(async (item): Promise<CaseQueueRowView> => {
      const encounter = parseContract(
        encounterSchema,
        await api.getEncounter(item.encounter_id),
      );
      const patient = parseContract(
        patientSchema,
        await api.getPatient(encounter.patient_id),
      );
      return {
        caseId: item.case_id,
        caseReference: shortReference(item.case_id, "CASE"),
        encounterId: item.encounter_id,
        encounterReference: shortReference(item.encounter_id, "ENC"),
        patientId: patient.patient_id,
        patientReference: patient.patient_reference,
        demographics: safeDemographics(
          patient.safe_demographic_summary.age_band,
          patient.safe_demographic_summary.sex_at_birth,
        ),
        location: item.location,
        priority: item.priority,
        status: item.status,
        openedAt: item.opened_at,
        updatedAt: item.updated_at,
        aggregateVersion: item.aggregate_version,
        partial: false,
      };
    }),
  );
  const rows = results.map((result, index): CaseQueueRowView => {
    if (result.status === "fulfilled") return result.value;
    const item = page.items[index];
    if (!item) throw result.reason;
    return {
      caseId: item.case_id,
      caseReference: shortReference(item.case_id, "CASE"),
      encounterId: item.encounter_id,
      encounterReference: shortReference(item.encounter_id, "ENC"),
      patientId: null,
      patientReference: "Patient details unavailable",
      demographics: "Demographics unavailable",
      location: item.location,
      priority: item.priority,
      status: item.status,
      openedAt: item.opened_at,
      updatedAt: item.updated_at,
      aggregateVersion: item.aggregate_version,
      partial: true,
    };
  });
  return {
    rows,
    page: page.page,
    pageSize: page.page_size,
    total: page.total,
    partialCount: rows.filter((row) => row.partial).length,
    refreshedAt: new Date().toISOString(),
  };
}
