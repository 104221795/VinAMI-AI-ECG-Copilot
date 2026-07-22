"use client";

import {
  Activity,
  ClipboardList,
  FileClock,
  HeartPulse,
  ListTodo,
  NotebookText,
  Stethoscope,
  ServerCog,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { publicConfig } from "@web/shared/config/public";

function navClass(active: boolean) {
  return `vm-nav-link${active ? " vm-nav-link--active" : ""}`;
}

export function ClinicalSidebar() {
  const pathname = usePathname();
  const caseMatch = pathname.match(/^\/cases\/([^/]+)/);
  const caseId = caseMatch?.[1];
  return (
    <aside className="vm-sidebar" aria-label="Điều hướng chính">
      <div className="vm-brand">
        <span className="vm-brand__mark" aria-hidden="true">
          <HeartPulse size={21} />
        </span>
        <div>
          <strong>{publicConfig.productName}</strong>
          <span>{publicConfig.organizationName}</span>
        </div>
      </div>
      <nav>
        <p className="vm-nav-label">Điều phối lâm sàng</p>
        <Link
          href="/command-center"
          className={navClass(pathname === "/command-center")}
        >
          <ClipboardList size={18} /> Trung tâm điều phối
        </Link>
        {caseId && (
          <div className="vm-case-nav">
            <p className="vm-nav-label">Ca đang chọn</p>
            <Link
              href={`/cases/${caseId}`}
              className={navClass(pathname === `/cases/${caseId}`)}
            >
              <Activity size={18} /> Tổng quan
            </Link>
            <Link
              href={`/cases/${caseId}/documentation`}
              className={navClass(pathname.endsWith("/documentation"))}
            >
              <NotebookText size={18} /> Tiếp nhận / Sinh hiệu
            </Link>
            <Link
              href={`/cases/${caseId}/ecg`}
              className={navClass(pathname.endsWith("/ecg"))}
            >
              <HeartPulse size={18} /> ECG
            </Link>
            <Link
              href={`/cases/${caseId}/troponin`}
              className={navClass(pathname.endsWith("/troponin"))}
            >
              <ClipboardList size={18} /> Troponin
            </Link>
            <Link
              href={`/cases/${caseId}/clinical-reasoning`}
              className={navClass(pathname.endsWith("/clinical-reasoning"))}
            >
              <Stethoscope size={18} /> Tổng hợp lâm sàng
            </Link>
            <Link
              href={`/cases/${caseId}/workflow`}
              className={navClass(pathname.endsWith("/workflow"))}
            >
              <ListTodo size={18} /> Quy trình
            </Link>
            <Link
              href={`/cases/${caseId}/timeline`}
              className={navClass(pathname.endsWith("/timeline"))}
            >
              <FileClock size={18} /> Dòng thời gian
            </Link>
            <Link
              href={`/cases/${caseId}/audit`}
              className={navClass(pathname.endsWith("/audit"))}
            >
              <ShieldCheck size={18} /> Nhật ký kiểm chứng
            </Link>
          </div>
        )}
        <p className="vm-nav-label vm-nav-label--system">Hệ thống</p>
        <Link
          href="/system-health"
          className={navClass(pathname === "/system-health")}
        >
          <ServerCog size={18} /> Trạng thái hệ thống
        </Link>
      </nav>
      <footer>
        <span className="vm-research-dot" />
        <div>
          <strong>Nguyên mẫu nghiên cứu</strong>
          <span>Không dùng để ra quyết định chăm sóc</span>
        </div>
      </footer>
    </aside>
  );
}
