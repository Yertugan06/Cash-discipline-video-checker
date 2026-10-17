"""Stage 3+4: probe plan at anchors (which VLM question groups at which times) and the rule set.

The plan depends only on detector anchors, never on VLM answers, so all probes run in one concurrent batch.
Rules combine anchor structure (who arrived/left, when) with the VLM state answers at the planned probes.
Each rule maps to one codex ID; the citation text comes from codex_verified.json, never from the VLM.
"""
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from . import vlm

PERIODIC_SEC = 6.0
LEAVE_MIN_AWAY = 2.0      # cashier must stay away from the workplace at least this long
COLLECTOR_MAX_VISIT = 10.0


def _idx(det, t):
    return max(0, min(len(det["samples"]) - 1, round(t * det["sample_fps"])))


def structure(anchors, det):
    """Derive semantic events from raw anchors."""
    dur = det["duration"]
    sz = [a for a in anchors if a["kind"].startswith("staff_zone_")]
    leaves = []
    for a in sz:
        if a["kind"] == "staff_zone_down" and a["after"] == 0:
            back = next((b["t"] for b in sz if b["t"] > a["t"] and b["kind"] == "staff_zone_up"), dur)
            if back - a["t"] >= LEAVE_MIN_AWAY:
                leaves.append({"t": a["t"], "back": back})
    arrivals_cashier = [a for a in sz if a["kind"] == "staff_zone_up" and a["before"] == 0 and a["t"] > 0.5]
    safe_downs = [a for a in anchors if a["kind"] == "at_safe_down"]
    enters = [a for a in anchors if a["kind"] == "room_up" and a["t"] > 0.5]
    oth = [a for a in anchors if a["kind"].startswith("others_")]
    arrivals = [a for a in oth if a["kind"] == "others_up"]
    departs = [a for a in oth if a["kind"] == "others_down"]
    periodic = [a for a in anchors if a["kind"] == "periodic"]
    return {"leaves": leaves, "cashier_arrivals": arrivals_cashier, "safe_downs": safe_downs,
            "enters": enters, "arrivals": arrivals, "departs": departs, "periodic": periodic, "duration": dur}


def plan(st, det):
    """Returns list of (time_sec, group, tag)."""
    dur = det["duration"]
    P = []

    def add(t, g, tag):
        if 0 <= t <= dur:
            P.append((round(t, 2), g, tag))

    for lv in st["leaves"]:
        for dt in (2.0, 4.0):
            t = min(lv["t"] + dt, lv["back"] - 0.4)
            for g in ("desk", "laptop", "safe"):
                add(t, g, f"leave@{lv['t']}+{dt}")
    for a in st["safe_downs"]:
        for dt in (2.0, 4.0):
            add(a["t"] + dt, "safe", f"safe_down@{a['t']}+{dt}")
    for a in st["enters"]:
        for dt in (3.0, 5.0):
            add(a["t"] + dt, "door", f"enter@{a['t']}+{dt}")
        add(a["t"] + 2.0, "people", f"enter@{a['t']}+2")
    for a in st["arrivals"]:
        add(a["t"] + 1.0, "desk", f"arrive@{a['t']}+1")
        add(a["t"] + 2.0, "people", f"arrive@{a['t']}+2")
    for a in st["departs"]:
        for dt in (-3.0, 1.0, 4.0):
            add(a["t"] + dt, "desk", f"depart@{a['t']}{dt:+}")
    for a in st["cashier_arrivals"]:
        for dt in (3.0, 6.0):
            add(a["t"] + dt, "desk", f"carrive@{a['t']}+{dt}")
    for a in st["periodic"]:
        add(a["t"], "people", "periodic")
        add(a["t"], "desk", "periodic")
    return P


def run_probes(P, det, frames_dir, workers=6):
    regions = det["_geo"]["regions"]
    jobs = sorted({(_idx(det, t), g) for t, g, _ in P})

    def one(job):
        i, g = job
        with Image.open(f"{frames_dir}/{i:05d}.jpg") as im:
            fr = im.convert("RGB")
        ans, lat, err, used = vlm.ask(g, fr, regions, mode="full" if g == "people" else "crop")
        return job, {"ans": ans, "lat": lat, "err": err, "mode": used}

    out = {}
    with ThreadPoolExecutor(workers) as ex:
        for job, r in ex.map(one, jobs):
            out[job] = r
    return out


def _get(answers, det, t, g, field):
    r = answers.get((_idx(det, t), g))
    if not r or r["ans"] is None:
        return None
    return r["ans"].get(field)


# rule id -> (codex id, short Russian description template)
RULES = {
    "LEAVE_CASH": ("231-20-2", "Кассир покинул рабочее место, на столе остались наличные деньги"),
    "LEAVE_BAG": ("231-20-2", "Кассир покинул рабочее место, на столе осталась инкассаторская сумка"),
    "LEAVE_DOCS": ("231-80-3", "Кассир покинул рабочее место, на столе остались документы/планшет"),
    "LEAVE_LAPTOP": ("53-71-9", "Кассир покинул рабочее место, экран ноутбука не заблокирован"),
    "LEAVE_SAFE_OPEN": ("231-20-2b", "Кассир покинул рабочее место, сейф оставлен открытым"),
    "LEAVE_KEY": ("231-80-1", "Кассир покинул рабочее место, ключ оставлен в замке сейфа"),
    "SAFE_LEFT_OPEN": ("231-20-2b", "Кассир отошёл от сейфа, дверца сейфа осталась открытой"),
    "DOOR_OPEN": ("14-16-1", "После входа дверь кассы осталась открытой"),
    "OUTSIDER": ("14-8-1", "На стороне кассира находится посторонний человек"),
    "PREV_CASH_NEXT_CLIENT": ("231-20-2", "Следующий клиент подошёл, а на столе лежат наличные предыдущего клиента"),
    "SECOND_CLIENT": ("231-21", "Второй посетитель обслуживается одновременно с текущим клиентом"),
    "COUNT_AFTER_EXIT": ("231-20-1", "Клиент ушёл до пересчёта; пересчёт начат в его отсутствие"),
    "COLLECTOR_BRIEF": ("231-24-3", "Инкассатор передал сумку и сразу ушёл, совместной проверки не было"),
    "PERSONAL_ITEMS": ("231-12-1", "Личные вещи кассира на кассовом столе"),
    "FOOD": ("231-12-2", "Кассир ест или пьёт за кассовым столом"),
    "PHONE": ("231-12-2b", "Кассир держит мобильный телефон на рабочем месте"),
}


