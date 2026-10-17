"""Stage 3: targeted state questions to the LOCAL vLLM (OpenAI-compatible), on upscaled crops.

The VLM is only a perceiver of named states; it never decides whether something is a violation.
Each question group has its own small JSON schema and is answered from the crop of one scene region
(desk / safe / laptop / door), optionally with a reference crop of the same region from earlier.
"""
import base64
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.request

from PIL import Image

BASE_URL = os.environ.get("AGENTB_VLM_URL", "http://127.0.0.1:8010/v1")
MODEL = os.environ.get("AGENTB_VLM_MODEL", "Qwen/Qwen3.5-9B")
TARGET_SIDE = 768  # vLLM server caps images at max_pixels=589824 (768x768)

SYSTEM = (
    "You are a careful visual inspector of a bank cash room filmed by an overhead security camera. "
    "You only report what is directly visible. You never guess, never identify people, and never judge legality. "
    "If something is hidden, out of frame, or too small to see, choose not_visible / unclear (or false for yes/no fields). "
    "Answer ONLY with a JSON object that matches the requested schema."
)

B = {"type": "boolean"}

GROUPS = {
    "desk": {
        "region": "desk",
        "fields": {
            "desk_cash": B, "desk_bag": B, "desk_documents": B, "desk_personal_items": B,
            "desk_food_drink": B, "id_document_visible": B, "counting_machine_in_use": B,
            "detector_in_use": B,
        },
        "text": (
            "- desk_cash: scan the WHOLE desk surface. true if ANY banknotes lie on the desk, even one small pack or a few notes "
            "(tenge banknotes are small blue, green, beige or pink paper rectangles). Notes inside the counting machine or held in a hand do not count.\n"
            "- desk_bag: a cash collection bag (often green fabric, sometimes a sealed bag) lies on the desk.\n"
            "- desk_documents: papers, folders, a tablet or a notebook with documents lie on the desk.\n"
            "- desk_personal_items: personal items on the desk or chair: coat/jacket, handbag, backpack, wallet.\n"
            "- desk_food_drink: food, a cup, a bottle or a snack is on the desk or in someone's hand at the desk.\n"
            "- id_document_visible: an ID card or passport is visible in someone's hand or on the desk.\n"
            "- counting_machine_in_use: banknotes are being fed into / taken out of the banknote counting machine, or lie in its tray.\n"
            "- detector_in_use: banknotes are placed on or held at the small banknote detector (UV/magnifier device)."
        ),
    },
    "safe": {
        "region": "safe",
        "fields": {
            "safe_door": {"type": "string", "enum": ["open", "closed", "not_visible"]},
            "key_in_safe_lock": {"type": "string", "enum": ["yes", "no", "not_visible"]},
        },
        "text": (
            "- safe_door: is the door of the grey metal safe/cabinet open (door leaf swung away, interior/shelves visible) or closed (front flat and shut)?\n"
            "- key_in_safe_lock: look at the lock/keyhole on the front of the safe door: is a key sticking out of it "
            "(often a key on a ring with a small keychain hanging down)? yes only if you actually see a key in the lock; "
            "no if the lock area is visible and empty; not_visible only if the safe front is hidden."
        ),
    },
    "laptop": {
        "region": "laptop",
        "fields": {"laptop_screen": {"type": "string", "enum": ["unlocked", "lock_screen", "off_or_closed", "not_visible"]}},
        "text": (
            "- laptop_screen: unlocked = an application is visible on the screen: a spreadsheet/table (white with rows and columns), "
            "a document, a browser, or a bright white working window; lock_screen = a full-screen PHOTO or landscape picture "
            "(mountains, sky, sea, dark blue picture), possibly with a clock, and NO application windows (Windows lock screen); "
            "off_or_closed = black/dark screen or the lid is closed."
        ),
    },
    "door": {
        "region": "door",
        "fields": {
            "room_door": {"type": "string", "enum": ["open", "closed", "not_visible"]},
            "person_at_door": B,
        },
        "text": (
            "- room_door: the room's glass door is open if its leaf is swung away from the frame (you see the leaf at an angle, "
            "or a gap/dark opening next to the frame), or if someone is passing through it; closed if the leaf is flush with the frame.\n"
            "- person_at_door: someone is entering or leaving through the door right now."
        ),
    },
    "people": {
        "region": None,
        "fields": {
            "cashier_at_desk": B, "cashier_in_room": B,
            "people_cashier_side": {"type": "integer", "minimum": 0, "maximum": 5},
            "clients_at_desk": {"type": "integer", "minimum": 0, "maximum": 5},
            "collector_present": B, "phone_in_cashier_hand": B,
            "cash_in_hands_of": {"type": "string", "enum": ["nobody", "cashier", "client", "collector", "several"]},
            "cashier_eating_drinking": B,
        },
        "text": (
            "- cashier_at_desk: the cashier (bank employee working with cash) is at the cashier's workplace, sitting or standing at the desk on the cashier side.\n"
            "- cashier_in_room: the cashier is anywhere inside the room (e.g. at the safe), even if not at the desk.\n"
            "- people_cashier_side: count EVERY person who is not on the client side of the desk: the cashier PLUS anyone standing behind or next to the cashier, "
            "near the safe, or just inside the door. Clients at the client side of the desk are NOT counted.\n"
            "- clients_at_desk: count EVERY person on the client side of the desk, seated OR standing, including someone who just walked up "
            "and hands something to the cashier. 0 if nobody is there.\n"
            "- collector_present: a cash collector is in the room (usually carries/handles a green collection bag, wears a dark jacket).\n"
            "- phone_in_cashier_hand: the cashier holds a mobile phone.\n"
            "- cash_in_hands_of: who holds banknotes right now.\n"
            "- cashier_eating_drinking: the cashier is eating or drinking (food or a cup at the mouth) right now."
        ),
    },
}

