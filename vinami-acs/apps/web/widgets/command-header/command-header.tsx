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
        {publicConfig.researchUse && (
          <Badge tone="warning">MVP nghiên cứu</Badge>
        )}
      </div>
      <div className="vm-command-header__status">
        <span
          className={`vm-connectivity ${online ? "is-online" : "is-offline"}`}
          role="status"
        >
          {online ? <Wifi size={16} /> : <WifiOff size={16} />}
          {online ? "Đang kết nối" : "Mất kết nối"}
        </span>
        {identity ? (
          <span className="vm-identity">
            <strong>{identity.displayName}</strong>
            <small>{identity.primaryRole}</small>
            {identity.developmentOnly && (
              <Badge tone="warning">Danh tính phát triển</Badge>
            )}
          </span>
        ) : (
          <Badge tone="critical">Phiên không khả dụng</Badge>
        )}
        <IconButton
          label="Làm mới thông tin hiện tại"
          disabled={refreshing}
          onClick={() => startTransition(() => router.refresh())}
        >
          <RefreshCw size={18} className={refreshing ? "vm-spin" : ""} />
        </IconButton>
      </div>
    </header>
  );
}
