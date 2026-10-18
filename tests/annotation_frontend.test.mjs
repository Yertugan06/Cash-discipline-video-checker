import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../realtime/static/annotate.js", import.meta.url), "utf8");
const settle = () => new Promise((resolve) => setImmediate(resolve));
const annotation = (clip = "X-1", extra = {}) => ({
  clip, version: 0, rows: [], reviews: [], assisted: false, status: "draft", annotator: "",
  layout: "unset", people_max: 0, summary: "", ...extra,
});

function page(url = "http://gateway/annotate?view=detailed") {
  const elements = new Map(), requests = [];
  const bodyClasses = new Set();
  const document = {
    body: { classList: {
      toggle(name, enabled) { if (enabled) bodyClasses.add(name); else bodyClasses.delete(name); },
      contains(name) { return bodyClasses.has(name); },
    } },
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {
        value: "", textContent: "", innerHTML: "", hidden: false, checked: false,
        currentTime: 0, duration: 20, videoWidth: 640, videoHeight: 360,
        clientWidth: 640, clientHeight: 360, style: {},
        listeners: {},
        classList: { toggle() {}, remove() {}, add() {} },
        addEventListener(type, listener) { this.listeners[type] = listener; },
        setAttribute() {}, checkValidity() { return true; }, pause() { this.paused = true; },
        play() { this.paused = false; this.playCalls = (this.playCalls || 0) + 1; return Promise.resolve(); },
        focus() { document.activeElement = this; this.listeners.focus?.({target: this}); },
        getContext() { return { clearRect() {} }; },
      });
      return elements.get(id);
    },
    querySelectorAll() { return []; }, addEventListener() {},
  };
  const context = vm.createContext({
    document, console, URL, URLSearchParams, location: new URL(url),
    history: { replaceState() {} }, localStorage: { getItem() { return null; } },
    window: { addEventListener() {}, devicePixelRatio: 1 },
    setTimeout() { return 1; }, clearTimeout() {},
    fetch(url, options = {}) {
      return new Promise((resolve) => requests.push({ url, options,
        reply(body, status = 200) {
          resolve({ ok: status >= 200 && status < 300, status, json: async () => body });
        },
      }));
    },
  });
  vm.runInContext(source, context);
  const run = (code) => vm.runInContext(code, context);
  run(`current = 'X-1'; doc = ${JSON.stringify(annotation())}; clips = [{key: 'X-1', name: 'X-1.mov'}, {key: 'X-2', name: 'X-2.mov'}, {key: 'X-3', name: 'X-3.mov'}];`);
  return { run, requests, elements,
    take(match) {
      const index = requests.findIndex(match);
      assert.notEqual(index, -1, "Expected API request");
      return requests.splice(index, 1)[0];
    },
  };
}

test("edits made during a save are sent next with the new version and are never replaced", async () => {
  const p = page();
  p.run("doc.summary = 'first edit'; changed()");
  const saving = p.run("save()");
  const first = p.take((r) => r.options.method === "PUT");
  assert.equal(JSON.parse(first.options.body).summary, "first edit");
  p.run("doc.summary = 'newer edit'; changed()");
  first.reply(annotation("X-1", { version: 1, summary: "first edit" }));
  await settle();
  const second = p.take((r) => r.options.method === "PUT");
  assert.match(second.url, /base_version=1$/);
  assert.equal(JSON.parse(second.options.body).summary, "newer edit");
  second.reply(annotation("X-1", { version: 2, summary: "newer edit" }));
  assert.equal(await saving, true);
  assert.equal(p.run("doc.summary"), "newer edit");
  assert.equal(p.run("savedRevision === revision"), true);
});

test("a conflicting save keeps edits and prevents navigation from discarding them", async () => {
  const p = page();
  p.run("doc.summary = 'keep my notes'; changed()");
  const saving = p.run("save()");
  p.take((r) => r.options.method === "PUT").reply({ detail: "Someone else saved" }, 409);
  assert.equal(await saving, false);
  await p.run("openClip('X-2')");
  assert.equal(p.run("current"), "X-1");
  assert.equal(p.run("doc.summary"), "keep my notes");
  assert.equal(p.elements.get("downloadNotes").hidden, false);
  assert.equal(p.requests.some((r) => r.url === "/api/annotations/X-2"), false);
});

