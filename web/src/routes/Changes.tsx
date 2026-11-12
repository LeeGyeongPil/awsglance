// 변경 이력: "누가 무엇을 바꿨지?"에 답한다.
// 왼쪽 = CloudTrail 쓰기 이벤트(탭: 사람이 한 작업(기본)·자동·판단 보류·전체), 오른쪽 = 스냅샷 비교로 찾은 자원 변경.
import { useState } from "react";
import { useApi, type ActorClass, type ChangesResponse, type FieldChange, type TrailEvent } from "../api";
import { ActorChip, Empty, ErrorBox, Link, Loading, Tabs } from "../components/ui";
import { show, typeLabel } from "../format";
import { eventReason, fmtTime } from "../i18n";
import { Rich, useI18n } from "../lang";
import { useQueryState } from "../router";

type Tab = ActorClass | "all";

// 속성 변경 한 건을 "필드: 전 → 후"로. 목록은 빠진 것(−)과 생긴 것(+)만 보여 준다.
export function FieldDiff({ fields }: { fields: FieldChange[] }) {
  if (!fields.length) return null;
  return (
    <ul className="diff">
      {fields.map((f) => {
        if (Array.isArray(f.before) || Array.isArray(f.after)) {
          const before = (Array.isArray(f.before) ? f.before : []).map(String);
          const after = (Array.isArray(f.after) ? f.after : []).map(String);
          const removed = before.filter((x) => !after.includes(x));
          const added = after.filter((x) => !before.includes(x));
          return (
            <li key={f.field}>
              <span className="mono">{f.field}</span>:
              {removed.map((x) => (
                <span key={`-${x}`} className="del mono">
                  {" "}
                  − {x}
                </span>
              ))}
              {added.map((x) => (
                <span key={`+${x}`} className="add mono">
                  {" "}
                  + {x}
                </span>
              ))}
            </li>
          );
        }
        return (
          <li key={f.field}>
            <span className="mono">{f.field}</span>: <span className="del mono">{show(f.before)}</span> →{" "}
            <span className="add mono">{show(f.after)}</span>
          </li>
        );
      })}
    </ul>
  );
}

function resourceText(e: TrailEvent): string {
  const names = e.resources.map((r) => r.name).filter(Boolean);
  if (names.length) return names.join(", ");
  const req = e.request;
  for (const k of ["groupId", "bucketName", "functionName", "logGroupName", "roleName", "dBInstanceIdentifier", "name"]) {
    const v = req[k];
    if (typeof v === "string") return v;
  }
  return "";
}

function EventRow({ e }: { e: TrailEvent }) {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <li className={e.error_code ? "event failed" : "event"}>
      <button type="button" className="event-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="muted small time">{fmtTime(lang, e.time)}</span>
        <ActorChip cls={e.actor_class} via={e.via} />
        <strong>{e.actor}</strong>
        {e.is_root ? <span className="badge sev-critical">{t("ch.root")}</span> : null}
        <span className="mono">{e.name}</span>
        <span className="muted small mono">{resourceText(e)}</span>
        {e.error_code ? <span className="err small">{t("ch.failed", { code: e.error_code })}</span> : null}
      </button>
      {open ? (
        <div className="event-body small">
          <div>
            {t("ch.reason")}: {eventReason(t, e)} · {t("ch.region")} <span className="mono">{e.region}</span> · {t("ch.source")}{" "}
            <span className="mono">{e.source}</span>
          </div>
          <pre className="code">{JSON.stringify(e.request, null, 2)}</pre>
          <div className="muted">{t("ch.redacted")}</div>
        </div>
      ) : null}
    </li>
  );
}

export default function Changes() {
  const { t, lang } = useI18n();
  const [query, setQuery] = useQueryState();
  const tab = (query.get("tab") as Tab | null) ?? "human";
  const q = query.get("q") ?? "";
  const days = query.get("days") ?? "14";
  const noise = query.get("noise") === "1";
  const [draft, setDraft] = useState(q);
  const params = new URLSearchParams({ tab, q, days, noise: noise ? "true" : "false" });
  const { data, error, loading, reload } = useApi<ChangesResponse>(`/api/changes?${params.toString()}`);
  const counts = data?.counts ?? {};
  const total = (counts.human ?? 0) + (counts.automated ?? 0) + (counts.unknown ?? 0);

  return (
    <div className="page">
      <h1>{t("ch.title")}</h1>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery({ q: draft });
        }}
      >
        <label>
          {t("ch.period")}{" "}
          <select value={days} onChange={(e) => setQuery({ days: e.target.value })}>
            {["1", "7", "14", "30", "90"].map((d) => (
              <option key={d} value={d}>
                {t(`ch.days_${d}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          {t("common.search")} <input type="search" value={draft} placeholder={t("ch.search_ph")} onChange={(e) => setDraft(e.target.value)} />
        </label>
        <button type="submit">{t("common.find")}</button>
      </form>

      <div className="grid-2 changes-grid">
        <section className="card">
          <h2>{t("ch.events_title")}</h2>
          <Tabs<Tab>
            value={tab}
            onChange={(v) => setQuery({ tab: v })}
            options={[
              { value: "human", label: t("ch.tab_human"), count: counts.human ?? 0 },
              { value: "automated", label: t("ch.tab_automated"), count: counts.automated ?? 0 },
              { value: "unknown", label: t("ch.tab_unknown"), count: counts.unknown ?? 0 },
              { value: "all", label: t("ch.tab_all"), count: total },
            ]}
          />
          {loading && !data ? <Loading /> : null}
          {error ? <ErrorBox failure={error} onRetry={reload} /> : null}
          {data && data.events.length === 0 ? <Empty>{t("ch.no_events")}</Empty> : null}
          <ul className="events">
            {data?.events.map((e) => <EventRow key={e.event_id} e={e} />)}
          </ul>
          {tab === "unknown" ? (
            <p className="muted small">
              <Rich text={t("ch.unknown_help")} />
            </p>
          ) : null}
        </section>

        <section className="card">
          <h2>{t("ch.res_title")}</h2>
          <p className="muted small">
            {t("ch.res_note")}{" "}
            <label>
              <input type="checkbox" checked={noise} onChange={(e) => setQuery({ noise: e.target.checked ? "1" : null })} />{" "}
              {t("ch.show_noise")}
            </label>
          </p>
          {data && data.resource_changes.length === 0 ? <Empty>{t("ch.no_res_changes")}</Empty> : null}
          <ul className="plain changes">
            {data?.resource_changes.map((c) => (
              <li key={c.id} className={c.noise ? "noise" : undefined}>
                <span className={`chip kind-${c.kind}`}>{t(`ch.kind_${c.kind}`)}</span>{" "}
                <span className="muted small">{fmtTime(lang, c.at)}</span> {typeLabel(t, c.type)}{" "}
                <Link to={`/resources?key=${encodeURIComponent(c.key)}`}>{c.name}</Link>
                {c.noise ? <span className="muted small"> {t("ch.noise")}</span> : null}
                <FieldDiff fields={c.fields} />
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
