"use strict";

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const LABEL = {
  unknown: "Not specified", cashier: "Cashier", client: "Client", collector: "Collector", other: "Other / describe below",
  enter: "Arrives / enters", exit: "Leaves the room", sit: "Sits down", stand_up: "Stands up",
  leave_desk: "Leaves the desk", return_desk: "Returns to the desk", hand_over: "Hands something over",
  take: "Takes an object", place_item: "Puts an object down", count_machine: "Counts with the machine",
  count_manual: "Counts by hand", open_safe: "Opens the safe", close_safe: "Closes the safe",
  open_door: "Opens the door", close_door: "Closes the door", show_id: "Shows an ID", lock_screen: "Locks the screen",
  none: "Not specified", cash: "Cash", bundle: "Cash bundle", bag: "Bag", seal: "Seal", key: "Key", id_card: "ID card",
  document: "Document", tablet: "Tablet", phone: "Phone", cup_food: "Cup / food", handbag_coat: "Personal bag / coat",
  desk: "Desk", safe: "Safe", counter: "Counting machine", hand: "In a hand", door: "Door", outside: "Outside",
  unset: "Not specified", over_shoulder: "Over the cashier’s shoulder", facing_cashier: "Facing the cashier", side: "Side view",
  person: "Person", glass: "Possible reflection", visitor: "Visitor",
};
const label = (value) => LABEL[value] ?? String(value ?? "").replaceAll("_", " ");
const round = (t) => Math.round(t * 10) / 10;
const time = (t) => `${Math.floor(Math.max(0, t) / 60)}:${(Math.max(0, t) % 60).toFixed(1).padStart(4, "0")}`;
const eventTitle = (row) => row.note || `${row.actor === "unknown" ? "Someone" : label(row.actor)} · ${label(row.action)}${row.item !== "none" ? ` · ${label(row.item)}` : ""}`;
let clips = [], vocab, current = null, doc = null, selection = null, editingRow = null, correcting = null;
let composerDirty = false, undo = null, revision = 0, savedRevision = 0, inFlight = null, saveTimer = null, saveConflict = false;
let navigation = 0, suggestionRequest = 0, detectionRequest = 0, suggestions = null, suggestionView = "events", lastFrame = null;
let easyMode = new URLSearchParams(location.search).get("view") !== "detailed";
let descriptionRequest = 0, descriptionTimer = null;

function descriptionLabel() {
  $("descriptionSource").textContent = doc.description_source === "ai_draft" ? "AI draft" : doc.description_source === "existing_notes" ? "Your existing notes" : "Your description";
}
function updateDescription() {
  if (!doc || !$("summary").checkValidity()) return;
  descriptionRequest++;
  clearTimeout(descriptionTimer);
  doc.summary = $("summary").value;
  if (doc.status === "done") doc.status = "draft";
  descriptionLabel();
  $("descriptionStatus").textContent = doc.description_source === "ai_draft" ? "Check the draft against the video and correct anything missing or wrong." : "Describe the actions in order. Approximate wording is enough.";
  $("refreshDescription").hidden = Boolean(doc.summary.trim());
  changed(); renderCompletion();
}
async function loadDescription() {
  if (!doc) return;
  clearTimeout(descriptionTimer);
  const request = ++descriptionRequest, clip = current;
  descriptionLabel();
  if (doc.summary.trim()) {
    $("descriptionStatus").textContent = doc.description_source === "ai_draft" ? "Saved AI draft and your corrections. Check small objects and add any missed actions." : "Your saved description. Correct or add anything while watching.";
    $("refreshDescription").hidden = true;
    return;
  }
  if (doc.rows.length) {
    const text = [...doc.rows].sort((a, b) => a.t_start - b.t_start).map(eventTitle).join("\n");
    if (text.length <= 6000) {
      doc.summary = text; doc.description_source = "existing_notes";
      $("summary").value = text;
      descriptionLabel(); changed();
      $("descriptionStatus").textContent = "Combined from your existing notes. Your original timeline is also saved in Detailed review.";
      $("refreshDescription").hidden = true;
      return;
    }
    $("descriptionStatus").textContent = "Your saved timeline is available in Detailed review. Write a shorter overall description here.";
    return;
  }
  $("descriptionStatus").textContent = "Checking for the local model’s description…";
  $("refreshDescription").hidden = true;
  try {
    const draft = await api(`/api/annotation-description/${encodeURIComponent(clip)}`);
    if (request !== descriptionRequest || clip !== current || doc.summary.trim()) return;
    if (draft.status === "ready") {
      doc.summary = draft.description; doc.description_source = "ai_draft";
      doc.description_model = draft.model; doc.assisted = true; doc.status = "draft";
      $("summary").value = doc.summary;
      descriptionLabel(); changed(); renderCompletion();
      $("descriptionStatus").textContent = "AI draft from sampled video frames. Check small objects and add any missed actions.";
    } else if (draft.status === "queued" || draft.status === "processing") {
      $("descriptionStatus").textContent = draft.status === "processing" ? "The local model is reading this clip. The description will appear here automatically." : "This clip is queued for a description. It will appear automatically; you can write here meanwhile.";
      descriptionTimer = setTimeout(loadDescription, 5000);
    } else {
      $("descriptionStatus").textContent = draft.status === "failed" ? `The description could not be generated: ${draft.error}` : "No model draft is available yet. You can write a description here or check again.";
      $("refreshDescription").hidden = false;
    }
  } catch (error) {
    if (request !== descriptionRequest || clip !== current) return;
    $("descriptionStatus").textContent = `Could not load the draft: ${error.message}`;
    $("refreshDescription").hidden = false;
  }
}

