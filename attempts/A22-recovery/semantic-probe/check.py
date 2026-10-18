"""One CPU-only parser/provenance/selection assertion check; no image decoding."""

import copy
import json
from pathlib import Path

import pilot

root = Path(__file__).resolve().parent
policy = json.loads((root / "preregistration.json").read_text())
native = json.loads(Path("/tmp/a22-native128-pilot-01/results.json").read_text())
dino = json.loads(
    Path(
        "/home/ubuntu/workspaces/datathon26-workers/shared/a22/dino-probe-02/results.json"
    ).read_text()
)
selected, missing = pilot.select(native, dino)
assert selected == policy["queries"] and not missing
assert len(selected) == 24 and len({(q["sha256"], q["t"]) for q in selected}) == 20
assert any(
    q["clip"] == "X-40" and q["source"] == "owlv2_native128" and q["detection"]["label"] == "bundle"
    for q in selected
)  # Evaluation coverage only.
for q in selected:
    row = next(
        r
        for r in (native if q["source"] == "owlv2_native128" else dino)
        if r["sha256"] == q["sha256"] and r["t"] == q["t"]
    )
    calls = (
        row["variants"]["full_desk_plus_native128"]["calls"]
        if q["source"] == "owlv2_native128"
        else row["calls"]
    )
    assert q["detection"] in calls[q["call_index"]]["detections"] and q["source_crop"] is not None
changed_n, changed_d = copy.deepcopy(native), copy.deepcopy(dino)
for row in changed_n + changed_d:
    row["expected"] = {"cash": "unused", "id_card": "unused"}
assert pilot.select(changed_n, changed_d) == (selected, missing)
pilot.self_check()
print("24 genuine proposals across20frames; labels do not affect selection; X40target included")
