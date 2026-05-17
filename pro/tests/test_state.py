from backend.shared import BroadcastState, apply_patch


def test_default_state_is_deck_slide_one():
    s = BroadcastState()
    assert s.view == "deck"
    assert s.slide == 1
    assert s.version == 0


def test_bumped_increments_version():
    s = BroadcastState(slide=3, version=5)
    next_state = s.bumped(slide=4)
    assert next_state.slide == 4
    assert next_state.version == 6
    assert next_state.updated_at >= s.updated_at


def test_apply_patch_rejects_unknown_keys():
    s = BroadcastState()
    try:
        apply_patch(s, {"slide": 2, "nope": 1})
    except ValueError as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_apply_patch_returns_new_state_with_bumped_version():
    s = BroadcastState(version=10)
    next_state = apply_patch(s, {"view": "glossary", "glossary_term": "harness"})
    assert next_state.view == "glossary"
    assert next_state.glossary_term == "harness"
    assert next_state.version == 11
