"""Bounded real Europe PMC metadata request; no full text or weights."""
from pathlib import Path
import tempfile
import json
from rpdistill.papers import PaperQuery, PaperCatalog, discover

with tempfile.TemporaryDirectory() as tmp:
    catalog = PaperCatalog(Path(tmp)/"db")
    query = PaperQuery(("malaria",), "2024-01-01", "2024-12-31", limit=3)
    stats = discover(query, catalog)
    assert 0 < stats["inspected"] <= 3
    assert stats["inserted"] > 0
    assert all(p["eligibility"] in ("blocked_metadata", "pending_fulltext_license") for p in catalog.list())
    print(json.dumps({"provider":"Europe PMC","metadata_only":True, **stats}))
