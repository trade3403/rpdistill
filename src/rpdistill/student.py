"""Marian student contract audited against RPTranslate D-line, not a deployable package."""
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import math
import re

D_REVISION="7f1fdb282bbdc947dc4a5d953768efaed429959d"
BASE_REVISION="a4193836671069f1f80ce341f9227a850ffb52d4"
BASE_SOURCE="Helsinki-NLP/opus-mt-en-zh"
LANGUAGE=">>cmn_Hans<<"
ASSETS={
 "config.json":(1403,"bcae8ed74fed77fb51c58462b62397fee6b1a1a34aece79183a0dd02ad329e71"),
 "generation_config.json":(293,"524dc91570823feb51fbd33a35e5aee3050a4441bdf65e66f6f5e945e5838e40"),
 "source.spm":(806435,"5775ddc9e3ff2fae91554da56468ad35ff56edaba870fea74447bc7234bfdaa8"),
 "target.spm":(804600,"81dc94efa84e4025ef38d25d5d07429fe41e3eb29d44003f1db6fe98487b0052"),
 "vocab.json":(1617791,"f1832ca38f7aa158b9a944ff583e4901e6b37d9d4ad9241f03838e636e9cfb03"),
}
ALIASES={
 "model.encoder.embed_tokens.weight":"model.shared.weight",
 "model.decoder.embed_tokens.weight":"model.shared.weight",
 "lm_head.weight":"model.shared.weight",
}


@dataclass(frozen=True)
class StudentProfile:
    vocab: int=65001
    hidden: int=512
    encoder_layers: int=6
    decoder_layers: int=6
    heads: int=8
    ffn: int=2048
    positions: int=512
    pad: int=65000
    eos: int=0
    unk: int=1

    def __post_init__(self):
        for name,cap in (("vocab",65001),("hidden",512),("encoder_layers",6),
                         ("decoder_layers",6),("heads",8),("ffn",2048),("positions",512)):
            value=getattr(self,name)
            if type(value) is not int or not 1<=value<=cap:
                raise ValueError("invalid student dimension: "+name)
        if self.hidden%2 or self.hidden%self.heads:
            raise ValueError("hidden must be even and divisible by heads")
        if (self.eos,self.unk,self.pad)!=(0,1,self.vocab-1) or self.vocab<4:
            raise ValueError("invalid special IDs")
        if self.positions<2:
            raise ValueError("positions must be at least two")

    @property
    def fixed(self):
        return self==StudentProfile()


FIXED=StudentProfile()


def expected_shapes(profile=FIXED):
    p=profile
    shapes={"model.shared.weight":(p.vocab,p.hidden),"final_logits_bias":(1,p.vocab)}
    for side,layers in (("encoder",p.encoder_layers),("decoder",p.decoder_layers)):
        prefix="model."+side+"."
        shapes[prefix+"embed_positions.weight"]=(p.positions,p.hidden)
        for i in range(layers):
            layer=prefix+f"layers.{i}."
            for attn in (("self_attn",) if side=="encoder" else ("self_attn","encoder_attn")):
                for proj in ("q_proj","k_proj","v_proj","out_proj"):
                    shapes[layer+attn+"."+proj+".weight"]=(p.hidden,p.hidden)
                    shapes[layer+attn+"."+proj+".bias"]=(p.hidden,)
                for field in ("weight","bias"):
                    shapes[layer+attn+"_layer_norm."+field]=(p.hidden,)
            shapes.update({layer+"fc1.weight":(p.ffn,p.hidden),
                           layer+"fc1.bias":(p.ffn,),layer+"fc2.weight":(p.hidden,p.ffn),
                           layer+"fc2.bias":(p.hidden,),
                           layer+"final_layer_norm.weight":(p.hidden,),
                           layer+"final_layer_norm.bias":(p.hidden,)})
    return shapes


def contract(profile=FIXED):
    shapes=expected_shapes(profile)
    return {"profile":asdict(profile),"d_revision":D_REVISION,
            "architecture":"Marian encoder-decoder, post-norm, swish, tied embeddings",
            "source_language":"English","target_language":"Chinese","language_prefix":LANGUAGE,
            "canonical_tensors":len(shapes),"fp32_payload_bytes":4*sum(math.prod(s) for s in shapes.values()),
            "fixed_rust_shape_profile":profile.fixed,"rust_deployable":False,
            "base_source":BASE_SOURCE,"base_revision":BASE_REVISION,
            "tokenizer_assets":{n:{"bytes":v[0],"sha256":v[1]} for n,v in ASSETS.items()}}


