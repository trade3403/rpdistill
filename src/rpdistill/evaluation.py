"""Frozen human-reference benchmark and conservative automatic translation metrics.

Independent means exact-source and declared paper identity disjoint from the
bound training snapshot. This does not prove semantic independence or rights.
External hypotheses are not authenticated model output. Never authorizes release.
"""
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from .datasets import DatasetStore, encoded, sha
from .papers import normalize_doi
from .training_data import MAX_SNAPSHOT_BYTES
from .student import no_duplicate_keys

SCHEMA="rpdistill-benchmark-v1"
MAX_BYTES=32*1024*1024
MAX_CASES=10000
NUMBERS=re.compile(r"(?<![A-Za-z0-9])[-+−]?[0-9]+(?:[.,][0-9]+)*(?:[eE][-+]?[0-9]+)?%?")
CITATIONS=re.compile(r"\[\s*\d+(?:\s*[-–,;]\s*\d+)*\s*\]")
HAN=re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def hash_json(value):
    return sha(encoded(value).encode())


def norm(text):
    return " ".join(unicodedata.normalize("NFKC",text).casefold().split())


def checked_text(value,name,limit=8000):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError("invalid "+name)
    return value.strip()


def read_json(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise ValueError("invalid or oversized evaluation file")
    with path.open("rb") as f:
        raw=f.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError("evaluation file too large")
    return json.loads(raw.decode("utf-8"),object_pairs_hook=no_duplicate_keys)


def read_jsonl(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_BYTES:
        raise ValueError("invalid or oversized JSONL")
    with path.open("rb") as f:
        raw=f.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError("evaluation JSONL too large")
    rows=[]
    for line in raw.decode("utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line,object_pairs_hook=no_duplicate_keys))
        if len(rows)>MAX_CASES:
            raise ValueError("too many evaluation rows")
    if not rows:
        raise ValueError("empty evaluation JSONL")
    return rows


def write_new(path,value):
    path=Path(path)
    if path.exists() or path.is_symlink():
        raise ValueError("output must be a new file")
    path=path.resolve()
    data=encoded(value).encode()
    if len(data)>MAX_BYTES:
        raise ValueError("evaluation artifact exceeds size budget")
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as out:
            tmp=Path(out.name)
            out.write(data)
        os.link(tmp,path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return str(path)


def paper_ids(row):
    values=set()
    pmcid=row.get("pmcid")
    doi=row.get("doi")
    if pmcid is not None:
        if not isinstance(pmcid,str) or not re.fullmatch(r"PMC[0-9]{1,15}",pmcid):
            raise ValueError("invalid PMCID")
        values.add("pmc:"+pmcid)
    if doi is not None:
        normalized=normalize_doi(doi)
        if normalized is None:
            raise ValueError("invalid DOI")
        values.add("doi:"+normalized)
    return values


def training_identity(db_path,version):
    """Verify complete frozen snapshot payload, collect conservative train exclusions."""
    if not isinstance(version,str) or not re.fullmatch(r"[a-f0-9]{64}",version):
        raise ValueError("invalid training dataset version")
    store=DatasetStore(db_path)
    sources,papers=set(),set()
    count=0
    h=hashlib.sha256()
    size=0
    counts=Counter()
    with closing(store.corpus.connect()) as db:
        db.execute("BEGIN")
        found=db.execute("SELECT manifest FROM dataset_versions WHERE version=?",(version,)).fetchone()
        if not found:
            raise KeyError("unknown training dataset")
        manifest=json.loads(found[0])
        if (manifest.get("version")!=version or manifest.get("status")!="candidate_snapshot"
            or hash_json({k:v for k,v in manifest.items() if k!="version"})!=version):
            raise ValueError("training dataset identity mismatch")
        for ordinal,raw in db.execute("SELECT ordinal,record FROM dataset_members WHERE version=? ORDER BY ordinal",(version,)):
            if ordinal!=count:
                raise ValueError("noncontiguous dataset members")
            data=(raw+"\n").encode("ascii")
            size+=len(data)
            if size>MAX_SNAPSHOT_BYTES:
                raise ValueError("training snapshot exceeds read budget")
            h.update(data)
            count+=1
            row=json.loads(raw)
            split=row.get("split")
            if split not in ("train","validation","test"):
                raise ValueError("invalid dataset split")
            counts[split]+=1
            if split!="train":
                continue
            text=checked_text(row.get("source_text"),"training source")
            if sha(row["source_text"].encode())!=row.get("source_sha256"):
                raise ValueError("training source hash mismatch")
            sources.add(norm(text))
            attribution=row.get("attribution",{})
            papers.update(paper_ids({"pmcid":row.get("pmcid"),"doi":attribution.get("doi")}))
        if (h.hexdigest()!=manifest["payload_sha256"] or count!=manifest["count"]
            or dict(counts)!=manifest["counts"] or not sources):
            raise ValueError("training dataset payload mismatch")
    return sources,papers


def clean_case(row):
    if not isinstance(row,dict):
        raise ValueError("benchmark row must be object")
    allowed={"id","paper_id","pmcid","doi","source","reference","terms","protected","rights_note"}
    if set(row)-allowed:
        raise ValueError("unexpected benchmark fields")
    identity=checked_text(row.get("id"),"case ID",128)
    paper=checked_text(row.get("paper_id"),"paper ID",256)
    source=checked_text(row.get("source"),"source")
    ref=checked_text(row.get("reference"),"human reference")
    if not HAN.search(ref) or norm(ref)==norm(source):
        raise ValueError("reference must be Chinese translation")
    terms=row.get("terms",[])
    protected=row.get("protected",[])
    if not isinstance(terms,list) or not isinstance(protected,list) or len(terms)>100 or len(protected)>100:
        raise ValueError("invalid terminology/protection list")
    term_rows=[]
    seen=set()
    for term in terms:
        if not isinstance(term,dict) or set(term)!={"source","targets"}:
            raise ValueError("invalid term mapping")
        src=checked_text(term["source"],"term source",256)
        targets=term["targets"]
        if not isinstance(targets,list) or not 1<=len(targets)<=10:
            raise ValueError("invalid term variants")
        variants=[checked_text(t,"term target",256) for t in targets]
        if norm(src) in seen or norm(src) not in norm(source) or not any(t in ref for t in variants):
            raise ValueError("term must occur in source and approved reference")
        seen.add(norm(src))
        term_rows.append({"source":src,"targets":variants})
    literals=[]
    for token in protected:
        token=checked_text(token,"protected literal",512)
        if token in literals or token not in source or token not in ref:
            raise ValueError("protected literal must occur in source and reference")
        literals.append(token)
    if Counter(NUMBERS.findall(unicodedata.normalize("NFKC",source)))!=Counter(NUMBERS.findall(unicodedata.normalize("NFKC",ref))):
        raise ValueError("reference numeric literals differ; review benchmark")
    if Counter(CITATIONS.findall(source))!=Counter(CITATIONS.findall(ref)):
        raise ValueError("reference citations differ; review benchmark")
    ids=paper_ids(row)
    result={"id":identity,"paper_id":paper,"source":source,"reference":ref,"terms":term_rows,
            "protected":literals,"rights_note":checked_text(row.get("rights_note"),"rights note",1000)}
    if row.get("pmcid") is not None:
        result["pmcid"]=row["pmcid"]
    if row.get("doi") is not None:
        result["doi"]=normalize_doi(row["doi"])
    return result


def freeze_benchmark(db_path,version,rows,*,review_note):
    review_note=checked_text(review_note,"operator human-reference and rights review",2000)
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_CASES:
        raise ValueError("invalid benchmark size")
    sources,papers=training_identity(db_path,version)
    cases=[]
    seen_ids=set()
    seen_text=set()
    for row in rows:
        case=clean_case(row)
        key=norm(case["source"])
        if key in sources or paper_ids(case)&papers:
            raise ValueError("benchmark overlaps training source or declared paper identity")
        if case["id"] in seen_ids or key in seen_text:
            raise ValueError("duplicate benchmark ID or source")
        seen_ids.add(case["id"])
        seen_text.add(key)
        cases.append(case)
    cases.sort(key=lambda c:c["id"])
    payload={"schema":SCHEMA,"training_dataset":version,"review_note":review_note,
             "reference_origin":"operator_asserted_human_reviewed",
             "independence":"exact_normalized_source_and_declared_pmcid_doi_only",
             "cases":cases}
    return payload|{"benchmark_id":hash_json(payload)}


def validate_benchmark(db_path,benchmark):
    if not isinstance(benchmark,dict) or benchmark.get("schema")!=SCHEMA:
        raise ValueError("invalid benchmark")
    rebuilt=freeze_benchmark(db_path,benchmark["training_dataset"],benchmark["cases"],review_note=benchmark["review_note"])
    if rebuilt!=benchmark:
        raise ValueError("benchmark integrity mismatch")
    return rebuilt


@dataclass(frozen=True)
class QualityGate:
    min_cases:int=100
    min_papers:int=20
    min_numeric_cases:int=10
    min_term_cases:int=10
    min_protected_cases:int=10
    min_bleu:float=20.0
    min_chrf:float=45.0
    min_numeric:float=1.0
    min_terminology:float=0.95
    min_protected:float=1.0
    min_citations:float=1.0
    max_suspicious:float=0.02

    def __post_init__(self):
        for key in ("min_cases","min_papers","min_numeric_cases","min_term_cases","min_protected_cases"):
            v=getattr(self,key)
            if type(v) is not int or not 1<=v<=MAX_CASES:
                raise ValueError("invalid coverage gate: "+key)
        for key in ("min_bleu","min_chrf","min_numeric","min_terminology","min_protected","min_citations","max_suspicious"):
            v=getattr(self,key)
            if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=(100 if key in ("min_bleu","min_chrf") else 1):
                raise ValueError("invalid metric gate: "+key)


def literal_counts(text,pattern):
    return Counter(pattern.findall(unicodedata.normalize("NFKC",text)))


def screen_case(case,hyp):
    src,ref=case["source"],case["reference"]
    numbers=literal_counts(src,NUMBERS)
    citations=literal_counts(src,CITATIONS)
    terms=case["terms"]
    protected=case["protected"]
    flags=[]
    if not hyp.strip():
        flags.append("empty")
    if not HAN.search(hyp):
        flags.append("no_chinese")
    if norm(hyp)==norm(src):
        flags.append("source_echo")
    ratio=len(hyp.strip())/len(ref)
    if not 0.5<=ratio<=2.0:
        flags.append("reference_length_ratio")
    if "<think>" in hyp.lower() or "</think>" in hyp.lower():
        flags.append("reasoning_markup")
    result={"id":case["id"],"hypothesis":hyp,"suspicious_flags":flags,
            "numeric_applicable":bool(numbers),"numeric_exact":numbers==literal_counts(hyp,NUMBERS),
            "citation_applicable":bool(citations),"citation_exact":citations==literal_counts(hyp,CITATIONS),
            "term_count":len(terms),"term_hits":sum(any(t in hyp for t in term["targets"]) for term in terms),
            "protected_count":len(protected),
            "protected_hits":sum(hyp.count(t)==src.count(t) for t in protected)}
    return result


def rate(n,d):
    return n/d if d else None


def evaluate(db_path,benchmark,hypotheses,*,gate=QualityGate(),label="external hypotheses"):
    import sacrebleu
    from sacrebleu.metrics import BLEU,CHRF
    benchmark=validate_benchmark(db_path,benchmark)
    if not isinstance(gate,QualityGate):
        raise ValueError("invalid quality gate")
    label=checked_text(label,"hypothesis label",256)
    if not isinstance(hypotheses,list) or len(hypotheses)!=len(benchmark["cases"]):
        raise ValueError("hypothesis count must match benchmark exactly")
    by_id={}
    for row in hypotheses:
        if not isinstance(row,dict) or set(row)!={"id","hypothesis"} or not isinstance(row["id"],str):
            raise ValueError("invalid hypothesis record")
        text=row["hypothesis"]
        if row["id"] in by_id or not isinstance(text,str) or len(text)>16000:
            raise ValueError("duplicate or invalid hypothesis")
        by_id[row["id"]]=text
    if set(by_id)!={c["id"] for c in benchmark["cases"]}:
        raise ValueError("hypothesis IDs must match benchmark exactly")
    cases=benchmark["cases"]
    outputs=[by_id[c["id"]] for c in cases]
    references=[c["reference"] for c in cases]
    bleu=BLEU(tokenize="zh",effective_order=True)
    chrf=CHRF(char_order=6,word_order=0,beta=2)
    bs=bleu.corpus_score(outputs,[references]).score
    cs=chrf.corpus_score(outputs,[references]).score
    details=[screen_case(c,h) for c,h in zip(cases,outputs)]
    coverage={"cases":len(cases),"papers":len({c["paper_id"] for c in cases}),
              "numeric_cases":sum(r["numeric_applicable"] for r in details),
              "term_cases":sum(r["term_count"]>0 for r in details),
              "protected_cases":sum(r["protected_count"]>0 for r in details),
              "citation_cases":sum(r["citation_applicable"] for r in details)}
    scores={"bleu":bs,"chrf":cs,
            "numeric":rate(sum(r["numeric_exact"] for r in details),len(details)),
            "citations":rate(sum(r["citation_exact"] for r in details),len(details)),
            "terminology":rate(sum(r["term_hits"] for r in details),sum(r["term_count"] for r in details)),
            "protected":rate(sum(r["protected_hits"] for r in details),sum(r["protected_count"] for r in details)),
            "suspicious":rate(sum(bool(r["suspicious_flags"]) for r in details),len(details))}
    failures=[]
    for key in ("cases","papers","numeric_cases","term_cases","protected_cases"):
        if coverage[key]<getattr(gate,"min_"+key):
            failures.append("coverage:"+key)
    for key in ("bleu","chrf","numeric","citations","terminology","protected"):
        if scores[key] is None or scores[key]<getattr(gate,"min_"+key):
            failures.append("metric:"+key)
    if scores["suspicious"]>gate.max_suspicious:
        failures.append("metric:suspicious")
    report={"schema":"rpdistill-evaluation-v1","benchmark_id":benchmark["benchmark_id"],
            "training_dataset":benchmark["training_dataset"],"hypothesis_label":label,
            "hypotheses_sha256":hash_json([{"id":c["id"],"hypothesis":by_id[c["id"]]} for c in cases]),
            "metrics":scores,"coverage":coverage,"gate":asdict(gate),"failures":failures,
            "automatic_gate_passed":not failures,"release_ready":False,
            "model_output_authenticated":False,
            "metric_versions":{"sacrebleu":sacrebleu.__version__,"bleu":str(bleu.get_signature()),
                               "chrf":str(chrf.get_signature())},
            "details":details}
    return report|{"report_id":hash_json(report)}
