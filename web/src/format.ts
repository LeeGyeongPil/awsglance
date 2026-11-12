// 화면 글자 도우미: 자원 종류·보안 기능 이름, 값 표시. 사용자에게 보이는 문구는 i18n.ts 의 표에서 온다.
import type { Translator } from "./i18n";

export const SEVERITY_ICON = {
  critical: "■",
  high: "▲",
  medium: "◆",
  low: "●",
} as const;

export function severityLabel(t: Translator, severity: string): string {
  return t.has(`sev.${severity}`) ? t(`sev.${severity}`) : severity;
}

export function actorLabel(t: Translator, cls: string): string {
  return t.has(`actor.${cls}`) ? t(`actor.${cls}`) : cls;
}

// 모르는 새 종류는 코드 이름 그대로 보여 준다
export function typeLabel(t: Translator, resourceType: string): string {
  return t.has(`type.${resourceType}`) ? t(`type.${resourceType}`) : resourceType;
}

export function featureLabel(t: Translator, feature: string): string {
  return t.has(`feature.${feature}`) ? t(`feature.${feature}`) : feature;
}

export function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map((v) => show(v)).join(", ") : "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