def apply_rules(st, det, A, enabled=None):
    """Returns list of {rule, codex, t, conf, probe_t}. A = answers dict."""
    ev = []
    on = (lambda r: True) if enabled is None else (lambda r: r in enabled)

    def fire(rule, t, conf, probe_t):
        if on(rule):
            ev.append({"rule": rule, "codex": RULES[rule][0], "t": round(max(0.0, t), 2), "conf": conf,
                       "probe_t": round(probe_t, 2)})

    for lv in st["leaves"]:
        ts = [min(lv["t"] + dt, lv["back"] - 0.4) for dt in (2.0, 4.0)]
        both = lambda g, f, v: all(_get(A, det, t, g, f) == v for t in ts)  # noqa: E731
        tl = lv["t"] - 0.5
        if both("desk", "desk_cash", True):
            fire("LEAVE_CASH", tl, 0.8, ts[0])
        if both("desk", "desk_bag", True):
            fire("LEAVE_BAG", tl, 0.8, ts[0])
        if both("desk", "desk_documents", True):
            fire("LEAVE_DOCS", tl, 0.5, ts[0])
        if both("laptop", "laptop_screen", "unlocked"):
            fire("LEAVE_LAPTOP", tl, 0.7, ts[0])
        if both("safe", "safe_door", "open"):
            fire("LEAVE_SAFE_OPEN", tl, 0.7, ts[0])
        if both("safe", "key_in_safe_lock", "yes"):
            fire("LEAVE_KEY", tl, 0.5, ts[0])
    for a in st["safe_downs"]:
        ts = [a["t"] + 2.0, a["t"] + 4.0]
        if all(_get(A, det, t, "safe", "safe_door") == "open" for t in ts):
            fire("SAFE_LEFT_OPEN", a["t"], 0.7, ts[0])
    for a in st["enters"]:
        ts = [a["t"] + 3.0, a["t"] + 5.0]
        if all(_get(A, det, t, "door", "room_door") == "open" for t in ts):
            fire("DOOR_OPEN", a["t"] + 0.5, 0.6, ts[0])
        n = _get(A, det, a["t"] + 2.0, "people", "people_cashier_side")
        if isinstance(n, int) and n >= 2:
            fire("OUTSIDER", a["t"] + 1.0, 0.5, a["t"] + 2.0)
    for a in st["arrivals"]:
        earlier_depart = any(d["t"] < a["t"] for d in st["departs"])
        if earlier_depart and _get(A, det, a["t"] + 1.0, "desk", "desk_cash") is True:
            fire("PREV_CASH_NEXT_CLIENT", a["t"], 0.7, a["t"] + 1.0)
        n = _get(A, det, a["t"] + 2.0, "people", "clients_at_desk")
        if isinstance(n, int) and n >= 2:
            fire("SECOND_CLIENT", a["t"], 0.5, a["t"] + 2.0)
        if _get(A, det, a["t"] + 2.0, "people", "collector_present") is True:
            dep = next((d["t"] for d in st["departs"] if d["t"] > a["t"]), None)
            if dep is not None and dep - a["t"] <= COLLECTOR_MAX_VISIT:
                fire("COLLECTOR_BRIEF", (a["t"] + dep) / 2, 0.6, a["t"] + 2.0)
    for d in st["departs"]:
        before = _get(A, det, d["t"] - 3.0, "desk", "counting_machine_in_use")
        after = [_get(A, det, d["t"] + dt, "desk", "counting_machine_in_use") for dt in (1.0, 4.0)]
        if before is False and any(x is True for x in after):
            fire("COUNT_AFTER_EXIT", d["t"], 0.6, d["t"] + 1.0)
    for a in st["cashier_arrivals"]:
        ts = [a["t"] + 3.0, a["t"] + 6.0]
        if all(_get(A, det, t, "desk", "desk_personal_items") is True for t in ts):
            fire("PERSONAL_ITEMS", a["t"], 0.6, ts[0])
    per = st["periodic"]
    for p, q in zip(per, per[1:]):
        if all(_get(A, det, x["t"], "people", "cashier_eating_drinking") is True for x in (p, q)):
            fire("FOOD", p["t"], 0.4, p["t"])
        if all(_get(A, det, x["t"], "people", "phone_in_cashier_hand") is True for x in (p, q)):
            fire("PHONE", p["t"], 0.4, p["t"])
    # one event per (rule, ~time); sort by confidence then time
    seen, out = set(), []
    for e in sorted(ev, key=lambda e: (-e["conf"], e["t"])):
        key = (e["rule"], round(e["t"] / 3))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out
