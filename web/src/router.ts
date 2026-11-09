// 의존성 없는 아주 작은 라우터: 경로(/changes)와 쿼리(?tab=human)를 주소창에 담아 링크로 공유할 수 있게 한다.
import { useCallback, useSyncExternalStore, type MouseEvent } from "react";

const EVENT = "awsglance:navigate";

// 내보낸 정적 사본(file:// 로 열기)에는 서버가 없어 /changes 같은 경로가 열리지 않는다.
// 그래서 스냅샷이 들어 있으면 화면 주소를 해시(#/changes?tab=human)에 담는다.
export function isStaticExport(): boolean {
  return typeof window !== "undefined" && (window as { __AWSGLANCE_SNAPSHOT__?: unknown }).__AWSGLANCE_SNAPSHOT__ !== undefined;
}

// 링크의 href: 서버 모드는 경로 그대로, 정적 사본은 앞에 # 을 붙인다
export function hrefFor(to: string): string {
  return isStaticExport() ? `#${to}` : to;
}

function subscribe(cb: () => void): () => void {
  window.addEventListener("popstate", cb);
  window.addEventListener("hashchange", cb);
  window.addEventListener(EVENT, cb);
  return () => {
    window.removeEventListener("popstate", cb);
    window.removeEventListener("hashchange", cb);
    window.removeEventListener(EVENT, cb);
  };
}

function snapshot(): string {
  if (isStaticExport()) return window.location.hash.slice(1) || "/";
  return window.location.pathname + window.location.search;
}

export function navigate(to: string, replace = false): void {
  if (to === snapshot()) return;
  if (isStaticExport()) {
    // 해시만 바꾸는 것은 file:// 에서도 항상 허용된다(pushState 는 file:// 에서 막힐 수 있다). hashchange 가 화면을 다시 그린다
    if (replace) window.location.replace(`#${to}`);
    else window.location.hash = to;
    return;
  }
  if (replace) window.history.replaceState(null, "", to);
  else window.history.pushState(null, "", to);
  window.dispatchEvent(new Event(EVENT));
}

export function useLocation(): { path: string; query: URLSearchParams } {
  const href = useSyncExternalStore(subscribe, snapshot);
  // file:// 에서는 origin 이 "null" 이라 URL 기준 주소로 쓸 수 없다 → 고정 가짜 기준 주소
  const url = new URL(href, "http://awsglance.local");
  return { path: url.pathname, query: url.searchParams };
}

// 필터 값을 쿼리 문자열에 읽고 쓴다. 빈 값은 주소에서 지운다.
export function useQueryState(): [URLSearchParams, (updates: Record<string, string | null>) => void] {
  const { path, query } = useLocation();
  const set = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(new URL(snapshot(), "http://awsglance.local").search);
      for (const [k, v] of Object.entries(updates)) {
        if (v === null || v === "") next.delete(k);
        else next.set(k, v);
      }
      const qs = next.toString();
      navigate(path + (qs ? `?${qs}` : ""), true);
    },
    [path],
  );
  return [query, set];
}

export function linkHandler(to: string) {
  return (e: MouseEvent) => {
    // 새 탭 열기(Ctrl/⌘ 클릭)는 브라우저에 맡긴다
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate(to);
  };
}
