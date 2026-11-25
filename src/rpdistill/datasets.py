"""Immutable candidate datasets with deterministic provenance and split guards."""
from collections import Counter
from contextlib import closing
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .corpus import CorpusStore, POLICY_VERSION, PARSER_VERSION, quality, stable_split
from .fulltext import MAX_FILE
from .inference import PROMPT_VERSION, TranslationOptions
from .teachers import validate_id, validate_revision

SCHEMA = "candidate-dataset-v1"
SPLITS = ("train","validation","test")


def encoded(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(",",":"),allow_nan=False)


def sha(value):
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class DatasetGate:
    min_train: int = 10
    min_validation: int = 1
    min_test: int = 1
    max_pairs: int = 10000

    def __post_init__(self):
        for key in ("min_train","min_validation","min_test","max_pairs"):
            value = getattr(self,key)
            if type(value) is not int or not 1 <= value <= 100000:
                raise ValueError("invalid dataset count: "+key)
        if self.min_train+self.min_validation+self.min_test > self.max_pairs:
            raise ValueError("minimum counts exceed dataset capacity")


class DatasetStore:
    def __init__(self, db_path):
        self.corpus = CorpusStore(db_path)
        with closing(self.corpus.connect()) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS dataset_versions (
                version TEXT PRIMARY KEY, manifest TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS dataset_members (
                version TEXT NOT NULL REFERENCES dataset_versions(version),
                ordinal INTEGER NOT NULL, record TEXT NOT NULL,
                PRIMARY KEY(version,ordinal))""")
            db.execute("""CREATE TABLE IF NOT EXISTS dataset_text_splits (
                source_sha256 TEXT PRIMARY KEY, split TEXT NOT NULL)""")

    def create(self, model_id, revision, options, *, source="huggingface",
               gate=DatasetGate()):
        validate_id(model_id)
        validate_revision(revision)
        if source not in ("huggingface","modelscope"):
            raise ValueError("invalid teacher source")
        if not isinstance(options,TranslationOptions) or not isinstance(gate,DatasetGate):
            raise ValueError("invalid dataset options or gate")
        teacher = dict(source=source,model_id=model_id,revision=revision)
        spec = dict(schema=SCHEMA,teacher=teacher,options=asdict(options),
                    parser=PARSER_VERSION,prompt=PROMPT_VERSION,policy=POLICY_VERSION,
                    gate=asdict(gate))
        stats = Counter({s:0 for s in SPLITS})
        excluded = Counter()
        seen, files, records = set(),{},[]
        with closing(self.corpus.connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            query = db.execute("""SELECT c.record,s.record,f.record FROM corpus_pairs c
              JOIN corpus_segments s ON s.id=c.segment_id
              JOIN papers p ON p.pmcid=s.pmcid JOIN paper_fulltexts f ON f.pmcid=s.pmcid
              WHERE json_extract(p.record,'$.eligibility')='pending_fulltext_license'
              AND json_extract(f.record,'$.status')='downloaded_pending_content_review'
              AND json_extract(f.record,'$.sha256')=json_extract(s.record,'$.attribution.xml_sha256')
              AND json_extract(c.record,'$.status')='screened_candidate'
              ORDER BY s.pmcid,c.id""")
            for raw,raw_segment,raw_file in query:
                row,segment,full = map(json.loads,(raw,raw_segment,raw_file))
                if (row.get("teacher")!=teacher or row.get("options")!=spec["options"]
                    or row.get("prompt_version")!=PROMPT_VERSION
                    or row.get("policy_version")!=POLICY_VERSION
                    or row.get("parser_version")!=PARSER_VERSION):
                    excluded["other_configuration"]+=1
                    continue
                text = row["source_text"]
                key = sha(text.encode())
                split = stable_split(segment["pmcid"])
                if (any(row.get(k)!=segment.get(k) for k in
                        ("segment_id","pmcid","source_text","source_sha256","attribution","split"))
                    or key!=segment["source_sha256"] or segment["split"]!=split
                    or quality(text,row | {"status":"candidate"})
                    or row.get("quality_flags")!=[]):
                    excluded["invalid_candidate"]+=1
                    continue
                # Verify actual current fulltext on disk once per paper.
                pmcid = segment["pmcid"]
                if pmcid not in files:
                    try:
                        path=Path(full["path"])
                        files[pmcid]=(not path.is_symlink() and path.stat().st_size==full["size"]
                          and path.stat().st_size<=MAX_FILE and sha(path.read_bytes())==full["sha256"])
                    except (OSError,KeyError):
                        files[pmcid]=False
                if not files[pmcid]:
                    excluded["invalid_fulltext"]+=1
                    continue
                prior=db.execute("SELECT split FROM dataset_text_splits WHERE source_sha256=?",(key,)).fetchone()
                if prior and prior[0]!=split:
                    excluded["cross_version_split_conflict"]+=1
                    continue
                if key in seen:
                    excluded["duplicate"]+=1
                    continue
                if len(records)>=gate.max_pairs:
                    excluded["capacity"]+=1
                    break
                seen.add(key)
                records.append(row)
                stats[split]+=1
            required={"train":gate.min_train,"validation":gate.min_validation,"test":gate.min_test}
            missing={s:required[s]-stats[s] for s in SPLITS if stats[s]<required[s]}
            if missing:
                return {"status":"insufficient_candidates","counts":dict(stats),
                        "missing":missing,"excluded":dict(excluded),"training_ready":False}
            payload = "".join(encoded(row)+"\n" for row in records).encode("ascii")
            manifest = spec | {"counts":dict(stats),"count":len(records),
                "payload_sha256":sha(payload),"status":"candidate_snapshot",
                "training_ready":False}
            version = sha(encoded(manifest).encode())
            manifest["version"]=version
            old=db.execute("SELECT manifest FROM dataset_versions WHERE version=?",(version,)).fetchone()
            if old:
                if json.loads(old[0])!=manifest:
                    raise ValueError("dataset version collision")
                return manifest | {"reused":True}
            db.execute("INSERT INTO dataset_versions VALUES (?,?)",(version,encoded(manifest)))
            db.executemany("INSERT INTO dataset_members VALUES (?,?,?)",
                           [(version,i,encoded(row)) for i,row in enumerate(records)])
            db.executemany("INSERT OR IGNORE INTO dataset_text_splits VALUES (?,?)",
                           [(row["source_sha256"],row["split"]) for row in records])
        return manifest | {"reused":False}

    def list(self):
        with closing(self.corpus.connect()) as db:
            return [json.loads(r[0]) for r in db.execute("SELECT manifest FROM dataset_versions ORDER BY version")]

    def export(self, version, destination):
        destination=Path(destination).resolve()
        if destination.exists() or destination==self.corpus.path.resolve():
            raise ValueError("export requires new destination")
        with closing(self.corpus.connect()) as db:
            found=db.execute("SELECT manifest FROM dataset_versions WHERE version=?",(version,)).fetchone()
            if not found:
                raise KeyError("unknown dataset version")
            manifest=json.loads(found[0])
            content="".join(r[0]+"\n" for r in db.execute(
                "SELECT record FROM dataset_members WHERE version=? ORDER BY ordinal",(version,))).encode("ascii")
        if sha(content)!=manifest["payload_sha256"] or sha(encoded({
                k:v for k,v in manifest.items() if k!="version"}).encode())!=version:
            raise ValueError("dataset integrity mismatch")
        destination.parent.mkdir(parents=True,exist_ok=True)
        tmp=None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as out:
                tmp=Path(out.name)
                out.write(content)
            os.link(tmp,destination)
        finally:
            if tmp:
                tmp.unlink(missing_ok=True)
        return manifest | {"path":str(destination)}
