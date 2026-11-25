"""Verified student tokenizer assets and bounded, masked candidate training batches.

Tokenization does not certify a dataset for training. No weight update here.
"""
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.error import HTTPError, URLError
import time

from .student import ASSETS,BASE_SOURCE,BASE_REVISION,FIXED,StudentCodec,checked_assets
from .transfer import transfer_file,hf_url,digest_file
from .papers import retry_delay
from .ncbi_papers import transient
from .datasets import DatasetStore,encoded,sha,SPLITS
from .fulltext import MAX_FILE

ASSET_BYTES=sum(size for size,_ in ASSETS.values())
MAX_SNAPSHOT_BYTES=256*1024*1024


def acquire_assets(root,*,max_bytes,transfer=transfer_file,sleep=time.sleep):
    """Download exactly five known, public revision-pinned assets; never weights."""
    if type(max_bytes) is not int or max_bytes<ASSET_BYTES or max_bytes>2**40:
        raise ValueError("asset budget must cover pinned files")
    root=Path(root)
    if root.is_symlink():
        raise ValueError("symlink asset root")
    root.mkdir(parents=True,exist_ok=True)
    root=root.resolve()
    if shutil.disk_usage(root).free<ASSET_BYTES:
        raise ValueError("insufficient disk space")
    received=0

    def count(n):
        nonlocal received
        received+=n
        if received>max_bytes:
            raise ValueError("asset network byte budget exceeded")

    for name,(size,hash_value) in ASSETS.items():
        for attempt in range(3):
            try:
                transfer(hf_url(BASE_SOURCE,BASE_REVISION,name),root/name,
                         size=size,sha256=hash_value,on_bytes=count)
                break
            except (HTTPError,URLError,TimeoutError,ConnectionError) as exc:
                if isinstance(exc,HTTPError):
                    exc.close()
                if attempt==2 or not transient(exc):
                    raise
                sleep(retry_delay(exc,attempt))
    checked_assets(root)
    return {"path":str(root),"source":BASE_SOURCE,"revision":BASE_REVISION,
            "files":len(ASSETS),"asset_bytes":ASSET_BYTES,"network_bytes":received,
            "weights_downloaded":False}


def batch_arrays(examples,profile=FIXED,*,max_padded_tokens=4096,max_logits=16_777_216):
    if not isinstance(examples,(list,tuple)) or not 1<=len(examples)<=64:
        raise ValueError("batch must contain 1–64 examples")
    if type(max_padded_tokens) is not int or not 1<=max_padded_tokens<=65536:
        raise ValueError("invalid padded token budget")
    if type(max_logits) is not int or not 1<=max_logits<=134217728:
        raise ValueError("invalid logits budget")
    p=profile
    for example in examples:
        for name in ("source_ids","target_ids"):
            ids=example[name]
            if (not isinstance(ids,(list,tuple)) or not 2<=len(ids)<=p.positions
                or ids[-1]!=p.eos or any(type(i) is not int or not 0<=i<p.vocab
                   or i in (p.pad,p.unk,p.eos) for i in ids[:-1])):
                raise ValueError("invalid sequence: "+name)
    src=max(len(e["source_ids"]) for e in examples)
    tgt=max(len(e["target_ids"]) for e in examples)
    if len(examples)*(src+tgt)>max_padded_tokens or len(examples)*tgt*p.vocab>max_logits:
        raise ValueError("batch budget exceeded")
    batch={k:[] for k in ("input_ids","attention_mask","decoder_input_ids",
                          "decoder_attention_mask","labels")}
    for e in examples:
        a,b=list(e["source_ids"]),list(e["target_ids"])
        sa,ta=src-len(a),tgt-len(b)
        batch["input_ids"].append(a+[p.pad]*sa)
        batch["attention_mask"].append([1]*len(a)+[0]*sa)
        # Decoder start token is PAD in Marian, but it MUST be attended.
        batch["decoder_input_ids"].append([p.pad]+b[:-1]+[p.pad]*ta)
        batch["decoder_attention_mask"].append([1]*len(b)+[0]*ta)
        batch["labels"].append(b+[-100]*ta)
    return batch


def tensor_batch(arrays,*,device="cpu"):
    import torch
    return {k:torch.tensor(v,dtype=torch.long,device=device) for k,v in arrays.items()}


