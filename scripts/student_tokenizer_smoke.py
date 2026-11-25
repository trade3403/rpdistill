"""Real pinned tokenizer assets, HF low-level and pinned Rust network-ID parity."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from transformers import MarianTokenizer
from rpdistill.student import StudentCodec,LANGUAGE
from rpdistill.training_data import acquire_assets,ASSET_BYTES

exe=Path(sys.argv[1]).resolve()
cases={
    False:["Academic paper translation.","The results are statistically significant (p < 0.05).",
           "A 95% confidence interval was calculated.","The Transformer uses multi-head attention.",
           "The solution contained 25 mg/mL of NaCl."],
    True:["学术论文。","实验结果表明模型具有较高的准确率。","计算机科学与人工智能",
          "参考文献 [12]","温度为 25 ℃。"],
}
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    assets=acquire_assets(root,max_bytes=ASSET_BYTES+1048576)
    codec=StudentCodec.from_assets(root)
    ref=MarianTokenizer(source_spm=str(root/"source.spm"),target_spm=str(root/"target.spm"),
                        vocab=str(root/"vocab.json"),source_lang="en",target_lang="zh")
    checks=0
    rejected=0
    for target,texts in cases.items():
        (ref._switch_to_target_mode if target else ref._switch_to_input_mode)()
        inputs=[text if target else LANGUAGE+" "+text for text in texts]
        spm=root/("target.spm" if target else "source.spm")
        lines=subprocess.run([str(exe),str(spm),str(root/"vocab.json")],
            input="\n".join(inputs)+"\n",text=True,encoding="utf-8",
            capture_output=True,check=True).stdout.splitlines()
        assert len(lines)==len(inputs)
        for text,source,line in zip(texts,inputs,lines):
            expected=ref.build_inputs_with_special_tokens(ref.convert_tokens_to_ids(ref._tokenize(source)))
            rust=[int(i) for i in line.split("\t")[0].split(",")]
            assert expected==rust,(text,expected,rust)
            if codec.profile.unk in expected:
                try:
                    codec.encode(text,target=target)
                except ValueError:
                    rejected+=1
                    continue
                raise AssertionError("unknown piece accepted")
            got=codec.encode(text,target=target)
            assert got==expected,(text,got,expected)
            checks+=1
    assert checks>=6
    print(json.dumps({"assets":assets,"three_way_id_matches":checks,
                      "unknown_piece_rejections":rejected,"weights_downloaded":False}))
