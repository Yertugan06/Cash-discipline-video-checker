import pytest

from backend.config import ROOT, Settings
from backend.f1.detector import F1Detector
from backend.knowledge import Knowledge


def test_deployed_f1_rules_match_codex_evaluators_and_knowledge_pack():
    settings = Settings(api_key="test-key", knowledge_dir=ROOT / "knowledge")
    knowledge = Knowledge.load(settings.knowledge_dir)
    detector = F1Detector(settings, knowledge.rules)
    assert detector is not None


def test_startup_rejects_enabled_rule_marked_unimplemented():
    settings = Settings(api_key="test-key", knowledge_dir=ROOT / "knowledge")
    knowledge = Knowledge.load(settings.knowledge_dir)
    changed = [
        rule.model_copy(update={"implementation_status": "unimplemented"}) if rule.enabled else rule
        for rule in knowledge.rules
    ]
    with pytest.raises(ValueError, match="implementation_status"):
        F1Detector(settings, changed)
