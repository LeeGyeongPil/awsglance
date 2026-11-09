// 변경 이력: "누가 무엇을 바꿨지?"에 답한다.
// 왼쪽 = CloudTrail 쓰기 이벤트(탭: 사람이 한 작업(기본)·자동·판단 보류·전체), 오른쪽 = 스냅샷 비교로 찾은 자원 변경.
import { useState } from "react";
import { useApi, type ActorClass, type ChangesResponse, type FieldChange, type TrailEvent } from "../api";
import { ActorChip, Empty, ErrorBox, Link, Loading, Tabs } from "../components/ui";
import { fmtTime, show, typeLabel } from "../format";
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
  const [open, setOpen] = useState(false);
  return (
    <li className={e.error_code ? "event failed" : "event"}>
      <button type="button" className="event-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="muted small time">{fmtTime(e.time)}</span>
        <ActorChip cls={e.actor_class} via={e.via} />
        <strong>{e.actor}</strong>
        {e.is_root ? <span className="badge sev-critical">■ 루트</span> : null}
        <span className="mono">{e.name}</span>
        <span className="muted small mono">{resourceText(e)}</span>
        {e.error_code ? <span className="err small">실패: {e.error_code}</span> : null}
      </button>
      {open ? (
        <div className="event-body small">
          <div>
            분류 근거: {e.reason} · 리전 <span className="mono">{e.region}</span> · 출처 <span className="mono">{e.source}</span>
          </div>
          <pre className="code">{JSON.stringify(e.request, null, 2)}</pre>
          <div className="muted">요청 파라미터는 저장 전에 비밀값 모양을 *** 로 가렸습니다.</div>
        </div>
      ) : null}
    </li>
  );
}

export default function Changes() {
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
      <h1>변경 이력</h1>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery({ q: draft });
        }}
      >
        <label>
          기간{" "}
          <select value={days} onChange={(e) => setQuery({ days: e.target.value })}>
            <option value="1">1일</option>
            <option value="7">7일</option>
            <option value="14">14일</option>
            <option value="30">30일</option>
            <option value="90">90일</option>
          </select>
        </label>
        <label className="grow">
          검색 <input type="search" value={draft} placeholder="작업·주체·자원" onChange={(e) => setDraft(e.target.value)} />
        </label>
        <button type="submit">찾기</button>
      </form>

      <div className="grid-2 changes-grid">
        <section className="card">
          <h2>CloudTrail 쓰기 이벤트</h2>
          <Tabs<Tab>
            value={tab}
            onChange={(v) => setQuery({ tab: v })}
            options={[
              { value: "human", label: "사람이 한 작업", count: counts.human ?? 0 },
              { value: "automated", label: "자동", count: counts.automated ?? 0 },
              { value: "unknown", label: "판단 보류", count: counts.unknown ?? 0 },
              { value: "all", label: "전체", count: total },
            ]}
          />
          {loading && !data ? <Loading /> : null}
          {error ? <ErrorBox message={error} onRetry={reload} /> : null}
          {data && data.events.length === 0 ? <Empty>이 기간에 해당하는 이벤트가 없습니다.</Empty> : null}
          <ul className="events">
            {data?.events.map((e) => <EventRow key={e.event_id} e={e} />)}
          </ul>
          {tab === "unknown" ? (
            <p className="muted small">
              판단 보류는 역할 이름만으로 사람·자동을 가를 수 없는 호출입니다. 설정 파일 <code>config.toml</code> 의 <code>[classify]</code> 에 역할 이름 패턴을 적으면 분류됩니다.
            </p>
          ) : null}
        </section>

        <section className="card">
          <h2>자원 변경(스냅샷 비교)</h2>
          <p className="muted small">
            두 번의 인벤토리 수집을 비교한 결과입니다. CloudTrail 이 놓친 변경도 결과로 잡습니다.{" "}
            <label>
              <input type="checkbox" checked={noise} onChange={(e) => setQuery({ noise: e.target.checked ? "1" : null })} /> 시각만 바뀐
              변경(노이즈)도 보기
            </label>
          </p>
          {data && data.resource_changes.length === 0 ? <Empty>자원 변경이 없습니다.</Empty> : null}
          <ul className="plain changes">
            {data?.resource_changes.map((c) => (
              <li key={c.id} className={c.noise ? "noise" : undefined}>
                <span className={`chip kind-${c.kind}`}>{c.kind === "created" ? "+ 생성" : c.kind === "deleted" ? "− 삭제" : "~ 수정"}</span>{" "}
                <span className="muted small">{fmtTime(c.at)}</span> {typeLabel(c.type)}{" "}
                <Link to={`/resources?key=${encodeURIComponent(c.key)}`}>{c.name}</Link>
                {c.noise ? <span className="muted small"> (노이즈)</span> : null}
                <FieldDiff fields={c.fields} />
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
