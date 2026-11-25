"""Real CPU Marian student initialization and forward; no pretrained download."""
import json
import torch
from rpdistill.student import StudentProfile,FIXED,build_student,canonical_state,contract

torch.set_num_threads(1)
p=StudentProfile(vocab=32,hidden=16,encoder_layers=1,decoder_layers=1,heads=2,
                 ffn=32,positions=32,pad=31)
model=build_student(p).eval()
with torch.no_grad():
    out=model(input_ids=torch.tensor([[2,3,0,31],[2,4,5,0]]),
        attention_mask=torch.tensor([[1,1,1,0],[1,1,1,1]]),
        decoder_input_ids=torch.tensor([[31,7,8],[31,9,10]]),
        decoder_attention_mask=torch.ones((2,3),dtype=torch.long),use_cache=False)
assert out.logits.shape==(2,3,32)
assert torch.isfinite(out.logits).all()
assert model.model.encoder.embed_tokens.weight is model.model.shared.weight
assert model.model.decoder.embed_tokens.weight is model.model.shared.weight
assert model.lm_head.weight is model.model.shared.weight
from rpdistill.training_data import batch_arrays,tensor_batch
arrays=batch_arrays([{"source_ids":[2,3,0],"target_ids":[7,0]},
                     {"source_ids":[2,4,5,0],"target_ids":[9,10,0]}],p)
with torch.no_grad():
    tensors=tensor_batch(arrays)
    result=model(**tensors,use_cache=False)
    reference=torch.nn.functional.cross_entropy(result.logits.reshape(-1,p.vocab),
        tensors["labels"].reshape(-1),ignore_index=-100)
    assert torch.isfinite(result.loss)
    assert torch.allclose(result.loss,reference)
    assert tensors["decoder_attention_mask"][:,0].tolist()==[1,1]
    assert (tensors["labels"]!=-100).sum().item()==5
print(json.dumps({"masked_loss":result.loss.item(),"supervised_tokens":5,"parameter_update":False}))
del model
# Exact production-shape random initialization: no full-size generation or training.
model=build_student(FIXED)
state=canonical_state(model)
assert len(state)==256
assert sum(v.numel()*v.element_size() for v in state.values())==312033188
print(json.dumps({"tiny_cpu_forward":True,"fixed_shape":contract(),"trained":False}))
