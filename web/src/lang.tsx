// 언어 상태: 처음 열 때만 브라우저 언어로 정하고, 사용자가 고른 값은 localStorage 에 저장한다.
// 문구 표와 순수 도우미는 i18n.ts 에 있다 — 이 파일은 React 와 이어 주는 얇은 층이다.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { detectLang, isLang, LANG_STORAGE_KEY, makeTranslator, type Lang, type Translator } from "./i18n";

interface LangValue {
  lang: Lang;
  setLang: (next: Lang) => void;
  t: Translator;
}

const LangContext = createContext<LangValue>({ lang: "en", setLang: () => undefined, t: makeTranslator("en") });

// file:// 로 연 사본에서는 브라우저가 localStorage 를 막을 수 있다 → 실패해도 화면은 그대로 뜬다
function readSaved(): string | null {
  try {
    return window.localStorage.getItem(LANG_STORAGE_KEY);
  } catch {
    return null;
  }
}

function save(lang: Lang): void {
  try {
    window.localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch {
    /* 저장은 편의 기능일 뿐 */
  }
}

// 주소의 ?lang=ko 는 직접 고른 것으로 보고(스크린샷·공유 링크) 저장한 뒤 쓴다
function initialLang(): Lang {
  const fromUrl = new URLSearchParams(window.location.search).get("lang");
  if (isLang(fromUrl)) {
    save(fromUrl);
    return fromUrl;
  }
  return detectLang(readSaved(), window.navigator.language);
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    save(next);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const value = useMemo(() => ({ lang, setLang, t: makeTranslator(lang) }), [lang, setLang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useI18n(): LangValue {
  return useContext(LangContext);
}

// 문구 속 `백틱` 구간을 <code> 로 그린다(명령·설정 이름 표시용)
export function Rich({ text }: { text: string }) {
  return (
    <>
      {text.split("`").map((part, i) => (i % 2 === 1 ? <code key={i}>{part}</code> : part))}
    </>
  );
}
