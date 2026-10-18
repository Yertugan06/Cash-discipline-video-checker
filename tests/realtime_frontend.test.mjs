import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../realtime/static/index.html", import.meta.url), "utf8")
  .match(/<script>([\s\S]*?)<\/script>/)[1];
const item = (id) => ({ id, name: `${id}.mov`, status: "done", verdict: "no_violation" });
const settle = () => new Promise((resolve) => setImmediate(resolve));

async function page(url = "http://gateway/") {
  const elements = new Map();
  const listeners = {};
  const pending = [];
  const sockets = [];
  let holdState = false;
  const location = new URL(url);
  const document = {
    activeElement: { tagName: "BODY" },
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {
        innerHTML: "", textContent: "", value: "", style: {}, disabled: false,
        addEventListener(type, handler) { this[type] = handler; },
        setAttribute() {},
      });
      return elements.get(id);
    },
    querySelector() { return null; },
    addEventListener(type, handler) { listeners[type] = handler; },
  };
  const context = vm.createContext({
    document, location, URL, URLSearchParams, console,
    history: {
      pushState(_state, _unused, next) { location.href = new URL(next, location).href; },
      replaceState(_state, _unused, next) { location.href = new URL(next, location).href; },
    },
    window: { addEventListener(type, handler) { listeners[type] = handler; } },
    localStorage: { getItem() { return null; } },
    setInterval() { return 1; }, clearInterval() {}, setTimeout() {},
    alert() {},
    WebSocket: class { constructor() { sockets.push(this); } },
    fetch(path) {
      const response = (data, status = 200) => ({
        ok: status === 200, status, json: async () => data, text: async () => JSON.stringify(data),
      });
      if (path === "/api/runs") return Promise.resolve(response({ runs: ["live", "old", "new"] }));
      if (path === "/api/config") return Promise.resolve(response({ folder: null, labels: 0 }));
      if (path === "/api/state" && !holdState) return Promise.resolve(response({ items: [item("live")] }));
      return new Promise((resolve) => pending.push({ path, reply: (data, status) => resolve(response(data, status)) }));
    },
  });
  vm.runInContext(source, context);
  await settle();
  return {
    run: (code) => vm.runInContext(code, context), elements, listeners, sockets, location,
    holdState() { holdState = true; },
    reply(path, items, status = 200) {
      const index = pending.findIndex((request) => request.path === path);
      assert.notEqual(index, -1, `No pending request for ${path}`);
      pending.splice(index, 1)[0].reply({ items }, status);
    },
  };
}

test("offline replay details tolerate omitted evidence frames and checker job", async () => {
  const p = await page();
  assert.doesNotThrow(() => p.run(`detail({id: 'offline', status: 'done',
    result: {violations: [{type: 'rule', timecode_sec: 1}]}})`));
});

test("rapid navigation ignores an older run response arriving last", async () => {
  const p = await page();
  const old = p.run("selectRun('old')");
  const newer = p.run("selectRun('new')");
  p.reply("/api/runs/new?full=true", [item("new")]);
  await newer;
  p.reply("/api/runs/old?full=true", [item("old")]);
  await old;
  assert.equal(p.run("currentRun"), "new");
  assert.equal(p.run("[...items.keys()].join()"), "new");
});

test("returning to live cannot be overwritten by an archive request", async () => {
  const p = await page();
  const old = p.run("selectRun('old')");
  await p.run("selectRun('live')");
  p.reply("/api/runs/old?full=true", [item("old")]);
  await old;
  assert.equal(p.run("[...items.keys()].join()"), "live");
});

test("live updates stay cached during archive browsing and beat an older HTTP snapshot", async () => {
  const p = await page();
  const old = p.run("selectRun('old')");
  p.reply("/api/runs/old?full=true", [item("old")]);
  await old;
  p.sockets[0].onmessage({ data: JSON.stringify({ type: "item", item: item("fresh") }) });
  assert.equal(p.run("[...items.keys()].join()"), "old");
  p.holdState();
  const live = p.run("selectRun('live')");
  assert.equal(p.run("items.has('fresh')"), true);
  p.sockets[0].onmessage({ data: JSON.stringify({ type: "item", item: item("newest") }) });
  p.reply("/api/state", [item("live")]);
  await live;
  assert.equal(p.run("items.has('newest')"), true);
});

test("saved run links load on open and selections update the URL", async () => {
  const p = await page("http://gateway/?run=old");
  p.reply("/api/runs/old?full=true", [item("old")]);
  await settle();
  assert.equal(p.run("currentRun"), "old");
  await p.run("selectRun('live')");
  assert.equal(p.location.searchParams.has("run"), false);
});

test("previous goes to a saved run from live; video arrow keys keep their native behavior", async () => {
  const p = await page();
  assert.equal(p.elements.get("prevRun").disabled, false);
  assert.equal(p.elements.get("nextRun").disabled, true);
  p.run("document.activeElement = {tagName: 'VIDEO', closest() { return this; }}");
  p.listeners.keydown({ key: "ArrowLeft", target: p.run("document.activeElement"),
    preventDefault() { assert.fail("video seek was intercepted"); } });
  assert.equal(p.run("currentRun"), "live");
});

test("failed archive loads clear the previous results and display an inline error", async () => {
  const p = await page();
  const old = p.run("selectRun('old')");
  p.reply("/api/runs/old?full=true", [], 500);
  await old;
  assert.equal(p.run("items.size"), 0);
  assert.match(p.elements.get("runError").textContent, /500/);
});
