from __future__ import annotations

from functools import wraps
from typing import Any, Mapping

_METRIC_WIDGET_PREFIXES = ("market_data_ranking_", "market_data_cockpit_")
_METRIC_WIDGET_SUFFIX = "_enabled"
_PATCH_MARKER = "_smai_metric_checkbox_state_sync"


def _coerce_widget_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def is_metric_checkbox_key(key: object) -> bool:
    return (
        isinstance(key, str)
        and key.startswith(_METRIC_WIDGET_PREFIXES)
        and key.endswith(_METRIC_WIDGET_SUFFIX)
    )


def resolved_metric_checkbox_value(
    *,
    key: object,
    widget_value: object,
    session_state: Mapping[str, object],
) -> bool:
    """Prefer the just-updated Streamlit state for ranking metric toggles.

    Older ranking widgets provide both ``value`` and ``key`` while the same key is
    already restored into ``st.session_state``. Depending on the Streamlit rerun,
    the checkbox can be visibly checked while the immediate return value is still
    the previous value. Numeric inputs then remain disabled for that rerun.
    """

    if is_metric_checkbox_key(key) and key in session_state:
        return _coerce_widget_bool(session_state[key])
    return _coerce_widget_bool(widget_value)


def install_metric_checkbox_state_sync(streamlit_api: Any) -> None:
    """Install an idempotent, narrowly scoped checkbox state compatibility shim."""

    current_checkbox = streamlit_api.checkbox
    if getattr(current_checkbox, _PATCH_MARKER, False):
        return

    @wraps(current_checkbox)
    def state_synced_checkbox(*args: Any, **kwargs: Any) -> bool:
        widget_value = current_checkbox(*args, **kwargs)
        return resolved_metric_checkbox_value(
            key=kwargs.get("key"),
            widget_value=widget_value,
            session_state=streamlit_api.session_state,
        )

    setattr(state_synced_checkbox, _PATCH_MARKER, True)
    streamlit_api.checkbox = state_synced_checkbox
