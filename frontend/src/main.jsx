// PixiJS v8 compiles shader/uniform glue with `new Function`, which the
// server's Content-Security-Policy (script-src 'self', no unsafe-eval)
// rightly forbids — without this module the scene renderer dies at init
// under production CSP while working on the CSP-less Vite dev server.
import "pixi.js/unsafe-eval";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { withKey } from "./auth.js";

// Browser crashes were invisible to operators (Sentry is server-side only);
// forward them so a broken deploy shows up in the server logs.
function reportClientError(message, source) {
  try {
    fetch(withKey("/client-error"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: String(message).slice(0, 512),
                             source: String(source || "app").slice(0, 256) }),
    }).catch(() => {});
  } catch { /* reporting must never crash the app */ }
}
window.addEventListener("error", e =>
  reportClientError(e.message, `${e.filename || ""}:${e.lineno || 0}`));
window.addEventListener("unhandledrejection", e =>
  reportClientError(`unhandled rejection: ${String(e.reason).slice(0, 480)}`, "app"));

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
