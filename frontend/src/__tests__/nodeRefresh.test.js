import { expect, it, vi } from "vitest";
import { createNodeRefresher } from "../nodeRefresh.js";

it.each(["HTTP first", "socket first"])("reads an acceptance and its echo once: %s", async order => {
  const read = vi.fn().mockResolvedValue({ pending_actions: [{ count: 1 }] });
  const apply = vi.fn();
  const refresh = createNodeRefresher(read, apply);
  const http = { event_id: 12, work: { id: 7 }, flavor: "Your kindle is planted" };
  const socket = { event_id: 12, work: { id: 7 }, type: "scale_act", actor: "Ada" };
  const [notice, echo] = order === "HTTP first" ? [http, socket] : [socket, http];
  const first = refresh(382, "Galaxy", notice);
  expect(refresh(382, "Galaxy", echo)).toBe(first);
  await first;
  await refresh(382, "Galaxy", echo);
  expect(read).toHaveBeenCalledTimes(1);
  expect(apply).toHaveBeenCalledTimes(1);
  await refresh(382, "Galaxy", { matured: true, work_id: 7 });
  expect(read).toHaveBeenCalledTimes(2);
  // Distinct requests and shared/no-op responses still read current state.
  await refresh(382, "Galaxy", { event_id: 13 });
  await refresh(382, "Galaxy", { action_status: "shared" });
  await refresh(382, "Galaxy", { action_status: "noop" });
  expect(read).toHaveBeenCalledTimes(5);
});

it("cannot replace a newer node read with an older response", async () => {
  const releases = [];
  const apply = vi.fn();
  const refresh = createNodeRefresher(() => new Promise(resolve => releases.push(resolve)), apply);
  const old = refresh(382, "Galaxy", { event_id: 1 });
  const current = refresh(382, "Galaxy", { event_id: 2 });
  await Promise.resolve();
  releases[1]({ density: 459 });
  await current;
  releases[0]({ density: 438 });
  await old;
  expect(apply).toHaveBeenCalledExactlyOnceWith({ density: 459 }, 382, "Galaxy");
});

it("retries failed reads and isolates nodes and worlds", async () => {
  const read = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue({});
  const refresh = createNodeRefresher(read, vi.fn());
  await expect(refresh(382, "Galaxy", { event_id: 1 })).rejects.toThrow("offline");
  await refresh(382, "Galaxy", { event_id: 1 });
  await refresh(383, "Galaxy", { event_id: 1 });
  await refresh(382, "Other", { event_id: 1 });
  expect(read).toHaveBeenCalledTimes(4);
});