function composerLabels() {
  const editing = Boolean(editingRow || correcting);
  $("composerTitle").textContent = easyMode ? (editing ? "Edit comment" : "What happened?") : (editing ? "Edit this event" : "What happened?");
  $("addNote").textContent = easyMode ? (editing ? "Update comment" : "Save & keep watching") : (editing ? "Save changes" : "Add to timeline");
}
function setEasyMode(enabled) {
  easyMode = enabled;
  document.body.classList.toggle("easy-mode", enabled);
  $("easyMode").setAttribute("aria-pressed", String(enabled));
  $("detailedMode").setAttribute("aria-pressed", String(!enabled));
  if (enabled) { switchPanel("notes"); if (doc) loadDescription(); }
  composerLabels();
  const url = new URL(location.href); url.searchParams.set("view", enabled ? "easy" : "detailed");
  history.replaceState(null, "", url);
  if (doc) drawObjects();
}
function prepareComment({ atCurrentTime = false } = {}) {
  if (!doc || !easyMode) return;
  if (atCurrentTime || !selection) selection = { start: round($("video").currentTime), end: null };
  $("video").pause();
  updateRange();
}
async function finishAndNext() {
  if (!await saveNow()) return;
  if (easyMode && !doc.summary.trim() && doc.rows.length) await loadDescription();
  if (easyMode && !doc.summary.trim()) {
    $("descriptionStatus").textContent = "Wait for the draft or write a description before marking this clip reviewed.";
    $("summary").focus();
    return;
  }
  doc.status = "done"; changed();
  if (!await save()) return;
  const next = clips[clips.findIndex((clip) => clip.key === current) + 1];
  if (next) await openClip(next.key);
}

function message(id, text = "") { $(id).textContent = text; $(id).hidden = !text; }
function saveStatus(text, error = false) { $("saveStatus").textContent = text; $("saveStatus").classList.toggle("error", error); }
async function api(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status}). Check the entered values.`);
    error.status = response.status;
    throw error;
  }
  return body;
}
function fillOptions(id, values, selected) {
  $(id).innerHTML = values.map((v) => `<option value="${esc(v)}">${esc(label(v))}</option>`).join("");
  if (selected != null) $(id).value = selected;
}
function duration() {
  return Number.isFinite($("video").duration) ? $("video").duration : suggestions?.duration_sec ?? 0;
}
function range() { return selection ?? { start: round($("video").currentTime || 0), end: null }; }
function payload() {
  const { clip: _clip, version: _version, ...body } = doc;
  return { ...body, annotator: $("annotator").value.trim() || doc.annotator };
}

// Writes are serialized. A response updates the version, never the newer edits in memory.
function changed() {
  revision++;
  saveStatus("Unsaved changes");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(save, 650);
}
function composerChanged() {
  composerDirty = true;
  saveStatus("Note not added yet · add it to the timeline");
}
async function saveNow() {
  if (composerDirty) {
    addNote();
    if (composerDirty) return false;
  }
  return save();
}
function save() {
  clearTimeout(saveTimer);
  saveTimer = null;
  if (inFlight) return inFlight;
  if (saveConflict) return Promise.resolve(false);
  if (!doc || savedRevision === revision) return Promise.resolve(true);
  inFlight = saveLoop().finally(() => { inFlight = null; });
  return inFlight;
}
async function saveLoop() {
  try {
    while (savedRevision < revision) {
      const writingRevision = revision;
      saveStatus("Saving…");
      const saved = await api(`/api/annotations/${encodeURIComponent(current)}?base_version=${doc.version}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()),
      });
      doc.version = saved.version;
      doc.annotator = saved.annotator;
      doc.assisted = saved.assisted || doc.assisted;
      savedRevision = writingRevision;
    }
    saveStatus(composerDirty ? "Timeline saved · your current note is not added yet" : "All changes saved");
    const clip = clips.find((c) => c.key === current);
    if (clip) Object.assign(clip, { rows: doc.rows.length, status: doc.status, annotator: doc.annotator });
    renderClips();
    renderCompletion();
    return true;
  } catch (error) {
    saveConflict = error.status === 409;
    saveStatus(saveConflict ? "Someone else edited this clip. Your notes are kept here; download them before reloading." : `Could not save: ${error.message}. Use Save now to retry.`, true);
    $("downloadNotes").hidden = false;
    return false;
  }
}

