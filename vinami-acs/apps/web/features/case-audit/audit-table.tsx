import {
  EmptyState,
  StatusBadge,
  TechnicalDetailsDisclosure,
} from "@vinami/ui";
import type { AuditEntryView } from "@web/entities/audit-entry/model";
import { formatTimestamp } from "@web/shared/formatting";

export function AuditTable({ entries }: { entries: AuditEntryView[] }) {
  if (!entries.length)
    return (
      <EmptyState
        title="No projected audit entries"
        description="The immutable audit projection may still be processing. No entries are created by the frontend."
      />
    );
  return (
    <div
      className="vm-table-wrap"
      style={{
        borderTop: "1px solid var(--border)",
        borderRadius: "var(--radius-md)",
      }}
    >
      <table
        className="vm-table vm-audit-table"
        aria-label="Immutable case audit history"
      >
        <thead>
          <tr>
            <th scope="col">Timestamp</th>
            <th scope="col">Actor</th>
            <th scope="col">Role</th>
            <th scope="col">Action</th>
            <th scope="col">Resource</th>
            <th scope="col">Outcome</th>
            <th scope="col">Version</th>
            <th scope="col">Source</th>
            <th scope="col">Details</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td className="vm-tabular">{formatTimestamp(entry.timestamp)}</td>
              <td>{entry.actor}</td>
              <td>{entry.actorRole}</td>
              <td>{entry.action}</td>
              <td>{entry.resource}</td>
              <td>
                <StatusBadge status={entry.outcome} />
              </td>
              <td>
                {entry.priorVersion ?? "-"} → {entry.resultingVersion ?? "-"}
              </td>
              <td>{entry.requestSource}</td>
              <td>
                <TechnicalDetailsDisclosure>
                  <dl>
                    <dt>Correlation</dt>
                    <dd>
                      <code>{entry.correlationId}</code>
                    </dd>
                    <dt>Causation</dt>
                    <dd>
                      <code>{entry.causationId ?? "None"}</code>
                    </dd>
                    <dt>Identity provider</dt>
                    <dd>{entry.identityProvider ?? "Not supplied"}</dd>
                    <dt>Authentication</dt>
                    <dd>{entry.authenticationMethod ?? "Not supplied"}</dd>
                    <dt>Resource UUID</dt>
                    <dd>
                      <code>{entry.resourceId}</code>
                    </dd>
                    <dt>Reason</dt>
                    <dd>{entry.reason ?? "Not supplied"}</dd>
                  </dl>
                </TechnicalDetailsDisclosure>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
