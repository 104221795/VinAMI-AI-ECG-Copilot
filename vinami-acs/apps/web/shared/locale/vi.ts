const GENERIC_LABELS: Record<string, string> = {
  acknowledge: "Ghi nhận",
  acknowledged: "Đã ghi nhận",
  active: "Đang hoạt động",
  amended: "Đã hiệu chỉnh",
  available: "Có sẵn",
  below_threshold: "Dưới ngưỡng mô hình",
  cancelled: "Đã hủy",
  cardiac_troponin_i: "Troponin tim I",
  cardiac_troponin_t: "Troponin tim T",
  cardiology_review: "Hội chẩn Tim mạch",
  cath_lab_review: "Bác sĩ yêu cầu xem xét can thiệp",
  critical: "Khẩn cấp",
  current: "Hiện hành",
  duplicate: "Trùng lặp",
  failed: "Thất bại",
  final: "Cuối cùng",
  healthy: "Ổn định",
  incomplete: "Chưa đủ",
  in_progress: "Đang xử lý",
  identity: "Giữ nguyên",
  local_upload: "Tải lên tại chỗ",
  manual: "Nhập tay",
  missing: "Thiếu dữ liệu",
  mock: "Mô phỏng",
  none: "Không có",
  not_assessed: "Chưa đánh giá",
  not_requested: "Chưa yêu cầu",
  not_started: "Chưa bắt đầu",
  open: "Đang mở",
  original: "Bản gốc",
  overdue: "Quá hạn",
  pending: "Đang chờ",
  physician: "Bác sĩ",
  "physician review required": "Cần bác sĩ rà soát",
  physician_reassessment: "Bác sĩ đánh giá lại",
  priority: "Ưu tiên",
  provider: "Nhà cung cấp mô hình",
  ready: "Sẵn sàng",
  requested: "Đã yêu cầu",
  resolved: "Đã xử lý",
  review: "Cần rà soát",
  reviewed: "Đã rà soát",
  routine: "Thường quy",
  stale: "Cũ",
  success: "Thành công",
  technically_limited: "Giới hạn kỹ thuật",
  technical_limit: "Giới hạn kỹ thuật",
  unavailable: "Không khả dụng",
  unknown: "Chưa rõ",
  unresolved: "Chưa xử lý",
  urgent: "Ưu tiên cao",
  "mi-related ecg pattern": "Mẫu ECG liên quan MI",
  "model scores are not clinical probabilities":
    "Điểm mô hình không phải xác suất lâm sàng",
  evidence_reviewed: "Bằng chứng đã rà soát",
  hs_ctni: "hs-cTnI",
  hs_ctnt: "hs-cTnT",
};

const PRIORITY_LABELS: Record<string, string> = {
  routine: "Thường quy",
  priority: "Ưu tiên",
  urgent: "Ưu tiên cao",
  critical: "Khẩn cấp",
};

const WORKFLOW_STATE_LABELS: Record<string, string> = {
  NEW: "Ca mới",
  TRIAGE_IN_PROGRESS: "Đang tiếp nhận ban đầu",
  AWAITING_ECG: "Chờ ECG",
  ECG_UNDER_REVIEW: "Đang rà soát ECG",
  AWAITING_TROPONIN: "Chờ Troponin",
  OBSERVATION: "Theo dõi",
  PHYSICIAN_REVIEW_REQUIRED: "Cần bác sĩ đánh giá",
  PATHWAY_SELECTED: "Đã chọn hướng xử trí",
  TRANSFER_IN_PROGRESS: "Đang chuyển tuyến/chuyển đơn vị",
  CATH_LAB_REVIEW: "Xem xét can thiệp",
  DISCHARGE_REVIEW: "Rà soát trước ra viện",
  CLOSED: "Đã đóng ca",
  CANCELLED: "Đã hủy ca",
};

const TASK_LABELS: Record<string, string> = {
  repeat_ecg: "Lặp lại ECG",
  repeat_troponin: "Lặp lại Troponin",
  obtain_additional_information: "Bổ sung thông tin",
  cardiology_review: "Hội chẩn Tim mạch",
  cath_lab_review: "Bác sĩ yêu cầu xem xét can thiệp",
  physician_reassessment: "Bác sĩ đánh giá lại",
  other_documented_task: "Công việc khác đã ghi nhận",
};

