# RAG Knowledge Base User Guide

This guide explains how to use the **Retrieval-Augmented Generation (RAG)** feature in the SupportPilot Admin Panel to empower your real-time Voice Agents with custom, domain-specific knowledge.

## What is RAG?
RAG (Retrieval-Augmented Generation) allows your AI voice agents to search through internal documents, guidelines, and specific procedures that you upload. Instead of relying solely on general knowledge or web searches, the agent connects directly to a Google Cloud Vertex AI RAG Corpus, looks up the exact documents you provide, and gives accurate and context-aware answers to your customers.

---

## Step 1: Enabling Knowledge for an Agent

Before uploading documents, ensure that your agent is configured to use the Knowledge Base during its conversations:

1. **Log in** to the Admin Panel.
2. From your agent list on the home page, select an existing agent or click **Create Agent** to set up a new one.
3. In the agent configuration form (during creation or by clicking **Edit**), ensure the **"Enable Knowledge Base"** option is checked.
4. **Save** your changes.

> **Pro Tip:** In the agent's **System Instruction**, explicitly tell the agent when to use its knowledge base. 
> Example: *"Use the `knowledge_base` tool to search for our internal guidelines or specific store procedures when a customer asks about return policies."*

## Step 2: Accessing the Document Library

Each agent has its own dedicated Document Library where its assigned knowledge files are securely stored.

1. From the **Agent Details** page, locate and click the **Documents** button.
2. You will be taken to the **Document Library** for that specific agent.
3. This page monitors all the documents currently available to the agent via Google Cloud Vertex AI RAG.

## Step 3: Uploading Documents

You can upload files such as PDFs (`.pdf`) and plain text (`.txt`) containing internal guidelines, FAQs, workflows, or troubleshooting steps.

1. On the Document Library page, find the **Upload New** card on the left side.
2. Click **Choose File** to select a document from your computer.
3. Click the **Upload Document** button.
4. The system will securely process and upload the file into the Vertex AI RAG Corpus dedicated specifically to this agent.
5. Once uploaded, the file will appear in the **Uploaded Documents** list on the right, and the agent will immediately be capable of searching its contents during live voice calls.

## Step 4: Managing and Deleting Documents

If a guideline becomes outdated, you should remove it so the agent doesn't provide incorrect information based on old policies:

1. In the Document Library, locate the outdated document in the **Uploaded Documents** list.
2. Click the red **Delete** button next to the file.
3. Read the prompt and confirm the deletion. 
4. The document will be permanently removed from the agent's Vertex AI corpus and it will no longer be referenced in conversations.

---

## Best Practices for RAG Documents

To get the most reliable answers from your Voice Agents when they query the Knowledge Base, follow these document formatting guidelines:

- **Use Clear Headings:** Structure your PDFs or text files with clear, descriptive sections (e.g., "Return Policy", "How to Reset Password"). This helps the AI cleanly isolate the correct answer.
- **Keep it Relevant:** Only upload documents that are directly relevant to the tasks the agent handles. Too much unrelated information can dilute the search quality.
- **Break Large Files Down:** While Vertex AI RAG handles large files well, splitting massive manuals into focused, smaller documents (e.g., `shipping-policy.pdf`, `billing-faq.pdf`) can sometimes yield faster and more precise semantic searches.
- **Clean Text Formatting:** Avoid unstructured tables or messy images with text if possible. Standard paragraphs, lists, and headings are parsed and retrieved with the highest accuracy.
