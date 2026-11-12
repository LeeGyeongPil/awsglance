// 개요: 아침에 한 번 보는 화면. 신뢰 신호 → 지금 확인할 것 → 24시간 띠 → KPI → 14일 변경 막대 → 보안 기능 행렬.
import { useApi, type Overview as OverviewData } from "../api";
import { ChangeBars, PostureMatrix } from "../components/charts";
import { ErrorBox, Link, Loading, SeverityBadge, TrustDot } from "../components/ui";
import { severityLabel } from "../format";
import { ago, findingDetail, fmtNumber, fmtTime, ruleText, trustReason } from "../i18n";
import { useI18n } from "../lang";

export default function Overview() {
  const { t, lang } = useI18n();
  const { data, error, loading, reload } = useApi<OverviewData>("/api/overview");
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorBox failure={error ?? { code: null, params: {}, message: t("common.no_data") }} onRetry={reload} />;

  const { trust, checks, kpi, since_24h: since, severity_counts: sev } = data;
  const num = (n: number) => fmtNumber(lang, n);
  return (
    <div className="page">
      <section className={`card trust-card trust-bg-${trust.level}`}>
        <div className="trust-big">
          <TrustDot level={trust.level} />
        </div>
        <div>
          <div className="trust-reason">{trustReason(t, trust)}</div>
          <div className="muted small">{t("ov.last_collect", { time: fmtTime(lang, trust.at), ago: ago(lang, trust.at) })}</div>
        </div>
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>{t("ov.check_now")}</h2>
          {checks.length === 0 ? (
            <p className="muted">{t("ov.no_findings")}</p>
          ) : (
            <ul className="checks">
              {checks.map((c) => (
                <li key={c.rule_id}>
                  <SeverityBadge severity={c.severity} />
                  <Link to={`/findings?rule=${encodeURIComponent(c.rule_id)}`} className="check-title">
                    {ruleText(t, c.rule_id, "title", c.title)}
                    {c.count > 1 ? <span className="count">{c.count}</span> : null}
                  </Link>
                  <div className="muted small check-example">
                    {findingDetail(t, { rule_id: c.rule_id, detail: c.example, params: c.example_params })}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <Link to="/findings" className="more">
            {t("ov.all_findings")}
          </Link>
        </section>

        <section className="card">
          <h2>{t("ov.last_24h")}</h2>
          <ul className="since">
            <li>
              <span className="num">{num(since.new)}</span> {t("ov.new")}
            </li>
            <li>
              <span className="num">{num(since.reopened)}</span> {t("ov.reopened")}
            </li>
            <li>
              <span className="num">{num(since.resolved)}</span> {t("ov.resolved")}
            </li>
            <li>
              <Link to="/changes?tab=human">
                <span className="num">{num(since.human_changes)}</span> {t("ov.human_changes")}
              </Link>
            </li>
          </ul>
          <div className="kpis">
            <div className="kpi">
              <div className="num">{num(kpi.resources)}</div>
              <div className="muted small">{t("ov.kpi_resources")}</div>
            </div>
            <div className="kpi">
              <div className="num">{num(kpi.events_24h)}</div>
              <div className="muted small">{t("ov.kpi_events")}</div>
            </div>
            <div className="kpi">
              <div className="num">{num(kpi.changes_24h)}</div>
              <div className="muted small">{t("ov.kpi_changes")}</div>
            </div>
            <div className="kpi">
              <div className="num">{num(kpi.open_findings)}</div>
              <div className="muted small">{t("ov.kpi_open")}</div>
            </div>
          </div>
          <div className="sev-row small">
            {(Object.keys(sev) as (keyof typeof sev)[]).map((s) => (
              <span key={s} className={`sev-count sev-${s}`}>
                {severityLabel(t, s)} <span className="mono">{num(sev[s])}</span>
              </span>
            ))}
          </div>
        </section>
      </div>

      <section className="card">
        <h2>{t("ov.bars_title")}</h2>
        <p className="muted small">{t("ov.bars_note")}</p>
        <ChangeBars bars={data.bars} />
      </section>

      <section className="card">
        <h2>{t("ov.posture_title")}</h2>
        <p className="muted small">{t("ov.posture_note")}</p>
        <PostureMatrix posture={data.posture} />
      </section>
    </div>
  );
}