test("a failed save is retryable without losing the unsaved revision", async () => {
  const p = page();
  p.run("doc.summary = 'unsaved'; changed()");
  const failed = p.run("save()");
  p.take((r) => r.options.method === "PUT").reply({ detail: "Storage unavailable" }, 500);
  assert.equal(await failed, false);
  const retry = p.run("save()");
  const request = p.take((r) => r.options.method === "PUT");
  assert.equal(JSON.parse(request.options.body).summary, "unsaved");
  request.reply(annotation("X-1", { version: 3, summary: "unsaved" }));
  assert.equal(await retry, true);
});

test("rapid clip navigation ignores an earlier response arriving last", async () => {
  const p = page();
  const earlier = p.run("openClip('X-2')");
  await settle();
  const later = p.run("openClip('X-3')");
  await settle();
  p.take((r) => r.url === "/api/annotations/X-3").reply(annotation("X-3"));
  await later;
  p.take((r) => r.url === "/api/annotations/X-2").reply(annotation("X-2"));
  await earlier;
  assert.equal(p.run("current"), "X-3");
  assert.equal(p.run("doc.clip"), "X-3");
});

test("an unfinished note blocks clip navigation until it is added or cleared", async () => {
  const p = page();
  p.run("composerDirty = true");
  await p.run("openClip('X-2')");
  assert.equal(p.run("current"), "X-1");
  assert.match(p.elements.get("pageError").textContent, /unfinished note/);
});

test("object sightings cannot turn into action rows when a reviewer confirms a box", () => {
  const p = page();
  p.run(`suggestions = {run: 'old', frames: [{t: 0, objects: []}]};
    recordReview({id: 'job:object:0:0', label: 'cash', box: [.1,.2,.3,.4]}, 'object', 'accepted')`);
  assert.equal(p.run("doc.rows.length"), 0);
  assert.equal(p.run("doc.reviews[0].decision"), "accepted");
  assert.equal(p.run("doc.assisted"), true);
});

test("confirming an event already on the manual timeline keeps the existing note", () => {
  const p = page();
  p.run(`doc.rows = [{t_start: 3, actor: 'client', action: 'enter', item: 'none', note: 'my observation'}]`);
  assert.equal(p.run(`alreadyAnnotated({id: 'event:1', row: {t_start: 3, actor: 'client', action: 'enter', item: 'none'}})`), true);
  assert.equal(p.run(`alreadyAnnotated({id: 'event:2', row: {t_start: 8, actor: 'client', action: 'enter', item: 'none'}})`), false);
});

test("Save now adds and saves the unfinished note so the saved indicator is truthful", async () => {
  const p = page();
  p.run(`$('note').value = 'The client returns'; $('actor').value = 'client';
    $('action').value = 'other'; $('item').value = 'none'; $('place').value = 'none'; composerChanged()`);
  assert.match(p.elements.get("saveStatus").textContent, /not added/);
  const saving = p.run("saveNow()");
  const request = p.take((r) => r.options.method === "PUT");
  const body = JSON.parse(request.options.body);
  assert.equal(body.rows[0].note, "The client returns");
  assert.equal(p.run("composerDirty"), false);
  request.reply(annotation("X-1", {version: 1, ...body}));
  assert.equal(await saving, true);
  assert.equal(p.elements.get("saveStatus").textContent, "All changes saved");
});

test("Save now keeps an invalid unfinished note and displays validation instead of claiming it saved", async () => {
  const p = page();
  p.run(`$('note').value = 'Keep this draft'; $('action').value = 'other'; selection = {start: 8, end: 3}; composerChanged()`);
  assert.equal(await p.run("saveNow()"), false);
  assert.equal(p.run("composerDirty"), true);
  assert.match(p.elements.get("noteError").textContent, /valid start/);
  assert.equal(p.requests.some((r) => r.options.method === "PUT"), false);
});

