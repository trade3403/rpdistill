# E4a RPTranslate 学生模型兼容性审计

审计来源：trade3403/ai-research-pdf-reader 的 feature/rptranslate 固定提交 7f1fdb282bbdc947dc4a5d953768efaed429959d（只读，未修改原仓库）。

- [RPMODEL_FORMAT_V1.md](https://github.com/trade3403/ai-research-pdf-reader/blob/7f1fdb282bbdc947dc4a5d953768efaed429959d/rptranslate/docs/RPMODEL_FORMAT_V1.md)
- [D1.8_REAL_MODEL.md](https://github.com/trade3403/ai-research-pdf-reader/blob/7f1fdb282bbdc947dc4a5d953768efaed429959d/rptranslate/docs/D1.8_REAL_MODEL.md)
- [config.rs](https://github.com/trade3403/ai-research-pdf-reader/blob/7f1fdb282bbdc947dc4a5d953768efaed429959d/rptranslate/crates/rpmodel/src/config.rs)
- [package.rs](https://github.com/trade3403/ai-research-pdf-reader/blob/7f1fdb282bbdc947dc4a5d953768efaed429959d/rptranslate/crates/rpmodel/src/package.rs)
- [marian_weights.rs](https://github.com/trade3403/ai-research-pdf-reader/blob/7f1fdb282bbdc947dc4a5d953768efaed429959d/rptranslate/crates/rpinfer/src/marian_weights.rs)
- [offline.rs](https://github.com/trade3403/ai-research-pdf-reader/blob/7f1fdb282bbdc947dc4a5d953768efaed429959d/rptranslate/crates/rptranslate/src/offline.rs)
- [convert_opus_checkpoint.py](https://github.com/trade3403/ai-research-pdf-reader/blob/7f1fdb282bbdc947dc4a5d953768efaed429959d/rptranslate/tools/convert_opus_checkpoint.py)

## 已确认的固定模型契约

Marian encoder-decoder 6+6 层，hidden 512，8 heads，FFN 2048，Swish，post-norm，scale_embedding=true，位置表 512×512，网络词表 65001，pad/start 65000，EOS 0，UNK 1，源语言前缀 >>cmn_Hans<<。共享 embedding 与 tied LM head；两张位置表和 final_logits_bias 保留。256 canonical tensors，312033188 FP32 payload bytes；不含文件头、KV cache、训练优化器或进程内存。D 线当前固定 Helsinki-NLP/opus-mt-en-zh 的审计 revision a4193836671069f1f80ce341f9227a850ffb52d4。source.spm、target.spm 与 vocab.json 必须匹配固定哈希，网络 token ID 与 SentencePiece ID 不等价。

## E4a 实现

student.py：精确 shape/name/dtype/finite/tied storage 验证、随机初始化 Marian 学生（不是已训练模型）、只读本地资产完整性检查、SentencePiece piece → 共享词表映射、源前缀和 EOS、拒绝未知 token/过长文本而不截断；源/目标分别使用 SPM。学生 optional extra，不会使基础 CLI 导入 torch。新增 student-info CLI。CI：合成小尺寸真实 CPU 前向、完整固定尺寸随机初始化与 canonical shape/payload 校验，不联网下载权重；另有 4 个无 torch 的单元测试。未实测固定资产上的真实 SentencePiece 编码或 Rust token parity；后续 E4b 完成。

## 明确不兼容之处

当前 Rust loader 对官方来源、revision、checkpoint SHA、固定配置/分词器及 canonical 权重 manifest 有强约束。新学生权重来源不同，即便形状相同也不能把它伪装成官方基线权重；现阶段 rust_deployable=false。E9 必须协调 D 线独立自训练 package profile、可信来源与实际 Rust 加载/数值/生成对照，不能修改官方 SHA 冒充官方包。E4b 接真实本地分词器资产与训练 batch、mask、labels、长度限制及小型真实 CPU 训练入口；E5 执行实际学生参数更新、检查点和蒸馏。可缩小的测试 profile 不是 D 线部署模型。真实 Qwen 权重及 GPU 留用户本机验收。
