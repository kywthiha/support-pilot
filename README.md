# SupportPilot

> **See my screen. Hear my voice. Solve my problem.**

SupportPilot is a real-time, multimodal AI customer support agent that **sees your screen**, **hears your voice**, and **guides you step-by-step** through complex SaaS software — ERP systems, cloud consoles, admin panels, and more.

Most support bots are turn-based text chatbots. SupportPilot breaks the "text box" paradigm with a fully live, interruptible voice agent powered by Google's Gemini Live API and Agent Development Kit.

🏆 **Category:** Live Agents — [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com)

---

## ✨ Key Features

| Feature                           | Description                                                                                                              |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| 🎙️ **Live Voice Conversation**    | Natural, real-time voice interaction powered by Gemini Live API. No turn-taking — just talk.                             |
| 👁️ **Screen Vision**              | The agent can request a snapshot of your screen anytime to give precise guidance (using Gemini Flash to analyze the UI). |
| 🔊 **Barge-in / Interruption**    | Interrupt the agent mid-sentence — it stops immediately and listens. Natural conversation flow.                          |
| 📋 **Copy-to-Clipboard**          | Agent pushes text, code snippets, or config values directly to the user's screen for easy copy-paste.                    |
| 🔍 **Google Search (Grounded)**   | Searches official documentation domains in real-time. No hallucinations — answers grounded in real sources.              |
| 📚 **Knowledge Base (RAG)**       | Upload internal PDFs, SOPs, or manuals. The agent searches them via Vertex AI RAG for precise answers.                   |
| 🧠 **Session Memory**             | Uses Vertex AI Memory Bank. Users can return later and the agent remembers past interactions.                            |
| 🏗️ **Multi-Tenant Admin Panel**   | Django-based dashboard to create, configure, and deploy new agents — no code required.                                   |
| 🚀 **One-Click Cloud Deployment** | Deploy agents directly to Google Cloud Run from the admin panel UI.                                                      |
| 🤖 **AI Prompt Generator**        | Auto-generates system prompts with built-in tool usage guidance using Gemini.                                            |

---

## Visual Demo & Screenshots

Here are key screenshots showing SupportPilot in action.

<details open>
<summary>1. Live support session (screen share + voice guidance)</summary>

![Live session example](screenshots/live-session.png)

The agent sees your screen, hears your question, and points to the exact button.

</details>

<details open>
<summary>2. Admin dashboard – agent creation</summary>

![Admin create agent](screenshots/admin-dashboard-create.png)

Managers set persona, upload PDFs for RAG, pick voice, and deploy with one click.

</details>

<details open>
<summary>3. Architecture overview</summary>

![Architecture diagram](screenshots/architecture-diagram.png)

Client streams to FastAPI → Gemini Live API via ADK → Vertex AI + Cloud Run.

</details>

## 🎬 Links for Judges

