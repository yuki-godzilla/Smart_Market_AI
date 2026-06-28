from __future__ import annotations

import json

import streamlit.components.v1 as components

PWA_HEAD_ELEMENTS: tuple[dict[str, str], ...] = (
    {
        "tag": "meta",
        "name": "apple-mobile-web-app-capable",
        "content": "yes",
    },
    {
        "tag": "meta",
        "name": "apple-mobile-web-app-title",
        "content": "SMAI",
    },
    {
        "tag": "meta",
        "name": "apple-mobile-web-app-status-bar-style",
        "content": "black-translucent",
    },
    {
        "tag": "meta",
        "name": "theme-color",
        "content": "#07111f",
    },
    {
        "tag": "link",
        "rel": "apple-touch-icon",
        "href": "/app/static/pwa/apple-touch-icon.png",
    },
    {
        "tag": "link",
        "rel": "icon",
        "href": "/app/static/pwa/favicon.png",
    },
    {
        "tag": "link",
        "rel": "manifest",
        "href": "/app/static/pwa/manifest.json",
    },
)


def pwa_head_injection_html() -> str:
    """Return a small same-origin script that idempotently updates Streamlit's head."""

    elements_json = json.dumps(PWA_HEAD_ELEMENTS, ensure_ascii=True)
    return f"""
<script>
(() => {{
  const head = window.parent.document.head;
  const elements = {elements_json};
  for (const spec of elements) {{
    const selector = spec.tag === "meta"
      ? `meta[name="${{spec.name}}"]`
      : `link[rel="${{spec.rel}}"][data-smai-pwa="true"]`;
    let element = head.querySelector(selector);
    if (!element) {{
      element = window.parent.document.createElement(spec.tag);
      head.appendChild(element);
    }}
    for (const [key, value] of Object.entries(spec)) {{
      if (key !== "tag") element.setAttribute(key, value);
    }}
    element.setAttribute("data-smai-pwa", "true");
  }}
}})();
</script>
"""


def inject_pwa_head_metadata() -> None:
    components.html(pwa_head_injection_html(), height=0, width=0)
