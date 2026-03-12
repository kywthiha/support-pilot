"""Views for agent management — CRUD + document management with auth."""

import os
import json
import tempfile
import logging

from django.shortcuts import render, redirect
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from .firestore_client import (
    list_agents,
    get_agent,
    create_agent,
    update_agent,
    delete_agent,
    check_agent_key_exists,
)
from .rag_manager import (
    create_rag_corpus,
    delete_rag_corpus,
    upload_document,
    list_documents,
    delete_document,
)
from .deployment_client import deploy_agent_service
from .forms import AgentForm, DocumentUploadForm, EmailLoginForm, EmailRegistrationForm

# The default SaaS support demo instruction
SAAS_DEMO_INSTRUCTION = """\
# Identity & Role
You are a live customer support agent for a SaaS software platform.
Your mission is to help users navigate the software interface, configure settings, troubleshoot issues, and accomplish tasks — using real-time voice conversation and live screen observation.
You support a wide range of software including ERP systems, cloud management consoles, hosting control panels, CRM platforms, and custom business applications.

# Core Capabilities
- **See**: You continuously receive a passive 1 FPS screen-share feed showing the customer's screen. You can usually understand what page they are on just by watching.
- **Hear & Speak**: You converse naturally in real-time with a warm, professional, and patient tone.
- **Think**: You reason about software workflows, settings, configurations, dashboards, and UI navigation.
- **Search**: (Via `google_search`) Look up official documentation, release notes, community forums, or known issues when needed.
- **Knowledge Base**: (Via `knowledge_base`) Search internal documentation, product guides, SOPs, and troubleshooting procedures uploaded for this agent.

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
1. **Greet & Listen**: Welcome the user warmly. Understand what they are trying to do in the software. Ask brief clarifying questions if necessary.
2. **Observe Screen**: Rely on your passive 1 FPS screen-share feed first.
   - Use your native vision to identify which page, module, or settings panel the user is viewing.
   - **ONLY call `analyze_screen` if the visual task is complex** (reading small error text, diagnosing detailed settings pages, reviewing data tables).
   - If the screen share is unclear, politely ask the user to adjust.
3. **Guide Step by Step**:
   - Walk the user through **ONE step at a time**. Never list multiple steps at once.
   - Be specific: refer to exact button names (e.g., 'Save' in the top right), menu items (e.g., 'Settings' in the sidebar), tabs, and locations on screen.
4. **Verify**:
   - After each step, confirm with the user verbally or visually via your passive feed.
   - Once confirmed, provide the next step.
5. **Wrap Up**:
   - Once the task is complete, summarize what was accomplished and ask if there is anything else.

# Crucial Guardrails
- **Customer Data Privacy**: Never ask the user to share sensitive information like passwords, API secrets, or payment details aloud.
- **Do Not Guess**: If you're unsure about a feature or setting, use `knowledge_base` and `google_search` rather than guessing.
- **Always On**: The user's screen share is continuously streaming. Never ask them to "start sharing."

# Error Handling
- If `analyze_screen` errors with NO_FRAME: "I can't see your screen just yet. Could you make sure your screen is being shared?"
- If `analyze_screen` returns ANALYSIS_FAILED: "I'm having a little trouble reading your screen. Could you hold still for a moment?"
"""

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------
def login_view(request):
    """Login with email and password."""
    if request.user.is_authenticated:
        return redirect("agent_list")

    if request.method == "POST":
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            password = form.cleaned_data["password"]
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get("next", "/")
                return redirect(next_url)
            else:
                form.add_error(None, "Invalid email or password.")
    else:
        form = EmailLoginForm()
    return render(request, "agents/auth/login.html", {"form": form})


