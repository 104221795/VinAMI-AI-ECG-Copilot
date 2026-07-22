"use client";

import { useQuery } from "@tanstack/react-query";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { presentError } from "@web/shared/errors/presentation";
import { formatTimestamp } from "@web/shared/formatting";
import { viClinicalTerm, viStatus } from "@web/shared/locale/vi";

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
        Đang tải trạng thái tích hợp...
      </section>
    );
  }
  if (query.isError) {
    const error = presentError(query.error);
    return (
      <section className="vm-integration-panel vm-integration-panel--error">
        <strong>Không tải được trạng thái tích hợp</strong>
        <p>{error.description}</p>
      </section>
    );
  }
  const messages = query.data?.messages ?? [];
  const reviewQueue = messages.filter(
    (item) =>
      item.review_required === true ||
      ["failed", "dead_letter", "retry_pending"].includes(text(item.status)),
  );
  return (
    <section className="vm-integration-panel" aria-label="Trạng thái tích hợp">
      <div className="vm-integration-panel__heading">
        <div>
          <strong>Tích hợp bệnh viện mô phỏng</strong>
          <p>
            Chưa cấu hình kết nối sản xuất tới LIS, HIS, EHR, PACS hoặc thiết
            bị.
          </p>
        </div>
        <button
          className="vm-button vm-button--secondary"
          onClick={() => query.refetch()}
          disabled={query.isFetching}
        >
          {query.isFetching ? "Đang làm mới" : "Làm mới"}
        </button>
      </div>
      <div className="vm-integration-connectors">
        {(query.data?.connectors ?? []).map((connector) => (
          <span key={text(connector.connector_id)}>
            {text(connector.connector_id)} - {viStatus(text(connector.status))}
          </span>
        ))}
      </div>
      {reviewQueue.length ? (
        <div className="vm-integration-errors" role="status">
          {reviewQueue.map((item) => (
            <article key={text(item.message_id)}>
              <strong>
                {viClinicalTerm(
                  text(item.reconciliation_status, text(item.status)),
                )}
              </strong>
              <span>
                {text(item.source_system)} - {text(item.message_type)}
              </span>
              <small>{formatTimestamp(text(item.received_at))}</small>
              <p>
                {text(
                  item.reconciliation_reason,
                  text(item.dead_letter_reason),
                )}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <p className="vm-inline-empty">
          Không có thông điệp tích hợp mô phỏng nào cần rà soát đối soát.
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

function text(value: unknown, fallback = "chưa rõ") {
  return typeof value === "string" && value.length ? value : fallback;
}