const DECISION_LABELS: Record<string, string> = {
  continue_observation: "Tiếp tục theo dõi",
  request_repeat_ecg: "Yêu cầu lặp lại ECG",
  request_repeat_troponin: "Yêu cầu lặp lại Troponin",
  request_additional_information: "Yêu cầu bổ sung thông tin",
  request_cardiology_review: "Yêu cầu hội chẩn Tim mạch",
  request_cath_lab_review: "Bác sĩ yêu cầu xem xét can thiệp",
  maintain_current_plan: "Duy trì kế hoạch hiện tại",
  other_documented_plan: "Kế hoạch khác đã ghi nhận",
};

const EVIDENCE_LABELS: Record<string, string> = {
  triage: "Tiếp nhận ban đầu",
  symptom_onset: "Thời điểm khởi phát triệu chứng",
  risk_factors: "Yếu tố nguy cơ",
  vitals: "Dấu hiệu sinh tồn",
  ecg: "ECG",
  troponin: "Troponin",
  clinical_case: "Ca lâm sàng",
  repeat_troponin: "Troponin lặp lại",
  repeat_ecg: "ECG lặp lại",
};

const OBSERVATION_LABELS: Record<string, string> = {
  present: "Có",
  absent: "Không có",
  unknown: "Chưa rõ",
  not_assessed: "Chưa đánh giá",
  exact: "Chính xác",
  approximate: "Ước lượng",
  date_only: "Chỉ biết ngày",
};

const CLINICAL_LABELS: Record<string, string> = {
  body_temperature: "Nhiệt độ",
  diastolic_blood_pressure: "Huyết áp tâm trương",
  heart_rate: "Nhịp tim",
  oxygen_saturation: "SpO2",
  pain_score: "Điểm đau",
  respiratory_rate: "Nhịp thở",
  systolic_blood_pressure: "Huyết áp tâm thu",
  dyspnoea: "Khó thở",
  nausea: "Buồn nôn",
  smoking_history: "Tiền sử hút thuốc",
  diabetes_history: "Tiền sử đái tháo đường",
  smoking: "Hút thuốc",
  diabetes: "Đái tháo đường",
};

const SAFETY_NOTICES: Record<string, string> = {
  "Research-use prototype. Evidence synthesis does not diagnose ACS or AMI.":
    "Nguyên mẫu phục vụ nghiên cứu. Tổng hợp bằng chứng không chẩn đoán ACS hoặc nhồi máu cơ tim cấp.",
  "Demonstration workflow - not for clinical use.":
    "Quy trình minh họa - không dùng cho chăm sóc lâm sàng.",
  "Demonstration workflow — not for clinical use.":
    "Quy trình minh họa - không dùng cho chăm sóc lâm sàng.",
  "Demonstration automation - not for clinical use.":
    "Tự động hóa minh họa - không dùng cho chăm sóc lâm sàng.",
  "Demonstration rule - not for clinical use.":
    "Luật minh họa - không dùng cho chăm sóc lâm sàng.",
  "Demonstration rule — not for clinical use.":
    "Luật minh họa - không dùng cho chăm sóc lâm sàng.",
  "Task completion does not imply diagnosis or case closure.":
    "Hoàn tất công việc không đồng nghĩa với chẩn đoán hoặc đóng ca.",
  "Operational workflow only. Task completion does not imply diagnosis, disposition or case closure.":
    "Chỉ là quy trình điều phối. Hoàn tất công việc không đồng nghĩa với chẩn đoán, hướng xử trí hoặc đóng ca.",
  "Missing, unknown, stale, or technically limited evidence is not negative evidence.":
    "Dữ liệu thiếu, chưa rõ, cũ hoặc giới hạn kỹ thuật không được xem là bằng chứng âm tính.",
  "Model scores are not clinical probabilities.":
    "Điểm mô hình không phải xác suất lâm sàng.",
  "Model-attention aid; not causal clinical evidence.":
    "Bản đồ chú ý của mô hình chỉ hỗ trợ diễn giải, không phải bằng chứng nhân quả lâm sàng.",
};