| Resource                 | Link                                                         |
| ------------------------ | ------------------------------------------------------------ |
| **Demo Video**           | [YouTube Link](https://youtu.be/UU9l0fM66oA)                 |
| **GCP Deployment Proof** | [YouTube Link](https://youtu.be/sPj2fDGeI04)                 |
| **Architecture Diagram** | [architecture.md](architecture.md)                           |
| **Admin Panel Guide**    | [ADMIN_PANEL_USER_GUIDE.md](admin/ADMIN_PANEL_USER_GUIDE.md) |
| **RAG Guide**            | [RAG_USER_GUIDE.md](admin/RAG_USER_GUIDE.md)                 |
| **CI/CD Guide**          | [GITHUB_ACTIONS_DEPLOYMENT.md](GITHUB_ACTIONS_DEPLOYMENT.md) |

---

## 🏗️ Architecture

SupportPilot is designed as a **multi-tenant SaaS platform** with two planes:

- **Control Plane (Admin)** — Django dashboard for managing agents, knowledge bases, and deployments
- **Execution Plane (Agent)** — FastAPI + ADK server that handles live voice/vision sessions

```mermaid
flowchart LR
    classDef client fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#1e293b
    classDef server fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#1e293b
    classDef google fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#1e293b
    classDef adk fill:#f3f4f6,stroke:#4b5563,stroke-width:2px,color:#1e293b,stroke-dasharray: 5 5
    classDef admin fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#1e293b
    classDef bonus fill:#fef08a,stroke:#ca8a04,stroke-width:2px,color:#1e293b,stroke-dasharray: 5 5

    %% ── CI/CD Pipeline ──
    subgraph CICD ["CI/CD Pipeline (GitHub Actions)"]
        direction TB
        GHA["GitHub Actions<br>(Push to main)"]:::bonus
        CloudBuild["Google Cloud Build<br>(gcloud builds submit)"]:::bonus
        GCR[("Google Container Registry<br>(Base Agent Image)")]:::google

        GHA -->|"1. Triggers Build"| CloudBuild
        CloudBuild -->|"2. Pushes Image"| GCR
    end

    %% ── Control Plane ──
    subgraph ControlPlane ["Control Plane (Cloud Run)"]
        direction TB
        AdminUI["Django Admin Panel<br>(Deploy & Config)"]:::admin
    end

    %% ── Frontend ──
    subgraph Frontend ["Frontend (Client UI)"]
        direction TB
        UI["SupportPilot UI<br>(React/Vite)"]:::client
    end

    %% ── Backend ──
    subgraph Backend ["Execution Plane (Cloud Run Agents)"]
        direction TB
        WS["WebSocket Endpoint<br>(FastAPI Proxy)"]:::server
        LiveState["Live State Buffer<br>(Memory/Frames)"]:::server

        subgraph ADK_Framework ["Google Agent Development Kit (ADK)"]
            direction TB
            Queue["LiveRequestQueue"]:::adk
            Runner["ADK Runner<br>(Lifecycle Manager)"]:::adk
            Agent["Agent Setup & Context"]:::adk

            subgraph ToolBox ["Multimodal Agent Tools"]
                direction TB
                AnalyzeScreen["analyze_screen<br>(Visual UI Action)"]:::adk
                GoogleSearch["google_search"]:::adk
                KnowledgeBase["knowledge_base"]:::adk
                SendCopyText["send_copy_text"]:::adk
                PreloadMemory["PreloadMemoryTool"]:::adk
            end
        end

        %% Internal Execution Flow
        WS -->|"Updates Latest Frame"| LiveState
        WS -->|"Pushes Audio/Text"| Queue
        Queue <-->|"Streams IO"| Runner
        Runner -->|"Loads"| Agent
        Agent -->|"Executes"| ToolBox
        AnalyzeScreen -.->|"Reads Latest Frame"| LiveState
        Runner -->|"Yields Audio & Tool Events"| WS
    end

    %% ── Databases & External APIs ──
    subgraph GCP ["Google Cloud Databases & Models"]
        direction TB
        subgraph Databases ["Databases & Search"]
            Firestore[("Cloud Firestore<br>(Agent Configs)")]:::google
            VertexRAG[("Vertex AI RAG<br>(Knowledge Base)")]:::google
            MemoryBank[("Vertex AI Memory<br>(Session Context)")]:::google
        end

        subgraph Gemini ["Gemini Foundation Models"]
            LiveAPI{{"Gemini Live API<br>(gemini-live-audio)"}}:::google
            GenAI{{"Gemini 3 Flash<br>(Multimodal Vision)"}}:::google
        end
    end

    %% ── Connections ──

    %% CI/CD to Control Plane Flow
    GHA -->|"3. gcloud run deploy<br>(Sets BASE_AGENT_IMAGE)"| AdminUI
    AdminUI -.->|"4. Pulls Base Image"| GCR
    AdminUI -->|"5. Spawns Live Agents"| Backend

    %% Control Plane to GCP Flow
    AdminUI -->|"Saves Auth/Config"| Firestore
    AdminUI -->|"Uploads RAG Docs"| VertexRAG

    %% Client Flow
    UI <-->|"wss:// (Bidi Audio, Video @ 1fps, Tool Responses)"| WS

    %% Backend to GCP Flow
    Runner <-->|"Native Audio Stream"| LiveAPI
    Agent -.->|"Loads Config on Boot"| Firestore
    WS -->|"Saves Session on Disconnect"| MemoryBank
    PreloadMemory -.->|"Queries Session History"| MemoryBank

    %% Tool to GCP Flow
    AnalyzeScreen <-->|"Sends Frame → JSON Action"| GenAI
    KnowledgeBase <-->|"Semantic Search"| VertexRAG
    GoogleSearch -.->|"Grounded Web Search"| GCP
```

> 👉 [See the detailed architecture breakdown](architecture.md)

---

## 🛠️ Tech Stack (Google Cloud Native)

| Layer               | Technology                         | Purpose                                             |
| ------------------- | ---------------------------------- | --------------------------------------------------- |
| **AI Model**        | Gemini 2.5 Flash (Live API)        | Real-time voice + vision processing                 |
| **Agent Framework** | Google Agent Development Kit (ADK) | Agent lifecycle, tool execution, session management |
| **SDK**             | Google GenAI SDK                   | Gemini API access for screen analysis               |
| **Knowledge Base**  | Vertex AI RAG                      | PDF/document retrieval for grounded answers         |
| **Memory**          | Vertex AI Memory Bank              | Cross-session user context retention                |
| **Database**        | Cloud Firestore                    | Agent configuration storage                         |
| **Hosting**         | Google Cloud Run                   | Serverless container deployment (admin + agents)    |
| **Admin Backend**   | Django + Firestore                 | Agent management dashboard                          |
| **Agent Backend**   | FastAPI + WebSockets               | Real-time bidirectional communication               |
| **Frontend**        | React + Vite + TypeScript          | Customer-facing support UI                          |
| **CI/CD**           | GitHub Actions                     | Automated build and deployment pipeline             |
| **Container**       | Docker + Docker Compose            | Local development and production builds             |

### Third-Party Integrations

- **Google Cloud Platform** — Cloud Run, Firestore, Vertex AI (RAG + Memory Bank), Gemini API
- **React + Vite** — Frontend framework for the customer support UI

All third-party tools are used in accordance with their respective licenses and terms of service.

---

## 🚀 Spin-Up Instructions

### Option 1: Quick Local Run (Recommended for Local Dev)

The fastest way to get the agent running locally without needing Google Cloud credentials is using our pre-built Docker image.

**Step 1 — Get your Google AI Studio API Key:**
Go to [Google AI Studio](https://aistudio.google.com/) and create a free API key.

**Step 2 — Run the Docker container:**

```bash
docker run -p 8080:8080 \
  -e AGENT_MODEL="gemini-2.5-flash-native-audio-preview-12-2025" \
  -e OBSERVE_MODEL="gemini-3-flash-preview" \
  -e GOOGLE_API_KEY="<YOUR_GEMINI_API_KEY_FROM_GOOGLE_AI_STUDIO>" \
  -e GOOGLE_GENAI_USE_VERTEXAI=FALSE \
  kyawthihadev/support-agent:latest
```

**Step 3 — Access the application:**

Open your browser and visit: [http://localhost:8080/](http://localhost:8080/)

---

### Option 2: Deploy to Google Cloud

Use the included deployment script to push everything to Cloud Run.

#### Prerequisites for Deployment

1. **Python 3.11+** and **Node.js 18+** (with `pnpm`)
2. **Google Cloud CLI** (`gcloud`) — [Install Guide](https://cloud.google.com/sdk/docs/install)
3. A GCP project with billing enabled
4. Enable required APIs:
   ```bash
   gcloud services enable \
     run.googleapis.com \
     cloudbuild.googleapis.com \
     firestore.googleapis.com \
     aiplatform.googleapis.com
   ```

**Step 1 — Login and set your project:**

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

**Step 2 — Run the deployment script:**

```bash
chmod +x deploy.sh
./deploy.sh
```

This will:

1. Build the agent Docker image and push to Container Registry
2. Deploy the Django admin panel to Cloud Run
3. Output the live admin panel URL

**Step 3 — Grant IAM permissions for agent deployment:**

The admin panel needs permission to dynamically spin up Cloud Run containers. In the [IAM Console](https://console.cloud.google.com/iam-admin/iam), grant the **Compute Engine default service account** these roles:

- `Cloud Run Admin`
- `Service Account User`
- `Artifact Registry Administrator`
- `Service Usage Consumer`
- `Cloud Datastore User`

---

### Option 3: GitHub Actions CI/CD (Recommended for Admin Panel)

The repository includes a fully automated CI/CD pipeline. Pushing to `main` triggers:

1. Agent image build + push to Container Registry
2. Admin panel deployment to Cloud Run

For the quickest and most reliable setup of the Admin Panel, we strongly recommend forking this repository and using GitHub Actions.

**Important Pre-Deployment Step:** Before your first deployment, ensure you manually create a **Firestore Database** in **Native mode** within your Google Cloud project. Choose the **(default)** location for your database.

> 💡 **Once the Admin Panel is deployed**, you can dynamically create, configure, and manage as many Support Agents as you need directly through the Admin Panel UI without needing to redeploy code!

👉 [Read the full GitHub Actions Deployment Guide](GITHUB_ACTIONS_DEPLOYMENT.md)

---

## 🧪 Reproducible Testing (For Judges)

We strongly encourage judges to experience the real-time multimodal AI support agent!

### Quick Local Run

We already host the image on Docker Hub, so you can run the default support agent directly:
[kyawthihadev/support-agent](https://hub.docker.com/r/kyawthihadev/support-agent)

Run the following command in your local terminal:

```bash
docker run -p 8080:8080 \
  -e AGENT_MODEL="gemini-2.5-flash-native-audio-preview-12-2025" \
  -e OBSERVE_MODEL="gemini-3-flash-preview" \
  -e GOOGLE_API_KEY="<YOUR_GEMINI_API_KEY_FROM_GOOGLE_AI_STUDIO>" \
  -e GOOGLE_GENAI_USE_VERTEXAI=FALSE \
  kyawthihadev/support-agent:latest
```

Then, open your browser and visit:
[http://localhost:8080/](http://localhost:8080/)

### Live Demo Links

> **⚠️ Note:** These live demo links are hosted on a personal Google Cloud account. They may be temporarily unavailable if budget alerts or pricing limits are reached. If the links are down, please use the **Quick Local Run** method above.

- **Agent Interface (No authentication needed)**: https://agent-google-cloud-366697832591.us-east5.run.app  
  → Jump straight in to test voice + screen vision + real-time guidance (Google Cloud support focus).
- **Admin Panel (Requires quick registration)**: https://supportpilot-admin-366697832591.us-east5.run.app  
  → Register/login → Create a new agent → Get a shareable session link to test custom agents.

Both are auto-deployed to Google Cloud Run (stable URLs — won't change on updates). Tested 100% functional as of March 13, 2026.

### How to Test (5–10 Minutes)

1. **Open in Google Chrome** (works in other modern browsers too).
2. **Access the Agent Demo**:
   - Visit: https://agent-google-cloud-366697832591.us-east5.run.app (or your local URL: http://localhost:8080/)
   - (Or from admin panel: create agent → copy session URL and open it.)
3. **Grant Permissions**:
   - Allow **Microphone** and **Screen Recording** when prompted.
   - Privacy tip: Share only a specific tab/window (e.g., Google Cloud Console) instead of entire screen.
4. **Start the Session**:
   - Click **"Start Screen Share"** (or equivalent button).
   - Agent greets you via voice — you're live!
5. **Test Core Multimodal Features**:
   - **Vision / Screen Awareness**:
     - Share a complex SaaS page (e.g., Google Cloud Billing, IAM console, GitHub repo settings).
     - Ask: _"What page am I looking at right now?"_ or _"Analyze my screen — where is the 'Create budget alert' button?"_
     - Expect accurate description + step-by-step pointers based on 1 fps passive capture.
   - **Grounded RAG / Search**:
     - Ask: _"How do I deploy a Python app to Google Cloud Run?"_ or _"Search docs for setting up Cloud Run with custom domain."_
     - Agent uses `google_search` tool → provides grounded, up-to-date answer with sources if needed.
   - **Barge-in / Real-Time Interruption**:
     - Start a long response: _"Explain the full history of the internet from ARPANET to now."_
     - While agent is speaking, interrupt loudly: _"Stop — tell me about Python instead!"_
     - Agent should halt immediately and pivot seamlessly (Gemini Live API native support).
   - **Voice + Guidance Flow**:
     - Say naturally: _"I'm stuck in the GCP console trying to enable billing export — walk me through it step by step."_
     - Listen for voice responses + on-screen highlights/instructions.
6. **Optional: Create Custom Agent (Admin Panel)**:
   - Go to https://supportpilot-admin-366697832591.us-east5.run.app (or your local Admin Panel URL).
   - Register (email/password) → Click "Create Agent".
   - Configure (e.g., name, key and instruction) → Save → Deploy → Open the generated session URL.
   - Test same flows above with your custom setup.

### Troubleshooting Tips

- No audio? Check mic permissions + Chrome settings (chrome://settings/content/microphone).
- Screen share fails? Ensure tab/window is active; retry permissions.
- Latency? Normal for first connection (Gemini Live streaming); subsequent interactions are faster.
- Issues? Ensure you have set the `GOOGLE_API_KEY` correctly when running the Docker container.

This live setup lets you fully experience the "see-hear-speak" immersion without any code/install. Thank you for testing — feedback welcome!

---

## 📁 Repository Structure

```text
support-pilot/
├── admin/                          # Django Admin Panel
│   ├── agents/                     # Agent CRUD, RAG management, deployment
│   │   ├── templates/              # HTML templates (Jinja2)
│   │   ├── views.py                # Views + AI prompt generation
│   │   ├── forms.py                # Agent creation forms
│   │   └── models.py               # User model
│   ├── livecustomersupport/        # Django project settings
│   ├── ADMIN_PANEL_USER_GUIDE.md   # Admin panel documentation
│   ├── RAG_USER_GUIDE.md           # RAG knowledge base guide
│   ├── Dockerfile                  # Admin container
│   └── requirements.txt
│
├── agent/                          # AI Agent Server
│   ├── client/                     # React + Vite Frontend
│   │   ├── src/                    # React components (TypeScript)
│   │   └── dist/                   # Production build
│   ├── server/                     # FastAPI Backend
│   │   ├── agent.py                # ADK agent loader (from Firestore config)
│   │   ├── tools.py                # analyze_screen, send_copy_text, etc.
│   │   ├── main.py                 # FastAPI app factory
│   │   ├── config.py               # Pydantic settings
│   │   └── routes/                 # WebSocket, health, config endpoints
│   ├── Dockerfile                  # Agent container
│   └── requirements.txt
│
├── .github/workflows/deploy.yml    # CI/CD pipeline
├── deploy.sh                       # Manual deployment script
├── architecture.md                 # Detailed architecture breakdown
└── GITHUB_ACTIONS_DEPLOYMENT.md    # CI/CD setup guide
```

---

## 🔍 How It Works

### The Support Session Flow

```mermaid
sequenceDiagram
    participant User as 👤 Customer
    participant UI as React Frontend
    participant WS as FastAPI Server
    participant ADK as ADK Agent
    participant Gemini as Gemini Live API
    participant Tools as Agent Tools

    User->>UI: Opens support page, grants mic + screen
    UI->>WS: WebSocket connection (wss://)
    WS->>ADK: Initialize ADK Runner
    ADK->>Gemini: Open Live API session

    loop Real-time Support Session
        User->>UI: Speaks + shares screen (1 FPS)
        UI->>WS: Audio chunks + video frames
        WS->>ADK: Forward media stream
        ADK->>Gemini: Interleaved audio + video input

        alt Agent needs to search docs
            Gemini->>ADK: Tool call: google_search
            ADK->>Tools: Execute search
            Tools-->>ADK: Search results
            ADK->>Gemini: Tool response
        end

        alt Agent analyzes screen
            Gemini->>ADK: Tool call: analyze_screen
            ADK->>Tools: Capture latest 1FPS frame
            Tools->>GenAI: Send frame to Gemini Flash
            GenAI-->>Tools: Structured UI State JSON
            Tools-->>ADK: ScreenAnalysis JSON
            ADK->>Gemini: Structured screen context
        end

        alt Agent sends copyable text
            Gemini->>ADK: Tool call: send_copy_text
            ADK->>WS: Push text to client
            WS->>UI: Display copy popup
        end

        Gemini->>ADK: Voice response (streaming)
        ADK->>WS: Audio output chunks
        WS->>UI: Play agent voice
    end

    Note over User, Gemini: User can interrupt (barge-in) at any time
```

1. **Optimized Screen Capture** — The React client captures the screen at 1 FPS and buffers it on the server.
2. **On-Demand Vision Analysis** — The agent doesn't passively process every frame (which would be slow and expensive). Instead, it uses an `analyze_screen` tool to actively request the latest frame when it needs visual context.
3. **Dual-Model Approach** — The main voice loop runs on `gemini-live-2.5-flash-native-audio` (Live API), while the `analyze_screen` tool offloads the visual analysis to a separate `gemini-3-flash-preview` call, returning structured JSON (UI state, errors, etc.) back to the main agent.
4. **Interleaved I/O** — Audio and video flow seamlessly through the application architecture.
5. **Dynamic Agent Provisioning** — Each agent gets its own Cloud Run container with isolated config, tools, and knowledge base.
6. **Grounding via RAG + Search** — Prevents hallucinations by anchoring responses in uploaded documents and official documentation.

---

## 📝 Findings & Learnings

1. **Gemini Live API is remarkably responsive** — barge-in handling feels natural, almost human-like. The agent stops mid-word when interrupted.
2. **Screen vision at 1 FPS is sufficient** — for SaaS admin panels that don't change rapidly, one frame per second provides enough context for the agent to guide effectively.
3. **Tool orchestration matters** — giving the agent clear tool usage guidelines in the system instruction dramatically improves tool selection accuracy.
4. **RAG grounding eliminates hallucinations** — when the agent has access to uploaded documentation, it cites specific sections instead of guessing.
5. **Multi-tenant architecture scales well** — deploying each agent as an isolated Cloud Run service means one bad config doesn't affect others.

---

## 📄 License

This project was created for the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com) hackathon.

Built with ❤️ using Google Cloud, Gemini, and the Agent Development Kit.