function renderClips() {
  const query = $("clipSearch").value.trim().toLowerCase();
  const filtered = clips.filter((c) => `${c.key} ${c.name}`.toLowerCase().includes(query) && (!$("unfinishedOnly").checked || c.status !== "done" || c.key === current));
  $("clipCount").textContent = clips.length;
  $("clipProgress").textContent = `${clips.filter((c) => c.status === "done").length} of ${clips.length} finished`;
  $("clips").innerHTML = filtered.map((c) => `<button class="clip-button" data-clip="${esc(c.key)}" aria-current="${c.key === current}"><span class="clip-key">${esc(c.key)}</span><span class="clip-status ${c.status === "done" ? "complete" : ""}">${c.status === "done" ? "✓ Done" : c.rows ? `${c.rows} notes` : "Start"}</span></button>`).join("") || '<p class="muted">No matching clips.</p>';
}
function canLeaveComposer() {
  if (!composerDirty) return true;
  message("pageError", "You have an unfinished note. Add it to the timeline, or press Clear before switching clips or editing another event.");
  return false;
}
async function openClip(key) {
  if (!key || key === current || !canLeaveComposer()) return;
  const request = ++navigation;
  if (!await save() || request !== navigation) return;
  try {
    const loaded = await api(`/api/annotations/${encodeURIComponent(key)}`);
    if (request !== navigation) return;
    $("video").pause();
    current = key;
    doc = loaded;
    descriptionRequest++;
    clearTimeout(descriptionTimer);
    revision = savedRevision = 0;
    saveConflict = false;
    suggestions = null;
    suggestionRequest++;
    detectionRequest++;
    selection = null;
    lastFrame = null;
    undo = null;
    $("editor").hidden = false;
    $("emptyState").hidden = true;
    $("downloadNotes").hidden = true;
    $("undoNotice").hidden = true;
    $("overlayControl").hidden = true;
    $("suggestionLane").hidden = true;
    $("detectClip").disabled = false;
    $("refreshSuggestions").disabled = false;
    $("suggestionStatus").textContent = "Choose a run and load its saved detections, or run the detector on this clip.";
    message("pageError"); message("videoError"); message("rangeError");
    const clip = clips.find((c) => c.key === current);
    $("clipTitle").textContent = current;
    $("clipSubtitle").textContent = `${clip.name} · Watch and review`;
    $("video").src = `/api/clips/${encodeURIComponent(current)}/video`;
    $("layout").value = doc.layout;
    $("people").value = doc.people_max;
    $("summary").value = doc.summary;
    $("scoreOut").textContent = "";
    resetComposer();
    switchPanel("notes");
    renderClips(); renderRows(); renderTimeline(); renderCompletion(); renderSuggestions(); updateTime();
    saveStatus(doc.version ? "All changes saved" : "Ready to annotate");
    const index = clips.findIndex((c) => c.key === current);
    $("previousClip").disabled = index === 0;
    $("nextClip").disabled = index === clips.length - 1;
    const url = new URL(location.href); url.searchParams.set("clip", current);
    history.replaceState(null, "", url);
    if (easyMode) loadDescription();
    else descriptionLabel();
  } catch (error) { if (request === navigation) message("pageError", `Could not open clip: ${error.message}`); }
}
function renderCompletion() {
  $("completionStatus").textContent = doc.status === "done" ? "✓ Clip finished" : "In progress";
  $("completionHint").textContent = doc.status === "done" ? "Saved and reviewed. You can keep editing or move to the next clip." : easyMode ? "Correct the description, then save and continue." : "Add the important moments, then mark this clip done.";
  $("finishClip").textContent = doc.status === "done" ? "Reopen for review" : "Save & mark done";
}
function switchPanel(panel) {
  if (easyMode && panel === "review") return;
  for (const name of ["notes", "review"]) {
    $(name + "Tab").setAttribute("aria-selected", String(name === panel));
    $(name + "Panel").hidden = name !== panel;
  }
}

function renderRows() {
  $("noteCount").textContent = doc.rows.length;
  $("rows").innerHTML = doc.rows.map((row, index) => `<li class="event-card">
    <button class="event-time" data-seek="${row.t_start}" aria-label="Seek to ${time(row.t_start)}">${time(row.t_start)}${row.t_end != null ? `<span>→ ${time(row.t_end)}</span>` : ""}</button>
    <div class="event-copy">${esc(eventTitle(row))}<div class="event-tags">${row.action !== "other" ? `<span>${esc(label(row.action))}</span>` : ""}${row.actor !== "unknown" ? `<span>${esc(label(row.actor))}</span>` : ""}${row.uncertain ? '<span class="needs-review">Needs a closer look</span>' : ""}${row.source === "suggestion" ? '<span>Reviewed suggestion</span>' : ""}</div></div>
    <div class="event-actions"><button class="text-button" data-edit="${index}" aria-label="Edit event at ${time(row.t_start)}">Edit</button><button class="text-button" data-delete="${index}" aria-label="Delete event at ${time(row.t_start)}">×</button></div></li>`).join("") || '<li class="empty-events"><strong>No notes yet</strong>Select a moment or drag a range below the video,<br>then write what happened above.</li>';
  renderTimeline();
}
function resetComposer() {
  editingRow = null; correcting = null; composerDirty = false;
  $("note").value = ""; $("actorDesc").value = ""; $("actor").value = "unknown";
  $("action").value = "other"; $("item").value = "none"; $("place").value = "none"; $("uncertain").checked = false;
  composerLabels();
  $("cancelEdit").textContent = "Clear";
  message("editingNotice"); message("noteError"); message("pageError");
  if (doc) saveStatus(revision === savedRevision ? "All changes saved" : "Unsaved changes");
}
function populateComposer(row, title) {
  $("note").value = row.note;
  for (const id of ["actor", "action", "item", "place"]) $(id).value = row[id];
  $("actorDesc").value = row.actor_desc ?? "";
  $("uncertain").checked = row.uncertain ?? false;
  selection = { start: row.t_start, end: row.t_end };
  $("composerTitle").textContent = title;
  composerLabels();
  $("cancelEdit").textContent = "Cancel";
  composerDirty = true;
  saveStatus("Editing a note · save changes when ready");
  switchPanel("notes");
  seek(row.t_start); updateRange();
  $("note").focus();
}
function addNote(event) {
  event?.preventDefault();
  const selected = range();
  if (!Number.isFinite(selected.start) || selected.start < 0 || selected.start > 10000 || (selected.end != null && (!Number.isFinite(selected.end) || selected.end < selected.start || selected.end > 10000))) {
    message("noteError", "Choose a valid start and an end at or after the start."); return;
  }
  if (duration() && (selected.start > duration() || selected.end > duration())) { message("noteError", "The selected time is beyond the end of this video."); return; }
  if (!$("note").value.trim() && $("action").value === "other") { message("noteError", "Write what happened, or choose an event."); $("note").focus(); return; }
  const continueWatching = easyMode && !editingRow && !correcting;
  const resumeAt = selected.end ?? $("video").currentTime;
  const row = { ...(editingRow ?? {}), t_start: round(selected.start), t_end: selected.end == null ? null : round(selected.end),
    actor: $("actor").value, actor_desc: $("actorDesc").value, action: $("action").value, item: $("item").value,
    place: $("place").value, note: $("note").value.trim(), uncertain: $("uncertain").checked,
    source: correcting || editingRow?.source === "suggestion" ? "suggestion" : "manual",
    suggestion_id: correcting?.id ?? editingRow?.suggestion_id ?? null };
  if (correcting) recordReview(correcting, "event", "corrected", row.note || label(row.action), correcting.comment);
  if (editingRow) doc.rows[doc.rows.indexOf(editingRow)] = row;
  else doc.rows.push(row);
  const review = doc.reviews.find((r) => r.suggestion_id === row.suggestion_id);
  if (review && editingRow) { review.decision = "corrected"; review.correction = label(row.action); }
  doc.rows.sort((a, b) => a.t_start - b.t_start);
  resetComposer(); selection = null;
  renderRows(); updateRange(); changed();
  if (continueWatching) {
    seek(resumeAt);
    $("playPause").focus({ preventScroll: true });
    $("video").play().catch((error) => message("videoError", `Comment added. Press Play to continue: ${error.message}`));
  }
}