test("easy notes is the default and changing views preserves the pending comment and selected range", () => {
  const p = page("http://gateway/annotate");
  assert.equal(p.run("easyMode"), true);
  p.run(`$('note').value = 'Client hands over cash'; selection = {start: 4, end: 7}; composerChanged(); setEasyMode(false); setEasyMode(true)`);
  assert.equal(p.elements.get("note").value, "Client hands over cash");
  assert.equal(p.run("selection.end"), 7);
  assert.equal(p.run("composerDirty"), true);
  assert.equal(p.run("document.body.classList.contains('easy-mode')"), true);
  assert.equal(p.elements.get("reviewPanel").hidden, true);
});

test("starting an easy comment pauses the video and fixes its timestamp before typing", () => {
  const p = page("http://gateway/annotate");
  p.run(`resetComposer(); $('video').currentTime = 6.3; prepareComment();`);
  assert.equal(p.elements.get("video").paused, true);
  p.run(`$('note').value = 'The client leaves'; $('video').currentTime = 12; addNote()`);
  assert.equal(p.run("doc.rows[0].t_start"), 6.3);
  assert.equal(p.run("doc.rows[0].action"), "other");
  assert.equal(p.run("doc.rows[0].actor"), "unknown");
});

test("Pause and comment here captures the playhead even after an older point or range was selected", () => {
  const p = page("http://gateway/annotate");
  p.run(`resetComposer(); selection = {start: 0, end: null}; $('video').currentTime = 8.4;
    $('commentNow').listeners.click()`);
  assert.equal(p.run("selection.start"), 8.4);
  assert.equal(p.run("selection.end"), null);
  assert.equal(p.elements.get("video").paused, true);
  p.run(`selection = {start: 4, end: 7}; $('video').currentTime = 14.7;
    $('commentNow').listeners.click(); $('note').value = 'Client leaves'; addNote()`);
  assert.equal(p.run("doc.rows[0].t_start"), 14.7);
  assert.equal(p.run("doc.rows[0].t_end"), null);
});

test("focusing the comment box preserves an intentionally selected time range", () => {
  const p = page("http://gateway/annotate");
  p.run(`resetComposer(); selection = {start: 4, end: 7}; $('video').currentTime = 12;
    $('note').focus()`);
  assert.equal(p.run("selection.start"), 4);
  assert.equal(p.run("selection.end"), 7);
  assert.equal(p.elements.get("video").paused, true);
});

test("saving a plain comment preserves its range and continues watching from the end", () => {
  const p = page("http://gateway/annotate");
  p.run(`resetComposer(); selection = {start: 4, end: 7}; prepareComment();
    $('note').value = 'The cashier counts the cash'; addNote()`);
  assert.equal(p.run("doc.rows[0].t_start"), 4);
  assert.equal(p.run("doc.rows[0].t_end"), 7);
  assert.equal(p.run("doc.rows[0].note"), "The cashier counts the cash");
  assert.equal(p.elements.get("video").currentTime, 7);
  assert.equal(p.elements.get("video").playCalls, 1);
});

test("Done and next saves the pending comment and completion before opening another clip", async () => {
  const p = page("http://gateway/annotate");
  p.run(`resetComposer(); $('note').value = 'Client leaves after counting'; composerChanged()`);
  const finishing = p.run("finishAndNext()");
  const note = p.take((r) => r.options.method === "PUT");
  assert.equal(JSON.parse(note.options.body).rows[0].note, "Client leaves after counting");
  note.reply(annotation("X-1", {version: 1}));
  await settle();
  const done = p.take((r) => r.options.method === "PUT");
  assert.equal(JSON.parse(done.options.body).status, "done");
  done.reply(annotation("X-1", {version: 2, status: "done"}));
  await settle();
  p.take((r) => r.url === "/api/annotations/X-2").reply(annotation("X-2"));
  await finishing;
  assert.equal(p.run("current"), "X-2");
});

test("Done and next keeps the comment and stays on the clip when saving fails", async () => {
  const p = page("http://gateway/annotate");
  p.run(`resetComposer(); $('note').value = 'Keep this observation'; composerChanged()`);
  const finishing = p.run("finishAndNext()");
  p.take((r) => r.options.method === "PUT").reply({detail: "Storage unavailable"}, 500);
  await finishing;
  assert.equal(p.run("current"), "X-1");
  assert.equal(p.run("doc.rows[0].note"), "Keep this observation");
  assert.equal(p.requests.some((r) => r.url === "/api/annotations/X-2"), false);
});

