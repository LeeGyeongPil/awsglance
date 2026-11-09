// 백엔드 /api/* 의 응답 모양과 호출 함수. 화면은 이 파일만 거쳐 서버와 이야기한다.
import { useCallback, useEffect, useState } from "react";

export type Severity = "critical" | "high" | "medium" | "low";
export type TrustLevel = "ok" | "warn" | "danger" | "unknown";
export type ActorClass = "human" | "automated" | "unknown";

export interface Trust {
  level: TrustLevel;
  reason: string;
  at: string | null;
}

export interface Identity {
  account: string;
  arn: string;
  user_id: string;
}

export interface Status {
  version: string;
  mode: "demo" | "live";
  identity: Identity | null;
  regions: string[];
  last_inventory: string | null;
  last_cloudtrail: string | null;
  trust: Trust;
  collecting: string | null;
}

export interface PermissionRow {
  collector: string;
  label: string;
  service: string;
  operation: string;
  region: string;
  status: "allowed" | "denied" | "unavailable" | "error" | "blocked";
  detail: string;
}

export interface Setup {
  identity: Identity | null;
  mode: string;
  regions: string[];
  checked_at: string | null;
  permissions: PermissionRow[];
  counts: Record<string, number>;
  policy: unknown;
  managed_policies: string[];
}

export interface Posture {
  regions?: string[];
  matrix?: Record<string, Record<string, string>>;
}

export interface CheckRow {
  rule_id: string;
  severity: Severity;
  title: string;
  count: number;
  example: string;
  finding_id: number;
}

export interface DayBar {
  date: string;
  human: number;
  automated: number;
  unknown: number;
  resource_changes: number;
}

export interface Overview {
  trust: Trust;
  checks: CheckRow[];
  kpi: { resources: number; events_24h: number; changes_24h: number; open_findings: number; last_collect: string | null };
  severity_counts: Record<Severity, number>;
  since_24h: { new: number; reopened: number; resolved: number; human_changes: number };
  bars: DayBar[];
  posture: Posture;
}

export interface Resource {
  key: string;
  type: string;
  region: string;
  id: string;
  name: string;
  props: Record<string, unknown>;
  tags: Record<string, string>;
  first_seen: string;
  last_seen: string;
  deleted_at: string | null;
  open_findings?: number;
}

export interface FieldChange {
  field: string;
  before: unknown;
  after: unknown;
}

export interface ResourceChange {
  id: number;
  at: string;
  key: string;
  type: string;
  region: string;
  name: string;
  kind: "created" | "deleted" | "modified";
  fields: FieldChange[];
  noise: boolean | number;
  summary: string;
}

export interface TrailEvent {
  event_id: string;
  region: string;
  time: string;
  name: string;
  source: string;
  actor: string;
  actor_class: ActorClass;
  via: string;
  is_root: boolean | number;
  reason: string;
  error_code: string | null;
  resources: { type: string | null; name: string | null }[];
  request: Record<string, unknown>;
}

export interface Rule {
  id: string;
  severity: Severity;
  category: string;
  title: string;
  description: string;
  remediation: string;
}

export type FindingStatus = "open" | "suppressed" | "resolved" | "closed";

export interface Finding {
  id: number;
  rule_id: string;
  target: string;
  severity: Severity;
  title: string;
  detail: string;
  region: string;
  resource_key: string | null;
  status: FindingStatus;
  first_seen: string;
  last_seen: string;
  resolved_at: string | null;
  reopen_count: number;
  suppress_reason: string | null;
  suppress_until: string | null;
  close_reason: string | null;
  rule: Rule | null;
}

export interface FindingDetail extends Finding {
  actions: { id: number; at: string; action: string; note: string | null }[];
  max_suppress_days: number | null;
}

export interface ResourceDetail {
  resource: Resource;
  changes: ResourceChange[];
  events: TrailEvent[];
  // exact: 자원 ID·ARN 이 정확히 같은 이벤트만 / unsupported: 이 종류는 이벤트와 연결하지 않음
  events_match: "exact" | "unsupported";
  findings: Finding[];
}

export interface ChangesResponse {
  tab: string;
  events: TrailEvent[];
  resource_changes: ResourceChange[];
  counts: Partial<Record<ActorClass, number>>;
}

export interface FindingsResponse {
  items: Finding[];
  counts: Partial<Record<FindingStatus, number>>;
}

export interface ResourcesResponse {
  items: Resource[];
  total: number;
  facets: { types: Record<string, number>; regions: Record<string, number> };
}

// 정적 내보내기(awsglance export)가 index.html 에 넣어 두는 응답 모음: 요청 경로 → 응답 JSON
interface Snapshot {
  api: Record<string, unknown>;
  exported_at?: string;
}

function readSnapshot(): Snapshot | null {
  const snap = (window as { __AWSGLANCE_SNAPSHOT__?: Snapshot }).__AWSGLANCE_SNAPSHOT__;
  return snap ?? null;
}

// 스냅샷에서 답을 찾는다: 정확히 같은 주소 → 없으면 같은 경로의 기본 응답(필터를 바꿔도 화면이 비지 않게)
function fromSnapshot<T>(snap: Snapshot, path: string): T {
  if (path in snap.api) return snap.api[path] as T;
  const base = path.split("?")[0];
  const key = Object.keys(snap.api).find((k) => k.split("?")[0] === base);
  if (key !== undefined) return snap.api[key] as T;
  throw new Error("내보낸 사본에 없는 화면입니다 (서버를 실행하면 모두 볼 수 있습니다)");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const snap = readSnapshot();
  if (snap) {
    if (init?.method && init.method !== "GET") throw new Error("내보낸 사본에서는 읽기만 됩니다");
    return fromSnapshot<T>(snap, path);
  }
  const res = await fetch(path, { credentials: "same-origin", ...init });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      detail = (await res.text().catch(() => "")) || detail;
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function getJSON<T>(path: string): Promise<T> {
  return request<T>(path);
}

// 상태를 바꾸는 요청은 항상 JSON — 서버가 다른 형식(폼 몰래 보내기)을 거부한다
export function postJSON<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

// 주소(path)가 바뀌면 다시 불러오는 작은 훅. 늦게 도착한 옛 응답은 버린다.
export function useApi<T>(path: string | null): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(path !== null);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (path === null) return;
    let alive = true;
    setLoading(true);
    getJSON<T>(path)
      .then((d) => {
        if (alive) {
          setData(d);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, tick]);

  return { data, error, loading, reload };
}
