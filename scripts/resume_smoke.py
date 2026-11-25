"""Real CPU training: continuous vs serialized/resumed, including optimizer and RNG."""
import json
from pathlib import Path
import tempfile
import torch
from safetensors.torch import load_file
from rpdistill.student import StudentProfile
from rpdistill.distill import DistillConfig
from rpdistill.resumable import ResumeConfig,run_segment

torch.set_num_threads(1)
p=StudentProfile(vocab=32,hidden=16,encoder_layers=1,decoder_layers=1,heads=2,ffn=32,positions=32,pad=31)
cfg=ResumeConfig(DistillConfig(steps=7,batch_size=1,learning_rate=0.003,seed=37),accumulation=2)
examples=[{"source_ids":[2,i,0],"target_ids":[i+5,0] if i%2 else [i+5,i+6,0]} for i in range(3,8)]
prov={"fixture":"synthetic token targets"}
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    def run(name,**kwargs):
        return run_segment(examples,root/name,profile=p,config=cfg,provenance=prov,**kwargs)
    full=run("full")
    partial=run("part",run_steps=2)
    assert partial["status"]=="paused" and partial["step"]==2
    middle=run("middle",resume=root/"part",run_steps=2)
    resumed=run("resumed",resume=root/"middle")
    assert full["status"]==resumed["status"]=="complete"
    assert full["history"]==resumed["history"]
    a,b=[load_file(str(root/name/"training.safetensors")) for name in ("full","resumed")]
    assert a.keys()==b.keys() and all(torch.equal(a[k],b[k]) for k in a)
    assert any(k.startswith("optim.") for k in a)
    assert [h["microbatches"] for h in full["history"]]==[2,2,1,2,2,1,2]
    try:
        run_segment(examples[::-1],root/"wrong",profile=p,config=cfg,provenance=prov,resume=root/"part")
    except ValueError:
        pass
    else:
        raise AssertionError("changed input accepted")
    with (root/"part"/"training.safetensors").open("ab") as stream:
        stream.write(b"x")
    try:
        run("corrupt",resume=root/"part")
    except ValueError:
        pass
    else:
        raise AssertionError("corrupt state accepted")
    assert not (root/"corrupt").exists()
    print(json.dumps({"steps":7,"interruptions":2,"accumulation":2,
          "equal_state_tensors":len(a),"history_equal":True,"optimizer_rng_equal":True,
          "changed_data_rejected":True,"corruption_rejected":True,"device":"cpu","quality_test":False}))
