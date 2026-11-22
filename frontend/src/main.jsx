import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { withKey } from "./auth.js";
import "../../static/participation.js";
import "../../static/participation.css";
import "../../static/reporting.js";
import "../../static/reporting.css";

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

// Read the current server notice before mounting gameplay. An earlier intro
// preference never substitutes for this participant's affirmative choice.
globalThis.EnfoldedParticipation.ensure().then(() => {
  createRoot(document.getElementById("root")).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
});
