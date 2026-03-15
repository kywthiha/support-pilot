# SupportPilot — Architecture Overview

## System Architecture

SupportPilot is built as a **multi-tenant SaaS platform** with two distinct planes, fully hosted on Google Cloud.

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

---

## Component Deep Dive

### 1. Control Plane — Django Admin Panel

The admin panel is a full-featured web dashboard deployed on **Cloud Run**. It enables non-technical support managers to manage the entire agent lifecycle.

| Capability               | Implementation                                                                         |
| ------------------------ | -------------------------------------------------------------------------------------- |
| **User Auth**            | Django auth with Firestore backend                                                     |
| **Agent CRUD**           | Create, edit, delete agents with custom instructions, voice, and model                 |
| **AI Prompt Generation** | One-click system prompt generation using Gemini, with built-in tool usage guidance     |
| **RAG Knowledge Base**   | Upload PDFs/docs → creates Vertex AI RAG Corpus → auto-linked to agent                 |
| **Cloud Deployment**     | One-click deploy to Cloud Run via `gcloud` API — each agent gets an isolated container |
| **Google Search Config** | Toggle on/off, set allowed search domains (e.g., `cloud.google.com/docs`)              |
| **Demo Seeder**          | Pre-configured SaaS demo agent with realistic system instruction                       |

### 2. Execution Plane — Agent Server

Each agent runs in its own **Cloud Run** container. On boot, it loads its config from **Firestore** and initializes the ADK agent with the appropriate tools, voice, and instruction.

| Component            | Technology                  | Role                                                        |
| -------------------- | --------------------------- | ----------------------------------------------------------- |
| **WebSocket Server** | FastAPI                     | Bidirectional proxy between React client and ADK            |
| **ADK Runner**       | `google.adk.runners.Runner` | Manages the live session lifecycle with Gemini              |
| **Agent**            | `google.adk.agents.Agent`   | Core agent with system instruction, tools, and model config |
| **Screen State**     | In-memory frame buffer      | Stores latest screen capture for `analyze_screen` tool      |

### 3. Customer Client — React Frontend

A React + Vite + TypeScript SPA that handles:

- **Microphone capture** → streams audio chunks over WebSocket
- **Screen sharing** → captures at 1 FPS, sends JPEG frames
- **Chat panel** → displays transcription and agent-pushed guides
- **Copy widget** → receives `send_copy_text` events and shows copy-to-clipboard UI

### 4. Agent Tools

| Tool                | Input                      | Output                                                                                                | Google Cloud Service         |
| ------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------- |
| `analyze_screen`    | Latest screen frame (JPEG) | Structured JSON: `page_title`, `visible_sections`, `user_focus`, `error_messages`, `navigation_hints` | Gemini Flash (GenAI SDK)     |
| `google_search`     | Query string               | Web search results from allowed domains                                                               | Google Search (ADK built-in) |
| `knowledge_base`    | Query string               | Relevant document chunks from uploaded PDFs                                                           | Vertex AI RAG                |
| `send_copy_text`    | Text/code string           | Pushes to client clipboard widget                                                                     | WebSocket (internal)         |
| `PreloadMemoryTool` | Session ID                 | Past conversation context                                                                             | Vertex AI Memory Bank        |

---

## Data Flow

### Agent Provisioning Flow

```mermaid
sequenceDiagram
    participant Admin as 👨‍💼 Admin User
    participant Django as Django Admin (Cloud Run)
    participant Firestore as Cloud Firestore
    participant RAG as Vertex AI RAG
    participant CloudRun as Cloud Run API

    Admin->>Django: Create new agent (name, instruction, voice, model)
    Django->>Firestore: Save agent config document

    Admin->>Django: Upload knowledge base documents (PDFs)
    Django->>RAG: Create RAG corpus + import files
    Django->>Firestore: Save RAG corpus ID to agent config

    Admin->>Django: Click "Deploy to Cloud Run"
    Django->>CloudRun: gcloud run deploy (agent image + env vars)
    CloudRun-->>Django: Return service URL
    Django->>Firestore: Save deployment URL
    Django-->>Admin: Show live agent URL
```

### Live Support Session Flow

