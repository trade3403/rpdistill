"""Actual official PMC discovery and bounded full-text acquisition, temporary only."""
import json
from pathlib import Path
import tempfile
from rpdistill.papers import PaperCatalog, PaperQuery
from rpdistill.ncbi_papers import discover_with_source
from rpdistill.fulltext import FulltextLibrary

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    catalog = PaperCatalog(root/"db")
    stats = discover_with_source(PaperQuery(("malaria",),"2024-01-01","2024-12-31",limit=10),
                                 catalog,source="ncbi-pmc")
    assert stats["inserted"] > 0
    lib = FulltextLibrary(root/"db",root/"xml")
    result = lib.download(catalog.list(), max_bytes=8*1024*1024, limit=10)
    print(json.dumps({"discovery":stats,"download":result,
                      "statuses":[{k:r.get(k) for k in ("pmcid","status","reason","size","license")}
                                  for r in lib.list()]}))
    assert result["saved"] > 0
    assert all(r["status"] != "training_ready" for r in lib.list())