const EVENT_LABELS: Record<string, string> = {
  PatientRegistered: "Đăng ký bệnh nhân",
  EncounterStarted: "Bắt đầu lần tiếp nhận",
  ClinicalCaseOpened: "Mở ca ACS nghi ngờ",
  SymptomsRecorded: "Ghi nhận triệu chứng",
  VitalsRecorded: "Ghi nhận dấu hiệu sinh tồn",
  ECGUploaded: "Nạp ECG",
  ECGQualityAssessed: "Đánh giá chất lượng ECG",
  AIAnalysisRequested: "Yêu cầu phân tích AI",
  AIAnalysisCompleted: "Hoàn tất phân tích AI",
  AIAnalysisFailed: "Phân tích AI thất bại",
  TroponinOrdered: "Chỉ định Troponin",
  TroponinCollected: "Đã lấy mẫu Troponin",
  TroponinResulted: "Có kết quả Troponin",
  RepeatECGRequested: "Yêu cầu lặp lại ECG",
  RepeatECGDue: "Đến hạn lặp lại ECG",
  ClinicalPathwaySuggested: "Đề xuất hướng xử trí minh họa",
  PhysicianReviewRequested: "Yêu cầu bác sĩ rà soát",
  PhysicianDecisionRecorded: "Ghi quyết định của bác sĩ",
  TaskCreated: "Tạo công việc",
  TaskCompleted: "Hoàn tất công việc",
  AlertRaised: "Tạo cảnh báo",
  AlertAcknowledged: "Ghi nhận cảnh báo",
  CathLabReviewRequested: "Yêu cầu xem xét can thiệp",
  TransferRequested: "Yêu cầu chuyển tuyến/chuyển đơn vị",
  CaseClosed: "Đóng ca",
};

export function viStatus(value?: string | null): string {
  return labelFrom(GENERIC_LABELS, value);
}

export function viPriority(value?: string | null): string {
  return labelFrom(PRIORITY_LABELS, value);
}

export function viWorkflowState(value?: string | null): string {
  if (!value) return "Chưa ghi nhận";
  return WORKFLOW_STATE_LABELS[workflowKey(value)] ?? viStatus(value);
}

export function viTaskType(value?: string | null): string {
  return labelFrom(TASK_LABELS, value);
}

export function viDecisionType(value?: string | null): string {
  return labelFrom(DECISION_LABELS, value);
}

export function viEvidence(value?: string | null): string {
  return labelFrom(EVIDENCE_LABELS, value);
}

export function viObservationState(value?: string | null): string {
  return labelFrom(OBSERVATION_LABELS, value);
}

export function viClinicalLabel(value?: string | null): string {
  return labelFrom(CLINICAL_LABELS, value);
}

export function viSafetyNotice(value?: string | null): string {
  if (!value) return "Nguyên tắc an toàn chưa được ghi nhận.";
  return SAFETY_NOTICES[value] ?? value;
}

export function viEventTitle(
  eventType?: string | null,
  fallback?: string | null,
): string {
  if (eventType && EVENT_LABELS[eventType]) return EVENT_LABELS[eventType];
  if (fallback && EVENT_LABELS[fallback]) return EVENT_LABELS[fallback];
  if (fallback) return fallback;
  return viClinicalTerm(eventType);
}

export function viBooleanState(value: boolean): string {
  return value ? "Có" : "Không";
}

export function viCount(value: number, noun: string): string {
  return `${new Intl.NumberFormat("vi-VN").format(value)} ${noun}`;
}

export function viAction(value?: string | null): string {
  return labelFrom(
    {
      assign: "Gán phụ trách",
      acknowledge: "Ghi nhận",
      start: "Bắt đầu",
      complete: "Hoàn tất",
      cancel: "Hủy",
      resolve: "Xử lý xong",
      revoke: "Thu hồi",
    },
    value,
  );
}

export function viClinicalTerm(value?: string | null): string {
  if (!value) return "Chưa ghi nhận";
  return (
    WORKFLOW_STATE_LABELS[value] ??
    TASK_LABELS[value] ??
    DECISION_LABELS[value] ??
    EVIDENCE_LABELS[value] ??
    OBSERVATION_LABELS[value] ??
    CLINICAL_LABELS[value] ??
    GENERIC_LABELS[value.toLowerCase()] ??
    humanize(value)
  );
}

export function viOwnerLabel(userId?: string | null, teamId?: string | null) {
  if (userId) return `Người phụ trách ${shortToken(userId)}`;
  if (teamId) return `Nhóm ${shortToken(teamId)}`;
  return "Chưa phân công";
}

export function shortToken(value: string): string {
  return value.slice(0, 8).toUpperCase();
}

function labelFrom(labels: Record<string, string>, value?: string | null) {
  if (!value) return "Chưa ghi nhận";
  const lower = value.toLowerCase();
  const normalized = lower.replaceAll("-", "_").replaceAll(" ", "_");
  return (
    labels[value] ?? labels[lower] ?? labels[normalized] ?? humanize(value)
  );
}

function workflowKey(value: string): string {
  return value.replaceAll("-", "_").replaceAll(" ", "_").toUpperCase();
}

function humanize(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase()
    .replace(/^\p{L}/u, (letter) => letter.toUpperCase());
}
