from __future__ import annotations

import os
from typing import Any, Dict, List

import requests
from langchain.tools import tool

from ..config.settings import get_settings
from ..core.logger import setup_logging

try:
    # MarkItDown is optional until dependencies are installed
    from markitdown import MarkItDown  # type: ignore
except Exception:  # pragma: no cover
    MarkItDown = None  # type: ignore


def _is_url(text: str) -> bool:
    return text.strip().lower().startswith(("http://", "https://"))


def _ddg_search_to_markdown(query: str, max_results: int = 5) -> str:
    """Fallback web search using DuckDuckGo and format as Markdown."""
    try:
        from duckduckgo_search import DDGS  # type: ignore
    except Exception:
        return (
            "# Search\n\n"
            "- Unable to perform web search. Please install 'duckduckgo-search'.\n"
            f"- Query: {query}"
        )

    items: List[Dict[str, Any]] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            items.append(r)

    lines: List[str] = [f"# Web Search Results\n\n**Query:** {query}\n"]
    for i, r in enumerate(items, start=1):
        title = r.get("title") or r.get("source") or f"Result {i}"
        href = r.get("href") or r.get("link") or ""
        body = r.get("body") or r.get("snippet") or ""
        lines.append(f"- [{title}]({href})\n  - {body}")
    return "\n".join(lines)


def _bing_search_to_markdown(query: str, max_results: int = 5) -> str:
    """Use Bing Web Search API if configured; otherwise fall back to DDG."""
    settings = get_settings()
    api_key = getattr(settings, "bing_api_key", None)
    if not api_key:
        return _ddg_search_to_markdown(query, max_results)

    try:
        url = "https://api.bing.microsoft.com/v7.0/search"
        params = {"q": query, "count": max_results}
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("webPages", {}).get("value", [])
        lines: List[str] = [f"# Bing Search Results\n\n**Query:** {query}\n"]
        for i, r in enumerate(items, start=1):
            name = r.get("name")
            link = r.get("url")
            snippet = r.get("snippet") or r.get("about") or ""
            lines.append(f"- [{name}]({link})\n  - {snippet}")
        return "\n".join(lines)
    except Exception as e:
        return f"# Search Error\n\n- Query: `{query}`\n- Error: {e}"


def _convert_with_markitdown(input_value: str) -> str:
    """Convert path or URL to Markdown via MarkItDown."""
    if MarkItDown is None:
        return "# Error\n\n- 'markitdown' not installed. Please add it to requirements."
    md = MarkItDown()
    try:
        result = md.convert(input_value)
        # MarkItDown returns an object with text_content/markdown depending on version
        text = getattr(result, "text_content", None) or getattr(result, "markdown", None) or str(result)
        return text
    except Exception as e:
        return f"# Conversion Error\n\n- Input: `{input_value}`\n- Error: {e}"


@tool
def convert_to_markdown(input_value: str) -> str:
    """Convert any input to Markdown.

    - If `input_value` is a URL: fetch and convert web content (incl. YouTube transcripts).
    - If it's a local file path: convert PDF/DOCX/XLSX/PPTX/images/audio (audio is transcribed).
    - If it's a text query (e.g. "bing: AI news"), perform web search and return results as Markdown.
    - Otherwise, treat as a generic query: do web search and summarize results in Markdown.
    """
    logger = setup_logging()
    iv = (input_value or "").strip()
    if not iv:
        return "# Input Required\n\n- Please provide a URL, file path, or search query."

    logger.info(f"convert_to_markdown received: {iv}")

    # URL
    if _is_url(iv):
        return _convert_with_markitdown(iv)

    # Local file
    if os.path.exists(iv):
        return _convert_with_markitdown(iv)

    lowered = iv.lower()
    # Explicit search prefixes
    if lowered.startswith("bing:"):
        query = iv.split(":", 1)[1].strip()
        return _bing_search_to_markdown(query)
    if lowered.startswith("ddg:") or lowered.startswith("duckduckgo:"):
        query = iv.split(":", 1)[1].strip()
        return _ddg_search_to_markdown(query)

    # Generic query: try Bing API first, fallback to DDG
    return _bing_search_to_markdown(iv)