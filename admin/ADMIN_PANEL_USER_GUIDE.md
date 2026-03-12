# SupportPilot - Admin Panel User Guide

Welcome to the SupportPilot Admin Panel! This comprehensive guide will walk you through everything you need to know to manage your AI Voice Agents, from account creation to deployment and knowledge base management.

## Table of Contents
1. [Getting Started (Authentication)](#1-getting-started-authentication)
2. [Managing Agents (CRUD Operations)](#2-managing-agents-crud-operations)
   - [Viewing Your Agents](#viewing-your-agents)
   - [Creating a New Agent](#creating-a-new-agent)
   - [Using AI to Generate Prompts](#using-ai-to-generate-prompts)
   - [Seeding a Demo Agent](#seeding-a-demo-agent)
   - [Editing an Agent](#editing-an-agent)
   - [Deleting an Agent](#deleting-an-agent)
3. [Deploying Agents](#3-deploying-agents)
4. [Managing the Knowledge Base (RAG)](#4-managing-the-knowledge-base-rag)

---

## 1. Getting Started (Authentication)

The admin panel uses secure email and password authentication, backed by Google Cloud Firestore.

- **Registering:** Navigate to the `/auth/register/` page. Enter your email and a secure password to create an account.
- **Logging In:** Navigate to the `/auth/login/` page. Use your registered email and password to access your dashboard.
- **Logging Out:** Click the **Logout** button in the navigation bar to securely end your session.

---

## 2. Managing Agents (CRUD Operations)

The Admin Panel allows you to create, read, update, and delete (CRUD) configurations for your custom support AI voice agents.

### Viewing Your Agents (Read)
- Upon logging in, you will be directed to the **Agent List** dashboard.
- This page displays a list of all the AI agents you own.
- Click on any agent's name to view its detailed configuration.

### Creating a New Agent (Create)
1. From the Agent List dashboard, click the **Create Agent** button.
2. Fill out the Agent Configuration form:
   - **Name:** A descriptive name for your agent. **Validation Rule: Must be 1-100 characters long and contain only letters and numbers (no spaces).** Example: `BillingSupportAI`.
   - **Agent Key:** A unique, URL-safe identifier (e.g., `billing-support-ai`). If left blank, it will be automatically generated from the Name. **Validation Rule: Must be up to 100 characters long and contain only lowercase letters, numbers, and hyphens.**
   - **Description (Optional):** A brief summary of the agent's purpose. **Validation Rule: Maximum 500 characters.**
   - **Voice Name:** Select the AI voice tone (e.g., *Kore*, *Zephyr*).
   - **System Instruction (Optional):** The core prompt and rules the agent must follow. This controls the agent's persona and logic.
   - **Google Search (Optional):** Enable this so the agent can browse the web for answers. You can restrict the search to specific domains (e.g., `help.yourcompany.com`). **Validation Rule: Search domains list max length is 500 characters.**
   - **Knowledge Base (Optional):** Enable this to allow the agent to read your uploaded custom documents (RAG).
3. Click **Save** to create the agent.

### Using AI to Generate Prompts
Writing a good "System Instruction" can be difficult. The Admin Panel includes an AI Prompt Generator to help you:
1. On the Create or Edit Agent page, fill in the **Name**, **Description**, and any **Context** you have.
2. Click the **Generate Prompt** button.
3. Our integrated AI (powered by Gemini) will automatically write a highly effective, structured system instruction tailored for a real-time voice-based support agent. You can review and edit this prompt before saving.

### Seeding a Demo Agent
If you want to immediately see what a fully configured agent looks like:
1. On the Agent List dashboard, click the **Seed Demo Agent** button.
2. The system will instantly create a "SaaS Support" agent equipped with a comprehensive system instruction and pre-configured settings.

### Editing an Agent (Update)
1. Click on the agent you wish to modify from the Agent List.
2. Click the **Edit** button.
3. Update the fields as needed (e.g., altering the system instruction, toggling features, or changing the voice).
4. Click **Save Changes**.

### Deleting an Agent (Delete)
1. Open the details page for the agent you want to remove.
2. Click the **Delete** button.
3. **Warning:** This action is permanent. It will delete the agent's configuration and permanently erase its associated Knowledge Base (RAG corpus) and uploaded documents.
4. Confirm the deletion when prompted.

---

## 3. Deploying Agents

Once your agent is configured, you need to deploy it so it can start accepting real-time voice calls.

1. Navigate to the Details page of the configured Agent.
2. Click the **Deploy** button.
3. The Admin panel will programmatically package and deploy the agent as a scalable service to Google Cloud Run.
4. Once deployment succeeds, the system will display a success message and update the agent's profile with a **Service URL**. This URL is the public endpoint where your live application or frontend can connect to your voice agent.

---

## 4. Managing the Knowledge Base (RAG)

If you checked "Enable Knowledge Base" during the agent setup, you can upload custom documents (like PDFs or TXT files) for the AI to reference using Retrieval-Augmented Generation (RAG).

> **Note:** For a highly detailed guide dedicated specifically to the RAG feature, please see the `RAG_USER_GUIDE.md`.

### Adding Documents
1. Navigate to the Agent Details page.
2. Click the **Documents** button to open the Document Library.
3. In the "Upload New" section, select your file and click **Upload Document**.
4. The file is uploaded to a Vertex AI Corpus dedicated solely to this agent.

### Removing Documents
1. In the Document Library, locate the specific file in the "Uploaded Documents" list.
2. Click the red **Delete** button.
3. The document will be permanently removed from the agent's knowledge base.