function updateRange() {
  const selected = range();
  if (document.activeElement !== $("rangeStart")) $("rangeStart").value = round(selected.start);
  if (document.activeElement !== $("rangeEnd")) $("rangeEnd").value = selected.end == null ? "" : round(selected.end);
  $("selectedTime").textContent = selected.end == null ? `At ${time(selected.start)}` : `${time(selected.start)} → ${time(selected.end)}`;
  const overlay = $("rangeSelection");
  overlay.hidden = !selection || !duration();
  if (!overlay.hidden) { overlay.style.left = `${100 * selected.start / duration()}%`; overlay.style.width = `${100 * Math.max(0, (selected.end ?? selected.start) - selected.start) / duration()}%`; }
}
function seek(t) {
  const video = $("video");
  video.currentTime = Math.max(0, duration() ? Math.min(t, duration()) : t);
  updateTime();
}
function renderTimeline() {
  const total = duration();
  $("timeTicks").innerHTML = [0, .25, .5, .75, 1].map((part) => `<span>${time(total * part)}</span>`).join("");
  function mark(row, extra = "") {
    return `<button type="button" class="timeline-mark ${row.uncertain ? "uncertain" : ""}" style="left:${Math.min(99, total ? 100 * row.t_start / total : 0)}%;width:${total ? Math.max(.7, 100 * ((row.t_end ?? row.t_start) - row.t_start) / total) : 1}%" data-seek="${row.t_start}" ${extra} title="${esc(`${time(row.t_start)} · ${eventTitle(row)}`)}" aria-label="${esc(`${time(row.t_start)} · ${eventTitle(row)}`)}"></button>`;
  }
  $("noteMarks").innerHTML = total ? doc.rows.map((row) => mark(row)).join("") : "";
  $("suggestionLane").hidden = !suggestions;
  $("suggestionMarks").innerHTML = total && suggestions ? suggestions.events.map((s) => mark(s.row)).join("") : "";
  updateRange();
}
function updateTime() {
  if (!doc) return;
  const t = $("video").currentTime || 0;
  $("clock").innerHTML = `${time(t)} <span>/ ${time(duration())}</span>`;
  $("scrubber").max = duration(); $("scrubber").value = t;
  $("playhead").style.left = `${duration() ? 100 * t / duration() : 0}%`;
  updateRange(); drawObjects();
  const frame = frameAt(t);
  if (suggestionView === "objects" && frame !== lastFrame && !$("reviewPanel").hidden) { lastFrame = frame; renderSuggestions(); }
}

function frameAt(t) {
  const frames = suggestions?.frames;
  if (!frames?.length) return null;
  let low = 0, high = frames.length;
  while (low < high) { const mid = (low + high) >>> 1; if (frames[mid].t < t) low = mid + 1; else high = mid; }
  const a = frames[Math.max(0, low - 1)], b = frames[Math.min(low, frames.length - 1)];
  const nearest = Math.abs(a.t - t) <= Math.abs(b.t - t) ? a : b;
  const gap = frames.length > 1 ? Math.max(.1, frames[1].t - frames[0].t) : .5;
  return Math.abs(nearest.t - t) <= gap * .75 ? nearest : null;
}
function drawObjects() {
  const canvas = $("objectOverlay"), video = $("video");
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(canvas.clientWidth * ratio); canvas.height = Math.round(canvas.clientHeight * ratio);
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (easyMode || !suggestions || !$("showBoxes").checked || !video.videoWidth) return;
  const frame = frameAt(video.currentTime);
  if (!frame) return;
  const scale = Math.min(canvas.width / video.videoWidth, canvas.height / video.videoHeight);
  const w = video.videoWidth * scale, h = video.videoHeight * scale, dx = (canvas.width - w) / 2, dy = (canvas.height - h) / 2;
  ctx.lineWidth = 2 * ratio; ctx.font = `${11 * ratio}px system-ui`;
  for (const object of frame.objects) {
    const review = doc.reviews.find((r) => r.suggestion_id === object.id);
    if (review?.decision === "rejected") continue;
    const [x1, y1, x2, y2] = object.box;
    const color = review ? "#8ce1b2" : "#f0cd7c";
    ctx.strokeStyle = color; ctx.strokeRect(dx + x1 * w, dy + y1 * h, (x2 - x1) * w, (y2 - y1) * h);
    const text = review?.correction || `${label(object.label)}${object.label === "person" ? ` · ${label(object.role)}` : ""}`;
    const top = Math.max(dy, dy + y1 * h - 17 * ratio), width = ctx.measureText(text).width + 8 * ratio;
    ctx.fillStyle = color; ctx.fillRect(dx + x1 * w, top, width, 17 * ratio);
    ctx.fillStyle = "#17211c"; ctx.fillText(text, dx + x1 * w + 4 * ratio, top + 12 * ratio);
  }
}