test("description view combines existing notes without changing or timing them again", async () => {
  const p = page();
  p.run(`doc.status = 'done'; doc.rows = [
    {t_start: 8, note: 'Cashier counts the cash'}, {t_start: 3, note: 'Client closes the door'}]`);
  await p.run("loadDescription()");
  assert.equal(p.run("doc.summary"), "Client closes the door\nCashier counts the cash");
  assert.equal(p.run("doc.rows[0].t_start"), 8);
  assert.equal(p.run("doc.status"), "done");
  assert.equal(p.run("doc.description_source"), "existing_notes");
  assert.equal(p.requests.some((r) => r.url.includes("annotation-description")), false);
});

const draft = (clip = "X-1") => ({
  clip, status: "ready", description: "A client approaches the desk.\nThe cashier handles a small object.",
  model: "local-video-model", sampled_timestamps: [0, 1, 2, 3],
});

test("a model draft prefills the description as assisted and unreviewed, without inventing event times", async () => {
  const p = page();
  const loading = p.run("loadDescription()");
  p.take((r) => r.url.includes("annotation-description")).reply(draft());
  await loading;
  assert.equal(p.run("doc.summary"), draft().description);
  assert.equal(p.elements.get("summary").value, draft().description);
  assert.equal(p.run("doc.assisted"), true);
  assert.equal(p.run("doc.description_source"), "ai_draft");
  assert.equal(p.run("doc.description_model"), "local-video-model");
  assert.equal(p.run("doc.status"), "draft");
  assert.equal(p.run("doc.rows.length"), 0);
});

test("a late model draft cannot replace text the user started writing", async () => {
  const p = page();
  const loading = p.run("loadDescription()");
  p.run(`$('summary').value = 'My own observation'; updateDescription()`);
  p.take((r) => r.url.includes("annotation-description")).reply(draft());
  await loading;
  assert.equal(p.run("doc.summary"), "My own observation");
  assert.equal(p.run("doc.assisted"), false);
});

test("a draft response for a previous clip cannot fill the current clip", async () => {
  const p = page();
  const loading = p.run("loadDescription()");
  p.run(`current = 'X-2'; doc.clip = 'X-2'`);
  p.take((r) => r.url.includes("annotation-description")).reply(draft());
  await loading;
  assert.equal(p.run("doc.summary"), "");
});

test("saved descriptions take priority over model drafts and do not trigger regeneration", async () => {
  const p = page();
  p.run(`doc.summary = 'Already corrected'; doc.description_source = 'ai_draft'; doc.description_model = 'local-model'`);
  await p.run("loadDescription()");
  assert.equal(p.run("doc.summary"), "Already corrected");
  assert.equal(p.requests.some((r) => r.url.includes("annotation-description")), false);
});

test("blank descriptions cannot be marked reviewed by the description shortcut", async () => {
  const p = page("http://gateway/annotate");
  await p.run("finishAndNext()");
  assert.equal(p.run("doc.status"), "draft");
  assert.equal(p.run("current"), "X-1");
  assert.match(p.elements.get("descriptionStatus").textContent, /Wait for the draft/);
});

test("description completion saves the correction and its provenance before opening the next clip", async () => {
  const p = page("http://gateway/annotate");
  p.run(`doc.description_source = 'ai_draft'; doc.description_model = 'local-model'; doc.assisted = true;
    $('summary').value = 'The corrected action sequence'; updateDescription()`);
  const finishing = p.run("finishAndNext()");
  const correction = p.take((r) => r.options.method === "PUT");
  const body = JSON.parse(correction.options.body);
  assert.equal(body.summary, "The corrected action sequence");
  assert.equal(body.description_model, "local-model");
  assert.equal(body.rows.length, 0);
  correction.reply(annotation("X-1", {version: 1, ...body}));
  await settle();
  const done = p.take((r) => r.options.method === "PUT");
  assert.equal(JSON.parse(done.options.body).status, "done");
  done.reply(annotation("X-1", {version: 2, ...JSON.parse(done.options.body)}));
  await settle();
  p.take((r) => r.url === "/api/annotations/X-2").reply(annotation("X-2"));
  await finishing;
  assert.equal(p.run("current"), "X-2");
});
