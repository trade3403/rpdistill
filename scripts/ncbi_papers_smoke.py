"""Real NCBI PMC search + summary, no article text or model weights."""
import json
from pathlib import Path
import tempfile
from rpdistill.papers import PaperCatalog, PaperQuery
from rpdistill.ncbi_papers import discover_with_source

with tempfile.TemporaryDirectory() as tmp:
    catalog = PaperCatalog(Path(tmp)/"db")
    query = PaperQuery(("malaria",), "2024-01-01", "2024-12-31", limit=3)
    stats = discover_with_source(query, catalog, source="ncbi-pmc")
    assert 0 < stats["inspected"] <= 3
    assert stats["inserted"] > 0
    assert stats["provider"] == "ncbi-pmc"
    assert all(p["eligibility"] == "pending_fulltext_license" and p["pmcid"]
               for p in catalog.list())
    print(json.dumps({"metadata_only": True, **stats}))
