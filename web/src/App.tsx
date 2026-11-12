// 화면 틀: 위쪽 띠(연습 모드 표시) → 머리글(이름·메뉴·신뢰 신호·언어·테마) → 주소에 맞는 화면 하나.
import { useEffect, useState } from "react";
import { useApi, type Status } from "./api";
import { Link, TrustDot } from "./components/ui";
import { ago, LANGS, trustReason, type Lang } from "./i18n";
import { useI18n } from "./lang";
import { useLocation } from "./router";
import Changes from "./routes/Changes";
import Findings from "./routes/Findings";
import Overview from "./routes/Overview";
import Resources from "./routes/Resources";
import Setup from "./routes/Setup";

const NAV = [
  { to: "/", key: "nav.overview" },
  { to: "/resources", key: "nav.resources" },
  { to: "/changes", key: "nav.changes" },
  { to: "/findings", key: "nav.findings" },
  { to: "/setup", key: "nav.setup" },
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
  const { t } = useI18n();
  if (path === "/" || path === "/overview") return <Overview />;
  if (path === "/resources") return <Resources />;
  if (path === "/changes") return <Changes />;
  if (path === "/findings") return <Findings />;
  if (path === "/setup") return <Setup />;
  return (
    <div className="page">
      <h1>{t("app.not_found")}</h1>
      <Link to="/">{t("app.go_overview")}</Link>
    </div>
  );
}

export default function App() {
  const { path } = useLocation();
  const { t, lang, setLang } = useI18n();
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
          {t("app.demo_banner", { account: s.identity?.account ?? "" })}
        </div>
      ) : null}
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="logo" aria-hidden="true">
            ◔
          </span>
          awsglance
        </Link>
        <nav aria-label={t("app.nav_label")}>
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} className={active(n.to) ? "nav active" : "nav"}>
              {t(n.key)}
            </Link>
          ))}
        </nav>
        <div className="topbar-right">
          {s ? (
            <>
              <TrustDot level={s.trust.level} reason={trustReason(t, s.trust)} />
              <span className="muted small mono" title={t("app.last_inventory")}>
                {s.identity?.account ?? "—"} ·{" "}
                {s.collecting ? t("app.collecting", { job: s.collecting }) : t("app.collected", { ago: ago(lang, s.last_inventory) })}
              </span>
            </>
          ) : null}
          <label className="lang-picker">
            <span className="visually-hidden">{t("lang.label")}</span>
            <select value={lang} onChange={(e) => setLang(e.target.value as Lang)} aria-label={t("lang.label")}>
              {LANGS.map((code) => (
                <option key={code} value={code}>
                  {t(`lang.${code}`)}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="icon-btn"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={theme === "dark" ? t("app.theme_to_light") : t("app.theme_to_dark")}
            title={t("app.theme_title")}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </div>
      </header>
      <main>
        <Page path={path} />
      </main>
      <footer className="footer muted small">
        {t("app.footer", { version: s?.version ?? "" })}
      </footer>
    </>
  );
}
