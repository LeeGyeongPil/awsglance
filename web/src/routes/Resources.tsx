// 자원: 종류·리전·검색 필터 표 → 행을 누르면 상세 드로어(속성·태그·변경 이력·관련 CloudTrail·발견 사항).
import { useCallback, useState } from "react";
import { useApi, type ResourceDetail, type ResourcesResponse } from "../api";
import { ActorChip, Drawer, Empty, ErrorBox, Link, Loading, SeverityBadge } from "../components/ui";
import { show, typeLabel } from "../format";
import { fmtTime, ruleText } from "../i18n";
import { useI18n } from "../lang";
import { useQueryState } from "../router";
import { FieldDiff } from "./Changes";

function DetailDrawer({ resKey, onClose }: { resKey: string; onClose: () => void }) {
  const { t, lang } = useI18n();
  const { data, error, loading } = useApi<ResourceDetail>(`/api/resources/${encodeURIComponent(resKey)}`);
  const r = data?.resource;
  return (
    <Drawer title={r ? `${typeLabel(t, r.type)} · ${r.name}` : t("re.drawer_default")} onClose={onClose}>
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorBox failure={error} /> : null}
      {data && r ? (
        <>
          <dl className="kv">
            <dt>ID</dt>
            <dd className="mono wrap">{r.id}</dd>
            <dt>{t("re.region")}</dt>
            <dd className="mono">{r.region}</dd>
            <dt>{t("re.first_seen")}</dt>
            <dd>{fmtTime(lang, r.first_seen)}</dd>
            {r.deleted_at ? (
              <>
                <dt>{t("re.deleted")}</dt>
                <dd>{fmtTime(lang, r.deleted_at)}</dd>
              </>
            ) : null}
          </dl>
          <h3>{t("re.props")}</h3>
          <dl className="kv">
            {Object.entries(r.props).map(([k, v]) => (
              <span key={k} className="kv-row">
                <dt className="mono">{k}</dt>
                <dd className="mono wrap">{show(v)}</dd>
              </span>
            ))}
          </dl>
          {Object.keys(r.tags).length ? (
            <>
              <h3>{t("re.tags")}</h3>
              <div className="tags">
                {Object.entries(r.tags).map(([k, v]) => (
                  <span key={k} className="chip mono">
                    {k}={v}
                  </span>
                ))}
              </div>
            </>
          ) : null}
          <h3>{t("re.findings_h", { count: data.findings.length })}</h3>
          {data.findings.length === 0 ? <p className="muted small">{t("re.none")}</p> : null}
          <ul className="plain">
            {data.findings.map((f) => (
              <li key={f.id}>
                <SeverityBadge severity={f.severity} />{" "}
                <Link to={`/findings?status=all&id=${f.id}`}>{ruleText(t, f.rule_id, "title", f.title)}</Link>{" "}
                <span className="muted small">({t(`fi.status_${f.status}`)})</span>
              </li>
            ))}
          </ul>
          <h3>{t("re.changes_h", { count: data.changes.length })}</h3>
          {data.changes.length === 0 ? <p className="muted small">{t("re.no_changes")}</p> : null}
          <ul className="plain">
            {data.changes.map((c) => (
              <li key={c.id}>
                <span className="muted small">{fmtTime(lang, c.at)}</span>{" "}
                {t(`ch.summary_${c.kind}`, { type: typeLabel(t, c.type), name: c.name })}
                {c.fields.length ? `: ${c.fields.map((fc) => fc.field).join(", ")}` : ""}
                <FieldDiff fields={c.fields} />
              </li>
            ))}
          </ul>
          {/* 관련 이벤트는 자원 ID·ARN 이 정확히 같은 것만 — 이름이 비슷한 다른 자원의 이벤트를 섞지 않으려고 일부러 덜 보인다 */}
          {data.events_match === "unsupported" ? (
            <>
              <h3>{t("re.events_h_plain")}</h3>
              <p className="muted small">{t("re.events_unsupported")}</p>
            </>
          ) : (
            <>
              <h3>{t("re.events_h", { count: data.events.length })}</h3>
              <p className="muted small">{t("re.events_note")}</p>
              {data.events.length === 0 ? <p className="muted small">{t("re.no_events")}</p> : null}
            </>
          )}
          <ul className="plain">
            {data.events.map((e) => (
              <li key={e.event_id}>
                <span className="muted small">{fmtTime(lang, e.time)}</span> <ActorChip cls={e.actor_class} via={e.via} />{" "}
                <strong>{e.actor}</strong> · <span className="mono">{e.name}</span>
                {e.error_code ? <span className="err small"> ({e.error_code})</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </Drawer>
  );
}

export default function Resources() {
  const { t, lang } = useI18n();
  const [query, setQuery] = useQueryState();
  const type = query.get("type") ?? "";
  const region = query.get("region") ?? "";
  const q = query.get("q") ?? "";
  const selected = query.get("key");
  const [draft, setDraft] = useState(q);
  const params = new URLSearchParams({ type, region, q });
  const { data, error, loading, reload } = useApi<ResourcesResponse>(`/api/resources?${params.toString()}`);
  const closeDrawer = useCallback(() => setQuery({ key: null }), [setQuery]);

  return (
    <div className="page">
      <h1>{t("re.title")}</h1>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery({ q: draft });
        }}
      >
        <label>
          {t("re.type")}{" "}
          <select value={type} onChange={(e) => setQuery({ type: e.target.value })}>
            <option value="">{t("common.all")}</option>
            {Object.entries(data?.facets.types ?? {}).map(([kind, n]) => (
              <option key={kind} value={kind}>
                {typeLabel(t, kind)} ({n})
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("re.region")}{" "}
          <select value={region} onChange={(e) => setQuery({ region: e.target.value })}>
            <option value="">{t("common.all")}</option>
            {Object.entries(data?.facets.regions ?? {}).map(([r, n]) => (
              <option key={r} value={r}>
                {r} ({n})
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          {t("common.search")} <input type="search" value={draft} placeholder={t("re.search_ph")} onChange={(e) => setDraft(e.target.value)} />
        </label>
        <button type="submit">{t("common.find")}</button>
      </form>
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorBox failure={error} onRetry={reload} /> : null}
      {data && data.items.length === 0 ? <Empty>{t("re.empty")}</Empty> : null}
      {data && data.items.length > 0 ? (
        <div className="table-wrap">
          <table className="rows">
            <thead>
              <tr>
                <th scope="col">{t("re.col_type")}</th>
                <th scope="col">{t("re.col_name")}</th>
                <th scope="col">ID</th>
                <th scope="col">{t("re.col_region")}</th>
                <th scope="col">{t("re.col_findings")}</th>
                <th scope="col">{t("re.col_first_seen")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr
                  key={r.key}
                  tabIndex={0}
                  className="clickable"
                  onClick={() => setQuery({ key: r.key })}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") setQuery({ key: r.key });
                  }}
                >
                  <td>{typeLabel(t, r.type)}</td>
                  <td>{r.name}</td>
                  <td className="mono small">{r.id}</td>
                  <td className="mono small">{r.region}</td>
                  <td>{r.open_findings ? <span className="badge sev-high">▲ {r.open_findings}</span> : <span className="muted">—</span>}</td>
                  <td className="small">{fmtTime(lang, r.first_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">{t("re.total", { count: data.total })}</p>
        </div>
      ) : null}
      {selected ? <DetailDrawer resKey={selected} onClose={closeDrawer} /> : null}
    </div>
  );
}
