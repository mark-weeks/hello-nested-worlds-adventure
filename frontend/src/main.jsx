// PixiJS v8 compiles shader/uniform glue with `new Function`, which the
// server's Content-Security-Policy (script-src 'self', no unsafe-eval)
// rightly forbids — without this module the scene renderer dies at init
// under production CSP while working on the CSP-less Vite dev server.
import "pixi.js/unsafe-eval";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
