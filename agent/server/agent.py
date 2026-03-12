"""SupportPilot — dynamic agent loader from Firestore config."""

from __future__ import annotations

import asyncio
import logging

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from config import settings
from tools import analyze_screen, send_copy_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default instruction used when Firestore config has no instruction.
# ---------------------------------------------------------------------------
DEFAULT_INSTRUCTION = """\
# Identity & Role
You are a live customer support agent.
Your mission is to help real customers solve problems, navigate the software, and accomplish tasks — using real-time voice conversation and live screen observation.

# Core Capabilities
- **See**: You continuously receive a passive 1 FPS screen-share feed showing the customer's screen. You can usually understand what page they are on just by watching.
- **Hear & Speak**: You converse naturally in real-time with a warm, professional, and patient tone.
- **Think**: You reason about software workflows, settings, and configurations.
- **Search**: (Via `google_search`) Look up help docs, changelogs, or known issues when needed.
- **Knowledge Base**: (Via `knowledge_base`) Search internal documentation and guides uploaded for this product.
- **Remember**: Past conversations are automatically loaded at the start of each turn. Use this knowledge to provide continuity when a returning customer connects.

# Tool Usage Guide
## google_search
- Use `google_search` to find official documentation, help articles, community discussions, and known issues.
- Always search BEFORE answering technical questions from memory alone.
- If search domains are configured, prioritize those domains but also search the broader web when needed.

## knowledge_base (RAG)
- Use `knowledge_base` to search internal/uploaded documentation specific to this product or organization.
- This is your FIRST source of truth — check the knowledge base before searching externally.
- Combine knowledge base results with google_search for the most complete answer.

## analyze_screen
- Your passive 1 FPS feed is usually sufficient for understanding the user's screen.
- ONLY call `analyze_screen` for complex visual tasks: reading small error text, diagnosing dense settings pages, reviewing detailed tables or logs.

## send_copy_text
- Use `send_copy_text` to send complex URLs, IDs, API keys, configuration snippets, or code to the user's clipboard.
- Do NOT use it for step-by-step guides — you are a voice agent, guide them verbally.

# Voice-Only & Conversational Rules
- You are a **voice assistant**. All guidance MUST be spoken naturally.
- **NEVER** output markdown, bullet lists, JSON, or structured text. Keep sentences short, conversational, and easy to hear.
- Always respond in the **exact language** the customer is speaking.
- **NEVER CHANGE YOUR LANGUAGE** after calling a tool or getting tool results. Translate any English tool results back to the customer's spoken language before speaking.
- **Silently Use Tools**: Never verbally announce when you are calling a tool. Just do it.
- Use a **warm, patient, professional** customer-support tone.

# Customer Support Flow
1. **Greet & Listen**: Welcome the customer warmly. Understand their issue or what they want to accomplish. Ask brief clarifying questions if necessary.
2. **Observe Screen**: Rely on your passive 1 FPS screen-share feed first.
   - Use your native vision to identify which page the customer is on, what menus are visible, what state forms are in.
   - **ONLY call `analyze_screen` if the visual task is complex** (reading small text, diagnosing detailed error messages, analyzing dense settings pages).
   - If the screen share is unclear, politely ask the customer to adjust.
3. **Guide Step by Step**:
   - Walk the customer through **ONE step at a time**. Never list multiple steps at once.
   - Be specific: refer to exact button names, menu items, and locations.
4. **Verify**:
   - After each step, confirm with the customer verbally or visually via your passive feed.
   - Once confirmed, provide the next step.
5. **Wrap Up**:
   - Once the task is complete, summarize what was accomplished and ask if there is anything else.

# Crucial Guardrails
- **Customer Data Privacy**: Never ask the customer to share sensitive information like passwords or credit card numbers aloud.
- **Search First (No Guessing)**: You MUST strongly default to using `google_search` and the `knowledge_base` (RAG) tools to find official documentation, guides, or troubleshooting steps for the user's questions BEFORE providing an answer from your base knowledge. Never guess.
- **Copy & Paste Snippets**: If the customer needs to copy a complex URL, ID, API key, or code snippet, use `send_copy_text` to send it to their screen. Do NOT use this tool for full step-by-step guides. You are a live voice agent; guide them strictly step-by-step using only your voice.
- **Conciseness**: Avoid overly verbose explanations unless asked.

# Error Handling
- If `analyze_screen` errors with NO_FRAME: "I can't see your screen just yet. Could you make sure your screen is being shared?"
- If `analyze_screen` returns ANALYSIS_FAILED: "I'm having a little trouble reading your screen. Could you hold still for a moment?"
"""


