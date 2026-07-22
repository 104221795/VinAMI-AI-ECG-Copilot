import type { Metadata } from "next";
import { PageHeader } from "@vinami/ui";
import { loadSystemHealth } from "@web/features/system-health/data";
import { SystemHealth } from "@web/features/system-health/system-health";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { presentError } from "@web/shared/errors/presentation";

export const metadata: Metadata = { title: "Trạng thái hệ thống" };

export default async function SystemHealthPage() {
  try {
    const value = await loadSystemHealth();
    return (
      <>
        <PageHeader
          eyebrow="Vận hành kỹ thuật"
          title="Trạng thái hệ thống"
          description="Kiểm tra sẵn sàng của phụ thuộc được tách khỏi hàng đợi lâm sàng và không chứa thông tin bệnh nhân."
        />
        <SystemHealth value={value} />
      </>
    );
  } catch (error) {
    return (
      <>
        <PageHeader eyebrow="Vận hành kỹ thuật" title="Trạng thái hệ thống" />
        <ErrorPanel presentation={presentError(error)} />
      </>
    );
  }
}
