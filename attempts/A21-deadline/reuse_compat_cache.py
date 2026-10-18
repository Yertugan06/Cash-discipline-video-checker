"""Reuse unchanged numeric perception after restoring the legacy default-false flag."""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import yaml


def main() -> None:
    from backend.config import ROOT, Settings
    from backend.f1.perception import load_perception_config, verify_weights

    base = ROOT.parent
    previous = base / "source-before-compat"
    current = ROOT / "backend/f1/perception.py"

    def neural_code(path: Path) -> str:
        tree = ast.parse(path.read_text())
        tree.body = [
            node
            for node in tree.body
            if not isinstance(node, ast.FunctionDef) or node.name != "load_perception_config"
        ]
        return ast.dump(tree, include_attributes=False)

    assert neural_code(previous / "perception.py") == neural_code(current)
    config = load_perception_config(ROOT / "config/perception.yaml")
    assert config["desk_objects"] is False
    assert {k: v for k, v in config.items() if k != "desk_objects"} == yaml.safe_load(
        (previous / "perception.yaml").read_text()
    )
    settings = Settings(
        api_key="local-compat-proof", weights_dir=Path.home() / "agentA-rulebook/weights"
    )
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "implementation": hashlib.sha256(
                    b"".join(
                        (ROOT / "backend/f1" / name).read_bytes()
                        for name in ("perception.py", "calibration.py", "vision_types.py")
                    )
                ).hexdigest(),
                "models": verify_weights(settings.weights_dir),
                "config": config,
                "overrides": settings.overrides_path.read_text(),
                "fps": 2.0,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    records = []
    for source in sorted((base / "fresh-merged").glob("*/*.json")):
        assert source.stem == "97d26089af4d0fed1fd997bb48c72e58fbf3f7707bc0240b48628addce403bd7"
        data = source.read_bytes()
        assert set(json.loads(data)) == {"scene", "observations"}
        target = ROOT / "runtime/perception_cache" / source.parent.name / (fingerprint + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists(), "Never overwrite an independently generated cache"
        shutil.copy2(source, target)
        assert target.read_bytes() == data
        records.append(
            {"sha256": source.parent.name, "payload_sha256": hashlib.sha256(data).hexdigest()}
        )
    assert len(records) == 40
    report = {
        "purpose": "explicit compatibility-only reuse; no new neural inference claimed",
        "neural_code_ast_unchanged": True,
        "default_desk_history_enabled": False,
        "new_fingerprint": fingerprint,
        "records": records,
    }
    (base / "cache-compatibility-reuse.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "verified_identical_numeric_caches_reused": len(records),
                "new_fingerprint": fingerprint,
            }
        )
    )


if __name__ == "__main__":
    main()
