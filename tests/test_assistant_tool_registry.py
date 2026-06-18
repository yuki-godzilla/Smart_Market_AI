from backend.assistant import assistant_action_catalog, assistant_action_registry


def test_assistant_action_catalog_has_unique_ids_and_copy():
    actions = assistant_action_catalog()
    action_ids = [action.action_id for action in actions]

    assert len(action_ids) == len(set(action_ids))
    assert all(action.label for action in actions)
    assert all(action.description for action in actions)
    assert not any(action.is_destructive for action in actions)


def test_external_fetch_actions_require_confirmation():
    external_actions = [action for action in assistant_action_catalog() if action.is_external_fetch]

    assert external_actions
    assert all(action.requires_confirmation for action in external_actions)


def test_registry_exposes_research_and_report_actions():
    registry = assistant_action_registry()

    assert registry["update_research"].is_external_fetch
    assert registry["create_decision_report"].requires_confirmation
    assert registry["open_cockpit"].action_type == "navigation"
