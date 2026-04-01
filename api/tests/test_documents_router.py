"""
test_documents_router.py — Router-level tests for /documents endpoints.

Uses a TestClient backed by a fresh SQLite DB and all external services mocked.
"""
import io
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

USER = "local@dev"   # default injected by the router from CF header


def upload(client, filename="test.txt", content=b"test content",
           doc_type="standard", scope="global", client_id=None, project_id=None):
    params = {"doc_type": doc_type}
    if client_id:  params["client_id"]  = client_id
    if project_id: params["project_id"] = project_id
    return client.post(
        "/documents",
        params=params,
        files={"file": (filename, io.BytesIO(content), "text/plain")},
    )


# ── GET /documents ────────────────────────────────────────────────────────────

def test_list_documents_empty(app_client):
    r = app_client.get("/documents")
    assert r.status_code == 200
    assert r.json() == []


def test_list_documents_after_upload(app_client):
    upload(app_client, "iec61508.pdf")
    r = app_client.get("/documents")
    assert r.status_code == 200
    docs = r.json()
    assert len(docs) == 1
    assert docs[0]["filename"] == "iec61508.pdf"


# ── POST /documents ───────────────────────────────────────────────────────────

def test_upload_returns_metadata(app_client):
    r = upload(app_client, "manual.pdf", doc_type="technical_manual")
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "manual.pdf"
    assert body["doc_type"] == "technical_manual"
    assert "id" in body


def test_upload_global_standard_classified_public(app_client):
    r = upload(app_client, "iso13849.pdf", doc_type="standard")
    assert r.json()["classification"] == "public"


def test_upload_global_non_standard_classified_client(app_client):
    r = upload(app_client, "contract.pdf", doc_type="contract")
    assert r.json()["classification"] == "client"


def test_upload_client_scope_forces_client_classification(app_client):
    # Create a client first.
    client_r = app_client.post("/workspace/clients", json={"name": "ACME"})
    cid = client_r.json()["id"]
    r = upload(app_client, "spec.pdf", doc_type="requirement", client_id=cid)
    body = r.json()
    assert body["classification"] == "client"
    assert body["scope_type"] == "client"


def test_upload_invalid_doc_type_falls_back_to_misc(app_client):
    r = upload(app_client, "file.pdf", doc_type="not_a_real_type")
    assert r.json()["doc_type"] == "misc"


# ── PATCH /documents/{id} ─────────────────────────────────────────────────────

def test_patch_filename(app_client):
    doc = upload(app_client, "old_name.pdf").json()
    r = app_client.patch(f"/documents/{doc['id']}",
                         json={"filename": "new_name.pdf"})
    assert r.status_code == 200
    assert r.json()["filename"] == "new_name.pdf"


def test_patch_doc_type(app_client):
    doc = upload(app_client, "doc.pdf", doc_type="misc").json()
    r = app_client.patch(f"/documents/{doc['id']}", json={"doc_type": "fmea"})
    assert r.status_code == 200
    assert r.json()["doc_type"] == "fmea"


def test_patch_invalid_doc_type_returns_422(app_client):
    doc = upload(app_client, "doc.pdf").json()
    r = app_client.patch(f"/documents/{doc['id']}", json={"doc_type": "banana"})
    assert r.status_code == 422


def test_patch_scope_global_to_client(app_client):
    client_r = app_client.post("/workspace/clients", json={"name": "Client X"})
    cid = client_r.json()["id"]
    doc = upload(app_client, "doc.pdf", doc_type="standard").json()
    assert doc["scope_type"] == "global"

    r = app_client.patch(f"/documents/{doc['id']}",
                         json={"scope_type": "client", "scope_id": cid})
    assert r.status_code == 200
    body = r.json()
    assert body["scope_type"] == "client"
    assert body["scope_id"] == cid
    # Moving to client scope forces classification to client.
    assert body["classification"] == "client"


def test_patch_scope_client_to_global(app_client):
    client_r = app_client.post("/workspace/clients", json={"name": "Client Y"})
    cid = client_r.json()["id"]
    doc = upload(app_client, "doc.pdf", client_id=cid).json()
    assert doc["scope_type"] == "client"

    r = app_client.patch(f"/documents/{doc['id']}",
                         json={"scope_type": "global", "scope_id": None,
                               "classification": "public"})
    assert r.status_code == 200
    assert r.json()["scope_type"] == "global"


def test_patch_public_classification_blocked_for_client_scope(app_client):
    client_r = app_client.post("/workspace/clients", json={"name": "Client Z"})
    cid = client_r.json()["id"]
    doc = upload(app_client, "doc.pdf", client_id=cid).json()

    r = app_client.patch(f"/documents/{doc['id']}",
                         json={"classification": "public"})
    assert r.status_code == 422


def test_patch_nonexistent_document_returns_404(app_client):
    r = app_client.patch("/documents/does-not-exist", json={"filename": "x.pdf"})
    assert r.status_code == 404


def test_patch_calls_update_chunk_scope_on_scope_change(app_client, mock_externals):
    import rag
    doc = upload(app_client, "doc.pdf").json()
    app_client.patch(f"/documents/{doc['id']}",
                     json={"scope_type": "global", "scope_id": None})
    rag.update_chunk_scope.assert_called()


# ── DELETE /documents/{id} ────────────────────────────────────────────────────

def test_delete_document(app_client):
    doc = upload(app_client, "to_delete.pdf").json()
    r = app_client.delete(f"/documents/{doc['id']}")
    assert r.status_code == 204
    # Confirm it's gone.
    docs = app_client.get("/documents").json()
    assert not any(d["id"] == doc["id"] for d in docs)


def test_delete_nonexistent_returns_404(app_client):
    r = app_client.delete("/documents/ghost-id")
    assert r.status_code == 404
