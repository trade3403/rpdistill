"""Bounded lexical leakage audit and blinded bilingual review workflow.

Hashes bind local artifacts, not reviewer identity or authenticity. All approvals
remain candidate-only; release and real-world independence are separate gates.
"""
from collections import Counter,defaultdict
from dataclasses import asdict,dataclass
import math
import re
import secrets

from .evaluation import (MAX_CASES,QualityGate,checked_text,evaluate,hash_json,norm,
                         training_identity,validate_benchmark)
from .datasets import encoded

AUDIT_SCHEMA="rpdistill-lexical-audit-v1"
PACKET_SCHEMA="rpdistill-blind-packet-v1"
KEY_SCHEMA="rpdistill-blind-key-v1"
MAX_POSTINGS=2_000_000
MAX_VISITS=20_000_000
MAX_MATCHES=1000


def seal(value,key):
    return value|{key:hash_json(value)}


def verify(value,key,schema):
    if (not isinstance(value,dict) or value.get("schema")!=schema
        or value.get(key)!=hash_json({k:v for k,v in value.items() if k!=key})):
        raise ValueError("invalid "+schema+" identity")


def shingles(text):
    words=re.findall(r"\w+",norm(text))
    # Short cases: normalized token equality only, avoiding noisy 3-gram overlap.
    if len(words)<8:
        return set(),tuple(words)
    return set(zip(words,words[1:],words[2:])),tuple(words)


def leakage_audit(db_path,benchmark,*,max_postings=MAX_POSTINGS,max_visits=MAX_VISITS):
    """All matching candidates via inverted trigrams, no approximate LSH recall claim.

    Fail closed when resource limits are reached, never return a partial pass.
    Flags 3-gram Jaccard >=0.8 or containment >=0.9 for >=6 distinct trigrams.
    Also checks short normalized token equality and internal benchmark duplication.
    """
    if (type(max_postings) is not int or not 1<=max_postings<=MAX_POSTINGS
        or type(max_visits) is not int or not 1<=max_visits<=MAX_VISITS):
        raise ValueError("invalid lexical audit budget")
    benchmark=validate_benchmark(db_path,benchmark)
    sources,_=training_identity(db_path,benchmark["training_dataset"])
    index=defaultdict(list)
    token_index=defaultdict(list)
    sizes={}
    labels={}
    postings=visits=0
    matches=[]

    def add(text,label):
        nonlocal postings
        grams,tokens=shingles(text)
        # Track normalized token identity even when punctuation differs.
        postings+=len(grams)+1
        if postings>max_postings:
            raise ValueError("lexical index budget exhausted; no audit pass")
        idx=len(sizes)
        sizes[idx]=len(grams)
        labels[idx]=label
        token_index[tokens].append(idx)
        for gram in grams:
            index[gram].append(idx)

    for text in sorted(sources):
        add(text,{"kind":"train","source_hash":hash_json(text)})
    for case in benchmark["cases"]:
        grams,tokens=shingles(case["source"])
        equal=token_index.get(tokens,[])
        visits+=len(equal)
        if visits>max_visits:
            raise ValueError("lexical comparison budget exhausted; no audit pass")
        hits=Counter()
        for gram in grams:
            posting=index.get(gram,[])
            visits+=len(posting)
            if visits>max_visits:
                raise ValueError("lexical comparison budget exhausted; no audit pass")
            hits.update(posting)
        for idx in sorted(set(equal)|set(hits)):
            common=hits[idx]
            union=len(grams)+sizes[idx]-common
            smaller=min(len(grams),sizes[idx])
            jac=common/union if union else 0.0
            containment=common/smaller if smaller else 0.0
            if idx in equal or (smaller>=6 and (jac>=0.8 or containment>=0.9)):
                if len(matches)>=MAX_MATCHES:
                    raise ValueError("too many lexical matches; no audit pass")
                matches.append({"case_id":case["id"],"other":labels[idx],
                    "token_equal":idx in equal,"jaccard":jac,"containment":containment})
        add(case["source"],{"kind":"benchmark","case_id":case["id"]})
    return seal({"schema":AUDIT_SCHEMA,"benchmark_id":benchmark["benchmark_id"],
                 "training_dataset":benchmark["training_dataset"],"training_sources":len(sources),
                 "cases":len(benchmark["cases"]),"policy":"word-trigram-v1",
                 "postings":postings,"visits":visits,"matches":matches,
                 "passed":not matches,"semantic_independence_proven":False},"audit_id")


