"""Synthetic `StateTimeline` builder for rules tests, modeled on the kit's
`tests/make_fixture_states.py` (same idea: a base "cashier working" frame, with named segments
overlaid, as if a VLM had answered every sampled frame perfectly -- no GPU needed).
"""

from __future__ import annotations

from backend.contracts import Coverage, FrameObservation, FrameState, StateTimeline, VideoInfo

BASE: dict = {
    "cashier_at_desk": True,
    "cashier_in_room": True,
    "people_cashier_side": 1,
    "clients_at_desk": 0,
    "person_at_door": False,
    "collector_present": False,
    "desk_cash": False,
    "desk_bag": False,
    "desk_documents": False,
    "desk_personal_items": False,
    "desk_food_drink": False,
    "phone_in_cashier_hand": False,
    "id_document_visible": False,
    "counting_machine_in_use": False,
    "detector_in_use": False,
    "safe_door": "closed",
    "key_in_safe_lock": "no",
    "laptop_screen": "lock_screen",
    "room_door": "closed",
    "cash_in_hands_of": "nobody",
    "cashier_action": "working_on_laptop",
}

AWAY: dict = {"cashier_at_desk": False, "cashier_action": "walking_out", "people_cashier_side": 0}
GONE: dict = {
    "cashier_at_desk": False,
    "cashier_in_room": False,
    "cashier_action": "not_present",
    "people_cashier_side": 0,
}

Segment = tuple[int, int, dict]


def make_timeline(
    video_id: str,
    duration_s: int,
    segments: list[Segment],
    unknown_t: set[int] | None = None,
    step_s: float = 1.0,
) -> StateTimeline:
    """One sample per integer second in `[0, duration_s]`, `BASE` overlaid by `segments`
    (`(t0, t1, updates)`, half-open `[t0, t1)`, applied in order). Seconds in `unknown_t` become
    `ok=False` frames with no state, simulating a VLM answer that failed or was schema-invalid.
    """
    unknown_t = unknown_t or set()
    frames: list[FrameObservation] = []
    for t in range(0, duration_s + 1):
        if t in unknown_t:
            frames.append(
                FrameObservation(
                    t=float(t), ok=False, state=None, error="stub failure", latency_s=0.1
                )
            )
            continue
        st = dict(BASE)
        for t0, t1, upd in segments:
            if t0 <= t < t1:
                st.update(upd)
        frames.append(FrameObservation(t=float(t), ok=True, state=FrameState(**st), latency_s=0.5))

    info = VideoInfo(
        sha256="0" * 64, duration_sec=float(max(duration_s, 1)), width=640, height=480, fps=1.0
    )
    done = sum(1 for f in frames if f.ok)
    coverage = Coverage(
        step_s=step_s,
        planned=len(frames),
        done=done,
        failed=len(frames) - done,
        deadline_hit=False,
        mode="full",
    )
    return StateTimeline(video=info, frames=frames, coverage=coverage)