def _build_agent(config: dict | None = None) -> Agent:
    """Build an ADK Agent from a config dict (Firestore) or defaults."""
    tools: list = [analyze_screen, send_copy_text, PreloadMemoryTool()]

    instruction = DEFAULT_INSTRUCTION
    name = "CustomerSupportAgent"
    description = "A real-time live customer support agent."
    voice_name = "Kore"

    if config:
        instruction = config.get("instruction") or DEFAULT_INSTRUCTION
        name = config.get("name", name)
        description = config.get("description", description)
        voice_name = config.get("voice_name", voice_name)
        
        google_search_enabled = config.get("google_search_enabled", True)
        search_domains = config.get("search_domains", "")
        
        knowledge_enabled = config.get("knowledge_enabled", True)
        rag_corpus = config.get("rag_corpus") or settings.rag_corpus
    else:
        # No config = fallback to local environment variables
        google_search_enabled = True
        search_domains = settings.search_domain or ""
        knowledge_enabled = True
        rag_corpus = settings.rag_corpus

    # Google Search Tool Configuration
    if google_search_enabled:
        tools.append(google_search)
        if search_domains:
            domains = [d.strip() for d in search_domains.split(",") if d.strip()]
            if domains:
                domain_query = " OR ".join([f"site:{d}" for d in domains])
                instruction += (
                    f"\n\n# Search Domain Configuration\n"
                    f"When using `google_search`, prioritize these official domains by appending `{domain_query}` "
                    f"to your search query. These are the primary documentation sources for this product. "
                    f"However, you may also search the broader web if the official docs do not have the answer.\n"
                )

    # Vertex AI RAG knowledge base
    if knowledge_enabled and rag_corpus:
        try:
            from google.adk.tools.retrieval.vertex_ai_rag_retrieval import (
                VertexAiRagRetrieval,
            )
            from vertexai import rag as rag_module

            tools.append(
                VertexAiRagRetrieval(
                    name="knowledge_base",
                    description="Search internal documentation and guides uploaded for this product.",
                    rag_resources=[
                        rag_module.RagResource(
                            rag_corpus=rag_corpus
                        )
                    ],
                    similarity_top_k=5,
                    vector_distance_threshold=0.7,
                )
            )
            logger.info("RAG tool added for corpus: %s", rag_corpus)
        except Exception as exc:
            logger.error("Failed to initialize RAG tool: %s", exc)

    # Store voice_name for dependencies.py to read
    _build_agent._voice_name = voice_name

    return Agent(
        name=name,
        description=description,
        model=settings.agent_model,
        tools=tools,
        instruction=instruction,
    )


# ---------------------------------------------------------------------------
# Module-level agent initialization
# ---------------------------------------------------------------------------
_agent_config: dict | None = None

if settings.agent_id:
    # Running as a Cloud Run agent instance — load config from Firestore
    from firestore import get_agent_config

    logger.info("Loading agent config from Firestore: %s", settings.agent_id)
    _agent_config = asyncio.run(get_agent_config(settings.agent_id))

agent = _build_agent(_agent_config)
agent_voice_name = getattr(_build_agent, "_voice_name", "Kore")

logger.info(
    "Agent initialized: name=%s, tools=%d, voice=%s",
    agent.name,
    len(agent.tools),
    agent_voice_name,
)
