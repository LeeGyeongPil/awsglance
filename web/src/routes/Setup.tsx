// 연결 마법사: 어떤 계정·주체로 붙었는지 → 수집기별 권한 점검 표 → 부족하면 최소 IAM 정책 복사.
import { useState } from "react";
import { useApi, type PermissionRow, type Setup as SetupData } from "../api";
import { ErrorBox, Link, Loading } from "../components/ui";
import { fmtTime } from "../format";

const STATUS_TEXT: Record<PermissionRow["status"], string> = {
  allowed: "✓ 허용",
  denied: "✕ 거부",
  unavailable: "– 사용 불가",
  error: "? 오류",
  blocked: "⛔ 코드에서 차단",
};

const STATUS_HELP: Record<PermissionRow["status"], string> = {
  allowed: "읽기 권한이 있습니다.",
  denied: "IAM 권한이 없습니다. 아래 최소 정책을 붙이면 해결됩니다.",
  unavailable: "권한 문제가 아니라 기능이 꺼져 있거나 구독이 필요합니다. 그대로 써도 됩니다.",
  error: "일시적인 오류일 수 있습니다. 다시 실행해 보세요.",
  blocked: "허용 목록 밖 작업이라 프로그램이 스스로 막았습니다.",
};

export default function Setup() {
  const { data, error, loading, reload } = useApi<SetupData>("/api/setup");
  const [copied, setCopied] = useState(false);
  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorBox message={error ?? "no data"} onRetry={reload} />;

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
      <h1>연결 확인</h1>
      <ol className="steps">
        <li className="card">
          <h2>1. 연결된 계정</h2>
          {data.identity ? (
            <dl className="kv">
              <dt>계정 ID</dt>
              <dd className="mono">{data.identity.account}</dd>
              <dt>주체(ARN)</dt>
              <dd className="mono wrap">{data.identity.arn}</dd>
              <dt>리전</dt>
              <dd className="mono">{data.regions.join(", ") || "—"}</dd>
            </dl>
          ) : (
            <p>아직 연결 정보가 없습니다.</p>
          )}
          <p className="muted">
            awsglance 는 표준 AWS 자격증명(환경 변수·<code>AWS_PROFILE</code>·SSO·역할)을 그대로 쓰며, 읽기 작업만 부를 수 있습니다.
          </p>
        </li>
        <li className="card">
          <h2>2. 권한 점검</h2>
          <p className="muted">수집기마다 대표 읽기 작업을 한 번씩 불러 본 결과입니다. 점검 시각 {fmtTime(data.checked_at)}</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">수집기</th>
                  <th scope="col">작업</th>
                  <th scope="col">결과</th>
                  <th scope="col">의미</th>
                </tr>
              </thead>
              <tbody>
                {data.permissions.map((p) => (
                  <tr key={p.collector}>
                    <td>{p.label}</td>
                    <td className="mono small">
                      {p.service}:{p.operation} @{p.region}
                    </td>
                    <td className={`perm perm-${p.status}`}>
                      {STATUS_TEXT[p.status]}
                      {p.detail ? <div className="small muted mono">{p.detail}</div> : null}
                    </td>
                    <td className="small">{STATUS_HELP[p.status]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </li>
        <li className="card">
          <h2>3. 권한이 모자라면</h2>
          <p>
            {denied > 0 ? <strong>거부된 수집기가 {denied}개 있습니다. </strong> : null}
            아래 최소 IAM 정책(읽기 작업 목록, 이 프로그램의 허용 목록과 같은 원천에서 생성)을 사용자·역할에 붙이거나, AWS 관리형 정책{" "}
            {data.managed_policies.map((m, i) => (
              <span key={m}>
                {i ? " + " : ""}
                <code>{m.split("/").pop()}</code>
              </span>
            ))}{" "}
            를 함께 붙입니다.
          </p>
          <div className="row">
            <button type="button" className="primary" onClick={copy}>
              {copied ? "복사했습니다" : "최소 IAM 정책 복사"}
            </button>
            <span className="muted small">
              터미널에서는 <code>awsglance policy</code>
            </span>
          </div>
          <pre className="code">{policyText}</pre>
        </li>
      </ol>
      <p>
        <Link to="/" className="button">
          개요로 가기 →
        </Link>
      </p>
    </div>
  );
}