def report_outputs(report,benchmark):
    if (not isinstance(report,dict) or report.get("schema")!="rpdistill-evaluation-v1"
        or report.get("report_id")!=hash_json({k:v for k,v in report.items() if k!="report_id"})
        or report.get("benchmark_id")!=benchmark["benchmark_id"]
        or report.get("training_dataset")!=benchmark["training_dataset"]):
        raise ValueError("evaluation report identity mismatch")
    outputs=[{"id":r["id"],"hypothesis":r["hypothesis"]} for r in report["details"]]
    if (len(outputs)!=len(benchmark["cases"]) or
        [r["id"] for r in outputs]!=[c["id"] for c in benchmark["cases"]]
        or hash_json(outputs)!=report.get("hypotheses_sha256")):
        raise ValueError("evaluation output identity mismatch")
    return outputs


def checked_reports(db_path,benchmark,student,baseline):
    benchmark=validate_benchmark(db_path,benchmark)
    student_outputs=report_outputs(student,benchmark)
    baseline_outputs=report_outputs(baseline,benchmark)
    if (student.get("model_output_generated_locally") is not True
        or not isinstance(student.get("checkpoint_id"),str)
        or not re.fullmatch(r"[a-f0-9]{64}",student["checkpoint_id"])):
        raise ValueError("local student checkpoint evaluation required")
    for report,outputs in ((student,student_outputs),(baseline,baseline_outputs)):
        # Recompute metrics with the reported version/gate; no trust in self-asserted scores.
        scored=evaluate(db_path,benchmark,outputs,gate=QualityGate(**report["gate"]),
                        label=report["hypothesis_label"])
        for name in ("metrics","coverage","metric_versions","details"):
            if scored[name]!=report.get(name):
                raise ValueError("evaluation metric recomputation mismatch: "+name)
    return student_outputs,baseline_outputs


def create_blind_review(db_path,benchmark,student,baseline):
    """Generate public anonymous A/B packet and separate private identity key."""
    a,b=checked_reports(db_path,benchmark,student,baseline)
    cases=[]
    mappings=[]
    for case,student_row,baseline_row in zip(benchmark["cases"],a,b):
        side=secrets.choice(("A","B"))
        opaque=secrets.token_hex(16)
        cases.append({"id":opaque,"source":case["source"],"reference":case["reference"],
                      "A":student_row["hypothesis"] if side=="A" else baseline_row["hypothesis"],
                      "B":baseline_row["hypothesis"] if side=="A" else student_row["hypothesis"]})
        mappings.append({"id":opaque,"case_id":case["id"],"student_side":side})
    order=list(range(len(cases)))
    secrets.SystemRandom().shuffle(order)
    packet=seal({"schema":PACKET_SCHEMA,"cases":[cases[i] for i in order],
                 "rubric":{"adequacy":"0-4 (0 absent/wrong, 4 complete and accurate)",
                           "fluency":"0-4 (0 unreadable, 4 fluent)",
                           "critical_error":"true for materially wrong scientific meaning, missing key content, or unsafe numeric/formula error",
                           "preference":"A, B or tie"},
                 "review_instructions":"Score both independently before seeing mapping. Do not infer model identity."},"packet_id")
    key=seal({"schema":KEY_SCHEMA,"packet_id":packet["packet_id"],
              "benchmark_id":benchmark["benchmark_id"],"student_report":student["report_id"],
              "baseline_report":baseline["report_id"],"mappings":[mappings[i] for i in order]},"key_id")
    return packet,key


@dataclass(frozen=True)
class ReviewGate:
    min_reviewers:int=2
    min_cases:int=100
    min_adequacy:float=3.5
    min_fluency:float=3.0
    max_critical_rate:float=0.0
    min_preference_credit:float=0.5

    def __post_init__(self):
        if type(self.min_reviewers) is not int or not 2<=self.min_reviewers<=20:
            raise ValueError("at least two declared reviewers required")
        if type(self.min_cases) is not int or not 1<=self.min_cases<=MAX_CASES:
            raise ValueError("invalid review coverage")
        for name,upper in (("min_adequacy",4),("min_fluency",4),
                           ("max_critical_rate",1),("min_preference_credit",1)):
            value=getattr(self,name)
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=upper:
                raise ValueError("invalid review gate")


