// 화면 글자 도우미: 시각·심각도·자원 종류 이름 등.
import type { ActorClass, Severity } from "./api";

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "치명",
  high: "높음",
  medium: "보통",
  low: "낮음",
};

export const SEVERITY_ICON: Record<Severity, string> = {
  critical: "■",
  high: "▲",
  medium: "◆",
  low: "●",
};

export const ACTOR_LABEL: Record<ActorClass, string> = {
  human: "사람",
  automated: "자동",
  unknown: "판단 보류",
};

export const TYPE_LABEL: Record<string, string> = {
  ec2_instance: "EC2 인스턴스",
  vpc: "VPC",
  subnet: "서브넷",
  security_group: "보안 그룹",
  rds_instance: "RDS DB",
  lambda_function: "Lambda 함수",
  load_balancer: "로드 밸런서",
  log_group: "로그 그룹",
  s3_bucket: "S3 버킷",
  iam_user: "IAM 사용자",
  iam_access_key: "액세스 키",
  iam_role: "IAM 역할",
};

export const FEATURE_LABEL: Record<string, string> = {
  guardduty: "GuardDuty",
  securityhub: "Security Hub",
  config: "AWS Config",
  accessanalyzer: "Access Analyzer",
  cloudtrail_multi_region: "다중 리전 트레일",
  s3_account_public_access_block: "계정 S3 공개 차단",
};

export function typeLabel(t: string): string {
  return TYPE_LABEL[t] ?? t;
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "—";
  const sec = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (sec < 60) return "방금";
  if (sec < 3600) return `${Math.floor(sec / 60)}분 전`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}시간 전`;
  return `${Math.floor(sec / 86400)}일 전`;
}

export function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map((v) => show(v)).join(", ") : "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
