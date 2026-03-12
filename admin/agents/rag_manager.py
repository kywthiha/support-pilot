"""Vertex AI RAG management — corpus and document operations."""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import vertexai
from vertexai import rag

logger = logging.getLogger(__name__)

# Load env variables explicitly for rag manager
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env')

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

if PROJECT_ID and LOCATION:
    vertexai.init(project=PROJECT_ID, location=LOCATION)


def create_rag_corpus(display_name: str) -> str:
    """Create a new Vertex AI RAG corpus and return its resource name."""
    corpus = rag.create_corpus(display_name=display_name)
    logger.info("Created RAG corpus: %s", corpus.name)
    return corpus.name


def delete_rag_corpus(corpus_name: str) -> None:
    """Delete a Vertex AI RAG corpus."""
    try:
        rag.delete_corpus(name=corpus_name)
        logger.info("Deleted RAG corpus: %s", corpus_name)
    except Exception as exc:
        logger.error("Failed to delete RAG corpus %s: %s", corpus_name, exc)


def upload_document(corpus_name: str, file_path: str, display_name: str) -> str:
    """Upload a document to a RAG corpus. Returns the file resource name."""
    rag_file = rag.upload_file(
        corpus_name=corpus_name,
        path=file_path,
        display_name=display_name,
    )
    logger.info("Uploaded document '%s' to corpus %s", display_name, corpus_name)
    return rag_file.name


def list_documents(corpus_name: str) -> list[dict[str, Any]]:
    """List all documents in a RAG corpus."""
    try:
        files = rag.list_files(corpus_name=corpus_name)
        return [
            {
                "name": f.name,
                "display_name": f.display_name,
            }
            for f in files
        ]
    except Exception as exc:
        logger.error("Failed to list documents for corpus %s: %s", corpus_name, exc)
        return []


def delete_document(file_name: str) -> None:
    """Delete a document from a RAG corpus."""
    try:
        rag.delete_file(name=file_name)
        logger.info("Deleted document: %s", file_name)
    except Exception as exc:
        logger.error("Failed to delete document %s: %s", file_name, exc)
