#!/usr/bin/env python3
"""
e2e_smoke.py — End-to-end smoke test against the live Hexcaliper API.

Runs against http://localhost:8080/api by default.  Exercises every major
feature area: health, workspace, documents (upload/patch/scope/delete),
library (upload/list/delete), and site-config.

Usage:
    python3 tests/e2e_smoke.py [BASE_URL]
    # e.g.  python3 tests/e2e_smoke.py http://localhost:8080
"""
import io
import json
import sys
import textwrap
import traceback
import requests

BASE = (sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8080")
API  = f"{BASE}/api"

PASS = "✓"
FAIL = "✗"
_failures = []


def _check(name, condition, detail=""):
    if condition:
        print(f"  {PASS}  {name}")
    else:
        suffix = f" ({detail})" if detail else ""
        msg = f"{name}{suffix}"
        print(f"  {FAIL}  {msg}")
        _failures.append(msg)


def _status_check(name, r, expected):
    # Use ``is not None`` rather than truthiness: ``bool(requests.Response)``
    # delegates to ``.ok``, which is False for any 4xx/5xx status. Truthiness
    # therefore mislabels a correct 403/422 error response as "no response"
    # and fails the check for the opposite of the real reason.
    got = r.status_code if r is not None else "no response"
    _check(name, r is not None and r.status_code == expected,
           f"expected {expected}, got {got}")


def section(title):
    print(f"\n── {title} {'─' * (50 - len(title))}")


def req(method, path, timeout=30, **kwargs):
    url = f"{API}{path}"
    try:
        r = getattr(requests, method)(url, timeout=timeout, **kwargs)
        return r
    except requests.RequestException as e:
        print(f"  {FAIL}  REQUEST FAILED: {method.upper()} {url}: {e}")
        _failures.append(str(e))
        return None


# ─────────────────────────────────────────────────────────────────────────────

section("Health & config")

r = req("get", "/health")
_check("GET /health → 200", r and r.status_code == 200)

r = req("get", "/site-config")
_check("GET /site-config → 200", r and r.status_code == 200)
if r and r.ok:
    _check("site-config has public_library_mode flag",
           "public_library_mode" in r.json())

# ─────────────────────────────────────────────────────────────────────────────

section("GPU / system meters")

r = req("get", "/gpu")
_check("GET /gpu → 200", r and r.status_code == 200)

r = req("get", "/system")
_check("GET /system → 200", r and r.status_code == 200)

# ─────────────────────────────────────────────────────────────────────────────

section("Workspace — clients & projects")

r = req("post", "/workspace/clients", json={"name": "E2E Test Client"})
_check("POST /workspace/clients → 200/201", r and r.status_code in (200, 201))
client_id = r.json()["id"] if r and r.ok else None

r = req("get", "/workspace/clients")
_check("GET /workspace/clients → 200", r and r.status_code == 200)
if r and r.ok:
    names = [c["name"] for c in r.json()]
    _check("Created client appears in list", "E2E Test Client" in names)

project_id = None
if client_id:
    r = req("post", "/workspace/projects",
            json={"name": "E2E Test Project", "client_id": client_id})
    _check("POST /workspace/projects → 200/201", r and r.status_code in (200, 201))
    project_id = r.json()["id"] if r and r.ok else None

    r = req("get", "/workspace/projects", params={"client_id": client_id})
    _check("GET /workspace/projects for client → 200", r and r.status_code == 200)
    if r and r.ok:
        _check("Project appears in list for client",
               any(p["id"] == project_id for p in r.json()))

# ─────────────────────────────────────────────────────────────────────────────

section("Documents — upload, patch, scope change, delete")

pdf_content = b"%PDF-1.4\nThis is a test document for E2E testing of Hexcaliper."

r = req("post", "/documents",
        params={"doc_type": "standard"},
        files={"file": ("e2e_test.txt", io.BytesIO(pdf_content), "text/plain")},
        timeout=120,
        )
_check("POST /documents (global standard) → 200", r and r.status_code == 200)
doc_id = None
if r and r.ok:
    doc = r.json()
    doc_id = doc["id"]
    _check("Document has id", bool(doc_id))
    _check("scope_type is global", doc.get("scope_type") == "global")
    _check("classification is public (global standard)",
           doc.get("classification") == "public")

r = req("get", "/documents")
_check("GET /documents → 200", r and r.status_code == 200)
if r and r.ok:
    _check("Uploaded document appears in list",
           any(d["id"] == doc_id for d in r.json()))

if doc_id:
    r = req("patch", f"/documents/{doc_id}",
            json={"filename": "e2e_renamed.txt", "doc_type": "requirement"})
    _check("PATCH filename + doc_type → 200", r and r.status_code == 200)
    if r and r.ok:
        _check("Filename updated", r.json().get("filename") == "e2e_renamed.txt")
        _check("doc_type updated", r.json().get("doc_type") == "requirement")

if doc_id and client_id:
    r = req("patch", f"/documents/{doc_id}",
            json={"scope_type": "client", "scope_id": client_id})
    _check("PATCH scope global→client → 200", r and r.status_code == 200)
    if r and r.ok:
        _check("scope_type updated to client", r.json().get("scope_type") == "client")
        _check("classification auto-forced to client",
               r.json().get("classification") == "client")

    # Move back to global.
    r = req("patch", f"/documents/{doc_id}",
            json={"scope_type": "global", "scope_id": None, "classification": "public"})
    _check("PATCH scope client→global → 200", r and r.status_code == 200)

if doc_id:
    r = req("patch", f"/documents/{doc_id}", json={"doc_type": "not_a_type"})
    _status_check("PATCH invalid doc_type → 422", r, 422)

if doc_id:
    r = req("delete", f"/documents/{doc_id}")
    _check("DELETE /documents/{id} → 204", r and r.status_code == 204)
    r2 = req("get", "/documents")
    if r2 and r2.ok:
        _check("Deleted document gone from list",
               not any(d["id"] == doc_id for d in r2.json()))

# ─────────────────────────────────────────────────────────────────────────────

section("Library — upload, list, delete")

lib_content = b"%PDF-1.4\nManufacturer manual for E2E test."

r = req("post", "/library/items/upload",
        files={
            "source":   (None, "E2E Manufacturer"),
            "reference": (None, "E2E-001"),
            "doc_type": (None, "technical_manual"),
            "file":     ("e2e_manual.pdf", io.BytesIO(lib_content), "application/pdf"),
        })
_check("POST /library/items/upload → 201", r and r.status_code == 201)
lib_id = None
if r and r.ok:
    lib = r.json()
    lib_id = lib["id"]
    _check("Library item has id", bool(lib_id))
    _check("manufacturer is 'E2E Manufacturer'",
           lib.get("manufacturer") == "E2E Manufacturer")
    _check("product_id is 'E2E-001'", lib.get("product_id") == "E2E-001")
    _check("classification is public", lib.get("classification") == "public")
    _check("source is 'manual'", lib.get("source") == "manual")

    _check("filepath returned in response", bool(lib.get("filepath")))

r = req("get", "/library/items")
_check("GET /library/items → 200", r and r.status_code == 200)
if r and r.ok:
    _check("Uploaded item appears in list",
           any(i["id"] == lib_id for i in r.json()))

# Upload without a reference (optional field).
r = req("post", "/library/items/upload",
        files={
            "source":    (None, "General"),
            "reference": (None, ""),
            "doc_type":  (None, "misc"),
            "file":      ("howto.pdf", io.BytesIO(b"how-to content"), "application/pdf"),
        })
_check("Upload with empty reference → 201", r and r.status_code == 201)
general_id = r.json()["id"] if r and r.ok else None

r = req("get", "/library/sources")
_check("GET /library/sources → 200", r and r.status_code == 200)
if r and r.ok:
    names = {s["manufacturer"] for s in r.json()}
    _check("'E2E Manufacturer' in sources", "E2E Manufacturer" in names)
    _check("'General' in sources", "General" in names)

# Library mode blocks write operations.
r = req("post", "/library/items/upload",
        headers={"X-Site-Mode": "library"},
        files={
            "source":   (None, "Test"),
            "doc_type": (None, "misc"),
            "file":     ("x.pdf", io.BytesIO(b"data"), "application/pdf"),
        })
_status_check("Upload blocked in library mode → 403", r, 403)

if lib_id:
    r = req("delete", f"/library/items/{lib_id}")
    _check("DELETE /library/items/{id} → 204", r and r.status_code == 204)
    r2 = req("get", "/library/items")
    if r2 and r2.ok:
        _check("Deleted item gone from list",
               not any(i["id"] == lib_id for i in r2.json()))

# ─────────────────────────────────────────────────────────────────────────────

section("Cleanup")

if general_id:
    req("delete", f"/library/items/{general_id}")

if project_id:
    req("delete", f"/workspace/projects/{project_id}")

if client_id:
    req("delete", f"/workspace/clients/{client_id}")
    r = req("get", "/workspace/clients")
    if r and r.ok:
        _check("Test client deleted",
               not any(c["id"] == client_id for c in r.json()))

# ─────────────────────────────────────────────────────────────────────────────

print(f"\n{'─' * 55}")
total = len(_failures)
if total == 0:
    print(f"All checks passed.")
else:
    print(f"{total} check(s) FAILED:")
    for f in _failures:
        print(f"  {f}")
    sys.exit(1)
