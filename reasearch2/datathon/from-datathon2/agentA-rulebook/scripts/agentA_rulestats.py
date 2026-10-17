"""Per-rule aggregate stats for a prediction file (no per-clip output).

hit3   = violation clips where the rule fires within +-3 s of a label
offlab = violation clips where it fires but never within +-3 s of a label
clean  = clean clips where it fires
solo   = clean clips where it is the only firing rule (removing it flips the verdict)
"""

import collections
import json
import sys
from pathlib import Path

GT = next(
    p
    for p in (
        Path.home() / "dt26-validation/validation-private",
        Path.home() / "dt26-validation/data/validation-private",
    )
    if (p / "gt.json").is_file()
)


def main() -> None:
    pred = json.loads(Path(sys.argv[1]).read_text())
    split = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else "dev"
    gt = json.loads((GT / "gt.json").read_text())
    groups = json.loads((GT / "split.json").read_text())
    ids = [k for k in gt if (split == "all" or groups[k] == split) and k in pred]
    stats = collections.defaultdict(collections.Counter)
    for k in ids:
        events = pred[k]["events"]
        rules = {e["rule"] for e in events}
        for rule in rules:
            times = [e["t"] for e in events if e["rule"] == rule]
            if gt[k]["violation"]:
                near = any(abs(t - y) <= 3 for t in times for y in gt[k]["org_times"])
                stats[rule]["hit3" if near else "offlab"] += 1
            else:
                stats[rule]["clean"] += 1
                if len(rules) == 1:
                    stats[rule]["solo"] += 1
            stats[rule]["events"] += len(times)
    print(f"{'rule':24} hit3 offlab clean solo events")
    for rule, c in sorted(stats.items()):
        print(f"{rule:24} {c['hit3']:4} {c['offlab']:6} {c['clean']:5} {c['solo']:4} {c['events']:6}")


if __name__ == "__main__":
    main()