def agent_register(request):
    """Register a new user with email and password by writing to Firestore."""
    if request.user.is_authenticated:
        return redirect("agent_list")

    if request.method == "POST":
        form = EmailRegistrationForm(request.POST)
        if form.is_valid():
            import uuid
            from django.contrib.auth.hashers import make_password
            from google.cloud import firestore
            
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password1"]
            
            # Hash password before saving to Firestore
            hashed_password = make_password(password)
            
            uid = str(uuid.uuid4())
            
            # Write directly to Firestore since we removed SQLite
            from .firestore_client import _get_db
            db = _get_db()
            db.collection("users").document(uid).set({
                "email": email,
                "password": hashed_password,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            
            # Rehydrate using our custom auth backend
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome, {email}!")
                return redirect("agent_list")
            else:
                messages.error(request, "Registration successful but auto-login failed.")
    else:
        form = EmailRegistrationForm()
    return render(request, "agents/auth/register.html", {"form": form})


def logout_view(request):
    """Log out the current user."""
    logout(request)
    return redirect("login")


# ---------------------------------------------------------------------------
# Ownership check helper
# ---------------------------------------------------------------------------
def _check_ownership(agent: dict, user) -> bool:
    """Return True if the user owns this agent."""
    return str(agent.get("owner_id", "")) == str(user.id)


# ---------------------------------------------------------------------------
# Agent CRUD views
# ---------------------------------------------------------------------------
@login_required
def agent_list_view(request):
    """List agents owned by the current user."""
    agents = list_agents(owner_id=request.user.id)
    return render(request, "agents/list.html", {"agents": agents})


@login_required
def agent_create(request):
    """Create a new agent."""
    if request.method == "POST":
        form = AgentForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if not data.get("agent_key"):
                data["agent_key"] = data["name"].lower().replace(" ", "-")
            
            if check_agent_key_exists(data["agent_key"]):
                form.add_error("agent_key", "This agent key is already in use. Please choose another one.")
            else:
                agent_id = create_agent(data, owner_id=request.user.id)
                messages.success(request, f"Agent '{data['name']}' created successfully.")
                return redirect("agent_detail", agent_id=agent_id)
    else:
        form = AgentForm()
    return render(request, "agents/create.html", {"form": form})


@login_required
def seed_demo_agent(request):
    """Programmatically seed a SaaS Support Demo agent for the logged-in user."""
    if request.method == "POST":
        agent_key = "saas-support-agent"
        if check_agent_key_exists(agent_key):
            import time
            agent_key = f"saas-support-agent-{int(time.time())}"
            
        data = {
            "name": "SaaSSupport",
            "agent_key": agent_key,
            "description": "Live voice support agent that helps users navigate SaaS software platforms — ERP systems, cloud consoles, hosting panels, and more.",
            "instruction": SAAS_DEMO_INSTRUCTION,
            "voice_name": "Zephyr",
            "search_domains": "cloud.google.com/docs",
            "is_demo": True,
        }
        agent_id = create_agent(data, owner_id=request.user.id)
        messages.success(request, "SaaS Demo Agent successfully seeded!")
        return redirect("agent_detail", agent_id=agent_id)
    return redirect("agent_list")


@login_required
def agent_detail(request, agent_id):
    """View agent details."""
    agent = get_agent(agent_id)
    if not agent:
        raise Http404("Agent not found")
    if not _check_ownership(agent, request.user):
        return HttpResponseForbidden("You don't have access to this agent.")
    return render(request, "agents/detail.html", {
        "agent": agent,
    })


@login_required
def agent_documents(request, agent_id):
    """Manage agent RAG documents."""
    agent = get_agent(agent_id)
    if not agent:
        raise Http404("Agent not found")
    if not _check_ownership(agent, request.user):
        return HttpResponseForbidden("You don't have access to this agent.")
    
    docs = []
    if agent.get("rag_corpus"):
        docs = list_documents(agent["rag_corpus"])

    return render(request, "agents/documents.html", {
        "agent": agent,
        "documents": docs,
        "upload_form": DocumentUploadForm(),
    })


@login_required
def agent_edit(request, agent_id):
    """Edit an agent."""
    agent = get_agent(agent_id)
    if not agent:
        raise Http404("Agent not found")
    if not _check_ownership(agent, request.user):
        return HttpResponseForbidden("You don't have access to this agent.")

    if request.method == "POST":
        form = AgentForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if not data.get("agent_key"):
                data["agent_key"] = data["name"].lower().replace(" ", "-")
            
            if check_agent_key_exists(data["agent_key"], exclude_id=agent_id):
                form.add_error("agent_key", "This agent key is already in use. Please choose another one.")
            else:
                update_agent(agent_id, data)
                messages.success(request, f"Agent '{data['name']}' updated successfully.")
                return redirect("agent_detail", agent_id=agent_id)
    else:
        form = AgentForm(initial={
            "name": agent.get("name", ""),
            "agent_key": agent.get("agent_key", ""),
            "description": agent.get("description", ""),
            "instruction": agent.get("instruction", ""),
            "voice_name": agent.get("voice_name", "Kore"),
            "google_search_enabled": agent.get("google_search_enabled", True),
            "search_domains": agent.get("search_domains", ""),
            "knowledge_enabled": agent.get("knowledge_enabled", True),
        })

    return render(request, "agents/edit.html", {"form": form, "agent": agent})


@login_required
def agent_delete(request, agent_id):
    """Delete an agent."""
    if request.method == "POST":
        agent = get_agent(agent_id)
        if not agent:
            raise Http404
        if not _check_ownership(agent, request.user):
            return HttpResponseForbidden("You don't have access to this agent.")
        # Clean up RAG corpus if exists
        if agent.get("rag_corpus"):
            delete_rag_corpus(agent["rag_corpus"])
        delete_agent(agent_id)
        messages.success(request, f"Agent '{agent.get('name')}' deleted.")
        return redirect("agent_list")
    raise Http404


@login_required
def agent_deploy(request, agent_id):
    """Programmatically deploy or update the agent on Cloud Run."""
    agent = get_agent(agent_id)
    if not agent:
        raise Http404
    if not _check_ownership(agent, request.user):
        return HttpResponseForbidden("You don't have access to this agent.")

    if request.method == "POST":
        try:
            # We enforce a URL-safe agent key, fallback to ID if missing
            agent_key = agent.get("agent_key") or agent_id[:20]
            service_url = deploy_agent_service(agent_id, agent_key)
            
            # Save the service URL to the agent document
            update_agent(agent_id, {"service_url": service_url})
            messages.success(request, f"Agent successfully deployed to Cloud Run! Available at: {service_url}")
        except Exception as e:
            logger.exception("Deploy failed")
            messages.error(request, f"Deployment failed: {e}")
            
    return redirect("agent_detail", agent_id=agent_id)


@login_required
def agent_upload_document(request, agent_id):
    """Upload a document to an agent's RAG corpus."""
    if request.method != "POST":
        return redirect("agent_documents", agent_id=agent_id)

    agent = get_agent(agent_id)
    if not agent:
        raise Http404("Agent not found")
    if not _check_ownership(agent, request.user):
        return HttpResponseForbidden("You don't have access to this agent.")

    form = DocumentUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Invalid file upload.")
        return redirect("agent_documents", agent_id=agent_id)

    # Create RAG corpus if agent doesn't have one yet
    if not agent.get("rag_corpus"):
        corpus_name = create_rag_corpus(f"agent-{agent_id}-{agent.get('name', 'unnamed')}")
        update_agent(agent_id, {"rag_corpus": corpus_name})
        agent["rag_corpus"] = corpus_name

    # Save uploaded file to temp and upload to RAG
    uploaded_file = request.FILES["file"]
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=os.path.splitext(uploaded_file.name)[1],
    ) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        upload_document(
            corpus_name=agent["rag_corpus"],
            file_path=tmp_path,
            display_name=uploaded_file.name,
        )
        messages.success(request, f"Document '{uploaded_file.name}' uploaded.")
    except Exception as exc:
        logger.error("Document upload failed: %s", exc)
        messages.error(request, f"Upload failed: {exc}")
    finally:
        os.unlink(tmp_path)

    return redirect("agent_documents", agent_id=agent_id)


@login_required
def agent_delete_document(request, agent_id, doc_name):
    """Delete a document from an agent's RAG corpus."""
    agent = get_agent(agent_id)
    if not agent:
        raise Http404
    if not _check_ownership(agent, request.user):
        return HttpResponseForbidden("You don't have access to this agent.")
    if request.method == "POST":
        delete_document(doc_name)
        messages.success(request, "Document deleted.")
    return redirect("agent_documents", agent_id=agent_id)


@login_required
@require_POST
def generate_system_prompt(request):
    """Generate a system prompt using Gemini based on agent name and description."""
    try:
        data = json.loads(request.body)
        name = data.get("name", "")
        description = data.get("description", "")
        context = data.get("context", "")

        if not name:
            return JsonResponse({"error": "Agent name is required to generate a prompt."}, status=400)

        # Build enhanced generation prompt
        prompt = (
            "You are an expert prompt engineer specializing in real-time customer support AI agents "
            "for SaaS software platforms (ERP systems, cloud management consoles, hosting panels, "
            "CRM platforms, custom business applications, etc.).\n\n"
            "Write a highly effective, production-ready system instruction for a live, real-time "
            "voice-based customer support AI agent.\n\n"
            f"Agent Name: {name}\n"
        )
        if description:
            prompt += f"Agent Target / Description: {description}\n"
        if context:
            prompt += f"Additional Context: {context}\n"
        
        prompt += (
            "\n## Agent Platform Context\n"
            "The agent operates in a live voice call environment with these capabilities:\n"
            "- Receives a passive 1 FPS screen share of the caller's screen\n"
            "- Talks to customers via real-time voice (NOT text chat)\n"
            "- Has access to the following tools:\n\n"
            "### Available Tools (MUST include usage guidance for ALL of these)\n"
            "1. **`google_search`** — Search the web for official documentation, help articles, "
            "community forums, release notes, and known issues. The agent should ALWAYS search "
            "before answering technical questions from memory.\n"
            "2. **`knowledge_base`** (RAG) — Search internal/uploaded documentation, product guides, "
            "SOPs, and troubleshooting procedures specific to this product. This should be the "
            "FIRST source of truth — check before searching externally. Combine with google_search "
            "for the most complete answer.\n"
            "3. **`analyze_screen`** — Analyze the customer's screen in detail. The passive 1 FPS feed "
            "is usually sufficient, so ONLY call this for complex visual tasks (small text, dense "
            "settings, error messages, data tables).\n"
            "4. **`send_copy_text`** — Send text (URLs, IDs, API keys, config snippets, code) to the "
            "customer's clipboard. Do NOT use for step-by-step guides.\n\n"
            "## Required Sections in Output\n"
            "Write the system instruction with these sections:\n"
            "1. **Identity & Role** — Who the agent is and what software/product it supports\n"
            "2. **Core Capabilities** — See, Hear & Speak, Think, Search, Knowledge Base\n"
            "3. **Tool Usage Guide** — Detailed guidance for EACH tool: google_search, knowledge_base, "
            "analyze_screen, send_copy_text. When to use each, how to use them effectively, and "
            "how to combine them.\n"
            "4. **Voice-Only & Conversational Rules** — Voice-natural output, language matching, "
            "silent tool use, professional tone\n"
            "5. **Customer Support Flow** — Step-by-step flow: Greet, Observe, Guide, Verify, Wrap Up\n"
            "6. **Crucial Guardrails** — Privacy, no guessing (search first), screen share always on\n"
            "7. **Error Handling** — How to handle analyze_screen errors (NO_FRAME, ANALYSIS_FAILED)\n\n"
            "## Important Rules\n"
            "- Write the instruction as plain text with markdown headings, NOT wrapped in code blocks.\n"
            "- Make it specific to the agent's software domain if a description is provided.\n"
            "- Emphasize that the agent must ALWAYS use `knowledge_base` and `google_search` tools "
            "to find answers before relying on its base knowledge.\n"
            "- The instruction should be comprehensive but concise — aim for production quality.\n"
        )

        from google import genai
        
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        if project_id and project_id != "your-google-cloud-project-id":
            client = genai.Client(vertexai=True, project=project_id, location="global")
        else:
            client = genai.Client()
            
        observe_model = os.environ.get("OBSERVE_MODEL", "gemini-3-flash-preview")
        response = client.models.generate_content(
            model=observe_model,
            contents=prompt,
        )

        generated_text = response.text.strip()
        # Strip potential markdown backticks if the model ignores the instruction
        if generated_text.startswith("```") and generated_text.endswith("```"):
            lines = generated_text.split("\n")
            generated_text = "\n".join(lines[1:-1])

        return JsonResponse({"prompt": generated_text})

    except Exception as e:
        logger.exception("Failed to generate system prompt")
        return JsonResponse({"error": str(e)}, status=500)
