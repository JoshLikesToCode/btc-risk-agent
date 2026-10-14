import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore

from btc_risk.ingest.pipeline import chunk_documents, ingest, load_sources
from btc_risk.web import html_to_text, is_allowed


def test_corpus_chunks_have_stable_unique_ids(tmp_path):
    docs = load_sources(["corpus"])
    chunks = chunk_documents(docs)
    ids = [c.metadata["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)) > 3
    assert ids == [c.metadata["chunk_id"] for c in chunk_documents(load_sources(["corpus"]))]
    assert all(i.startswith("doc:") for i in ids)


def test_ingest_is_idempotent():
    store = InMemoryVectorStore(DeterministicFakeEmbedding(size=16))
    n1 = ingest(["corpus"], store)
    n2 = ingest(["corpus"], store)
    assert n1 == n2
    assert len(store.store) == n1  # same ids replaced, not duplicated


def test_pdf_loading_is_page_aware(tmp_path):
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(200, 200)
    pdf = tmp_path / "blank.pdf"
    with open(pdf, "wb") as f:
        w.write(f)
    docs = load_sources([str(pdf)])
    assert docs[0].metadata == {"source": "blank", "page": 1}
    assert chunk_documents(docs) == []  # blank pages produce no chunks


def test_unsupported_file_type_rejected(tmp_path):
    bad = tmp_path / "x.exe"
    bad.write_text("x")
    with pytest.raises(ValueError):
        from btc_risk.ingest.pipeline import load_file

        load_file(bad)


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://home.treasury.gov/news", True),
        ("https://www.fatf-gafi.org/x", True),
        ("https://evil.example/treasury.gov", False),
        ("https://treasury.gov.evil.example/", False),
        ("file:///etc/passwd", False),
    ],
)
def test_web_allowlist(url, ok):
    assert is_allowed(url) is ok


def test_html_to_text_drops_scripts():
    html = "<html><script>alert(1)</script><body><p>Hello</p><style>x{}</style></body></html>"
    assert html_to_text(html) == "Hello"
