// 여러 화면이 같이 쓰는 작은 조각들. 상태는 색 + 아이콘 + 글자로 겹쳐 표시한다(색을 구분하기 어려운 사람도 읽게).
import { useEffect, useRef, type ReactNode } from "react";
import type { ActorClass, Severity, TrustLevel } from "../api";
import { ACTOR_LABEL, SEVERITY_ICON, SEVERITY_LABEL } from "../format";
import { hrefFor, linkHandler } from "../router";

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`badge sev-${severity}`} title={`심각도: ${SEVERITY_LABEL[severity]}`}>
      <span aria-hidden="true">{SEVERITY_ICON[severity]}</span> {SEVERITY_LABEL[severity]}
    </span>
  );
}

export function ActorChip({ cls, via }: { cls: ActorClass; via?: string }) {
  const icon = cls === "human" ? "◉" : cls === "automated" ? "⚙" : "?";
  return (
    <span className={`chip actor-${cls}`}>
      <span aria-hidden="true">{icon}</span> {ACTOR_LABEL[cls]}
      {via ? <span className="muted"> · {via}</span> : null}
    </span>
  );
}

const TRUST_TEXT: Record<TrustLevel, string> = { ok: "정상", warn: "주의", danger: "위험", unknown: "판단 보류" };
const TRUST_ICON: Record<TrustLevel, string> = { ok: "✓", warn: "!", danger: "✕", unknown: "?" };

export function TrustDot({ level, reason }: { level: TrustLevel; reason?: string }) {
  return (
    <span className={`trust trust-${level}`} title={reason}>
      <span className="trust-dot" aria-hidden="true">
        {TRUST_ICON[level]}
      </span>
      {TRUST_TEXT[level]}
    </span>
  );
}

export function Link({ to, children, className }: { to: string; children: ReactNode; className?: string }) {
  return (
    <a href={hrefFor(to)} onClick={linkHandler(to)} className={className}>
      {children}
    </a>
  );
}

export function Loading() {
  return (
    <div className="state" role="status">
      불러오는 중…
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      불러오지 못했습니다: {message}
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          다시 시도
        </button>
      ) : null}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>;
}

export function Tabs<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string; count?: number }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={value === o.value}
          className={value === o.value ? "tab active" : "tab"}
          onClick={() => onChange(o.value)}
        >
          {o.label}
          {o.count !== undefined ? <span className="count">{o.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

// 오른쪽에서 나오는 상세 창. Esc 로 닫고, 열릴 때 닫기 버튼에 초점을 둔다(키보드 탐색).
export function Drawer({ title, onClose, children }: { title: ReactNode; onClose: () => void; children: ReactNode }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <h2>{title}</h2>
          <button ref={closeRef} type="button" className="icon-btn" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}
