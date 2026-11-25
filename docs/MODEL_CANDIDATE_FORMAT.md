# RPDistill 自训练候选包 v1（E9a）

独立 schema：`rpdistill-model-candidate-v1`。不是官方 RPModel v1，不冒用 Helsinki-NLP 原始模型权重身份。D 线最新只读审计提交 [cce002d](https://github.com/trade3403/ai-research-pdf-reader/commit/cce002dd2667e6fcd0ec4c86c9b41a3da144b26e)，官方 package::open 仍要求固定官方 source/revision/checkpoint SHA/metadata/F32；原仓库未修改。

## 文件

- manifest.json：规范 JSON、64KiB 上限，独立 schema、固定 profile、三条共享权重逻辑 alias、原训练 checkpoint ID/schema/dataset/provenance SHA、分词器独立来源及许可标签、操作者声明模型许可及权利说明、全部 6 文件大小与 SHA256、package_id（排除自身字段后的规范 JSON SHA256）。
- weights.safetensors：256 个 canonical tensors、F32、312033188 payload bytes；metadata format=pt / rpdistill_format=1 / source_checkpoint_id；不出现官方 rpmodel_format/source_sha256。LM head 共享表，不复制。
- config.json / generation_config.json / source.spm / target.spm / vocab.json：沿用 D 线审计的固定 5 个 tokenizer/config 资产，字节及哈希逐个验证，总 3230522 bytes。分词器来自官方固定 revision，训练权重不是官方权重。

## 创建与验证

仅完整 E5/E6 固定尺寸训练检查点，严格校验训练 dataset 和 checkpoint、模型张量，要求明确候选用途确认和操作者许可/权利说明。没有默认自训练权重许可证，不自动认定拥有分发权。写入同一父目录临时目录，校验后 rename，新目录不覆盖；假定稳定本地文件及单写者，未提供跨进程事务或抵抗并发恶意修改保证。

`student-export-plan` 只计算布局；`student-export-candidate VERSION --checkpoint DIR --assets DIR --output NEW_DIR --license-label LABEL --rights-note NOTE --max-bytes 340000000 --acknowledge-candidate-only`；`student-verify-package --root DIR --expected-package-id HASH`。校验必须由调用者独立提供预期 package_id，哈希本身不构成签名、可信身份或正式授权。候选 quality_approved=false、distribution_authorized=false、release_ready=false、rust_deployable=false。

## CI 及 E9b

独立 workflow checkout 固定 D commit，仅在 Runner 临时 checkout 增加 test-only Rust example，通过实际自主 SafeTensorReader 读取全部 256 FP32 张量，比较规范 little-endian stream SHA256/字节数、检查点权重逐位相等，并确认官方 package loader 拒绝独立候选。脚本以完整尺寸网络真实执行 1 个合成 token 训练步，非正式科研译文质量，不下载官方大型权重。待新 CI 验收。当前尚未通过 Rust 神经网络加载/生成，且未接自动质量授权或压缩候选导出；E9b 需独立生产加载入口、可信 pin/版本策略、实际 Rust encoder/decoder/generation 对照与质量授权绑定。正式许可、归属/训练数据限制、真实人评与发布策略仍需核查。