async function loadSuggestions() {
  if (!current) return;
  const request = ++suggestionRequest, clip = current, run = $("suggestionRun").value;
  suggestions = null; lastFrame = null; renderTimeline(); drawObjects();
  $("suggestionStatus").classList.remove("error"); $("suggestionStatus").textContent = "Loading saved detections…";
  $("refreshSuggestions").disabled = true;
  try {
    const data = await api(`/api/annotation-suggestions/${encodeURIComponent(clip)}?run=${encodeURIComponent(run)}`);
    if (request !== suggestionRequest || clip !== current) return;
    suggestions = data;
    if (!doc.assisted) { doc.assisted = true; changed(); }
    $("clipSubtitle").textContent = `${clips.find((c) => c.key === current).name} · Assisted review`;
    $("overlayControl").hidden = false;
    $("suggestionStatus").textContent = `${data.events.length} event suggestions · ${data.frames.length} sampled frames. Nothing is accepted automatically.`;
    renderTimeline(); renderSuggestions(); drawObjects();
  } catch (error) {
    if (request !== suggestionRequest || clip !== current) return;
    $("suggestionStatus").textContent = error.message;
    $("suggestionStatus").classList.add("error");
    renderSuggestions();
  } finally { if (request === suggestionRequest) $("refreshSuggestions").disabled = false; }
}
function visibleSuggestions() {
  return suggestionView === "events" ? suggestions?.events ?? [] : (frameAt($("video").currentTime)?.objects ?? []);
}
function alreadyAnnotated(suggestion) {
  return doc.rows.some((row) => row.suggestion_id === suggestion.id ||
    ["t_start", "actor", "action", "item"].every((key) => row[key] === suggestion.row[key]));
}
function renderSuggestions() {
  $("suggestionsList").setAttribute("aria-labelledby", suggestionView === "events" ? "eventSuggestionsTab" : "objectSuggestionsTab");
  if (!suggestions) { $("suggestionsList").innerHTML = '<div class="empty-events">Load a detector run to start reviewing.</div>'; return; }
  const kind = suggestionView === "events" ? "event" : "object";
  const frame = frameAt($("video").currentTime);
  $("reviewHint").textContent = kind === "object" ? `Objects sampled at ${frame ? time(frame.t) : "this moment"}. A correct box records an object sighting; add actions separately to your timeline.` : "Accept an event to add it to your timeline. Use Correct to edit its time, description, person, or action.";
  $("suggestionsList").innerHTML = visibleSuggestions().map((s) => {
    const review = doc.reviews.find((r) => r.suggestion_id === s.id);
    const t = kind === "event" ? s.row.t_start : frame.t;
    const title = kind === "event" ? eventTitle(s.row) : `${label(s.label)}${s.label === "person" ? ` · ${label(s.role)}` : ""}`;
    return `<article class="suggestion-card ${review ? "reviewed" : ""}" data-suggestion="${esc(s.id)}" data-kind="${kind}">
      <div class="suggestion-heading"><button class="event-time" data-seek="${t}">${time(t)}</button><strong>${esc(title)}</strong></div>
      ${kind === "object" ? `<p class="suggestion-meta">Detector confidence: ${Math.round(s.score * 100)}% · review this frame</p>` : alreadyAnnotated(s) ? '<p class="suggestion-meta">This event is already on your timeline. Confirming will keep your existing note.</p>' : ""}
      <div class="suggestion-actions">${review ? `<span class="review-decision ${review.decision}">${({ accepted: "✓ Confirmed", corrected: "✓ Corrected", rejected: "Rejected" })[review.decision]}${review.correction ? ` · ${esc(review.correction)}` : ""}</span><button data-review="undo">Undo decision</button>` : '<button class="accept-button" data-review="accepted">✓ Correct</button><button data-review="correct">Correct…</button><button data-review="rejected">Not correct</button>'}</div>
      <div class="object-correction" hidden><label>What is it actually?<input class="correction-input" maxlength="120" placeholder="For example: document, not cash"></label><button data-review="corrected">Save correction</button></div>
      <details class="review-comment" ${review?.comment ? "open" : ""}><summary>${review?.comment ? "Your comment" : "Add a comment / describe a gap"}</summary><textarea class="review-comment-input" rows="2" maxlength="500" aria-label="Comment on suggestion" placeholder="What is wrong, uncertain, or missing? Choose a decision above to save it.">${esc(review?.comment ?? "")}</textarea></details></article>`;
  }).join("") || `<div class="empty-events">${kind === "event" ? "No event suggestions were recorded. You can write the timeline yourself." : "No object boxes were recorded at this moment. Seek to another time, or add a note about what is missing."}</div>`;
}
function recordReview(suggestion, kind, decision, correction = "", comment = "") {
  const old = doc.reviews.find((r) => r.suggestion_id === suggestion.id);
  const review = { suggestion_id: suggestion.id, run: suggestion.run ?? suggestions.run, kind,
    t_start: kind === "event" ? suggestion.row.t_start : frameAt($("video").currentTime).t,
    label: suggestion.label, box: kind === "object" ? suggestion.box : null, decision, correction: correction.slice(0, 120), comment: comment || old?.comment || "" };
  doc.reviews = doc.reviews.filter((r) => r.suggestion_id !== suggestion.id);
  doc.reviews.push(review); doc.assisted = true;
}
async function detectClip() {
  const clip = current, request = ++detectionRequest;
  $("detectClip").disabled = true; $("suggestionStatus").classList.remove("error");
  try {
    const started = await api(`/api/clips/${encodeURIComponent(clip)}/analyze`, { method: "POST" });
    const deadline = Date.now() + 600000;
    while (clip === current && request === detectionRequest && Date.now() < deadline) {
      const state = await api("/api/state");
      if (clip !== current || request !== detectionRequest) return;
      const item = state.items.find((i) => i.id === started.item_id);
      if (item?.status === "failed") throw new Error(item.error || "Detection failed. You can retry.");
      if (item?.status === "done") { $("suggestionRun").value = "live"; await loadSuggestions(); return; }
      $("suggestionStatus").textContent = item?.status === "queued" ? "Queued for the local detector. You can keep writing notes while it runs." : "Detecting objects and events locally… You can keep writing notes.";
      await new Promise((resolve) => setTimeout(resolve, 1800));
    }
    if (clip === current) $("suggestionStatus").textContent = "Detection is still running. Load the live run again when it finishes.";
  } catch (error) { if (clip === current) { $("suggestionStatus").textContent = error.message; $("suggestionStatus").classList.add("error"); } }
  finally { if (clip === current && request === detectionRequest) $("detectClip").disabled = false; }
}

