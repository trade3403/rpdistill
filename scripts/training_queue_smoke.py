"""Real micro CPU training through durable queue with pause, restart and resume."""
import json
from pathlib import Path
import tempfile
import torch
from safetensors.torch import load_file
from rpdistill.training_queue import TrainingQueue
from rpdistill.student import StudentProfile
from rpdistill.distill import DistillConfig
from rpdistill.resumable import ResumeConfig,run_segment

torch.set_num_threads(1)
p=StudentProfile(vocab=32,hidden=16,encoder_layers=1,decoder_layers=1,heads=2,ffn=32,positions=32,pad=31)
cfg=ResumeConfig(DistillConfig(steps=5,batch_size=1,learning_rate=0.003,seed=37),accumulation=2)
examples=[{"source_ids":[2,i,0],"target_ids":[i+5,0]} for i in range(3,8)]
provenance={"fixture":"synthetic queue targets"}
def prepare(*args,**kwargs):
    return examples,provenance

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    q=TrainingQueue(root/"db")
    version="a"*64
    job=q.enqueue(version,root/"assets",root/"states",reviewed_dataset=version,
        reviewed_teacher_license="synthetic",config=cfg,segment_steps=2,segment_seconds=30,
        total_seconds=120,total_checkpoint_bytes=4*2**30)
    def execute(*args,**kwargs):
        control=kwargs["should_stop"]
        def pause():
            q.control(job["id"],"pause")
            return control()
        kwargs["should_stop"]=pause
        return run_segment(*args,**kwargs)
    paused=q.run_next(prepare=prepare,execute=execute,profile=p)
    assert paused["state"]=="paused" and paused["step"]==1
    q=TrainingQueue(root/"db")
    q.control(job["id"],"resume")
    done=q.run_next(prepare=prepare,profile=p)
    assert done["state"]=="complete" and done["step"]==5 and done["attempt"]==3
    assert done["reserved_seconds"]==90 and done["reserved_bytes"]==3*2**30
    full=run_segment(examples,root/"full",profile=p,config=cfg,provenance=provenance)
    a=load_file(str(Path(done["checkpoint"])/"training.safetensors"))
    b=load_file(str(root/"full"/"training.safetensors"))
    assert a.keys()==b.keys() and all(torch.equal(a[k],b[k]) for k in a)
    assert len(list((root/"states"/job["id"]).glob("attempt-*")))==3
    from rpdistill.studio import snapshot
    samples=snapshot(q.path)["rows"]["training_loss"]
    assert [v["step"] for v in samples]==[1,2,3,4,5]
    assert all(v["committed"]==1 and v["seconds"]>0 and v["tokens"]>0 for v in samples)
    assert [v["loss"] for v in samples]==[v["loss"] for v in full["history"]]
    print(json.dumps({"steps":done["step"],"checkpoint_count":done["attempt"],
        "equal_state_tensors":len(a),"pause_restart_resume":True,"budget_reservations":True,
        "fixture":"synthetic CPU targets","quality_test":False}))
