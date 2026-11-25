"""Real SacreBLEU corpus scoring; synthetic independent fixtures, not model quality."""
import json
from dataclasses import asdict
from pathlib import Path
import tempfile
from contextlib import closing
import hashlib

from rpdistill.datasets import DatasetStore,encoded,sha
from rpdistill.evaluation import freeze_benchmark,validate_benchmark,evaluate,QualityGate,write_new,read_json

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    store=DatasetStore(root/"db")
    row={"source_text":"Training-only sample.","source_sha256":sha(b"Training-only sample."),
         "split":"train","pmcid":"PMC999","attribution":{"doi":"10.1234/train"}}
    raw=encoded(row)
    manifest={"status":"candidate_snapshot","counts":{"train":1},"count":1,
              "payload_sha256":sha((raw+"\n").encode("ascii"))}
    version=sha(encoded(manifest).encode())
    manifest["version"]=version
    with closing(store.corpus.connect()) as db,db:
        db.execute("INSERT INTO dataset_versions VALUES (?,?)",(version,encoded(manifest)))
        db.execute("INSERT INTO dataset_members VALUES (?,?,?)",(version,0,raw))
    rows=[{"id":"a","paper_id":"paper-a","pmcid":"PMC100","source":"The confidence interval is 95%. [12] x=2",
           "reference":"置信区间为95%。 [12] x=2","terms":[{"source":"confidence interval","targets":["置信区间"]}],
           "protected":["x=2"],"rights_note":"Synthetic authored fixture"},
          {"id":"b","paper_id":"paper-b","pmcid":"PMC101","source":"The sample was heated to 300 K.",
           "reference":"样品加热至300 K。","terms":[{"source":"sample","targets":["样品"]}],
           "rights_note":"Synthetic authored fixture"}]
    b=freeze_benchmark(root/"db",version,rows,review_note="Synthetic author-reviewed fixture")
    write_new(root/"benchmark.json",b)
    b=read_json(root/"benchmark.json")
    gate=QualityGate(min_cases=2,min_papers=2,min_numeric_cases=2,min_term_cases=2,min_protected_cases=1,
                     min_bleu=90,min_chrf=90,min_terminology=1,max_suspicious=0)
    good=evaluate(root/"db",b,[{"id":r["id"],"hypothesis":r["reference"]} for r in rows],gate=gate)
    bad=evaluate(root/"db",b,[{"id":"a","hypothesis":"区间90%。 [13] x=3"},{"id":"b","hypothesis":""}],gate=gate)
    assert good["automatic_gate_passed"] and not good["release_ready"]
    assert good["metrics"]["bleu"]>99 and good["metrics"]["chrf"]>99
    assert not bad["automatic_gate_passed"] and not bad["release_ready"]
    assert bad["metrics"]["numeric"]<1 and bad["metrics"]["protected"]==0
    assert not evaluate(root/"db",b,[{"id":r["id"],"hypothesis":r["reference"]} for r in rows])["automatic_gate_passed"]
    try:
        freeze_benchmark(root/"db",version,[rows[0]|{"pmcid":"PMC999"}],review_note="Fixture")
    except ValueError:
        pass
    else:
        raise AssertionError("paper leakage accepted")
    with closing(store.corpus.connect()) as db,db:
        db.execute("UPDATE dataset_members SET record='{}' WHERE version=?",(version,))
    try:
        validate_benchmark(root/"db",b)
    except ValueError:
        pass
    else:
        raise AssertionError("tampered snapshot accepted")
    print(json.dumps({"fixture":"synthetic authored references","identical_metrics":good["metrics"],
                      "corrupted_metrics":bad["metrics"],"good_gate_pass":True,"bad_gate_rejected":True,
                      "insufficient_coverage_rejected":True,"training_overlap_rejected":True,
                      "tampered_snapshot_rejected":True,"model_quality_test":False}))
