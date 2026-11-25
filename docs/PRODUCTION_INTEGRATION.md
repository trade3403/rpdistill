# 独立自训练模型生产加载协调（E9b2）

## 当前已验证与未验证
RPDistill 独立 candidate v1 是固定 Marian F32 256 张量与五个固定资产的诊断包。E9b1 的真实 Rust bridge 在固定 D revision 上执行两组 encoder/full+cached decoder/greedy 对照。正式 RPTranslate 官方包 loader 应继续拒绝该包，原 D 仓库未修改。

## 本地集成候选审查接口
`student-review-integration` 使用外部可信 package pin、完整训练 checkpoint、冻结评测集、student/baseline report、盲评 packet/key/reviews、操作者明确权利声明、独立可信本地 Rust executable。重算默认质量门槛与 lexical audit，要求完整评审；实际核对全部源 tensor 与当前训练 selection/rights，逐段重放生成，重跑诊断。输出不可覆盖 receipt，绑定 package_id、weights_sha256、checkpoint_id、training_dataset、benchmark_id、评审、权利和 parity。任何失败不产生通过 receipt。receipt 自哈希不是签名；本地文件须无并发修改。外部基线与评审者身份未经验证，权利为操作者声明，不是法律认证。固定默认门槛是研发门槛，不是行业认证。

## D 线后续实施协议（未实现）
- 保持官方 RPModel v1 原来源、哈希及格式校验不变；为独立自训练模型新增明确区分的格式/profile 和独立加载入口，不覆盖官方模型路径。
- 可信外部 manifest pin 或受信发布方签名须独立分发，严格核验完整 inventory、大小、资产、权重、metadata、shape、aliases 与有限数；拒绝未知字段、错误 pin、路径逃逸与混用来源。
- 在真实 D loader 内完成分词器、encoder、decoder、KV cache、greedy/beam 与实际文本对照，测量完整模型延迟、峰值内存及异常回退；诊断 bridge 结果不能代替生产入口测试。
- 生产模型注册/选择与版本回退需明确授权及原子切换；不自动替换正在使用的模型。正式发行前核查真实权利、独立人评、GPU训练、基线、质量回归与可信发布链。
- E8 压缩候选只是存储压缩并还原 FP32，不能冒称 D 原生低精度推理；独立量化 profile 需另行审计。

当前只提交 RPDistill 代码，D 线变更需协调。E10 可独立进行实际诊断路径性能剖析，不能把生产集成待办标为完成。

## 双 pin 交接检查与终态复核
`student-check-handoff --root PACKAGE --receipt RECEIPT.json --expected-package-id HASH --expected-receipt-id HASH`；两个预期 ID 应由独立可信记录提供，不能从不可信候选自行取值充当授权。验证当前候选、receipt_id、权重/来源/评测绑定、默认质量审查、嵌套报告 hash、权利声明、重放结果、Rust 诊断身份；诊断报告不能冒充审批凭证。仅输出 handoff_integrity_verified=true、current_rights_revalidated=false、production_loader_verified=false、distribution_authorized=false、release_ready=false。生成新凭证前再核对候选与现有本地权利，完整训练状态核对 data_sha256。仍假定稳定本地文件与可信本地工具，不提供并发攻击防护、远端许可实时核验或数字签名。
