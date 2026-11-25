"""Actual tiny CPU sequence-target training; synthetic labels, no translation-quality claim."""
import json
from pathlib import Path
import tempfile
import torch

from rpdistill.student import StudentProfile,build_student,canonical_state
from rpdistill.distill import DistillConfig,train_sequence,eval_loss,save_checkpoint,load_checkpoint
from rpdistill.training_data import batch_arrays,tensor_batch

torch.set_num_threads(1)
p=StudentProfile(vocab=32,hidden=32,encoder_layers=1,decoder_layers=1,heads=4,
                 ffn=64,positions=32,pad=31)
config=DistillConfig(steps=80,batch_size=2,learning_rate=0.008,weight_decay=0,seed=42)
examples=[{"source_ids":[2,3,4,0],"target_ids":[7,8,0]},
          {"source_ids":[2,5,0],"target_ids":[9,0]}]
model=build_student(p,seed=config.seed)
initial={k:v.detach().clone() for k,v in canonical_state(model,p).items()}
before=eval_loss(model,examples,p,batch_size=2)
history=train_sequence(model,examples,config,p)
after=eval_loss(model,examples,p,batch_size=2)
changed=sum(not torch.equal(v,initial[k]) for k,v in canonical_state(model,p).items())
assert changed>0 and after["loss"]<before["loss"]*0.5
assert len(history)==80 and all(row["supervised_tokens"]==5 for row in history)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/"checkpoint"
    manifest=save_checkpoint(model,p,config,history,root,provenance={"fixture":"synthetic token targets"})
    restored,loaded=load_checkpoint(root)
    assert loaded["checkpoint_id"]==manifest["checkpoint_id"]
    assert all(torch.equal(v,canonical_state(restored,p)[k]) for k,v in canonical_state(model,p).items())
    batch=tensor_batch(batch_arrays(examples,p))
    with torch.no_grad():
        assert torch.equal(model(**batch,use_cache=False).logits,restored(**batch,use_cache=False).logits)
    try:
        save_checkpoint(model,p,config,history,root,provenance={})
    except ValueError:
        pass
    else:
        raise AssertionError("overwriting checkpoint accepted")
    with (root/"student.safetensors").open("ab") as stream:
        stream.write(b"x")
    try:
        load_checkpoint(root)
    except ValueError:
        pass
    else:
        raise AssertionError("corrupt checkpoint accepted")
print(json.dumps({"fixture":"synthetic token targets","steps":len(history),"initial_loss":before["loss"],
                  "final_loss":after["loss"],"changed_tensors":changed,"checkpoint_roundtrip":True,
                  "corruption_rejected":True,"quality_test":False,"exact_resume":False}))
