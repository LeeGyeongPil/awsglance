// 문제(발견 사항): 상태 탭 → 규칙별 묶음/낱개 목록 → 상세 드로어(설명·대응 방법·처리 기록) → 숨김(사유·기한)·닫기·다시 열기.
import { useCallback, useState } from "react";
import {
  postJSON,
  toFailure,
  useApi,
  type Finding,
  type FindingDetail,
  type FindingStatus,
  type FindingsResponse,
  type Severity,
} from "../api";
import { Drawer, Empty, ErrorBox, Link, Loading, SeverityBadge, Tabs } from "../components/ui";
import { severityLabel } from "../format";
import { errorText, findingDetail, fmtTime, ruleText, type Failure } from "../i18n";
import { useI18n } from "../lang";
import { useQueryState } from "../router";

type StatusTab = FindingStatus | "all";

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];
const CLOSE_REASONS = ["fixed", "false_positive", "accepted"];

function Actions({ f, onDone }: { f: FindingDetail; onDone: () => void }) {
  const { t } = useI18n();
  const [reason, setReason] = useState("");
  const [days, setDays] = useState(Math.min(30, f.max_suppress_days ?? 30));
  const [closeReason, setCloseReason] = useState("fixed");
  const [msg, setMsg] = useState<Failure | null>(null);
  const run = async (path: string, body: unknown) => {
    try {
      await postJSON(`/api/findings/${f.id}/${path}`, body);
      setMsg(null);
      onDone();
    } catch (e) {
      setMsg(toFailure(e));
    }
  };
  if (f.status === "closed" || f.status === "resolved") {
    return (
      <div className="actions">
        <button type="button" onClick={() => run("reopen", {})}>
          {t("fi.reopen")}
        </button>
        {msg ? <div className="err small">{errorText(t, msg)}</div> : null}
      </div>
    );
  }
  return (
    <div className="actions">
      {f.severity === "critical" ? (
        <p className="small muted">{t("fi.critical_note")}</p>
      ) : (
        <form
          className="suppress-form"
          onSubmit={(e) => {
            e.preventDefault();
            void run("suppress", { reason, days });
          }}
        >
          <h3>{t("fi.suppress_h")}</h3>
          <label>
            {t("fi.suppress_reason")}{" "}
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("fi.suppress_reason_ph")} required />
          </label>
          <label>
            {t("fi.suppress_days", { max: f.max_suppress_days })}{" "}
            <input type="number" min={1} max={f.max_suppress_days ?? 30} value={days} onChange={(e) => setDays(Number(e.target.value))} />
          </label>
          <button type="submit">{t("fi.suppress_btn")}</button>
        </form>
      )}
      <div className="row">
        <h3>{t("fi.close_h")}</h3>
        <select value={closeReason} onChange={(e) => setCloseReason(e.target.value)} aria-label={t("fi.close_reason_label")}>
          {CLOSE_REASONS.map((r) => (
            <option key={r} value={r}>
              {t(`fi.close_${r}`)}
            </option>
          ))}
        </select>
        <button type="button" onClick={() => run("close", { reason: closeReason })}>
          {t("fi.close_btn")}
        </button>
      </div>
      {msg ? <div className="err small">{t("fi.action_failed", { message: errorText(t, msg) })}</div> : null}
    </div>
  );
}

