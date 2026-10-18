"""One numeric-only check; no media, pretrained model or GPU."""
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import fit, predict

x = np.array([[1., 0., 0.], [.9, .1, 0.], [-1., 0., 0.], [-.9, -.1, 0.]])
head = fit(x, [1, 1, 0, 0], ["train-positive"]*2+["train-negative"]*2)
restored = json.loads(json.dumps(head, allow_nan=False))
assert [predict(v, restored)["state"] for v in x] == ["present"]*2+["not_detected"]*2
assert predict([0., 0., 1.], restored)["state"] == "unknown"
assert predict([0., 0., 1.], restored)["reason"] == "out_of_distribution"
assert np.isclose(restored["intercept"], 0)
imbalanced = fit(np.concatenate([x[:2], x[:2], x[2:]]), [1, 1, 1, 1, 0, 0], ["train"]*6)
assert np.allclose(imbalanced["coefficients"], head["coefficients"])
assert np.isclose(imbalanced["intercept"], head["intercept"])
for invalid in ([float("nan"), 0, 1], [0., 0., 0.]):
    try:
        predict(invalid, restored)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid feature accepted")
assert "probe" not in restored["train_group_hashes"]
print("PASS: weighted dual ridge, binary class map, finite JSON round-trip, prediction/OOD and invalid features")
