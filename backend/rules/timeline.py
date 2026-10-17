"""Temporal rules: ``StateTimeline`` -> ``list[Finding]``.

A typed, pure port of the kit's
``archive/vm-copies/datathon/forte_brev_kit/brev_kit/scripts/timeline_rules.py`` (``detect()``).
No I/O, no randomness, no label access. Every legal/business threshold is read
from the matching ``RuleEntry.params`` in ``knowledge/rules.yaml`` -- nothing here is a hardcoded
legal threshold.

Two implementation details stay as module constants rather than ``RuleEntry.params``, because they
are not legal thresholds but shared *signal-processing* parameters of the kit's pipeline, applied
identically to every rule (the kit keeps them in one global ``P`` dict for the same reason):

- ``SMOOTH_K``: the majority-smoothing half-window (kit default ``smooth_k=1``);
- ``DEDUPE_S``: the time window used to collapse repeated firings of the same rule (kit default
  ``dedupe_s=10.0``).

Both match the kit's defaults exactly, which is what the equivalence test
(``tests/test_rules_equivalence.py``) exercises. See ``knowledge/README.md`` for more detail on
this and the handful of other kit parameters that are *shared* across several canonical rules
(the kit computes one "cashier away" run and one "client session" run per timeline and derives
several rule findings from each). For those shared runs, one rule in each group is the designated
owner of the shared threshold:

- the away-run (``L-NO-CASH-ON-LEAVE``, ``L-SAFE-LOCKED-ON-LEAVE``, ``L-PC-LOCKED``,
  ``L-NO-DOCS-ON-LEAVE``) reads ``min_away_s``/``min_samples`` from ``L-NO-CASH-ON-LEAVE``;
- the post-exit check window (``L-SAFE-LOCKED-ON-LEAVE``, ``L-NO-DOCS-ON-LEAVE``) reads
  ``exit_window_s`` from ``L-SAFE-LOCKED-ON-LEAVE``;
- the client-session run (``S-CLEAN-DESK-HANDOVER``, ``S-NO-MERGE``, ``C-ID-BEFORE-CASH``,
  ``C-COUNT-BEFORE-EXIT``) reads ``session_gap_s``/``min_samples``/``entry_lookback_s`` from
  ``S-CLEAN-DESK-HANDOVER``.

Frames with ``ok=False`` (or a missing ``state``) are dropped before smoothing, exactly like the
kit's loader (``if r.get('ok') and isinstance(r.get('state'), dict)``): they are *unknown*, never
treated as a negative observation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable

from backend.contracts import Finding, FrameState, RuleEntry, StateTimeline

# Canonical rule ids this module knows how to compute. Kept as named constants (rather than a
# kit-name -> canonical-id lookup table) because the "mapping" is the one-time renaming done while
# porting the kit's logic: the canonical id *is* the detection branch below. The authoritative
# record of what each id means lives in knowledge/rules.yaml, not in a second table here.
L_NO_CASH_ON_LEAVE = "L-NO-CASH-ON-LEAVE"
L_SAFE_LOCKED_ON_LEAVE = "L-SAFE-LOCKED-ON-LEAVE"
L_PC_LOCKED = "L-PC-LOCKED"
L_NO_DOCS_ON_LEAVE = "L-NO-DOCS-ON-LEAVE"
S_SAFE_CLOSED = "S-SAFE-CLOSED"
S_CLEAN_DESK_HANDOVER = "S-CLEAN-DESK-HANDOVER"
S_NO_MERGE = "S-NO-MERGE"
A_OUTSIDER_ZONE = "A-OUTSIDER-ZONE"
A_DOOR_LOCK = "A-DOOR-LOCK"
A_SECOND_PERSON = "A-SECOND-PERSON"
C_COUNT_BEFORE_EXIT = "C-COUNT-BEFORE-EXIT"
C_ID_BEFORE_CASH = "C-ID-BEFORE-CASH"
C_DETECTOR_CHECK = "C-DETECTOR-CHECK"
W_NO_PERSONAL_ITEMS = "W-NO-PERSONAL-ITEMS"
W_NO_FOOD = "W-NO-FOOD"
W_NO_CAMERA_PHONE = "W-NO-CAMERA-PHONE"
K_SEAL_CHECK = "K-SEAL-CHECK"
K_RECOUNT_BEFORE_SAFE = "K-RECOUNT-BEFORE-SAFE"

SMOOTH_K = 1
DEDUPE_S = 10.0

_STATE_FIELDS = tuple(FrameState.model_fields.keys())

_Sample = tuple[float, dict]  # (t, smoothed state as a plain dict)


class _Raw:
    """One pending finding before dedupe, mirroring the kit's ``V.append({...})`` entries."""

    __slots__ = ("rule_id", "t", "t_start", "t_end", "support_t", "facts")

    def __init__(
        self,
        rule_id: str,
        t: float,
        t_start: float,
        t_end: float,
        support_t: list[float],
        facts: dict[str, str | int | float | bool],
    ) -> None:
        self.rule_id = rule_id
        self.t = t
        self.t_start = t_start
        self.t_end = t_end
        self.support_t = support_t
        self.facts = facts