def snapshot_examples(db_path,version,codec,*,split="train",limit=1000):
    """Read immutable candidate snapshot; check all member hashes and current rights metadata.

    Returns tokenized *candidate* examples. Caller must independently authorize
    training and assess content rights/semantic quality. Never silently truncate.
    """
    if split not in SPLITS or type(limit) is not int or not 1<=limit<=10000:
        raise ValueError("invalid split or example limit")
    if not isinstance(version,str) or not re.fullmatch(r"[a-f0-9]{64}",version):
        raise ValueError("invalid dataset version")
    store=DatasetStore(db_path)
    examples=[]
    stats=Counter(selected=0,accepted=0,excluded=0)
    hashes=hashlib.sha256()
    file_cache={}
    nbytes=0
    with closing(store.corpus.connect()) as db:
        db.execute("BEGIN")
        found=db.execute("SELECT manifest FROM dataset_versions WHERE version=?",(version,)).fetchone()
        if not found:
            raise KeyError("unknown dataset version")
        manifest=json.loads(found[0])
        if (manifest.get("version")!=version or manifest.get("training_ready") is not False
            or manifest.get("status")!="candidate_snapshot"
            or sha(encoded({k:v for k,v in manifest.items() if k!="version"}).encode())!=version):
            raise ValueError("invalid candidate manifest")
        counts=Counter()
        seen=set()
        for ordinal,raw in db.execute("SELECT ordinal,record FROM dataset_members WHERE version=? ORDER BY ordinal",(version,)):
            if ordinal!=sum(counts.values()):
                raise ValueError("noncontiguous snapshot members")
            data=(raw+"\n").encode("ascii")
            nbytes+=len(data)
            if nbytes>MAX_SNAPSHOT_BYTES:
                raise ValueError("snapshot exceeds read budget")
            hashes.update(data)
            row=json.loads(raw)
            member_split=row.get("split")
            text=row.get("source_text")
            text_hash=row.get("source_sha256")
            if (member_split not in SPLITS or not isinstance(text,str)
                or sha(text.encode())!=text_hash or text_hash in seen
                or row.get("status")!="screened_candidate"
                or row.get("teacher")!=manifest.get("teacher")
                or row.get("options")!=manifest.get("options")):
                raise ValueError("invalid snapshot member")
            seen.add(text_hash)
            counts[member_split]+=1
            if member_split!=split or stats["selected"]>=limit:
                continue
            stats["selected"]+=1
            pmcid=row.get("pmcid")
            if pmcid not in file_cache:
                current=db.execute("""SELECT p.record,f.record FROM papers p
                    JOIN paper_fulltexts f ON p.pmcid=f.pmcid WHERE p.pmcid=?""",(pmcid,)).fetchone()
                file_cache[pmcid]=None
                if current:
                    p,f=map(json.loads,current)
                    try:
                        path=Path(f["path"])
                        if (p.get("eligibility")=="pending_fulltext_license"
                            and f.get("status")=="downloaded_pending_content_review"
                            and not path.is_symlink() and path.is_file()
                            and path.stat().st_size==f["size"]<=MAX_FILE
                            and digest_file(path)==f["sha256"]):
                            file_cache[pmcid]=f
                    except (OSError,KeyError,TypeError):
                        pass
            full=file_cache[pmcid]
            attribution=row.get("attribution",{})
            if (not full or full.get("sha256")!=attribution.get("xml_sha256")
                or full.get("license_uri")!=attribution.get("license_uri")):
                stats["excluded"]+=1
                continue
            try:
                a=codec.encode(text)
                b=codec.encode(row["translation"],target=True)
            except (ValueError,KeyError,TypeError):
                stats["excluded"]+=1
                continue
            examples.append({"pair_id":row["pair_id"],"source_ids":a,"target_ids":b})
            stats["accepted"]+=1
        if (hashes.hexdigest()!=manifest["payload_sha256"]
            or sum(counts.values())!=manifest["count"]
            or {s:counts[s] for s in SPLITS}!=manifest["counts"]):
            raise ValueError("snapshot integrity mismatch")
    return examples,dict(stats)


def batches(examples,profile=FIXED,*,batch_size=4,max_padded_tokens=4096,max_logits=16777216):
    if type(batch_size) is not int or not 1<=batch_size<=64:
        raise ValueError("invalid batch size")
    current=[]
    for example in examples:
        # A single impossible example is rejected explicitly, not truncated.
        batch_arrays([example],profile,max_padded_tokens=max_padded_tokens,max_logits=max_logits)
        if current:
            try:
                if len(current)==batch_size:
                    raise ValueError("batch full")
                batch_arrays(current+[example],profile,max_padded_tokens=max_padded_tokens,max_logits=max_logits)
            except ValueError:
                yield batch_arrays(current,profile,max_padded_tokens=max_padded_tokens,max_logits=max_logits)
                current=[]
        current.append(example)
    if current:
        yield batch_arrays(current,profile,max_padded_tokens=max_padded_tokens,max_logits=max_logits)


def batch_plan(db_path,version,assets,*,split="train",limit=1000,batch_size=4,
               max_padded_tokens=4096,max_logits=16777216):
    codec=StudentCodec.from_assets(assets)
    examples,stats=snapshot_examples(db_path,version,codec,split=split,limit=limit)
    count=tokens=target=0
    for batch in batches(examples,batch_size=batch_size,max_padded_tokens=max_padded_tokens,max_logits=max_logits):
        count+=1
        tokens+=sum(map(len,batch["input_ids"]))+sum(map(len,batch["labels"]))
        target+=sum(i!=-100 for row in batch["labels"] for i in row)
    return {"dataset_version":version,"split":split,"examples":stats,"batches":count,
            "padded_tokens":tokens,"supervised_tokens":target,"training_ready":False}
