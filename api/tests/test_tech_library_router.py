"""
test_tech_library_router.py — Router-level tests for /library endpoints.

Uses the shared `app_client` fixture (fresh DB, temp LIBRARY_PATH, no external deps).
"""
import io
import os
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def upload_lib(client, source="Beckhoff", reference="EL1008",
               doc_type="technical_manual", filename="manual.pdf",
               content=b"%PDF-1.4 test content"):
    fd = {
        "source":    (None, source),
        "reference": (None, reference),
        "doc_type":  (None, doc_type),
        "file":      (filename, io.BytesIO(content), "application/pdf"),
    }
    return client.post("/library/items/upload", files=fd)


# ── GET /library/items (empty) ────────────────────────────────────────────────

def test_list_items_empty(app_client):
    r = app_client.get("/library/items")
    assert r.status_code == 200
    assert r.json() == []


# ── POST /library/items/upload ────────────────────────────────────────────────

def test_upload_creates_record(app_client):
    r = upload_lib(app_client)
    assert r.status_code == 201
    body = r.json()
    assert body["manufacturer"] == "Beckhoff"
    assert body["product_id"] == "EL1008"
    assert body["doc_type"] == "technical_manual"
    assert body["filename"] == "manual.pdf"
    assert body["classification"] == "public"


def test_upload_file_written_to_disk(app_client, tmp_path):
    r = upload_lib(app_client, source="Siemens", reference="S7-300")
    assert r.status_code == 201
    filepath = r.json()["filepath"]
    assert os.path.isfile(filepath)


def test_upload_no_reference_optional(app_client):
    """Empty reference should be accepted — file stored under source dir only."""
    fd = {
        "source":   (None, "General"),
        "reference": (None, ""),
        "doc_type":  (None, "misc"),
        "file":      ("howto.pdf", io.BytesIO(b"content"), "application/pdf"),
    }
    r = app_client.post("/library/items/upload", files=fd)
    assert r.status_code == 201
    body = r.json()
    assert body["product_id"] == ""
    # File should be at {LIBRARY_PATH}/general/howto.pdf (no ref subdir).
    assert "general" in body["filepath"].lower()
    assert os.path.isfile(body["filepath"])


def test_upload_source_with_spaces_safe_path(app_client):
    r = upload_lib(app_client, source="Allen Bradley", reference="1756-L71")
    assert r.status_code == 201
    filepath = r.json()["filepath"]
    # Spaces replaced with underscores in directory name.
    assert "allen_bradley" in filepath.lower()


def test_upload_duplicate_filename_gets_suffix(app_client):
    upload_lib(app_client, filename="manual.pdf")
    r2 = upload_lib(app_client, filename="manual.pdf")
    assert r2.status_code == 201
    # Second upload gets a different filepath.
    r1_path = app_client.get("/library/items").json()[0]["filepath"]
    r2_path = r2.json()["filepath"]
    assert r1_path != r2_path


# ── GET /library/items (with data) ───────────────────────────────────────────

def test_list_items_after_upload(app_client):
    upload_lib(app_client, source="Beckhoff", reference="EL1008")
    upload_lib(app_client, source="Siemens", reference="S7-300", filename="s7.pdf")
    r = app_client.get("/library/items")
    assert len(r.json()) == 2


def test_list_items_filter_by_source(app_client):
    upload_lib(app_client, source="Beckhoff", reference="EL1008")
    upload_lib(app_client, source="Siemens", reference="S7-300", filename="s7.pdf")
    r = app_client.get("/library/items", params={"source": "Beckhoff"})
    items = r.json()
    assert len(items) == 1
    assert items[0]["manufacturer"] == "Beckhoff"


# ── GET /library/sources ──────────────────────────────────────────────────────

def test_list_sources(app_client):
    upload_lib(app_client, source="ISO")
    upload_lib(app_client, source="TUV", reference="", filename="tuv.pdf")
    r = app_client.get("/library/sources")
    assert r.status_code == 200
    names = {s["manufacturer"] for s in r.json()}
    assert "ISO" in names
    assert "TUV" in names


# ── DELETE /library/items/{id} ────────────────────────────────────────────────

def test_delete_item_removes_record_and_file(app_client):
    upload_r = upload_lib(app_client)
    item_id  = upload_r.json()["id"]
    filepath = upload_r.json()["filepath"]
    assert os.path.isfile(filepath)

    r = app_client.delete(f"/library/items/{item_id}")
    assert r.status_code == 204

    r2 = app_client.get("/library/items")
    assert not any(i["id"] == item_id for i in r2.json())
    assert not os.path.exists(filepath)


def test_delete_nonexistent_returns_404(app_client):
    r = app_client.delete("/library/items/ghost-id")
    assert r.status_code == 404


# ── Library mode (read-only) ──────────────────────────────────────────────────

def test_upload_blocked_in_library_mode(app_client):
    fd = {
        "source":   (None, "Beckhoff"),
        "doc_type": (None, "technical_manual"),
        "file":     ("x.pdf", io.BytesIO(b"data"), "application/pdf"),
    }
    r = app_client.post(
        "/library/items/upload",
        files=fd,
        headers={"X-Site-Mode": "library"},
    )
    assert r.status_code == 403


def test_delete_blocked_in_library_mode(app_client):
    item_id = upload_lib(app_client).json()["id"]
    r = app_client.delete(f"/library/items/{item_id}",
                          headers={"X-Site-Mode": "library"})
    assert r.status_code == 403


# ── _safe_path_component helper ───────────────────────────────────────────────

def test_safe_path_component_lowercases():
    from routers.tech_library import _safe_path_component
    assert _safe_path_component("Beckhoff") == "beckhoff"


def test_safe_path_component_replaces_spaces():
    from routers.tech_library import _safe_path_component
    assert _safe_path_component("Allen Bradley") == "allen_bradley"


def test_safe_path_component_strips_slashes():
    from routers.tech_library import _safe_path_component
    result = _safe_path_component("path/with\\slashes")
    assert "/" not in result
    assert "\\" not in result
