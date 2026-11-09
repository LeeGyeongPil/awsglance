// 자원: 종류·리전·검색 필터 표 → 행을 누르면 상세 드로어(속성·태그·변경 이력·관련 CloudTrail·발견 사항).
import { useCallback, useState } from "react";
import { useApi, type ResourceDetail, type ResourcesResponse } from "../api";
import { ActorChip, Drawer, Empty, ErrorBox, Link, Loading, SeverityBadge } from "../components/ui";
import { fmtTime, show, typeLabel } from "../format";
import { useQueryState } from "../router";
import { FieldDiff } from "./Changes";

function DetailDrawer({ resKey, onClose }: { resKey: string; onClose: () => void }) {
  const { data, error, loading } = useApi<ResourceDetail>(`/api/resources/${encodeURIComponent(resKey)}`);
  const r = data?.resource;
  return (
    <Drawer title={r ? `${typeLabel(r.type)} · ${r.name}` : "자원"} onClose={onClose}>
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorBox message={error} /> : null}
      {data && r ? (
        <>
          <dl className="kv">
            <dt>ID</dt>
            <dd className="mono wrap">{r.id}</dd>
            <dt>리전</dt>
            <dd className="mono">{r.region}</dd>
            <dt>처음 본 때</dt>
            <dd>{fmtTime(r.first_seen)}</dd>
            {r.deleted_at ? (
              <>
                <dt>삭제됨</dt>
                <dd>{fmtTime(r.deleted_at)}</dd>
              </>
            ) : null}
          </dl>
          <h3>속성</h3>
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
              <h3>태그</h3>
              <div className="tags">
                {Object.entries(r.tags).map(([k, v]) => (
                  <span key={k} className="chip mono">
                    {k}={v}
                  </span>
                ))}
              </div>
            </>
          ) : null}
          <h3>발견 사항 ({data.findings.length})</h3>
          {data.findings.length === 0 ? <p className="muted small">없음</p> : null}
          <ul className="plain">
            {data.findings.map((f) => (
              <li key={f.id}>
                <SeverityBadge severity={f.severity} />{" "}
                <Link to={`/findings?status=all&id=${f.id}`}>{f.title}</Link> <span className="muted small">({f.status})</span>
              </li>
            ))}
          </ul>
          <h3>스냅샷 변경 이력 ({data.changes.length})</h3>
          {data.changes.length === 0 ? <p className="muted small">기준선 이후 바뀐 것이 없습니다.</p> : null}
          <ul className="plain">
            {data.changes.map((c) => (
              <li key={c.id}>
                <span className="muted small">{fmtTime(c.at)}</span> {c.summary}
                <FieldDiff fields={c.fields} />
              </li>
            ))}
          </ul>
          {/* 관련 이벤트는 자원 ID·ARN 이 정확히 같은 것만 — 이름이 비슷한 다른 자원의 이벤트를 섞지 않으려고 일부러 덜 보인다 */}
          {data.events_match === "unsupported" ? (
            <>
              <h3>관련 CloudTrail</h3>
              <p className="muted small">
                이 종류는 CloudTrail 이벤트와 정확히 맞춰 볼 수 없어 연결하지 않습니다. 변경 이력 화면의 검색을 쓰세요.
              </p>
            </>
          ) : (
            <>
              <h3>관련 CloudTrail ({data.events.length})</h3>
              <p className="muted small">
                ID·ARN 이 정확히 같은 이벤트만 보여 줍니다. 더 넓게 찾으려면 변경 이력 화면의 검색을 쓰세요.
              </p>
              {data.events.length === 0 ? <p className="muted small">관련 이벤트가 없습니다.</p> : null}
            </>
          )}
          <ul className="plain">
            {data.events.map((e) => (
              <li key={e.event_id}>
                <span className="muted small">{fmtTime(e.time)}</span> <ActorChip cls={e.actor_class} via={e.via} />{" "}
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
      <h1>자원</h1>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery({ q: draft });
        }}
      >
        <label>
          종류{" "}
          <select value={type} onChange={(e) => setQuery({ type: e.target.value })}>
            <option value="">전체</option>
            {Object.entries(data?.facets.types ?? {}).map(([t, n]) => (
              <option key={t} value={t}>
                {typeLabel(t)} ({n})
              </option>
            ))}
          </select>
        </label>
        <label>
          리전{" "}
          <select value={region} onChange={(e) => setQuery({ region: e.target.value })}>
            <option value="">전체</option>
            {Object.entries(data?.facets.regions ?? {}).map(([r, n]) => (
              <option key={r} value={r}>
                {r} ({n})
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          검색 <input type="search" value={draft} placeholder="이름·ID·태그" onChange={(e) => setDraft(e.target.value)} />
        </label>
        <button type="submit">찾기</button>
      </form>
      {loading && !data ? <Loading /> : null}
      {error ? <ErrorBox message={error} onRetry={reload} /> : null}
      {data && data.items.length === 0 ? <Empty>조건에 맞는 자원이 없습니다.</Empty> : null}
      {data && data.items.length > 0 ? (
        <div className="table-wrap">
          <table className="rows">
            <thead>
              <tr>
                <th scope="col">종류</th>
                <th scope="col">이름</th>
                <th scope="col">ID</th>
                <th scope="col">리전</th>
                <th scope="col">문제</th>
                <th scope="col">처음 본 때</th>
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
                  <td>{typeLabel(r.type)}</td>
                  <td>{r.name}</td>
                  <td className="mono small">{r.id}</td>
                  <td className="mono small">{r.region}</td>
                  <td>{r.open_findings ? <span className="badge sev-high">▲ {r.open_findings}</span> : <span className="muted">—</span>}</td>
                  <td className="small">{fmtTime(r.first_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">{data.total}개</p>
        </div>
      ) : null}
      {selected ? <DetailDrawer resKey={selected} onClose={closeDrawer} /> : null}
    </div>
  );
}
