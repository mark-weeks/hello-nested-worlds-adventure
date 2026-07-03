// Beta invite-key plumbing.
//
// Testers arrive on a URL like `/app?key=nw_<hex>&name=Alice`. The static
// shell loads ungated, but every data / WebSocket call is gated behind the
// invite key, so the app has to read the key out of its own URL and forward
// it. The key is stashed in localStorage so it survives client-side
// navigation (and page reloads without the query string).

const KEY_STORE = "nw_beta_key";

const params = new URLSearchParams(
  typeof location !== "undefined" ? location.search : "",
);

const urlKey = params.get("key");
if (urlKey && typeof localStorage !== "undefined") {
  localStorage.setItem(KEY_STORE, urlKey);
}

export function betaKey() {
  if (typeof localStorage !== "undefined") {
    const stored = localStorage.getItem(KEY_STORE);
    if (stored) return stored;
  }
  return urlKey || "";
}

// Append `?key=` (or `&key=`) to a same-origin URL when a beta key is present.
// No-op when the gate is off (no key), so local dev URLs stay clean.
export function withKey(url) {
  const key = betaKey();
  if (!key) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}key=${encodeURIComponent(key)}`;
}

// Player name suggested by the invite URL (`&name=`), if any.
export function urlName() {
  return params.get("name") || "";
}
