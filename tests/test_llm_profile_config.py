from __future__ import annotations

from backend.core.config import Settings


def test_assistant_gateway_profile_settings_default_to_notebook_auto():
    settings = Settings()

    assert settings.assistant.gateway.execution_mode == "auto"
    assert settings.assistant.gateway.environment_profile == "notebook"
    assert settings.assistant.gateway.preferred_profile is None


def test_assistant_gateway_profile_settings_accept_light_notebook_override():
    settings = Settings.model_validate(
        {
            "assistant": {
                "gateway": {
                    "enabled": True,
                    "execution_mode": "light",
                    "environment_profile": "notebook",
                    "preferred_profile": "assistant_fast",
                }
            }
        }
    )

    gateway = settings.assistant.gateway
    assert gateway.enabled
    assert gateway.execution_mode == "light"
    assert gateway.environment_profile == "notebook"
    assert gateway.preferred_profile == "assistant_fast"
