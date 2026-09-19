from sunosentry.engine import VoiceOpsEngine


def test_water_leak_requires_confirmation_before_handoff() -> None:
    engine = VoiceOpsEngine()
    session = engine.new_session()
    result = engine.handle_turn(session.session_id, "There is a water leak under my sink")
    assert result["handoff"] is False
    assert result["session"]["proposal"]["status"] == "draft"
    assert any(event["agent"] == "consent-agent" for event in result["session"]["trace"])


def test_emergency_is_human_escalation_not_a_dispatch() -> None:
    engine = VoiceOpsEngine()
    session = engine.new_session()
    result = engine.handle_turn(session.session_id, "I smell gas in the basement")
    assert result["handoff"] is True
    assert result["session"]["proposal"] is None
    assert any(event["outcome"] == "blocked" for event in result["session"]["trace"])


def test_spoken_confirmation_creates_only_verified_handoff() -> None:
    engine = VoiceOpsEngine()
    session = engine.new_session()
    result = engine.handle_turn(session.session_id, "My heater stopped working", confirmed=True)
    assert result["handoff"] is True
    assert result["session"]["proposal"]["confirmation_received"] is True


def test_heating_language_is_a_priority_issue() -> None:
    engine = VoiceOpsEngine()
    session = engine.new_session()
    result = engine.handle_turn(session.session_id, "My heating system stopped working")
    assert result["session"]["proposal"]["issue_type"] == "no_heat"
