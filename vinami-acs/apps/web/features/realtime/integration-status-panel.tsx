"use client";

import { useQuery } from "@tanstack/react-query";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { presentError } from "@web/shared/errors/presentation";
import { formatTimestamp } from "@web/shared/formatting";

export function IntegrationStatusPanel() {
  const query = useQuery({
    queryKey: ["r10-integration-status"],
    queryFn: async () => {
      const client = createBrowserApiClient();
      const [messages, connectors] = await Promise.all([
        client.getIntegrationMessages({ limit: 8 }),
        client.getIntegrationConnectorStatus(),
      ]);
      return {
        messages: list(messages),
        connectors: connectorList(connectors),
      };
    },
    staleTime: 20_000,
  });
  if (query.isLoading) {
    return (
      <section className="vm-integration-panel">
        Loading integration status...
      </section>
    );
  }
  if (query.isError) {
    const error = presentError(query.error);
    return (
      <section className="vm-integration-panel vm-integration-panel--error">
        <strong>Integration status unavailable</strong>
        <p>{error.description}</p>
      </section>
    );
  }
  const messages = query.data?.messages ?? [];
  const failed = messages.filter((item) =>
    ["failed", "dead_letter", "retry_pending"].includes(text(item.status)),
  );
  return (
    <section className="vm-integration-panel" aria-label="Integration status">
      <div className="vm-integration-panel__heading">
        <div>
          <strong>Simulated hospital integration</strong>
          <p>
            No production LIS, HIS, EHR, PACS or device connection is
            configured.
          </p>
        </div>
        <button
          className="vm-button vm-button--secondary"
          onClick={() => query.refetch()}
          disabled={query.isFetching}
        >
          {query.isFetching ? "Refreshing" : "Refresh"}
        </button>
      </div>
      <div className="vm-integration-connectors">
        {(query.data?.connectors ?? []).map((connector) => (
          <span key={text(connector.connector_id)}>
            {text(connector.connector_id)} - {text(connector.status)}
          </span>
        ))}
      </div>
      {failed.length ? (
        <div className="vm-integration-errors" role="status">
          {failed.map((item) => (
            <article key={text(item.message_id)}>
              <strong>{text(item.status).replaceAll("_", " ")}</strong>
              <span>
                {text(item.source_system)} - {text(item.message_type)}
              </span>
              <small>{formatTimestamp(text(item.received_at))}</small>
              <p>
                {list(item.validation_errors).join(", ") ||
                  text(item.dead_letter_reason)}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <p className="vm-inline-empty">
          No failed simulated integration messages in the latest ledger view.
        </p>
      )}
    </section>
  );
}

function list(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function connectorList(value: unknown): Record<string, unknown>[] {
  return isRecord(value) ? list(value.connectors) : [];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, fallback = "unknown") {
  return typeof value === "string" && value.length ? value : fallback;
}
