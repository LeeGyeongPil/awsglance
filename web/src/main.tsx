import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { LangProvider } from "./lang";
import "./styles.css";

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <LangProvider>
        <App />
      </LangProvider>
    </StrictMode>,
  );
}
