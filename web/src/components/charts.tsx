// 차트 라이브러리 없이 SVG·표로 그린다(번들을 작게, 의존성을 적게).
import type { DayBar, Posture } from "../api";
import { FEATURE_LABEL } from "../format";

// 14일 변경 막대: 날짜마다 사람/자동/판단 보류를 쌓아 올린다.
export function ChangeBars({ bars }: { bars: DayBar[] }) {
  const width = 560;
  const height = 140;
  const pad = 22;
  const max = Math.max(1, ...bars.map((b) => b.human + b.automated + b.unknown));
  const step = (width - pad) / Math.max(1, bars.length);
  const scale = (n: number) => (n / max) * (height - pad - 8);
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="최근 14일 CloudTrail 쓰기 이벤트 수">
        <line x1={pad} y1={height - pad} x2={width} y2={height - pad} className="axis" />
        <text x={2} y={12} className="tick">
          {max}
        </text>
        {bars.map((b, i) => {
          const x = pad + i * step + 3;
          const w = step - 6;
          let y = height - pad;
          const parts: [keyof DayBar, number][] = [
            ["human", b.human],
            ["automated", b.automated],
            ["unknown", b.unknown],
          ];
          return (
            <g key={b.date}>
              <title>{`${b.date} — 사람 ${b.human}, 자동 ${b.automated}, 판단 보류 ${b.unknown}, 스냅샷 변경 ${b.resource_changes}`}</title>
              {parts.map(([k, n]) => {
                const h = scale(n);
                y -= h;
                return n > 0 ? <rect key={k} x={x} y={y} width={w} height={h} className={`bar bar-${k}`} /> : null;
              })}
              {i % 2 === bars.length % 2 ? null : (
                <text x={x + w / 2} y={height - 6} textAnchor="middle" className="tick">
                  {b.date.slice(5)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <figcaption className="legend">
        <span className="key bar-human" /> 사람 <span className="key bar-automated" /> 자동 <span className="key bar-unknown" /> 판단 보류
      </figcaption>
    </figure>
  );
}

const STATE_TEXT: Record<string, string> = { on: "✓ 켜짐", off: "✕ 꺼짐", denied: "? 권한 없음", error: "? 오류" };

// 보안 기능 × 리전 행렬. '권한 없음'은 '꺼짐'과 구분해 보여 준다(모르는 것을 꺼졌다고 단정하지 않는다).
export function PostureMatrix({ posture }: { posture: Posture }) {
  const matrix = posture.matrix ?? {};
  const regions = posture.regions ?? [];
  const features = Object.keys(matrix);
  if (!features.length) return <p className="muted">아직 보안 태세를 수집하지 않았습니다.</p>;
  return (
    <div className="table-wrap">
      <table className="matrix">
        <thead>
          <tr>
            <th scope="col">기능</th>
            {regions.map((r) => (
              <th key={r} scope="col" className="mono">
                {r}
              </th>
            ))}
            <th scope="col">계정 전체</th>
          </tr>
        </thead>
        <tbody>
          {features.map((f) => (
            <tr key={f}>
              <th scope="row">{FEATURE_LABEL[f] ?? f}</th>
              {[...regions, "global"].map((r) => {
                const v = matrix[f]?.[r];
                return (
                  <td key={r} className={v ? `ps ps-${v}` : "ps"}>
                    {v ? (STATE_TEXT[v] ?? v) : ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