def build_student(profile=FIXED, *, seed=42):
    """Random initialization; no network, pretrained checkpoint or teacher weights."""
    import torch
    from transformers import MarianConfig, MarianMTModel
    if type(seed) is not int or not 0<=seed<2**32:
        raise ValueError("invalid seed")
    p=profile
    cfg=MarianConfig(vocab_size=p.vocab,decoder_vocab_size=p.vocab,d_model=p.hidden,
        encoder_layers=p.encoder_layers,decoder_layers=p.decoder_layers,
        encoder_attention_heads=p.heads,decoder_attention_heads=p.heads,
        encoder_ffn_dim=p.ffn,decoder_ffn_dim=p.ffn,max_position_embeddings=p.positions,
        activation_function="swish",scale_embedding=True,share_encoder_decoder_embeddings=True,
        tie_word_embeddings=True,pad_token_id=p.pad,decoder_start_token_id=p.pad,
        bos_token_id=p.eos,eos_token_id=p.eos,forced_eos_token_id=p.eos,
        dropout=0.1,attention_dropout=0.0,activation_dropout=0.0,
        encoder_layerdrop=0.0,decoder_layerdrop=0.0,
        normalize_before=False,normalize_embedding=False,add_final_layer_norm=False,
        max_length=p.positions,num_beams=4,bad_words_ids=[[p.pad]])
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model=MarianMTModel(cfg)
    canonical_state(model,p)
    return model


def canonical_state(model,profile=FIXED):
    """Validate exact canonical names/shapes, FP32 finite tensors, and tied storage."""
    import torch
    state=model.state_dict()
    shapes=expected_shapes(profile)
    if set(state)!=set(shapes)|set(ALIASES):
        raise ValueError("unexpected Marian state names: "+str(sorted(set(state)^ (set(shapes)|set(ALIASES)))))
    for name,shape in shapes.items():
        value=state[name]
        if tuple(value.shape)!=shape or value.dtype!=torch.float32 or not bool(torch.isfinite(value).all()):
            raise ValueError("invalid student tensor: "+name)
    for alias,name in ALIASES.items():
        value,shared=state[alias],state[name]
        if (value.shape!=shared.shape or value.dtype!=shared.dtype
            or value.data_ptr()!=shared.data_ptr() or value.stride()!=shared.stride()):
            raise ValueError("untied student weights: "+alias)
    return {name:state[name] for name in sorted(shapes)}


def checked_assets(root):
    root=Path(root).resolve(strict=True)
    for name,(size,expected) in ASSETS.items():
        path=root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=size:
            raise ValueError("invalid pinned tokenizer/config asset: "+name)
        with path.open("rb") as stream:
            data=stream.read(size+1)
        if len(data)!=size or hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError("asset checksum mismatch: "+name)
    return root


def no_duplicate_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate vocabulary key")
        result[key]=value
    return result


class StudentCodec:
    """Network vocabulary IDs, not raw SentencePiece IDs. No silent truncation."""
    def __init__(self,vocab,source_sp,target_sp,profile=FIXED):
        self.profile=profile
        if (not isinstance(vocab,dict) or len(vocab)!=profile.vocab
            or any(not isinstance(k,str) or not k or len(k.encode("utf-8"))>1024
                   or type(v) is not int for k,v in vocab.items())
            or set(vocab.values())!=set(range(profile.vocab))
            or any(vocab.get(k)!=v for k,v in
                (("</s>",profile.eos),("<unk>",profile.unk),("<pad>",profile.pad)))
            or LANGUAGE not in vocab or vocab[LANGUAGE] in (profile.eos,profile.unk,profile.pad)):
            raise ValueError("invalid shared vocabulary")
        self.vocab=dict(vocab)
        self.source_sp=source_sp
        self.target_sp=target_sp

    @classmethod
    def from_assets(cls,root):
        import sentencepiece as spm
        root=checked_assets(root)
        vocab=json.loads((root/"vocab.json").read_text(encoding="utf-8"),
                         object_pairs_hook=no_duplicate_keys)
        return cls(vocab,spm.SentencePieceProcessor(model_file=str(root/"source.spm")),
                   spm.SentencePieceProcessor(model_file=str(root/"target.spm")))

    def encode(self,text,*,target=False):
        if not isinstance(text,str) or not text.strip() or len(text.encode("utf-8"))>64000:
            raise ValueError("invalid student text")
        text=text.strip()
        if re.search(r">>[^<>]*<<|<pad>|</s>|<unk>",text):
            raise ValueError("explicit special token in text")
        sp=self.target_sp if target else self.source_sp
        pieces=sp.encode(text,out_type=str)
        ids=[self.vocab.get(piece,self.profile.unk) for piece in pieces]
        if not ids or any(i in (self.profile.unk,self.profile.pad,self.profile.eos) for i in ids):
            raise ValueError("unknown or special piece; reject rather than lose content")
        if not target:
            ids.insert(0,self.vocab[LANGUAGE])
        ids.append(self.profile.eos)
        if len(ids)>self.profile.positions:
            raise ValueError("student sequence exceeds positional limit")
        return ids
