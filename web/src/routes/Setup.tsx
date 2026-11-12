// 연결 마법사: 어떤 계정·주체로 붙었는지 → 수집기별 권한 점검 표 → 부족하면 최소 IAM 정책 복사.
import { useState } from "react";
import { useApi, type Setup as SetupData } from "../api";
import { ErrorBox, Link, Loading } from "../components/ui";
import { fmtTime, permLabel } from "../i18n";
import { Rich, useI18n } from "../lang";

export default function Setup() {
  const { t, lang } = useI18n();
  const { data, error, loading, reload } = useApi<SetupData>("/api/setup");
  const [copied, setCopied] = useState(false);
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorBox failure={error ?? { code: null, params: {}, message: t("common.no_data") }} onRetry={reload} />;

  const policyText = JSON.stringify(data.policy, null, 2);
  const denied = data.counts.denied ?? 0;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(policyText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="page">
      <h1>{t("setup.title")}</h1>
      <ol className="steps">
        <li className="card">
          <h2>{t("setup.step1")}</h2>
          {data.identity ? (
            <dl className="kv">
              <dt>{t("setup.account_id")}</dt>
              <dd className="mono">{data.identity.account}</dd>
              <dt>{t("setup.principal")}</dt>
              <dd className="mono wrap">{data.identity.arn}</dd>
              <dt>{t("setup.regions")}</dt>
              <dd className="mono">{data.regions.join(", ") || "—"}</dd>
            </dl>
          ) : (
            <p>{t("setup.no_identity")}</p>
          )}
          <p className="muted">
            <Rich text={t("setup.creds_note")} />
          </p>
        </li>
        <li className="card">
          <h2>{t("setup.step2")}</h2>
          <p className="muted">{t("setup.step2_note", { time: fmtTime(lang, data.checked_at) })}</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">{t("setup.col_collector")}</th>
                  <th scope="col">{t("setup.col_action")}</th>
                  <th scope="col">{t("setup.col_result")}</th>
                  <th scope="col">{t("setup.col_meaning")}</th>
                </tr>
              </thead>
              <tbody>
                {data.permissions.map((p) => (
                  <tr key={p.collector}>
                    <td>{permLabel(t, p.collector, p.label)}</td>
                    <td className="mono small">
                      {p.service}:{p.operation} @{p.region}
                    </td>
                    <td className={`perm perm-${p.status}`}>
                      {t(`perm.${p.status}`)}
                      {p.detail ? <div className="small muted mono">{p.detail}</div> : null}
                    </td>
                    <td className="small">{t(`perm.help.${p.status}`)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </li>
        <li className="card">
          <h2>{t("setup.step3")}</h2>
          <p>
            {denied > 0 ? <strong>{t("setup.denied_count", { count: denied })}</strong> : null}
            {t("setup.policy_intro")}{" "}
            {data.managed_policies.map((m, i) => (
              <span key={m}>
                {i ? " + " : ""}
                <code>{m.split("/").pop()}</code>
              </span>
            ))}{" "}
            {t("setup.policy_outro")}
          </p>
          <div className="row">
            <button type="button" className="primary" onClick={copy}>
              {copied ? t("setup.copied") : t("setup.copy")}
            </button>
            <span className="muted small">
              <Rich text={t("setup.terminal_hint")} />
            </span>
          </div>
          <pre className="code">{policyText}</pre>
        </li>
      </ol>
      <p>
        <Link to="/" className="button">
          {t("setup.go_overview")}
        </Link>
      </p>
    </div>
  );
}