async function compare(clipOnly) {
  if (!await save()) return;
  if (clipOnly && doc.status !== "done") { $("scoreOut").textContent = "Mark this clip done before comparing it."; return; }
  $("scoreOut").textContent = "Comparing timelines…";
  try {
    const data = await api(`/api/annotations-score?run=${encodeURIComponent($("scoreRun").value)}${clipOnly ? `&clip=${encodeURIComponent(current)}` : ""}`);
    const s = data.summary;
    $("scoreOut").innerHTML = `<p>${s.clips} finished timelines compared${s.assisted_clips ? ` · ${s.assisted_clips} used detector suggestions` : ""}. ${data.missing_traces.length ? `${data.missing_traces.length} clips have no saved trace.` : ""} ${data.description_only?.length ? `${data.description_only.length} descriptions without timed events are excluded.` : ""} Events match within 2 seconds.</p><table><thead><tr><th>Event</th><th>Your notes</th><th>Found</th><th>Extra detections</th></tr></thead><tbody>${Object.entries(s.per_action).map(([action, v]) => `<tr><td>${esc(label(action))}</td><td>${v.truth}</td><td>${v.detectable ? `${v.found}/${v.truth}` : "Not detected by this system"}</td><td>${v.detectable ? v.extra : "—"}</td></tr>`).join("")}</tbody></table>`;
  } catch (error) { $("scoreOut").textContent = `Could not compare: ${error.message}`; }
}

