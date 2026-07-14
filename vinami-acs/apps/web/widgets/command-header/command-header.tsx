"use client";

import { RefreshCw, Wifi, WifiOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Badge, IconButton } from "@vinami/ui";
import type { IdentityView } from "@web/entities/identity/model";
import { publicConfig } from "@web/shared/config/public";
import { useConnectivity } from "@web/shared/hooks/use-connectivity";

export function CommandHeader({ identity }: { identity: IdentityView | null }) {
  const online = useConnectivity();
  const router = useRouter();
  const [refreshing, startTransition] = useTransition();
  return (
    <header className="vm-command-header">
      <div className="vm-command-header__context">
        <Badge tone="neutral">{publicConfig.environment}</Badge>
        {publicConfig.researchUse && <Badge tone="warning">Research MVP</Badge>}
      </div>
      <div className="vm-command-header__status">
        <span
          className={`vm-connectivity ${online ? "is-online" : "is-offline"}`}
          role="status"
        >
          {online ? <Wifi size={16} /> : <WifiOff size={16} />}
          {online ? "Connected" : "Offline"}
        </span>
        {identity ? (
          <span className="vm-identity">
            <strong>{identity.displayName}</strong>
            <small>{identity.primaryRole}</small>
            {identity.developmentOnly && (
              <Badge tone="warning">Development identity</Badge>
            )}
          </span>
        ) : (
          <Badge tone="critical">Session unavailable</Badge>
        )}
        <IconButton
          label="Refresh current information"
          disabled={refreshing}
          onClick={() => startTransition(() => router.refresh())}
        >
          <RefreshCw size={18} className={refreshing ? "vm-spin" : ""} />
        </IconButton>
      </div>
    </header>
  );
}
