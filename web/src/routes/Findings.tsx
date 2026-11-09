// 문제(발견 사항): 상태 탭 → 규칙별 묶음/낱개 목록 → 상세 드로어(설명·대응 방법·처리 기록) → 숨김(사유·기한)·닫기·다시 열기.
import { useCallback, useState } from "react";
import { postJSON, useApi, type Finding, type FindingDetail, type FindingStatus, type FindingsResponse, type Severity } from "../api";
import { Drawer, Empty, ErrorBox, Link, Loading, SeverityBadge, Tabs } from "../components/ui";
import { fmtTime, SEVERITY_LABEL } from "../format";
import { useQueryState } from "../router";

type StatusTab = FindingStatus | "all";

const STATUS_LABEL: Record<FindingStatus, string> = { open: "열림", suppressed: "숨김", resolved: "해결", closed: "닫힘" };
const ACTION_LABEL: Record<string, string> = {
  opened: "처음 발견",
  reopened: "재발",
  resolved: "해결(다시 보이지 않음)",
  suppressed: "숨김",
  suppress_expired: "숨김 기한 지남",
  closed: "닫음",
  reopened_by_user: "다시 열기",
};
const CLOSE_REASONS = [
  { value: "fixed", label: "처리함" },
  { value: "false_positive", label: "오탐" },
  { value: "accepted", label: "위험 감수" },
];