$("clips").addEventListener("click", (event) => { const button = event.target.closest("[data-clip]"); if (button) openClip(button.dataset.clip); });
for (const id of ["clipSearch", "unfinishedOnly"]) $(id).addEventListener("input", renderClips);
$("previousClip").addEventListener("click", () => openClip(clips[clips.findIndex((c) => c.key === current) - 1]?.key));
$("nextClip").addEventListener("click", () => openClip(clips[clips.findIndex((c) => c.key === current) + 1]?.key));
$("saveNow").addEventListener("click", saveNow);
$("easyMode").addEventListener("click", () => setEasyMode(true));
$("detailedMode").addEventListener("click", () => setEasyMode(false));
$("commentNow").addEventListener("click", () => { switchPanel("notes"); prepareComment({ atCurrentTime: true }); $("note").focus(); });
$("note").addEventListener("focus", prepareComment);
$("finishNextClip").addEventListener("click", finishAndNext);
$("downloadNotes").addEventListener("click", () => {
  const draft = composerDirty ? { unfinished_note: { ...range(), note: $("note").value, actor: $("actor").value, action: $("action").value, item: $("item").value } } : {};
  const a = document.createElement("a"), url = URL.createObjectURL(new Blob([JSON.stringify({ ...doc, ...payload(), ...draft }, null, 2)], { type: "application/json" }));
  a.href = url; a.download = `${current}-notes.json`; a.click(); URL.revokeObjectURL(url);
});
$("noteForm").addEventListener("submit", addNote);
$("noteForm").addEventListener("input", composerChanged);
$("noteForm").addEventListener("change", composerChanged);
$("cancelEdit").addEventListener("click", () => { resetComposer(); selection = null; updateRange(); });
document.querySelectorAll("[data-preset]").forEach((button) => button.addEventListener("click", () => {
  const action = button.dataset.preset;
  $("action").value = action; composerChanged();
  if (action === "enter") $("actor").value = "client";
  if (action === "leave_desk" || action === "count_machine") $("actor").value = "cashier";
  if (action === "hand_over") { $("item").value = "cash"; $("place").value = "hand"; }
  if (action === "other") { $("uncertain").checked = true; $("note").focus(); }
}));
$("rows").addEventListener("click", (event) => {
  const edit = event.target.closest("[data-edit]"), remove = event.target.closest("[data-delete]");
  if (edit && canLeaveComposer()) { editingRow = doc.rows[Number(edit.dataset.edit)]; populateComposer(editingRow, "Edit this event"); }
  if (remove) {
    const row = doc.rows[Number(remove.dataset.delete)];
    const review = doc.reviews.find((r) => r.suggestion_id === row.suggestion_id);
    undo = { row, review };
    doc.rows.splice(Number(remove.dataset.delete), 1);
    doc.reviews = doc.reviews.filter((r) => r !== review);
    if (editingRow === row) resetComposer();
    $("undoNotice").hidden = false;
    renderRows(); changed();
  }
});
$("undoDelete").addEventListener("click", () => {
  if (!undo) return;
  doc.rows.push(undo.row); doc.rows.sort((a, b) => a.t_start - b.t_start);
  if (undo.review) doc.reviews.push(undo.review);
  undo = null; $("undoNotice").hidden = true; renderRows(); changed();
});
$("workspace").addEventListener("click", (event) => { const button = event.target.closest("[data-seek]"); if (button) seek(Number(button.dataset.seek)); });
for (const id of ["layout", "people"]) $(id).addEventListener("input", () => {
  if (!doc || !$(id).checkValidity()) return;
  doc.layout = $("layout").value; doc.people_max = Number($("people").value) || 0;
  changed();
});
$("summary").addEventListener("input", updateDescription);
$("refreshDescription").addEventListener("click", loadDescription);
$("saveDescription").addEventListener("click", saveNow);
$("annotator").addEventListener("input", () => { try { localStorage.setItem("annotate.name", $("annotator").value); } catch {} if (doc) changed(); });
$("finishClip").addEventListener("click", async () => {
  if (!canLeaveComposer()) return;
  doc.status = doc.status === "done" ? "draft" : "done"; changed(); await save();
});
$("notesTab").addEventListener("click", () => switchPanel("notes"));
$("reviewTab").addEventListener("click", () => { switchPanel("review"); if (!suggestions) loadSuggestions(); });
$("refreshSuggestions").addEventListener("click", loadSuggestions);
$("suggestionRun").addEventListener("change", loadSuggestions);
$("detectClip").addEventListener("click", detectClip);
$("addGap").addEventListener("click", () => { switchPanel("notes"); if (!composerDirty) { resetComposer(); $("uncertain").checked = true; } $("note").focus(); });
for (const [id, view] of [["eventSuggestionsTab", "events"], ["objectSuggestionsTab", "objects"]]) $(id).addEventListener("click", () => {
  suggestionView = view;
  $("eventSuggestionsTab").setAttribute("aria-selected", String(view === "events"));
  $("objectSuggestionsTab").setAttribute("aria-selected", String(view === "objects"));
  if (view === "objects") $("video").pause();
  renderSuggestions();
});
$("suggestionsList").addEventListener("focusin", () => $("video").pause());
$("suggestionsList").addEventListener("input", (event) => {
  if (!event.target.matches(".review-comment-input")) return;
  const card = event.target.closest("[data-suggestion]");
  const review = doc.reviews.find((r) => r.suggestion_id === card.dataset.suggestion);
  if (review) { review.comment = event.target.value; changed(); }
});
$("suggestionsList").addEventListener("click", (event) => {
  const button = event.target.closest("[data-review]"); if (!button) return;
  const card = button.closest("[data-suggestion]"), kind = card.dataset.kind;
  const suggestion = visibleSuggestions().find((s) => s.id === card.dataset.suggestion);
  if (!suggestion) return;
  const decision = button.dataset.review, comment = card.querySelector(".review-comment-input").value;
  if (decision === "undo") {
    doc.reviews = doc.reviews.filter((r) => r.suggestion_id !== suggestion.id);
    doc.rows = doc.rows.filter((r) => r.suggestion_id !== suggestion.id);
  } else if (decision === "correct") {
    if (kind === "object") { card.querySelector(".object-correction").hidden = false; card.querySelector(".correction-input").focus(); return; }
    if (!canLeaveComposer()) { switchPanel("notes"); return; }
    correcting = { ...suggestion, run: suggestions.run, comment };
    populateComposer(suggestion.row, "Correct the detector’s event");
    message("editingNotice", "Check the time and fields, then describe what actually happened. Save to add your corrected event.");
    return;
  } else {
    const correction = decision === "corrected" ? card.querySelector(".correction-input").value.trim() : "";
    if (decision === "corrected" && !correction) { card.querySelector(".correction-input").focus(); return; }
    recordReview(suggestion, kind, decision, correction, comment);
    if (kind === "event" && decision === "accepted" && !alreadyAnnotated(suggestion)) { doc.rows.push({ ...suggestion.row }); doc.rows.sort((a, b) => a.t_start - b.t_start); }
  }
  renderSuggestions(); renderRows(); drawObjects(); changed();
});
$("showBoxes").addEventListener("change", drawObjects);
$("scoreAll").addEventListener("click", () => compare(false));
$("scoreClip").addEventListener("click", () => compare(true));
$("playPause").addEventListener("click", () => { const video = $("video"); if (video.paused) video.play().catch((error) => message("videoError", error.message)); else video.pause(); });
$("backSecond").addEventListener("click", () => seek($("video").currentTime - 1));
$("forwardSecond").addEventListener("click", () => seek($("video").currentTime + 1));
$("playbackSpeed").addEventListener("change", () => { $("video").playbackRate = Number($("playbackSpeed").value); });
$("scrubber").addEventListener("input", () => seek(Number($("scrubber").value)));
$("video").addEventListener("timeupdate", updateTime);
$("video").addEventListener("seeked", updateTime);
$("video").addEventListener("loadedmetadata", () => { renderTimeline(); updateTime(); });
$("video").addEventListener("play", () => { $("playPause").textContent = "Pause"; $("playPause").setAttribute("aria-label", "Pause video"); });
$("video").addEventListener("pause", () => { $("playPause").textContent = "Play"; $("playPause").setAttribute("aria-label", "Play video"); });
$("video").addEventListener("error", () => message("videoError", "This browser could not play the video. Try reloading, or use another browser. Your notes are still available."));
window.addEventListener("resize", drawObjects);
for (const id of ["rangeStart", "rangeEnd"]) $(id).addEventListener("input", () => {
  selection = { start: $("rangeStart").valueAsNumber, end: $("rangeEnd").value === "" ? null : $("rangeEnd").valueAsNumber };
  updateRange();
});
$("startHere").addEventListener("click", () => { selection = { start: round($("video").currentTime), end: null }; message("rangeError"); updateRange(); });
$("endHere").addEventListener("click", () => {
  const start = range().start, end = round($("video").currentTime);
  if (end < start) { message("rangeError", "Move past the start before setting the end."); return; }
  selection = { start, end }; message("rangeError"); updateRange();
});
$("clearRange").addEventListener("click", () => { selection = null; message("rangeError"); updateRange(); });
let drag = null;
$("timeline").addEventListener("pointerdown", (event) => {
  if (event.target.closest("button") || !duration()) return;
  const bounds = $("timeline").getBoundingClientRect();
  drag = { x: event.clientX, t: Math.max(0, Math.min(duration(), (event.clientX - bounds.left) / bounds.width * duration())) };
  $("timeline").setPointerCapture(event.pointerId);
});
$("timeline").addEventListener("pointermove", (event) => {
  if (!drag) return;
  const bounds = $("timeline").getBoundingClientRect(), t = Math.max(0, Math.min(duration(), (event.clientX - bounds.left) / bounds.width * duration()));
  selection = { start: round(Math.min(drag.t, t)), end: round(Math.max(drag.t, t)) }; updateRange();
});
$("timeline").addEventListener("pointerup", (event) => {
  if (!drag) return;
  if (Math.abs(event.clientX - drag.x) < 4) { selection = null; seek(drag.t); }
  else { $("video").pause(); seek(selection.start); }
  drag = null;
});
$("timeline").addEventListener("pointercancel", () => { drag = null; });
document.addEventListener("keydown", (event) => {
  if (!doc) return;
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); if (easyMode) finishAndNext(); else if (!$("notesPanel").hidden) addNote(); return; }
  if (easyMode && !event.target.closest("input, textarea, select") && event.key.toLowerCase() === "n") { event.preventDefault(); $("video").pause(); $("summary").focus(); return; }
  if (easyMode && ["i", "o"].includes(event.key.toLowerCase())) return;
  if (!event.target.closest("input, textarea, select") && !event.ctrlKey && !event.metaKey && !event.altKey && ["n", "i", "o"].includes(event.key.toLowerCase())) {
    event.preventDefault();
    if (event.key.toLowerCase() === "n") { switchPanel("notes"); prepareComment({ atCurrentTime: true }); $("note").focus(); }
    else $(event.key.toLowerCase() === "i" ? "startHere" : "endHere").click();
    return;
  }
  if (event.target.closest("input, textarea, select, button, video, summary, a") || event.ctrlKey || event.metaKey || event.altKey) return;
  const steps = { ArrowLeft: -.5, ArrowRight: .5, ",": -.1, ".": .1 };
  if (event.key in steps) { event.preventDefault(); seek($("video").currentTime + steps[event.key]); }
  else if (event.key === " ") { event.preventDefault(); $("playPause").click(); }
});
document.querySelectorAll('[role="tablist"]').forEach((group) => group.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  const tabs = [...group.querySelectorAll('[role="tab"]')], index = tabs.indexOf(document.activeElement);
  if (index < 0) return;
  event.preventDefault();
  const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
  tabs[next].focus(); tabs[next].click();
}));
window.addEventListener("beforeunload", (event) => { if (composerDirty || inFlight || revision !== savedRevision) { event.preventDefault(); event.returnValue = ""; } });
try { $("annotator").value = localStorage.getItem("annotate.name") ?? ""; } catch {}
async function initialize() {
  $("retryLoad").hidden = true;
  try {
    const results = await Promise.all([api("/api/annotation-vocabulary"), api("/api/clips"), api("/api/runs")]);
    [vocab] = results; clips = results[1].clips;
    for (const id of ["actor", "action", "item", "place", "layout"]) fillOptions(id, vocab[id]);
    for (const id of ["scoreRun", "suggestionRun"]) $(id).innerHTML = results[2].runs.map((run) => `<option value="${esc(run)}">${esc(run === "live" ? "Live / latest results" : run)}</option>`).join("");
    renderClips();
    if (!clips.length) { $("emptyMessage").textContent = "No clips are available. Set VIDEO_DIR on the realtime gateway to your video folder."; return; }
    const requested = new URLSearchParams(location.search).get("clip");
    await openClip(clips.find((c) => c.key === requested)?.key ?? clips.find((c) => c.status !== "done")?.key ?? clips[0].key);
  } catch (error) { $("emptyMessage").textContent = `Could not load the workspace: ${error.message}`; $("retryLoad").hidden = false; }
}
$("retryLoad").addEventListener("click", initialize);
setEasyMode(easyMode);
initialize();