def collect_review(db_path,benchmark,student,baseline,packet,key,reviews,*,gate=ReviewGate()):
    """Validate blinded packet against both reports; require complete paired reviews."""
    if not isinstance(gate,ReviewGate):
        raise ValueError("invalid review gate")
    a,b=checked_reports(db_path,benchmark,student,baseline)
    verify(packet,"packet_id",PACKET_SCHEMA)
    verify(key,"key_id",KEY_SCHEMA)
    if (key["packet_id"]!=packet["packet_id"] or key["benchmark_id"]!=benchmark["benchmark_id"]
        or key["student_report"]!=student["report_id"] or key["baseline_report"]!=baseline["report_id"]):
        raise ValueError("review binding mismatch")
    by_case={c["id"]:(c,x["hypothesis"],y["hypothesis"]) for c,x,y in zip(benchmark["cases"],a,b)}
    maps={r["id"]:r for r in key["mappings"]}
    ids={r["id"] for r in packet["cases"]}
    if (len(ids)!=len(packet["cases"]) or len(ids)!=len(maps) or len(maps)!=len(key["mappings"])
        or ids!=set(maps) or len(maps)!=len(by_case)
        or {r["case_id"] for r in maps.values()}!=set(by_case)):
        raise ValueError("invalid blind mapping")
    for row in packet["cases"]:
        mapping=maps[row["id"]]
        case,x,y=by_case[mapping["case_id"]]
        side=mapping["student_side"]
        if side not in ("A","B") or row!={
            "id":row["id"],"source":case["source"],"reference":case["reference"],
            "A":x if side=="A" else y,"B":y if side=="A" else x}:
            raise ValueError("blind packet content mismatch")
    if not isinstance(reviews,list) or not 1<=len(reviews)<=20:
        raise ValueError("invalid reviewer count")
    names=set()
    total=Counter()
    for review in reviews:
        if (not isinstance(review,dict) or set(review)!={"reviewer","packet_id","independent_review_asserted","scores"}
            or review["packet_id"]!=packet["packet_id"] or review["independent_review_asserted"] is not True):
            raise ValueError("review identity or independence assertion missing")
        reviewer=norm(checked_text(review["reviewer"],"reviewer identifier",128))
        if reviewer in names:
            raise ValueError("duplicate reviewer")
        names.add(reviewer)
        rows=review["scores"]
        if not isinstance(rows,list) or len(rows)!=len(ids):
            raise ValueError("incomplete review")
        seen=set()
        for row in rows:
            if not isinstance(row,dict) or set(row)!={"id","A","B","preference"}:
                raise ValueError("invalid review score")
            ident=row["id"]
            if ident not in ids or ident in seen or row["preference"] not in ("A","B","tie"):
                raise ValueError("invalid or duplicate review case")
            seen.add(ident)
            for side in ("A","B"):
                scores=row[side]
                if (not isinstance(scores,dict) or set(scores)!={"adequacy","fluency","critical_error"}
                    or any(type(scores[k]) is not int or not 0<=scores[k]<=4 for k in ("adequacy","fluency"))
                    or type(scores["critical_error"]) is not bool):
                    raise ValueError("invalid bilingual review rubric score")
                label="student" if side==maps[ident]["student_side"] else "baseline"
                for field,value in scores.items():
                    total[label+"_"+field]+=value
            total["preference_credit"]+=0.5 if row["preference"]=="tie" else int(row["preference"]==maps[ident]["student_side"])
    n=len(names)*len(ids)
    metrics={k:total[k]/n for k in ("student_adequacy","student_fluency","student_critical_error",
                                   "baseline_adequacy","baseline_fluency","baseline_critical_error","preference_credit")}
    failures=[]
    if len(names)<gate.min_reviewers: failures.append("reviewer_coverage")
    if len(ids)<gate.min_cases: failures.append("case_coverage")
    if metrics["student_adequacy"]<gate.min_adequacy: failures.append("adequacy")
    if metrics["student_fluency"]<gate.min_fluency: failures.append("fluency")
    if metrics["student_critical_error"]>gate.max_critical_rate: failures.append("critical_error")
    if metrics["preference_credit"]<gate.min_preference_credit: failures.append("baseline_preference")
    audit=leakage_audit(db_path,benchmark)
    if not audit["passed"]: failures.append("lexical_overlap")
    # Re-evaluate with default engineering policy, not an arbitrarily weakened report gate.
    strict=evaluate(db_path,benchmark,a,gate=QualityGate(),label="candidate gate")
    if not strict["automatic_gate_passed"]: failures.append("automatic_quality")
    gen=student.get("generation",[])
    if ([r.get("id") for r in gen]!=[c["id"] for c in benchmark["cases"]]
        or any(r.get("finish_reason")!="eos" for r in gen)):
        failures.append("incomplete_generation")
    return seal({"schema":"rpdistill-quality-review-v1","benchmark_id":benchmark["benchmark_id"],
                 "training_dataset":benchmark["training_dataset"],"checkpoint_id":student["checkpoint_id"],
                 "student_report":student["report_id"],"baseline_report":baseline["report_id"],
                 "packet_id":packet["packet_id"],"key_id":key["key_id"],"reviews_sha256":hash_json(reviews),
                 "lexical_audit":audit,"automatic_gate_report":strict["report_id"],
                 "review_gate":asdict(gate),"metrics":metrics,"reviewer_count":len(names),
                 "case_count":len(ids),"failures":failures,"candidate_gate_passed":not failures,
                 "reviewer_identity_verified":False,"baseline_identity_verified":False,
                 "release_ready":False},"review_id")
