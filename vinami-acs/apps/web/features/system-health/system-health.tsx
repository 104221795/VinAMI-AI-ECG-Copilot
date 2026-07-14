import {
  Badge,
  ClinicalCard,
  StatusBadge,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import type { SystemHealthView } from "./data";
import { formatTimestamp } from "@web/shared/formatting";

function HealthRow({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="vm-health-row">
      <div>
        <strong>{label}</strong>
        {detail && <small>{detail}</small>}
      </div>
      <StatusBadge status={value} />
    </div>
  );
}

export function SystemHealth({ value }: { value: SystemHealthView }) {
  return (
    <div className="vm-health-grid">
      <ClinicalCard title="Application services">
        <HealthRow
          label="FastAPI liveness"
          value={value.apiStatus}
          detail="Process endpoint"
        />
        <HealthRow
          label="API readiness"
          value={value.readiness}
          detail="Dependency-aware check"
        />
        <HealthRow
          label="Database and schema"
          value={value.dependency}
          detail={`Migration ${value.revision}`}
        />
        <HealthRow
          label="Worker"
          value="Not exposed"
          detail="R1 does not expose a worker health contract"
        />
      </ClinicalCard>
      <ClinicalCard title="Identity provider">
        <HealthRow
          label="Provider state"
          value={value.identityStatus}
          detail={value.identityProvider}
        />
        <HealthRow
          label="Identity mode"
          value={value.identityMode}
          detail={
            value.developmentOnly
              ? "Synthetic identities only"
              : "Provider-verified"
          }
        />
        {value.developmentOnly && (
          <Badge tone="warning">
            Development identity is not production authentication
          </Badge>
        )}
        <TechnicalDetailsDisclosure>
          <dl>
            <dt>Last successful check</dt>
            <dd>{formatTimestamp(value.checkedAt)}</dd>
            <dt>Schema revision</dt>
            <dd>
              <code>{value.revision}</code>
            </dd>
          </dl>
        </TechnicalDetailsDisclosure>
      </ClinicalCard>
    </div>
  );
}