PAD = {"desk": 0.15, "safe": 0.25, "laptop": 0.35, "door": 0.15}


def schema_for(group):
    f = GROUPS[group]["fields"]
    return {"type": "object", "additionalProperties": False, "required": list(f), "properties": f}


def crop_region(img, box, pad):
    W, H = img.size
    x1, y1, x2, y2 = box
    px, py = (x2 - x1) * pad, (y2 - y1) * pad
    l, t = max(0, int((x1 - px) * W)), max(0, int((y1 - py) * H))
    r, b = min(W, int((x2 + px) * W) + 1), min(H, int((y2 + py) * H) + 1)
    c = img.crop((l, t, max(r, l + 8), max(b, t + 8)))
    k = TARGET_SIDE / max(c.size)
    if k > 1:
        c = c.resize((round(c.width * k), round(c.height * k)), Image.LANCZOS)
    return c


def _fit(img):
    k = (589824 / (img.width * img.height)) ** 0.5
    if k > 1.0:
        k = min(k, 1.6)
        img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
    return img


def _data_url(img):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build_prompt(group, mode, t=None):
    head = {
        "full": "The image is one full frame from an overhead camera in a small bank cash room.",
        "crop": "The image is an enlarged crop of one area ({region}) of an overhead camera frame in a small bank cash room.",
        "crop_ref": ("Image 1 is an enlarged crop of one area ({region}) of an overhead camera frame in a small bank cash room, "
                     "taken EARLIER in the same video (reference). Image 2 is the SAME area NOW. "
                     "Use image 1 only to understand what the area normally looks like; answer every field about image 2 (NOW)."),
    }[mode].format(region=GROUPS[group]["region"] or "room")
    return head + "\nFill every field:\n" + GROUPS[group]["text"]


_CACHE_DIR = None


def set_cache(path):
    global _CACHE_DIR
    _CACHE_DIR = path
    os.makedirs(path, exist_ok=True)


def chat(images, text, schema, max_tokens=300, timeout=120):
    content = [{"type": "image_url", "image_url": {"url": _data_url(im)}} for im in images]
    content.append({"type": "text", "text": text})
    body = {"model": MODEL, "temperature": 0.0, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "out", "schema": schema, "strict": True}}}
    raw_body = json.dumps(body).encode()
    key = hashlib.sha256(raw_body).hexdigest()
    if _CACHE_DIR:
        p = os.path.join(_CACHE_DIR, key + ".json")
        if os.path.exists(p):
            with open(p) as f:
                c = json.load(f)
            return c["ans"], 0.0, c["err"]
    req = urllib.request.Request(BASE_URL.rstrip("/") + "/chat/completions", data=raw_body,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer EMPTY"})
    t0 = time.time()
    err = None
    ans = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.load(r)
        txt = resp["choices"][0]["message"].get("content") or ""
        txt = re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip()
        ans = json.loads(txt)
    except urllib.error.HTTPError as e:
        err = f"HTTP {e.code}"
    except Exception as e:  # reported to caller, never swallowed silently
        err = f"{type(e).__name__}"
    lat = time.time() - t0
    if _CACHE_DIR and err is None:
        with open(os.path.join(_CACHE_DIR, key + ".json"), "w") as f:
            json.dump({"ans": ans, "err": err}, f)
    return ans, lat, err


def ask(group, frame, scene, mode="crop", ref_frame=None):
    """frame/ref_frame: PIL images. scene: dict label -> {box}. Returns (answers|None, latency, error, mode_used)."""
    region = GROUPS[group]["region"]
    if region is None or mode == "full" or region not in scene:
        used = "full"
        imgs = [_fit(frame)]
    elif mode == "crop_ref" and ref_frame is not None:
        used = "crop_ref"
        box = scene[region]["box"]
        imgs = [crop_region(ref_frame, box, PAD[region]), crop_region(frame, box, PAD[region])]
    else:
        used = "crop"
        imgs = [crop_region(frame, scene[region]["box"], PAD[region])]
    ans, lat, err = chat(imgs, build_prompt(group, used), schema_for(group))
    return ans, lat, err, used
