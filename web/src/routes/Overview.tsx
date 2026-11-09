// 개요: 아침에 한 번 보는 화면. 신뢰 신호 → 지금 확인할 것 → 24시간 띠 → KPI → 14일 변경 막대 → 보안 기능 행렬.
import { useApi, type Overview as OverviewData } from "../api";
import { ChangeBars, PostureMatrix } from "../components/charts";
import { ErrorBox, Link, Loading, SeverityBadge, TrustDot } from "../components/ui";
import { ago, fmtTime, SEVERITY_LABEL } from "../format";

export default function Overview() {
  const { data, error, loading, reload } = useApi<OverviewData>("/api/overview");
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorBox message={error ?? "no data"} onRetry={reload} />;

  const { trust, checks, kpi, since_24h: since, severity_counts: sev } = data;
  return (
    <div className="page">
      <section className={`card trust-card trust-bg-${trust.level}`}>
        <div className="trust-big">
          <TrustDot level={trust.level} />
        </div>
        <div>
          <div className="trust-reason">{trust.reason}</div>
          <div className="muted small">마지막 수집 {fmtTime(trust.at)} ({ago(trust.at)})</div>
        </div>
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>지금 확인할 것</h2>
          {checks.length === 0 ? (
            <p className="muted">열린 문제가 없습니다.</p>
          ) : (
            <ul className="checks">
              {checks.map((c) => (
                <li key={c.rule_id}>
                  <SeverityBadge severity={c.severity} />
                  <Link to={`/findings?rule=${encodeURIComponent(c.rule_id)}`} className="check-title">
                    {c.title}
                    {c.count > 1 ? <span className="count">{c.count}</span> : null}
                  </Link>
                  <div className="muted small check-example">{c.example}</div>
                </li>
              ))}
            </ul>
          )}
          <Link to="/findings" className="more">
            문제 전체 보기 →
          </Link>
        </section>

        <section className="card">
          <h2>최근 24시간</h2>
          <ul className="since">
            <li>
              <span className="num">{since.new}</span> 새 문제
            </li>
            <li>
              <span className="num">{since.reopened}</span> 재발
            </li>
            <li>
              <span className="num">{since.resolved}</span> 해결
            </li>
            <li>
              <Link to="/changes?tab=human">
                <span className="num">{since.human_changes}</span> 사람이 한 변경
              </Link>
            </li>
          </ul>
          <div className="kpis">
            <div className="kpi">
              <div className="num">{kpi.resources}</div>
              <div className="muted small">자원</div>
            </div>
            <div className="kpi">
              <div className="num">{kpi.events_24h}</div>
              <div className="muted small">24시간 쓰기 이벤트</div>
            </div>
            <div className="kpi">
              <div className="num">{kpi.changes_24h}</div>
              <div className="muted small">24시간 자원 변경</div>
            </div>
            <div className="kpi">
              <div className="num">{kpi.open_findings}</div>
              <div className="muted small">열린 문제</div>
            </div>
          </div>
          <div className="sev-row small">
            {(Object.keys(sev) as (keyof typeof sev)[]).map((s) => (
              <span key={s} className={`sev-count sev-${s}`}>
                {SEVERITY_LABEL[s]} <span className="mono">{sev[s]}</span>
              </span>
            ))}
          </div>
        </section>
      </div>

      <section className="card">
        <h2>최근 14일 변경</h2>
        <p className="muted small">CloudTrail 의 쓰기 이벤트를 호출 주체(사람·자동·판단 보류)별로 쌓았습니다. 막대에 마우스를 올리면 스냅샷 비교로 찾은 자원 변경 수도 보입니다.</p>
        <ChangeBars bars={data.bars} />
      </section>

      <section className="card">
        <h2>보안 기능 × 리전</h2>
        <p className="muted small">'권한 없음'은 꺼짐이 아니라 확인할 수 없다는 뜻입니다(연결 화면에서 권한을 확인하세요).</p>
        <PostureMatrix posture={data.posture} />
      </section>
    </div>
  );
}