```mermaid
sequenceDiagram
    participant User as 👤 Customer
    participant React as React Frontend
    participant FastAPI as FastAPI (WebSocket)
    participant ADK as ADK Agent
    participant Gemini as Gemini Live API
    participant Tools as Agent Tools

    User->>React: Open support page, grant mic + screen
    React->>FastAPI: Open WebSocket (wss://)
    FastAPI->>ADK: Initialize Runner with Firestore config
    ADK->>Gemini: Open Live API session (audio + video)

    loop Continuous Support
        React->>FastAPI: Stream audio + screen frames (1fps)
        FastAPI->>ADK: Forward media
        ADK->>Gemini: Interleaved audio/video input

        Note over Gemini: Agent decides to use tools or respond

        alt Screen guidance needed
            Gemini->>ADK: analyze_screen()
            Tools-->>ADK: ScreenAnalysis JSON
            ADK->>Gemini: Structured screen context
        end

        alt Documentation lookup
            Gemini->>ADK: knowledge_base(query)
            ADK->>Tools: Search Vertex AI RAG
            Tools-->>ADK: Relevant doc chunks
        end

        alt Send copyable text
            Gemini->>ADK: send_copy_text(text)
            ADK->>FastAPI: Push via WebSocket
            FastAPI->>React: Display copy widget
        end

        Gemini-->>ADK: Streaming voice response
        ADK-->>FastAPI: Audio output chunks
        FastAPI-->>React: Play agent voice

        Note over User, React: User can interrupt at ANY time (barge-in)
    end
```

---

## Google Cloud Services Used

| Service                   | Usage                                                                | Why                                                   |
| ------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------- |
| **Cloud Run**             | Hosts admin panel + each deployed agent as isolated containers       | Serverless, auto-scaling, per-agent isolation         |
| **Cloud Firestore**       | Stores agent configs, user accounts, and sessions                    | Real-time, schemaless, single database for everything |
| **Vertex AI RAG**         | Knowledge base — uploaded PDFs are chunked, embedded, and searchable | Grounded answers from internal documentation          |
| **Vertex AI Memory Bank** | Cross-session memory — remembers users across visits                 | Continuity without repetition                         |
| **Gemini Live API**       | Core voice + vision processing — real-time, interruptible            | Native barge-in, interleaved audio/video              |
| **Gemini Flash**          | Screen analysis — converts screenshots to structured data            | Fast inference for UI understanding                   |
| **Cloud Build**           | Docker image builds (via GitHub Actions and deploy.sh)               | Automated CI/CD                                       |
| **Container Registry**    | Stores agent Docker images                                           | Image management for Cloud Run                        |

---

## Deployment Architecture

```mermaid
graph LR
    classDef run fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#1e293b
    classDef registry fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#1e293b
    classDef ci fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#1e293b

    GH["GitHub Repository"]:::ci
    GHA["GitHub Actions<br>(deploy.yml)"]:::ci
    CB["Cloud Build"]:::registry
    GCR["Container Registry<br>(Agent Image)"]:::registry

    AdminCR["Cloud Run<br>Admin Panel"]:::run
    Agent1["Cloud Run<br>Agent: GCP-Support"]:::run
    Agent2["Cloud Run<br>Agent: ERP-Help"]:::run
    Agent3["Cloud Run<br>Agent: Custom"]:::run

    GH -->|"push to main"| GHA
    GHA -->|"build agent image"| CB
    CB -->|"push image"| GCR
    GHA -->|"deploy from source"| AdminCR

    AdminCR -->|"Deploy (Cloud Run API)"| Agent1
    AdminCR -->|"Deploy (Cloud Run API)"| Agent2
    AdminCR -->|"Deploy (Cloud Run API)"| Agent3

    GCR -.->|"Image source"| Agent1
    GCR -.->|"Image source"| Agent2
    GCR -.->|"Image source"| Agent3
```

Each agent is deployed as an **isolated Cloud Run service** with its own:

- System instruction and persona
- Gemini model configuration
- Voice selection (Kore, Puck, Charon, etc.)
- Google Search domains
- RAG knowledge base (Vertex AI corpus)
- Memory bank session storage
