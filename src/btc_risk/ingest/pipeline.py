"""Document ingestion: files/URLs -> chunks with stable ids -> vector store."""

import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from btc_risk.web import fetch_text

SUPPORTED = {".md", ".txt", ".pdf"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def load_file(path: Path) -> list[Document]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [
            Document(
                page_content=page.extract_text() or "",
                metadata={"source": path.stem, "page": i + 1},
            )
            for i, page in enumerate(reader.pages)
        ]
    if suffix in (".md", ".txt"):
        return [
            Document(page_content=path.read_text(encoding="utf-8"), metadata={"source": path.stem})
        ]
    raise ValueError(f"unsupported file type: {path}")


def load_url(url: str) -> list[Document]:
    return [
        Document(page_content=fetch_text(url), metadata={"source": _slug(url)[:80], "url": url})
    ]


def load_sources(sources: list[str]) -> list[Document]:
    docs: list[Document] = []
    for src in sources:
        if src.startswith(("http://", "https://")):
            docs.extend(load_url(src))
            continue
        p = Path(src)
        files = (
            sorted(f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED) if p.is_dir() else [p]
        )
        for f in files:
            docs.extend(load_file(f))
    return docs


def chunk_documents(docs: list[Document], size: int = 1000, overlap: int = 150) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
    chunks = [c for c in splitter.split_documents(docs) if c.page_content.strip()]
    counters: dict[str, int] = {}
    for c in chunks:
        key = _slug(str(c.metadata["source"]))
        counters[key] = counters.get(key, 0) + 1
        c.metadata["chunk_id"] = f"doc:{key}#{counters[key]}"
    return chunks


def ingest(sources: list[str], store: VectorStore) -> int:
    """Idempotent: chunk ids are deterministic, so re-ingesting a source replaces its chunks."""
    chunks = chunk_documents(load_sources(sources))
    if chunks:
        store.add_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
    return len(chunks)