def _usable_samples(timeline: StateTimeline) -> list[_Sample]:
    """Drop ``ok=False``/missing-state frames, keep the rest sorted by time (as plain dicts)."""
    rows = [
        (fo.t, fo.state.model_dump()) for fo in timeline.frames if fo.ok and fo.state is not None
    ]
    rows.sort(key=lambda r: r[0])
    return rows


def _smooth(samples: list[_Sample], k: int) -> list[_Sample]:
    """Majority smoothing per field (bool/enum -> mode, int -> median), kit's ``smooth()``."""
    out: list[_Sample] = []
    n = len(samples)
    for i in range(n):
        lo, hi = max(0, i - k), min(n, i + k + 1)
        window = [samples[j][1] for j in range(lo, hi)]
        st: dict = {}
        for f in _STATE_FIELDS:
            vals = [w[f] for w in window if w.get(f) is not None]
            if not vals:
                st[f] = samples[i][1].get(f)
                continue
            v0 = samples[i][1][f]
            if isinstance(v0, int) and not isinstance(v0, bool):
                st[f] = sorted(vals)[len(vals) // 2]
            else:
                st[f] = Counter(vals).most_common(1)[0][0]
        out.append((samples[i][0], st))
    return out


def _runs(
    S: list[_Sample], pred: Callable[[dict], bool], min_len: int = 1
) -> list[tuple[int, int]]:
    """Maximal contiguous index ranges [i0, i1] where ``pred(state)`` holds, kit's ``runs()``."""
    res: list[tuple[int, int]] = []
    i = 0
    n = len(S)
    while i < n:
        if pred(S[i][1]):
            j = i
            while j + 1 < n and pred(S[j + 1][1]):
                j += 1
            if j - i + 1 >= min_len:
                res.append((i, j))
            i = j + 1
        else:
            i += 1
    return res


def _frac(S: list[_Sample], i0: int, i1: int, pred: Callable[[dict], bool]) -> float:
    seg = S[max(0, i0) : max(0, i1) + 1]
    if not seg:
        return 0.0
    return sum(1 for x in seg if pred(x[1])) / len(seg)


def _support(
    S: list[_Sample], i0: int, i1: int, pred: Callable[[dict], bool] | None = None
) -> list[float]:
    seg = S[max(0, i0) : max(0, i1) + 1]
    if pred is None:
        return [t for t, _ in seg]
    return [t for t, s in seg if pred(s)]


def _req(params: dict[str, float], *keys: str) -> tuple[float, ...]:
    missing = [k for k in keys if k not in params]
    if missing:
        raise KeyError(f"missing rule params {missing!r}")
    return tuple(params[k] for k in keys)


def evaluate(timeline: StateTimeline, rules: list[RuleEntry]) -> list[Finding]:
    """Pure function: a ``StateTimeline`` plus the enabled subset of ``rules`` -> ``Finding``s."""
    enabled: dict[str, RuleEntry] = {r.rule_id: r for r in rules if r.enabled}
    if not enabled:
        return []

    samples = _usable_samples(timeline)
    if not samples:
        return []
    S = _smooth(samples, SMOOTH_K)
    n_s = len(S)
    dt = ((S[-1][0] - S[0][0]) / max(1, n_s - 1)) or 1.0

    def n(sec: float) -> int:
        return max(1, round(sec / dt))

    raw: list[_Raw] = []

    def is_true(field: str) -> Callable[[dict], bool]:
        return lambda s: bool(s[field])

    def add(
        rule_id: str,
        anchor_i: int,
        t_start_i: int,
        t_end_i: int,
        support_t: Iterable[float],
        facts: dict[str, str | int | float | bool] | None = None,
    ) -> None:
        if rule_id not in enabled:
            return
        t0, t1 = S[t_start_i][0], S[t_end_i][0]
        f: dict[str, str | int | float | bool] = {"t_start": round(t0, 2), "t_end": round(t1, 2)}
        if facts:
            f.update(facts)
        raw.append(_Raw(rule_id, S[anchor_i][0], t0, t1, list(support_t), f))

    # ---- cashier leaves the desk -------------------------------------------------------
    leave_group = (
        L_NO_CASH_ON_LEAVE,
        L_SAFE_LOCKED_ON_LEAVE,
        L_PC_LOCKED,
        L_NO_DOCS_ON_LEAVE,
    )
    if any(rid in enabled for rid in leave_group) and L_NO_CASH_ON_LEAVE in enabled:
        (min_away_s, min_samples) = _req(
            enabled[L_NO_CASH_ON_LEAVE].params, "min_away_s", "min_samples"
        )
        for i0, i1 in _runs(S, lambda s: not s["cashier_at_desk"], n(min_away_s)):
            if i0 == 0:
                continue  # not at the desk at the very start -> not a "leave"
            exits = [k for k in range(i0, i1 + 1) if not S[k][1]["cashier_in_room"]]
            anchor = i0  # kit default leave_anchor='desk'

            if L_NO_CASH_ON_LEAVE in enabled:
                (check_window_s, cash_frac) = _req(
                    enabled[L_NO_CASH_ON_LEAVE].params, "check_window_s", "cash_frac_threshold"
                )
                a0, a1 = i0, min(i1, i0 + n(check_window_s))
                if _frac(S, a0, a1, lambda s: s["desk_cash"] or s["desk_bag"]) >= cash_frac:
                    cash_seen = _frac(S, a0, a1, is_true("desk_cash")) > 0
                    bag_seen = _frac(S, a0, a1, is_true("desk_bag")) > 0
                    obj = (
                        "наличные и сумка"
                        if cash_seen and bag_seen
                        else "сумка"
                        if bag_seen
                        else "наличные"
                    )
                    add(
                        L_NO_CASH_ON_LEAVE,
                        anchor,
                        i0,
                        i1,
                        _support(S, a0, a1, lambda s: s["desk_cash"] or s["desk_bag"]),
                        {"object": obj},
                    )

            if exits:
                if L_SAFE_LOCKED_ON_LEAVE in enabled:
                    (exit_window_s, key_frac, key_lookback_s) = _req(
                        enabled[L_SAFE_LOCKED_ON_LEAVE].params,
                        "exit_window_s",
                        "key_frac_threshold",
                        "key_lookback_s",
                    )
                    e0, e1 = exits[0], min(i1, exits[0] + n(exit_window_s))
                    if _frac(S, e0, e1, lambda s: s["key_in_safe_lock"] == "yes") >= key_frac:
                        at_safe = [
                            k
                            for k in range(i0 - n(key_lookback_s), exits[0])
                            if k >= 0 and S[k][1]["cashier_action"] == "at_safe"
                        ]
                        anchor_key = at_safe[-1] if at_safe else exits[0]
                        add(
                            L_SAFE_LOCKED_ON_LEAVE,
                            anchor_key,
                            e0,
                            e1,
                            _support(S, e0, e1, lambda s: s["key_in_safe_lock"] == "yes"),
                        )

                if L_NO_DOCS_ON_LEAVE in enabled:
                    (docs_frac,) = _req(enabled[L_NO_DOCS_ON_LEAVE].params, "docs_frac_threshold")
                    if L_SAFE_LOCKED_ON_LEAVE in enabled:
                        (exit_window_s,) = _req(
                            enabled[L_SAFE_LOCKED_ON_LEAVE].params, "exit_window_s"
                        )
                    else:
                        (exit_window_s,) = _req(enabled[L_NO_DOCS_ON_LEAVE].params, "exit_window_s")
                    e0, e1 = exits[0], min(i1, exits[0] + n(exit_window_s))
                    if _frac(S, e0, e1, is_true("desk_documents")) >= docs_frac:
                        add(
                            L_NO_DOCS_ON_LEAVE,
                            anchor,
                            e0,
                            e1,
                            _support(S, e0, e1, is_true("desk_documents")),
                        )

                if L_PC_LOCKED in enabled:
                    (unlocked_frac,) = _req(enabled[L_PC_LOCKED].params, "unlocked_frac_threshold")

                    def _unlocked(s: dict) -> bool:
                        return s["laptop_screen"] == "unlocked"

                    if _frac(S, exits[0], i1, _unlocked) >= unlocked_frac:
                        add(
                            L_PC_LOCKED,
                            anchor,
                            exits[0],
                            i1,
                            _support(S, exits[0], i1, _unlocked),
                        )

    # ---- safe left open without the cashier at it --------------------------------------
    if S_SAFE_CLOSED in enabled:
        (safe_open_s,) = _req(enabled[S_SAFE_CLOSED].params, "safe_open_s")

        def _safe_open_without_cashier(s: dict) -> bool:
            return s["safe_door"] == "open" and s["cashier_action"] != "at_safe"

        for i0, i1 in _runs(S, _safe_open_without_cashier, n(safe_open_s)):
            add(S_SAFE_CLOSED, i0, i0, i1, _support(S, i0, i1))

    # ---- client sessions: dirty_desk / merge_cash / no_id / client_left_count ----------
    session_group = (S_CLEAN_DESK_HANDOVER, S_NO_MERGE, C_ID_BEFORE_CASH, C_COUNT_BEFORE_EXIT)
    if any(rid in enabled for rid in session_group) and S_CLEAN_DESK_HANDOVER in enabled:
        (session_gap_s, sess_min_samples, entry_lookback_s) = _req(
            enabled[S_CLEAN_DESK_HANDOVER].params,
            "session_gap_s",
            "min_samples",
            "entry_lookback_s",
        )
        sess = _runs(S, lambda s: s["clients_at_desk"] >= 1, round(sess_min_samples))
        merged: list[tuple[int, int]] = []
        for a, b in sess:
            if merged and S[a][0] - S[merged[-1][1]][0] <= session_gap_s:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))

        for k, (a, b) in enumerate(merged):
            start = a
            for j in range(max(0, a - n(entry_lookback_s)), a):
                if S[j][1]["person_at_door"]:
                    start = j
                    break

            if k > 0 and S_CLEAN_DESK_HANDOVER in enabled:
                (cash_lookback_s, cash_frac) = _req(
                    enabled[S_CLEAN_DESK_HANDOVER].params, "cash_lookback_s", "cash_frac_threshold"
                )
                cash_lookback_i0 = max(0, start - n(cash_lookback_s))
                if _frac(S, cash_lookback_i0, start, is_true("desk_cash")) >= cash_frac:
                    add(
                        S_CLEAN_DESK_HANDOVER,
                        start,
                        cash_lookback_i0,
                        start,
                        _support(S, cash_lookback_i0, start, is_true("desk_cash")),
                    )
                    if S_NO_MERGE in enabled:
                        (merge_min_gap_s,) = _req(enabled[S_NO_MERGE].params, "merge_min_gap_s")
                        for j in range(a, b + 1):
                            s = S[j][1]
                            if s["cashier_action"] in ("receiving_cash", "counting_by_hand") or s[
                                "cash_in_hands_of"
                            ] in ("client", "several"):
                                if S[j][0] - S[start][0] >= merge_min_gap_s:
                                    add(S_NO_MERGE, j, j, j, [S[j][0]])
                                break

            if C_ID_BEFORE_CASH in enabled:
                (id_lookback_s,) = _req(enabled[C_ID_BEFORE_CASH].params, "id_lookback_s")
                t_cash = next(
                    (
                        j
                        for j in range(a, b + 1)
                        if S[j][1]["cash_in_hands_of"] in ("client", "several")
                        or S[j][1]["cashier_action"] == "receiving_cash"
                    ),
                    None,
                )
                id_shown_before_cash = t_cash is not None and any(
                    S[j][1]["id_document_visible"]
                    or S[j][1]["cashier_action"] == "checking_id_document"
                    for j in range(max(0, start - n(id_lookback_s)), t_cash + 1)
                )
                if t_cash is not None and not id_shown_before_cash:
                    add(C_ID_BEFORE_CASH, t_cash, t_cash, t_cash, [S[t_cash][0]])

            end = b + 1
            if end < n_s and C_COUNT_BEFORE_EXIT in enabled:
                (before_s, after_s, count_frac) = _req(
                    enabled[C_COUNT_BEFORE_EXIT].params,
                    "count_window_before_s",
                    "count_window_after_s",
                    "count_frac_threshold",
                )
                w0, w1 = max(0, end - n(before_s)), min(n_s - 1, end + n(after_s))

                def _counting(s: dict) -> bool:
                    return s["counting_machine_in_use"] or s["cashier_action"] in (
                        "using_counting_machine",
                        "counting_by_hand",
                    )

                if _frac(S, w0, w1, _counting) >= count_frac:
                    add(C_COUNT_BEFORE_EXIT, end, w0, w1, _support(S, w0, w1, _counting))

    # ---- simultaneous clients / outsiders / door / workplace conduct -------------------
    def _two_or_more_clients(s: dict) -> bool:
        return s["clients_at_desk"] >= 2 and not s["collector_present"]

    def _two_or_more_on_cashier_side(s: dict) -> bool:
        return s["people_cashier_side"] >= 2 and not s["collector_present"]

    if A_SECOND_PERSON in enabled:
        (min_samples,) = _req(enabled[A_SECOND_PERSON].params, "min_samples")
        for i0, i1 in _runs(S, _two_or_more_clients, round(min_samples)):
            add(A_SECOND_PERSON, i0, i0, i1, _support(S, i0, i1))

    if A_OUTSIDER_ZONE in enabled:
        (min_samples,) = _req(enabled[A_OUTSIDER_ZONE].params, "min_samples")
        for i0, i1 in _runs(S, _two_or_more_on_cashier_side, round(min_samples)):
            add(
                A_OUTSIDER_ZONE,
                i0,
                i0,
                i1,
                _support(S, i0, i1),
                {"people_count": S[i0][1]["people_cashier_side"]},
            )

    if A_DOOR_LOCK in enabled:
        (door_open_s, presence_frac) = _req(
            enabled[A_DOOR_LOCK].params, "door_open_s", "presence_frac_threshold"
        )
        for i0, i1 in _runs(S, lambda s: s["room_door"] == "open", n(door_open_s)):
            at = [k for k in range(i0, i1 + 1) if S[k][1]["cashier_at_desk"]]
            if len(at) >= n(door_open_s) * presence_frac:
                add(A_DOOR_LOCK, at[0], i0, i1, _support(S, i0, i1, lambda s: s["cashier_at_desk"]))

    if W_NO_PERSONAL_ITEMS in enabled:
        (min_samples,) = _req(enabled[W_NO_PERSONAL_ITEMS].params, "min_samples")
        for i0, i1 in _runs(S, is_true("desk_personal_items"), round(min_samples)):
            add(W_NO_PERSONAL_ITEMS, i0, i0, i1, _support(S, i0, i1))

    if W_NO_FOOD in enabled:
        (min_samples,) = _req(enabled[W_NO_FOOD].params, "min_samples")
        for i0, i1 in _runs(
            S,
            lambda s: s["desk_food_drink"] or s["cashier_action"] == "eating_drinking",
            round(min_samples),
        ):
            add(W_NO_FOOD, i0, i0, i1, _support(S, i0, i1))

    if W_NO_CAMERA_PHONE in enabled:
        (min_samples,) = _req(enabled[W_NO_CAMERA_PHONE].params, "min_samples")
        for i0, i1 in _runs(
            S,
            lambda s: s["phone_in_cashier_hand"] or s["cashier_action"] == "using_phone",
            round(min_samples),
        ):
            add(W_NO_CAMERA_PHONE, i0, i0, i1, _support(S, i0, i1))

    # ---- cash collector: bag handed over, collector leaves quickly ---------------------
    if K_SEAL_CHECK in enabled:
        (collector_quick_s,) = _req(enabled[K_SEAL_CHECK].params, "collector_quick_s")
        for i0, i1 in _runs(S, is_true("collector_present"), 1):
            bag = next((j for j in range(i0, i1 + 1) if S[j][1]["desk_bag"]), None)
            if bag is not None and S[i1][0] - S[bag][0] <= collector_quick_s and i1 + 1 < n_s:
                add(
                    K_SEAL_CHECK,
                    bag,
                    bag,
                    i1,
                    _support(S, bag, i1),
                    {"collector_quick_s": collector_quick_s},
                )

    # ---- bag opened -> safe used, without a recount in between -------------------------
    if K_RECOUNT_BEFORE_SAFE in enabled:
        opened = [j for j in range(n_s) if S[j][1]["cashier_action"] == "packing_or_opening_bag"]
        if opened:
            for j in range(opened[0], n_s):
                if S[j][1]["safe_door"] == "open" or S[j][1]["cashier_action"] == "at_safe":
                    counted = any(
                        S[k][1]["counting_machine_in_use"]
                        or S[k][1]["cashier_action"]
                        in ("counting_by_hand", "using_counting_machine")
                        for k in range(opened[0], j)
                    )
                    if not counted:
                        add(K_RECOUNT_BEFORE_SAFE, j, opened[0], j, [S[j][0]])
                    break

    # ---- experimental: hand counting with no detector used anywhere --------------------
    if C_DETECTOR_CHECK in enabled:
        hand = [j for j in range(n_s) if S[j][1]["cashier_action"] == "counting_by_hand"]
        if hand and not any(
            s[1]["detector_in_use"] or s[1]["cashier_action"] == "using_detector" for s in S
        ):
            add(C_DETECTOR_CHECK, hand[0], hand[0], hand[0], [S[hand[0]][0]])

    # ---- dedupe: same rule within DEDUPE_S keeps only the first ------------------------
    raw.sort(key=lambda v: v.t)
    kept: list[_Raw] = []
    for v in raw:
        if any(o.rule_id == v.rule_id and abs(o.t - v.t) < DEDUPE_S for o in kept):
            continue
        kept.append(v)

    findings: list[Finding] = []
    for v in kept:
        findings.append(
            Finding(
                rule_id=v.rule_id,
                t_anchor=v.t,
                t_start=v.t_start,
                t_end=v.t_end,
                support_t=v.support_t,
                facts=v.facts,
                rank_score=float(len(v.support_t)),
            )
        )
    return findings
