// 화면 틀: 위쪽 띠(연습 모드 표시) → 머리글(이름·메뉴·신뢰 신호·테마) → 주소에 맞는 화면 하나.
import { useEffect, useState } from "react";
import { useApi, type Status } from "./api";
import { Link, TrustDot } from "./components/ui";
import { ago } from "./format";
import { useLocation } from "./router";
import Changes from "./routes/Changes";
import Findings from "./routes/Findings";
import Overview from "./routes/Overview";
import Resources from "./routes/Resources";
import Setup from "./routes/Setup";

const NAV = [
  { to: "/", label: "개요" },
  { to: "/resources", label: "자원" },
  { to: "/changes", label: "변경 이력" },
  { to: "/findings", label: "문제" },
  { to: "/setup", label: "연결" },
];

type Theme = "light" | "dark";

// file:// 로 연 사본에서는 브라우저가 localStorage 를 막을 수 있다 → 실패해도 화면은 그대로 뜬다
function readSaved(): string | null {
  try {
    return window.localStorage.getItem("awsglance-theme");
  } catch {
    return null;
  }
}

function initialTheme(): Theme {
  const saved = readSaved();
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function Page({ path }: { path: string }) {
  if (path === "/" || path === "/overview") return <Overview />;
  if (path === "/resources") return <Resources />;
  if (path === "/changes") return <Changes />;
  if (path === "/findings") return <Findings />;
  if (path === "/setup") return <Setup />;
  return (
    <div className="page">
      <h1>없는 화면입니다</h1>
      <Link to="/">개요로 가기</Link>
    </div>
  );
}

export default function App() {
  const { path } = useLocation();
  const status = useApi<Status>("/api/status");
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem("awsglance-theme", theme);
    } catch {
      /* 저장은 편의 기능일 뿐 */
    }
  }, [theme]);

  // 실제 모드는 1분마다 상태를 다시 읽어 '마지막 수집'·신뢰 신호를 새로 고친다
  const reloadStatus = status.reload;
  useEffect(() => {
    const id = window.setInterval(reloadStatus, 60_000);
    return () => window.clearInterval(id);
  }, [reloadStatus]);

  const s = status.data;
  const active = (to: string) => (to === "/" ? path === "/" || path === "/overview" : path.startsWith(to));

  return (
    <>
      {s?.mode === "demo" ? (
        <div className="demo-banner" role="note">
          예제 계정(연습 모드) — 가상의 AWS 계정 {s.identity?.account} 의 mock 데이터입니다. AWS 를 호출하지 않습니다.
        </div>
      ) : null}
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="logo" aria-hidden="true">
            ◔
          </span>
          awsglance
        </Link>
        <nav aria-label="화면">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} className={active(n.to) ? "nav active" : "nav"}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="topbar-right">
          {s ? (
            <>
              <TrustDot level={s.trust.level} reason={s.trust.reason} />
              <span className="muted small mono" title="마지막 인벤토리 수집">
                {s.identity?.account ?? "—"} · {s.collecting ? `수집 중(${s.collecting})` : `수집 ${ago(s.last_inventory)}`}
              </span>
            </>
          ) : null}
          <button
            type="button"
            className="icon-btn"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={theme === "dark" ? "밝은 테마로" : "어두운 테마로"}
            title="테마 바꾸기"
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </div>
      </header>
      <main>
        <Page path={path} />
      </main>
      <footer className="footer muted small">
        awsglance {s?.version ?? ""} · 읽기 전용(허용 목록 밖 AWS 작업은 코드에서 차단) · 이 도구는 AWS 공식 도구가 아닙니다
      </footer>
    </>
  );
}
