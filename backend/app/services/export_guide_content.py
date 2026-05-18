"""Canonical 2026 export instructions surfaced by the Export Guide page."""
from __future__ import annotations

from app.schemas.export_guide import ExportGuide, ExportPlatform, ExportStep


def _steps(*items: str) -> list[ExportStep]:
    return [ExportStep(n=i + 1, text=t) for i, t in enumerate(items)]


_PLATFORMS: list[ExportPlatform] = [
    ExportPlatform(
        slug="chatgpt",
        name="ChatGPT (OpenAI)",
        icon="chatgpt",
        summary="Full account export emailed as a ZIP containing conversations.json.",
        steps=_steps(
            "Open ChatGPT and click your profile icon (bottom-left).",
            "Choose Settings → Data Controls.",
            "Click Export Data, then Confirm Export.",
            "Open the email from OpenAI and download the ZIP archive.",
            "Inside the ZIP, locate conversations.json — this is what AI Mirror ingests.",
        ),
        output_formats=["ZIP", "JSON"],
        notes=[
            "The export covers your entire account, not just visible chats.",
            "Link is valid for 24 hours from delivery.",
        ],
        docs_url="https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data",
    ),
    ExportPlatform(
        slug="claude",
        name="Claude (Anthropic)",
        icon="claude",
        summary="Privacy-managed export emailed as a ZIP containing JSON.",
        steps=_steps(
            "Open Claude and click your profile (bottom-left).",
            "Choose Settings → Privacy.",
            "Click Export data and confirm.",
            "Open the email from Anthropic and download the ZIP.",
            "Upload the ZIP directly into AI Mirror.",
        ),
        output_formats=["ZIP", "JSON"],
        notes=["Export contains your full conversation history across Projects and Chats."],
        docs_url="https://privacy.anthropic.com/en/articles/7996885-how-do-i-export-my-claude-ai-data",
    ),
    ExportPlatform(
        slug="grok",
        name="Grok (xAI)",
        icon="grok",
        summary="Account-data export delivered via secure email link.",
        steps=_steps(
            "Open Grok (grok.com or the X app) and open your profile menu.",
            "Choose Settings → Data Controls.",
            "Click Export Account Data and confirm.",
            "Open the email from xAI and download the archive.",
            "Drop the JSON into AI Mirror; auto-detection will recognise the Grok schema.",
        ),
        output_formats=["JSON"],
        notes=[
            "If you primarily use Grok on X, you may also export via twitter.com → Settings → Your account → Download an archive (Grok chats included).",
        ],
        docs_url="https://help.x.com/en/using-x/grok",
    ),
    ExportPlatform(
        slug="gemini",
        name="Gemini (Google)",
        icon="gemini",
        summary="Use Google Takeout for full history; per-chat export is also available.",
        steps=_steps(
            "Go to https://takeout.google.com.",
            "Click Deselect all, then scroll down and tick Gemini.",
            "Click Next step → choose ZIP, frequency, and destination.",
            "Click Create export — Google emails the archive when ready.",
            "For a single thread: open the chat → ⋮ menu → Export to Docs or Print → Save as PDF.",
        ),
        output_formats=["ZIP", "JSON", "PDF (per-chat)"],
        notes=[
            "Takeout is the most complete option. Per-chat export is faster for one-off threads.",
        ],
        docs_url="https://support.google.com/gemini/answer/13278892",
    ),
    ExportPlatform(
        slug="perplexity",
        name="Perplexity AI",
        icon="perplexity",
        summary="Per-thread export from the ⋮ menu, or bulk export from Settings.",
        steps=_steps(
            "For one thread: open it → ⋮ menu → Export as PDF, Markdown, or DOCX.",
            "For everything: Settings → Data Controls → Export My Data.",
            "Save the downloaded file (JSON or Markdown) locally.",
            "Upload to AI Mirror — the Perplexity parser handles both formats.",
        ),
        output_formats=["JSON", "Markdown", "PDF", "DOCX"],
        notes=[
            "Markdown export preserves citations inline — useful for audit trails.",
        ],
        docs_url="https://www.perplexity.ai/help-center",
    ),
    ExportPlatform(
        slug="local",
        name="Local Models (Ollama / Open WebUI / LM Studio / AnythingLLM)",
        icon="local",
        summary="Most local UIs expose a built-in export or store JSON in their data folder.",
        steps=_steps(
            "Open WebUI: open the chat → menu → Export Chat (Markdown or JSON).",
            "LM Studio: Chat → ⋮ menu → Export as JSON.",
            "AnythingLLM: Workspace → Export → choose JSON.",
            "Raw Ollama: history lives under ~/.ollama/history — copy the JSON files directly.",
            "Upload any of these into AI Mirror; the Local parser is tolerant to schema variants.",
        ),
        output_formats=["JSON", "Markdown"],
        notes=[
            "If your UI lacks an export, you can usually copy the SQLite/JSON datafile from its app-support folder.",
            "AI Mirror's local parser auto-detects OpenAI-style messages arrays.",
        ],
    ),
]


def build_export_guide() -> ExportGuide:
    return ExportGuide(
        version="2026.05",
        last_updated="2026-05-17",
        intro=(
            "Export your conversation history from any major AI platform, then drop the "
            "ZIP, JSON, or Markdown file into AI Mirror. Auto-detection handles the rest."
        ),
        footer_note=(
            "AI Mirror can ingest any of these exported JSON/ZIP/Markdown files directly. "
            "Everything stays on your machine."
        ),
        platforms=_PLATFORMS,
    )
