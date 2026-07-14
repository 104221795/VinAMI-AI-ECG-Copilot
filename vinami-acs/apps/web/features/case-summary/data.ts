import type { VinamiApiClient } from "@vinami/api-client";
import type { CaseWorkspaceView } from "@web/entities/clinical-case/model";
import { parseContract } from "@web/shared/api/parse";
import { safeDemographics, shortReference } from "@web/shared/formatting";
import {
  caseDetailSchema,
  encounterSchema,
  patientSchema,
} from "@web/shared/validation/contracts";

export async function loadCaseWorkspaceWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<CaseWorkspaceView> {
  const clinicalCase = parseContract(
    caseDetailSchema,
    await api.getClinicalCase(caseId),
  );
  const encounter = parseContract(
    encounterSchema,
    await api.getEncounter(clinicalCase.encounter_id),
  );
  const patient = parseContract(
    patientSchema,
    await api.getPatient(encounter.patient_id),
  );
  return {
    caseId: clinicalCase.case_id,
    caseReference: shortReference(clinicalCase.case_id, "CASE"),
    encounterId: encounter.encounter_id,
    encounterReference: shortReference(encounter.encounter_id, "ENC"),
    patientId: patient.patient_id,
    patientReference: patient.patient_reference,
    patientReferenceSystem: patient.reference_system,
    demographics: safeDemographics(
      patient.safe_demographic_summary.age_band,
      patient.safe_demographic_summary.sex_at_birth,
    ),
    location: encounter.location,
    arrivalAt: encounter.arrival_at,
    encounterStatus: encounter.status,
    priority: clinicalCase.priority,
    status: clinicalCase.status,
    openingReason: clinicalCase.opening_reason,
    openedAt: clinicalCase.opened_at,
    updatedAt: clinicalCase.updated_at,
    aggregateVersion: clinicalCase.aggregate_version,
  };
}
