"""Small shared source loader for the standalone RAG lessons.

Retrieval algorithms stay in the notebooks so readers can inspect each step.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
from dotenv import dotenv_values
from ollama import Client


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "live_example" / "data" / "documents" / "content"
DEMO_IDS = (
    "FIN-YTD-2011",
    "FIN-RECEIVABLES-2011",
    "FIN-CASH-2011",
    "SCI-FORECAST-2011",
    "SCI-STOCK-2011",
    "SCI-QUALITY-2011",
)
NON_EVIDENCE_HEADINGS = {
    "Questions for retrieval evaluation",
    "Retrieval exercises",
    "RAG questions this note should answer",
}


def load_document(document_id: str, version: int = 1) -> dict:
    """Read one shipped, versioned Acme source; retain its path and metadata."""
    if document_id not in DEMO_IDS:
        raise ValueError(f"Unknown teaching document: {document_id}")
    path = SOURCE_DIR / f"{document_id}.v{version}.md"
    raw = path.read_text(encoding="utf-8")
    _, header, body = raw.split("---\n", 2)
    return {"metadata": json.loads(header), "body": body.strip(), "path": path}


def section_records(document_ids: tuple[str, ...] = DEMO_IDS) -> list[dict]:
    """Split at Markdown H2 boundaries, keeping a stable source reference."""
    records = []
    for document_id in document_ids:
        document = load_document(document_id)
        heading = "Introduction"
        section_lines = []
        section_number = 0
        for line in [*document["body"].splitlines(), "## END"]:
            if line.startswith("## "):
                if section_lines:
                    text = "\n".join(section_lines).strip()
                    if heading not in NON_EVIDENCE_HEADINGS:
                        records.append(
                            {
                                "id": f"{document_id}:v1:s{section_number:02d}",
                                "document_id": document_id,
                                "version": document["metadata"]["version"],
                                "heading": heading,
                                "text": text,
                                "source_path": document["path"].relative_to(ROOT).as_posix(),
                                "access_scope": document["metadata"]["access_scope"],
                                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            }
                        )
                    section_number += 1
                heading = line[3:].strip()
                section_lines = [] if line == "## END" else [line]
            else:
                section_lines.append(line)
    return records


def ollama_settings() -> tuple[str, str]:
    """Use process overrides, then the single root .env, then local defaults."""
    values = dotenv_values(ROOT / ".env")
    host = os.environ.get("OLLAMA_BASE_URL") or values.get("OLLAMA_BASE_URL") or "http://localhost:11434"
    model = os.environ.get("RAG_EMBED_MODEL") or values.get("RAG_EMBED_MODEL") or "qwen3-embedding:0.6b"
    return host, model


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed text with the same local model in every lesson; reject truncation."""
    host, model = ollama_settings()
    vectors = Client(host=host).embed(model=model, input=texts, truncate=False).embeddings
    return np.asarray(vectors, dtype=np.float32)