function FindingDrawer({ id, onClose, onChanged }: { id: string; onClose: () => void; onChanged: () => void }) {
  const { t, lang } = useI18n();
  const { data, error, loading, reload } = useApi<FindingDetail>(`/api/findings/${encodeURIComponent(id)}`);
  const done = () => {
    reload();
    onChanged();
  };
  return (
    <Drawer title={data ? ruleText(t, data.rule_id, "title", data.title) : t("fi.drawer_default")} onClose={onClose}>
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorBox failure={error} /> : null}
      {data ? (
        <>
          <p>
            <SeverityBadge severity={data.severity} /> <span className={`chip st-${data.status}`}>{t(`fi.status_${data.status}`)}</span>
            {data.reopen_count ? <span className="chip">{t("fi.reopened_times", { count: data.reopen_count })}</span> : null}
          </p>
          <p className="detail">{findingDetail(t, data)}</p>
          {data.resource_key ? (
            <p className="small">
              {t("fi.resource")}: <Link to={`/resources?key=${encodeURIComponent(data.resource_key)}`}>{data.resource_key}</Link>
            </p>
          ) : null}
          <dl className="kv small">
            <dt>{t("fi.first_seen")}</dt>
            <dd>{fmtTime(lang, data.first_seen)}</dd>
            <dt>{t("fi.last_seen")}</dt>
            <dd>{fmtTime(lang, data.last_seen)}</dd>
            {data.suppress_until ? (
              <>
                <dt>{t("fi.suppress_until")}</dt>
                <dd>
                  {fmtTime(lang, data.suppress_until)} — {data.suppress_reason}
                </dd>
              </>
            ) : null}
          </dl>
          {data.rule ? (
            <>
              <h3>{t("fi.why")}</h3>
              <p>{ruleText(t, data.rule.id, "description", data.rule.description)}</p>
              <h3>{t("fi.how")}</h3>
              <p className="remedy">{ruleText(t, data.rule.id, "remediation", data.rule.remediation)}</p>
              <p className="muted small mono">{t("fi.rule_id", { id: data.rule.id })}</p>
            </>
          ) : null}
          <Actions f={data} onDone={done} />
          <h3>{t("fi.history")}</h3>
          <ul className="plain small">
            {data.actions.map((a) => (
              <li key={a.id}>
                <span className="muted">{fmtTime(lang, a.at)}</span> {t.has(`fi.action.${a.action}`) ? t(`fi.action.${a.action}`) : a.action}
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
  const { t } = useI18n();
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
        <span className="grow">{findingDetail(t, f)}</span>
        <span className="muted small mono">{f.region}</span>
        {f.status !== "open" ? <span className={`chip st-${f.status}`}>{t(`fi.status_${f.status}`)}</span> : null}
      </button>
    </li>
  );

  return (
    <div className="page">
      <h1>{t("fi.title")}</h1>
      <Tabs<StatusTab>
        value={status}
        onChange={(v) => setQuery({ status: v })}
        options={[
          { value: "open", label: t("fi.status_open"), count: counts.open ?? 0 },
          { value: "suppressed", label: t("fi.status_suppressed"), count: counts.suppressed ?? 0 },
          { value: "resolved", label: t("fi.status_resolved"), count: counts.resolved ?? 0 },
          { value: "closed", label: t("fi.status_closed"), count: counts.closed ?? 0 },
          { value: "all", label: t("common.all") },
        ]}
      />
      <div className="filters">
        <label>
          {t("fi.severity")}{" "}
          <select value={severity} onChange={(e) => setQuery({ severity: e.target.value })}>
            <option value="">{t("common.all")}</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {severityLabel(t, s)}
              </option>
            ))}
          </select>
        </label>
        {rule ? (
          <span className="chip">
            {t("fi.rule_chip")} <span className="mono">{rule}</span>{" "}
            <button type="button" className="icon-btn" aria-label={t("fi.clear_rule")} onClick={() => setQuery({ rule: null })}>
              ✕
            </button>
          </span>
        ) : null}
        <label>
          {t("fi.view")}{" "}
          <select value={view} onChange={(e) => setQuery({ view: e.target.value === "list" ? "list" : null })}>
            <option value="group">{t("fi.view_group")}</option>
            <option value="list">{t("fi.view_list")}</option>
          </select>
        </label>
      </div>
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorBox failure={error} onRetry={reload} /> : null}
      {data && data.items.length === 0 ? <Empty>{t("fi.empty")}</Empty> : null}
      {data && view === "list" ? <ul className="plain findings">{data.items.map(row)}</ul> : null}
      {data && view === "group"
        ? groupByRule(data.items).map((g) => (
            <section key={g.rule_id} className="card group">
              <h2>
                <SeverityBadge severity={g.severity} /> {ruleText(t, g.rule_id, "title", g.title)} <span className="count">{g.items.length}</span>
              </h2>
              <ul className="plain findings">{g.items.map(row)}</ul>
            </section>
          ))
        : null}
      {selected ? <FindingDrawer id={selected} onClose={closeDrawer} onChanged={reload} /> : null}
    </div>
  );
}
