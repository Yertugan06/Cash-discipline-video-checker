"""Own finite-JSON, class-balanced ridge cash-presence head; no media or peer code."""
import numpy as np

CLASSES = ["not_detected", "present"]
LAMBDA = 0.1


def normalized(values):
    values = np.asarray(values, dtype=np.float64)
    norms = np.linalg.norm(values, axis=-1, keepdims=True)
    if not np.isfinite(values).all() or not np.isfinite(norms).all() or (norms <= 0).any():
        raise ValueError("invalid/zero features")
    return values / norms


def fit(features, labels, group_hashes):
    x = normalized(features)
    labels = np.asarray(labels, dtype=np.int64)
    if x.ndim != 2 or labels.shape != (len(x),) or set(labels.tolist()) != {0, 1}:
        raise ValueError("need finite features and both binary classes")
    if len(group_hashes) != len(x):
        raise ValueError("training group count mismatch")
    counts = np.bincount(labels, minlength=2)
    weights = 1.0 / (2 * counts[labels])
    target = labels * 2.0 - 1
    mean_x, mean_y = weights @ x, float(weights @ target)
    z = (x - mean_x) * np.sqrt(weights[:, None])
    rhs = (target - mean_y) * np.sqrt(weights)
    coefficients = z.T @ np.linalg.solve(z @ z.T + LAMBDA * np.eye(len(x)), rhs)
    intercept = float(mean_y - mean_x @ coefficients)
    if not np.isfinite(coefficients).all() or not np.isfinite(intercept):
        raise ValueError("nonfinite fit")
    return {"schema": "a24-cash-ridge-v1", "classes": CLASSES, "dimension": x.shape[1],
            "coefficients": coefficients.tolist(), "intercept": intercept,
            "lambda": LAMBDA, "class_balanced": True, "score_kind": "uncalibrated_signed_ridge",
            "thresholds": {"present": 0.2, "not_detected": -0.2, "ood_cosine": 0.75},
            "train_group_hashes": sorted(set(group_hashes)), "train_reference_features": x.tolist()}


def predict(feature, head):
    if head["schema"] != "a24-cash-ridge-v1" or head["classes"] != CLASSES:
        raise ValueError("invalid head schema/class map")
    x = normalized(feature)
    coefficients = np.asarray(head["coefficients"], dtype=float)
    reference = normalized(head["train_reference_features"])
    if x.shape != (head["dimension"],) or coefficients.shape != x.shape or reference.shape[1] != len(x):
        raise ValueError("feature/head dimension mismatch")
    if not np.isfinite(coefficients).all() or not np.isfinite(head["intercept"]):
        raise ValueError("nonfinite head")
    score = float(x @ coefficients + head["intercept"])
    nearest = float(np.max(reference @ x))
    if not np.isfinite([score, nearest]).all():
        raise ValueError("nonfinite prediction")
    if nearest < 0.75:
        state, reason = "unknown", "out_of_distribution"
    elif score >= 0.2:
        state, reason = "present", "ridge_threshold"
    elif score <= -0.2:
        state, reason = "not_detected", "ridge_threshold"
    else:
        state, reason = "unknown", "score_gap"
    return {"state": state, "reason": reason, "score": score, "nearest_train_cosine": nearest,
            "score_kind": "uncalibrated_signed_ridge", "source": "own_dinov2_cash_ridge"}
