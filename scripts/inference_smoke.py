"""Actual local CPU inference on a tiny randomly initialized fixture (not quality)."""
import hashlib
import json
from pathlib import Path
import tempfile

import torch
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast

from rpdistill.inference import TranslationOptions, load_teacher
from rpdistill.teachers import Teacher, TeacherRegistry

REV = "a"*40

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    snapshot = root / "snapshot"
    snapshot.mkdir()
    torch.manual_seed(42)
    vocab = {"[UNK]":0, "[PAD]":1, "[EOS]":2, "source":3, "translation":4,
             "system":5, "user":6, "assistant":7, "test":8}
    raw = Tokenizer(WordLevel(vocab, unk_token="[UNK]"))
    raw.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=raw, unk_token="[UNK]",
                                        pad_token="[PAD]", eos_token="[EOS]")
    tokenizer.chat_template = ("{% for message in messages %}{{ message['role'] }} "
        "{{ message['content'] }} {% endfor %}{% if add_generation_prompt %}assistant {% endif %}")
    tokenizer.save_pretrained(snapshot)
    model = GPT2LMHeadModel(GPT2Config(vocab_size=len(vocab), n_positions=256, n_embd=16,
                            n_layer=1, n_head=2, bos_token_id=2, eos_token_id=2, pad_token_id=1))
    model.save_pretrained(snapshot, safe_serialization=True)
    manifest = [{"name":p.name, "size":p.stat().st_size,
                 "sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in snapshot.iterdir() if p.is_file()]
    TeacherRegistry(root/"db").put(Teacher("fixture/tiny", REV, "synthetic", False, False, None),
                                    snapshot, manifest)
    teacher = load_teacher(root/"db", "fixture/tiny", REV,
                           TranslationOptions(batch_size=2, max_input_tokens=200, max_new_tokens=4))
    rows = teacher.translate(["test source", "source test source"])
    assert len(rows) == 2
    assert all(0 <= row["generated_tokens"] <= 4 for row in rows)
    assert all(row["teacher"]["revision"] == REV for row in rows)
    assert all(row["finish_reason"] in ("eos", "length") for row in rows)
    assert all(isinstance(row["translation"], str) for row in rows)
    print(json.dumps({"fixture":"random tiny local GPT2", "device":"cpu",
                      "segments":len(rows), "quality_test":False,
                      "generated_tokens":[r["generated_tokens"] for r in rows]}))
