"""
rag.py — Retrieval-Augmented Generation (RAG) pipeline.

Provides document chunking, embedding via Ollama, and vector storage /
retrieval via ChromaDB.  Documents are stored per-user and tagged with a
*scope* (``"global"`` for persistent uploads or
``"conversation:<id>"`` for session-only uploads) so that search results
can be filtered appropriately for each request.
"""

import os

import chromadb
import httpx

# Ollama endpoint used for generating embeddings.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
# Embedding model served by Ollama; nomic-embed-text is a good default.
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")

# Characters per chunk when splitting document text.
CHUNK_SIZE = 1000
# Overlap between consecutive chunks to preserve context across boundaries.
CHUNK_OVERLAP = 150

# Number of nearest-neighbour chunks to retrieve per query.
TOP_K = 4
# Maximum cosine distance for a chunk to be considered relevant (0=identical, 1=unrelated).
DISTANCE_THRESHOLD = 0.45

# Lazily initialised ChromaDB collection (singleton).
_collection = None


# ── ChromaDB ───────────────────────────────────────────────────

def get_collection():
    """
    Return the shared ChromaDB collection, creating it on first access.

    Uses a module-level singleton so the persistent ChromaDB client is only
    opened once per process.  The collection uses cosine similarity so that
    distance scores are normalised between 0 and 1.

    :return: The ChromaDB ``Collection`` object for document chunks.
    """
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path="/app/data/chroma")
        _collection = client.get_or_create_collection(
            "documents",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ── Chunking ───────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """
    Split *text* into overlapping fixed-size chunks.

    Chunks are CHUNK_SIZE characters wide with a CHUNK_OVERLAP-character
    overlap so context is not lost at chunk boundaries.  Empty chunks
    (e.g. from trailing whitespace) are silently skipped.

    :param text: The document text to split.
    :type text: str
    :return: An ordered list of non-empty text chunks.
    :rtype: list[str]
    """
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start : start + CHUNK_SIZE].strip()
        if chunk:
            chunks.append(chunk)
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ── Embedding ──────────────────────────────────────────────────

async def embed(text: str) -> list[float]:
    """
    Generate a vector embedding for *text* using the Ollama embeddings API.

    :param text: The text to embed.
    :type text: str
    :return: A list of floats representing the embedding vector.
    :rtype: list[float]
    :raises httpx.HTTPStatusError: If the Ollama API returns a non-2xx status.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
        )
    resp.raise_for_status()
    return resp.json()["embedding"]


# ── Ingest ─────────────────────────────────────────────────────

async def ingest(doc_id: str, user_email: str, text: str, scope: str = "global") -> int:
    """
    Chunk, embed, and store a document in ChromaDB.

    Each chunk is stored with metadata so it can later be filtered by user
    and scope.  Chunk IDs follow the pattern ``"<doc_id>__<index>"``.

    :param doc_id: Unique identifier for the source document.
    :type doc_id: str
    :param user_email: Email of the user who owns this document.
    :type user_email: str
    :param text: Full extracted text of the document.
    :type text: str
    :param scope: Visibility scope — ``"global"`` for persistent uploads or
        ``"conversation:<id>"`` for session-scoped documents.
    :type scope: str
    :return: Number of chunks stored, or 0 if the text produced no chunks.
    :rtype: int
    """
    col = get_collection()
    chunks = chunk_text(text)
    if not chunks:
        return 0
    embeddings = [await embed(c) for c in chunks]
    col.add(
        ids=[f"{doc_id}__{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=chunks,
        metadatas=[{"doc_id": doc_id, "user_email": user_email, "scope": scope} for _ in chunks],
    )
    return len(chunks)


# ── Migration ──────────────────────────────────────────────────

def migrate_legacy_scopes() -> None:
    """
    Tag any pre-scope ChromaDB chunks as ``'global'`` (one-time, idempotent).

    Older document chunks stored before the scope field was introduced have
    no ``scope`` metadata key.  This function backfills them with
    ``"global"`` so scope-based filtering works correctly.  Safe to call on
    every startup — chunks that already have a scope are left untouched.
    """
    try:
        col = get_collection()
        results = col.get(include=["metadatas"])
        ids_to_update, new_metas = [], []
        for id_, meta in zip(results["ids"], results["metadatas"]):
            if not meta.get("scope"):
                ids_to_update.append(id_)
                new_metas.append({**meta, "scope": "global"})
        if ids_to_update:
            col.update(ids=ids_to_update, metadatas=new_metas)
    except Exception:
        pass


# ── Search ─────────────────────────────────────────────────────

async def search(
    user_email: str,
    query: str,
    top_k: int = TOP_K,
    conversation_id: str | None = None,
) -> tuple[list[str], list[str]]:
    """
    Retrieve the most relevant document chunks for a query.

    Embeds *query* and performs an approximate nearest-neighbour search
    against ChromaDB, filtering by user and scope.  When *conversation_id*
    is provided, chunks scoped to that conversation are included alongside
    globally-scoped chunks; otherwise only global chunks are searched.
    Results with a cosine distance >= DISTANCE_THRESHOLD are discarded.

    :param user_email: Email of the requesting user; used to restrict results
        to documents owned by that user.
    :type user_email: str
    :param query: The natural-language query to search for.
    :type query: str
    :param top_k: Maximum number of candidate chunks to request from ChromaDB
        before distance filtering.
    :type top_k: int
    :param conversation_id: Optional conversation ID; when set, chunks scoped
        to this conversation are included in the search.
    :type conversation_id: str | None
    :return: A tuple of ``(text_chunks, doc_ids)`` for chunks that pass the
        distance threshold.
    :rtype: tuple[list[str], list[str]]
    """
    col = get_collection()
    if col.count() == 0:
        return [], []
    query_emb = await embed(query)

    # Build the ChromaDB metadata filter based on scope visibility rules.
    if conversation_id:
        where: dict = {
            "$and": [
                {"user_email": {"$eq": user_email}},
                {"$or": [
                    {"scope": {"$eq": "global"}},
                    {"scope": {"$eq": f"conversation:{conversation_id}"}},
                ]},
            ]
        }
    else:
        where = {
            "$and": [
                {"user_email": {"$eq": user_email}},
                {"scope": {"$eq": "global"}},
            ]
        }

    try:
        results = col.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            where=where,
            include=["documents", "distances", "metadatas"],
        )
        if not results["documents"]:
            return [], []
        chunks, doc_ids = [], []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            # Only include chunks that are meaningfully close to the query.
            if dist < DISTANCE_THRESHOLD:
                chunks.append(doc)
                doc_ids.append(meta.get("doc_id", ""))
        return chunks, doc_ids
    except Exception:
        return [], []


# ── Deletion ───────────────────────────────────────────────────

def delete_chunks(doc_id: str) -> None:
    """
    Delete all ChromaDB chunks associated with a document.

    :param doc_id: The document ID whose chunks should be removed.
    :type doc_id: str
    """
    col = get_collection()
    col.delete(where={"doc_id": doc_id})
