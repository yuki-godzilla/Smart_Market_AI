from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.views.copilot import COPILOT_CHAT_HISTORY_STATE_KEY

GATEWAY = "http://127.0.0.1:8088"
BLOCKED = (
    "First, I need",
    "I need to",
    "I should",
    "The answer should",
    "The tool says",
    "We are given",
    "We must return",
    "Final decision:",
    "<think>",
    "</think>",
    "Let me",
    "Wait,",
)


def click_button_label(app: AppTest, label: str, *, timeout: float | None = None) -> None:
    for button in app.button:
        if str(getattr(button, "label", "")) == label:
            if timeout is None:
                button.click().run()
            else:
                button.click().run(timeout=timeout)
            return
    raise RuntimeError(f"button not found: {label}")


def gateway_check(
    name: str, question: str, task_type: str, timeout: float = 95
) -> dict[str, object]:
    payload = {
        "user_question": question,
        "language": "ja",
        "task_type": task_type,
        "execution_mode": "auto",
        "environment_profile": "notebook",
        "profile": "notebook_dev",
        "context": {
            "bundle_id": f"loop-{name}",
            "title": "SMAIアシスタント実画面確認",
            "source": "manual-validation",
            "language": "ja",
            "sections": [
                {
                    "section_id": "visible-materials",
                    "title": "参照中の材料",
                    "source_kind": "screen",
                    "included_fields": ["価格", "AI予測", "ニュース", "根拠資料"],
                    "summary": {"状態": "確認用の最小文脈"},
                }
            ],
        },
    }
    started = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{GATEWAY}/api/v1/context-answer", json=payload)
        response.raise_for_status()
        data = response.json()
    wall_ms = int((time.perf_counter() - started) * 1000)
    answer = str(data.get("answer", ""))
    return {
        "loop": name,
        "task_type": task_type,
        "wall_ms": wall_ms,
        "provider": data.get("provider"),
        "model": data.get("model"),
        "profile": data.get("profile"),
        "status": data.get("gateway_status"),
        "fallback": data.get("fallback_reason"),
        "timeout_sec": data.get("timeout_sec"),
        "answer_len": len(answer),
        "blocked_leak": any(marker in answer for marker in BLOCKED),
        "answer_preview": answer[:120],
    }


def main() -> None:
    results: list[dict[str, object]] = []
    health = httpx.get(f"{GATEWAY}/health", timeout=5).json()
    results.append(
        {
            "loop": "1_gateway_health",
            "status": health.get("status"),
            "service": health.get("service"),
        }
    )

    app = AppTest.from_file("ui/app.py", default_timeout=25)
    app.session_state["sidemenu_page"] = "copilot"
    app.run()
    css = Path("ui/styles.py").read_text(encoding="utf-8")
    shared_lane = "width: min(1120px, calc(100% - 48px));"
    page_text = "\n".join(
        str(element.value)
        for element in app.markdown
        if getattr(element, "value", None) is not None
    )
    button_labels = [str(getattr(element, "label", "")) for element in app.button]
    results.append(
        {
            "loop": "2_initial_ui",
            "exception_count": len(app.exception),
            "chat_input_count": len(app.chat_input),
            "text_input_count": len(app.text_input),
            "send_visible": "送信" in button_labels,
            "model_selector_present": "qwen3:4b" in page_text
            or any("qwen3:4b" in str(getattr(radio, "value", "")) for radio in app.radio),
            "large_greeting_card_absent": "こんにちは。SMAIナビです。" not in page_text,
            "header_width_lane": shared_lane in css and ".smai-copilot-chat-topbar" in css,
            "context_chip_width_lane": (
                shared_lane in css and ".smai-copilot-material-status" in css
            ),
            "chat_thread_width_lane": shared_lane in css and ".smai-copilot-thread" in css,
            "input_area_width_lane": (
                shared_lane in css and ".smai-copilot-composer-toolbar" in css
            ),
            "main_sections_aligned": css.count(shared_lane) >= 5,
        }
    )

    app.text_input[0].set_value("こんにちは")
    click_button_label(app, "送信")
    history = app.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    results.append(
        {
            "loop": "3_app_free_chat_greeting",
            "history_len": len(history),
            "intent": history[-1]["intent"],
            "meta": history[-1]["response_meta"],
            "blocked_leak": any(marker in history[-1]["answer"] for marker in BLOCKED),
            "answer_preview": history[-1]["answer"][:120],
        }
    )

    results.append(
        gateway_check(
            "4_free_chat_short_limit",
            "こんにちは。20文字以内で返事して",
            "free_chat",
            timeout=25,
        )
    )
    results.append(
        gateway_check("5_app_help", "SMAIの使い方を一文で教えて", "app_help", timeout=35)
    )
    results.append(
        gateway_check(
            "6_forecast_compare",
            "AI予測と下振れ警戒の違いを短く説明して",
            "forecast_risk_compare",
            timeout=50,
        )
    )

    app2 = AppTest.from_file("ui/app.py", default_timeout=25)
    app2.session_state["sidemenu_page"] = "copilot"
    app2.run()
    for button in app2.button:
        if getattr(button, "key", "") == "smai_copilot_suggestion_forecast_risk_compare":
            button.click().run(timeout=70)
            break
    hist2 = app2.session_state[COPILOT_CHAT_HISTORY_STATE_KEY]
    results.append(
        {
            "loop": "7_forecast_card_click",
            "history_len": len(hist2),
            "intent": hist2[-1]["intent"],
            "question": hist2[-1]["question"],
            "meta": hist2[-1]["response_meta"],
            "blocked_leak": any(marker in hist2[-1]["answer"] for marker in BLOCKED),
        }
    )

    results.append(
        gateway_check(
            "8_news_materials",
            "ニュース材料を見たい。未確認なら未確認と言って",
            "news_materials",
            timeout=75,
        )
    )
    results.append(
        gateway_check(
            "9_decision_report",
            "Decision Reportの下書き方針を短く教えて",
            "decision_report_draft",
            timeout=105,
        )
    )

    app3 = AppTest.from_file("ui/app.py", default_timeout=25)
    app3.session_state["sidemenu_page"] = "copilot"
    app3.run()
    results.append(
        {
            "loop": "10_final_ui_layout",
            "exception_count": len(app3.exception),
            "chat_input_removed": len(app3.chat_input) == 0,
            "composer_text_input": len(app3.text_input) == 1,
            "send_button_visible": any(
                getattr(button, "label", "") == "送信" for button in app3.button
            ),
            "suggestion_cards": sum(
                1
                for button in app3.button
                if str(getattr(button, "key", "")).startswith("smai_copilot_suggestion_")
            ),
        }
    )

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