function Actions({ f, onDone }: { f: FindingDetail; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [days, setDays] = useState(Math.min(30, f.max_suppress_days ?? 30));
  const [closeReason, setCloseReason] = useState("fixed");
  const [msg, setMsg] = useState<string | null>(null);
  const run = async (path: string, body: unknown) => {
    try {
      await postJSON(`/api/findings/${f.id}/${path}`, body);
      setMsg(null);
      onDone();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };
  if (f.status === "closed" || f.status === "resolved") {
    return (
      <div className="actions">
        <button type="button" onClick={() => run("reopen", {})}>
          다시 열기
        </button>
        {msg ? <div className="err small">{msg}</div> : null}
      </div>
    );
  }
  return (
    <div className="actions">
      {f.severity === "critical" ? (
        <p className="small muted">치명 심각도는 숨길 수 없습니다. 확인 후 '닫기'로 처리 사유를 남기세요.</p>
      ) : (
        <form
          className="suppress-form"
          onSubmit={(e) => {
            e.preventDefault();
            void run("suppress", { reason, days });
          }}
        >
          <h3>숨기기</h3>
          <label>
            사유(필수) <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="예: 공개 웹 서버라 의도한 설정" required />
          </label>
          <label>
            기한(일, 최대 {f.max_suppress_days}){" "}
            <input type="number" min={1} max={f.max_suppress_days ?? 30} value={days} onChange={(e) => setDays(Number(e.target.value))} />
          </label>
          <button type="submit">숨기기</button>
        </form>
      )}
      <div className="row">
        <h3>닫기</h3>
        <select value={closeReason} onChange={(e) => setCloseReason(e.target.value)} aria-label="닫는 사유">
          {CLOSE_REASONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <button type="button" onClick={() => run("close", { reason: closeReason })}>
          닫기
        </button>
      </div>
      {msg ? <div className="err small">처리하지 못했습니다: {msg}</div> : null}
    </div>
  );
}

function FindingDrawer({ id, onClose, onChanged }: { id: string; onClose: () => void; onChanged: () => void }) {
  const { data, error, loading, reload } = useApi<FindingDetail>(`/api/findings/${encodeURIComponent(id)}`);
  const done = () => {
    reload();
    onChanged();
  };
  return (
    <Drawer title={data ? data.title : "발견 사항"} onClose={onClose}>
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorBox message={error} /> : null}
      {data ? (
        <>
          <p>
            <SeverityBadge severity={data.severity} /> <span className={`chip st-${data.status}`}>{STATUS_LABEL[data.status]}</span>
            {data.reopen_count ? <span className="chip">재발 {data.reopen_count}회</span> : null}
          </p>
          <p className="detail">{data.detail}</p>
          {data.resource_key ? (
            <p className="small">
              자원: <Link to={`/resources?key=${encodeURIComponent(data.resource_key)}`}>{data.resource_key}</Link>
            </p>
          ) : null}
          <dl className="kv small">
            <dt>처음 발견</dt>
            <dd>{fmtTime(data.first_seen)}</dd>
            <dt>마지막 확인</dt>
            <dd>{fmtTime(data.last_seen)}</dd>
            {data.suppress_until ? (
              <>
                <dt>숨김 기한</dt>
                <dd>
                  {fmtTime(data.suppress_until)} — {data.suppress_reason}
                </dd>
              </>
            ) : null}
          </dl>
          {data.rule ? (
            <>
              <h3>왜 문제인가</h3>
              <p>{data.rule.description}</p>
              <h3>어떻게 고치나</h3>
              <p className="remedy">{data.rule.remediation}</p>
              <p className="muted small mono">규칙 {data.rule.id}</p>
            </>
          ) : null}
          <Actions f={data} onDone={done} />
          <h3>처리 기록</h3>
          <ul className="plain small">
            {data.actions.map((a) => (
              <li key={a.id}>
                <span className="muted">{fmtTime(a.at)}</span> {ACTION_LABEL[a.action] ?? a.action}
                {a.note ? <span className="muted"> — {a.note}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </Drawer>
  );
}

function groupByRule(items: Finding[]): { rule_id: string; title: string; severity: Severity; items: Finding[] }[] {
  const groups = new Map<string, { rule_id: string; title: string; severity: Severity; items: Finding[] }>();
  for (const f of items) {
    const g = groups.get(f.rule_id) ?? { rule_id: f.rule_id, title: f.title, severity: f.severity, items: [] };
    g.items.push(f);
    groups.set(f.rule_id, g);
  }
  return [...groups.values()];
}

export default function Findings() {
  const [query, setQuery] = useQueryState();
  const status = (query.get("status") as StatusTab | null) ?? "open";
  const severity = query.get("severity") ?? "";
  const rule = query.get("rule") ?? "";
  const view = query.get("view") === "list" ? "list" : "group";
  const selected = query.get("id");
  const params = new URLSearchParams({ status, severity, rule });
  const { data, error, loading, reload } = useApi<FindingsResponse>(`/api/findings?${params.toString()}`);
  const closeDrawer = useCallback(() => setQuery({ id: null }), [setQuery]);
  const counts = data?.counts ?? {};

  const row = (f: Finding) => (
    <li key={f.id}>
      <button type="button" className="finding-row" onClick={() => setQuery({ id: String(f.id) })}>
        <SeverityBadge severity={f.severity} />
        <span className="grow">{f.detail}</span>
        <span className="muted small mono">{f.region}</span>
        {f.status !== "open" ? <span className={`chip st-${f.status}`}>{STATUS_LABEL[f.status]}</span> : null}
      </button>
    </li>
  );

  return (
    <div className="page">
      <h1>문제</h1>
      <Tabs<StatusTab>
        value={status}
        onChange={(v) => setQuery({ status: v })}
        options={[
          { value: "open", label: "열림", count: counts.open ?? 0 },
          { value: "suppressed", label: "숨김", count: counts.suppressed ?? 0 },
          { value: "resolved", label: "해결", count: counts.resolved ?? 0 },
          { value: "closed", label: "닫힘", count: counts.closed ?? 0 },
          { value: "all", label: "전체" },
        ]}
      />
      <div className="filters">
        <label>
          심각도{" "}
          <select value={severity} onChange={(e) => setQuery({ severity: e.target.value })}>
            <option value="">전체</option>
            {(Object.keys(SEVERITY_LABEL) as Severity[]).map((s) => (
              <option key={s} value={s}>
                {SEVERITY_LABEL[s]}
              </option>
            ))}
          </select>
        </label>
        {rule ? (
          <span className="chip">
            규칙 <span className="mono">{rule}</span>{" "}
            <button type="button" className="icon-btn" aria-label="규칙 필터 지우기" onClick={() => setQuery({ rule: null })}>
              ✕
            </button>
          </span>
        ) : null}
        <label>
          보기{" "}
          <select value={view} onChange={(e) => setQuery({ view: e.target.value === "list" ? "list" : null })}>
            <option value="group">규칙별 묶음</option>
            <option value="list">낱개</option>
          </select>
        </label>
      </div>
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      {data && data.items.length === 0 ? <Empty>이 조건의 문제가 없습니다.</Empty> : null}
      {data && view === "list" ? <ul className="plain findings">{data.items.map(row)}</ul> : null}
      {data && view === "group"
        ? groupByRule(data.items).map((g) => (
            <section key={g.rule_id} className="card group">
              <h2>
                <SeverityBadge severity={g.severity} /> {g.title} <span className="count">{g.items.length}</span>
              </h2>
              <ul className="plain findings">{g.items.map(row)}</ul>
            </section>
          ))
        : null}
      {selected ? <FindingDrawer id={selected} onClose={closeDrawer} onChanged={reload} /> : null}
    </div>
  );
}
