# E 线路交接

仓库：trade3403/rpdistill；主分支 main。原科研 PDF 仓库 A/B/C/D 分支不得修改。

当前 E3.1：E2.3 CI 10/10 已通过；Europe PMC 论文发现与许可预筛已提交待 CI。

接手步骤：
1. 查阅本文件、ROADMAP、ARCHITECTURE。
2. 核实最新 main 提交与 CI；修复失败，不虚报测试通过。
3. E2.2b1 CI 通过后推进 E2.2b2 SDK 安装/联网验收与字节级进度，再 E2.3 和 E3。
4. 阶段完成后更新交接与测试记录，提交到本仓库。
5. 进入 E4 前核实 RPTranslate 当前真实模型结构和格式；不假定兼容性。

尚未确定 GPU 硬件、教师具体模型、开源许可证；公开仓库不等于已选定软件许可。

## 持续维护
每次阶段开发、提交、CI 验收和实测后同步 `PROGRESS.md`，功能范围或状态变化同步 `FEATURES.md`；记录真实 SHA、CI 链接、测试结果、阻塞和下一步。接手时先读这两份文件并重新核实 CI。不得将规划或演示当作实际完成。

## 在线下载硬性要求
E2 必须优先实现教师模型内置在线搜索、一键下载、暂停恢复、校验及自动注册（Hugging Face / ModelScope）；E3 实现开放许可语料在线下载，E11 接入下载中心 GUI。正常联网流程不得要求用户在浏览器手动下载权重或语料；受限资源须用户授权。具体以 FEATURES.md F23 与 ARCHITECTURE.md 为准。

## 论文在线采集硬性要求
用户所指在线下载重点是科研论文，而不仅是模型/现成数据集。E3 优先落实 F24：软件内检索、批量合法全文下载、自动解析、分段入库及教师翻译生成语料；不要求用户手动下载 PDF。验收须有真实开放许可论文全流程记录，具体参见 ARCHITECTURE.md；未知许可或受限全文不得自动采集训练。

## 全自动化核心目标
优先阅读 AUTOMATION.md：RPDistill 正常联网工作流必须实现从自动检索论文到蒸馏、评测、导出的无人值守运行，不能只提供彼此独立的工具按钮。E1.1 基础代码对应 CPU CI 已成功，E1.2 基础代码已提交；后续提交须重新检查 CI。

## GUI 设计依据
E11 界面须参考 `docs/assets/rpdistill-auto-distill-dashboard.png` 与同目录 README；实际模型、设备和进度来自后端，禁止用设计稿示例数据冒充实测。

## 测试环境
GitHub 标准免费 CPU runner 用于轻量跨平台 CI；真实 GPU、大模型、长时间蒸馏测试使用用户自己的电脑。先提供可复现本地命令及真实验收报告模板。不在托管 runner 下载大模型或声称模拟 GPU 测试等于实际训练。

E1.2 首次 CI 六环境失败，已修复 TaskStore 类型注解名称遮蔽问题；详见 PROGRESS.md。重新验证修复提交全部通过后才进入 E2。

E1.2 修复 CI 45581701119 已成功（6/6）。E2.1 可选 Hub 依赖安装方式见 README。CLI model-download 需要实际完整 commit SHA、已审核许可证标识与下载字节预算，仅公开 SafeTensors；合成测试通过不代表真实模型已验证。下一阶段补下载队列/进度/恢复与真实小模型验收，按用户要求大模型在用户电脑运行。

E2.1 CI 45582334642 已通过 6/6；E2.2a 新增 downloads.py。队列单 worker，每次 download-run 执行一个任务；只在文件间响应控制，缓存复用由 SDK 提供，真实断点续传待联网验证。恢复异常退出必须确认旧 worker 停止；禁止同时直接下载同一缓存绕过队列。剩余 ModelScope、网络字节实时速度和后台调度待开发。

E2.2a CI 45582666202 已成功。E2.2b1 使用独立 ModelScope SDK 可选依赖及来源注册表；下载仅接受公开、已审核许可、完整 SHA 和每文件上游 SHA-256。实时网络速度未实现，真实服务行为未验收。

E2.2b1 CI 45585519890 已通过 6/6。E2.2b2 新增 Hugging Face 队列流式 HTTP 传输、网络计数和 Range 恢复；旧 SDK 直接下载和 ModelScope 保留文件级进度。请先核验标准 CI（6 环境 + SDK 安装）及独立 Public Hub live smoke。后者只测试小 config 与查询，不代表模型下载/推理通过。网络实测、ModelScope 字节进度与 streaming 队列专项测试仍需完善。真实大模型与 GPU 训练在用户电脑进行。

E2.2b2 标准 CI 45586043352 与联网 smoke 45586043462 全部成功。E2.3 inference.py 使用已注册并重新核验的 SafeTensors 本地模型，禁用远程代码，支持显式 CPU/CUDA、批量生成和版本来源记录。新增独立 real-cpu-inference job，随机微型模型不用于质量验收。先核验最新 CI 全部通过，再进入 E3.1 论文检索、合法许可过滤、元数据和去重。真实 Qwen GPU 测试留用户电脑。上下文不足风险出现时提前给用户最新交接 Prompt；未出现风险则继续当前窗口，不要每阶段重复输出交接。

E2.3 CI 45586949170（8/8）及 45586948901（2/2）已通过。E3.1 papers.py 只处理检索元数据；CC BY/CC0+OA+PMCID 进入 pending_fulltext_license，不是训练授权，缺失或限制许可阻断。先检查标准 CI 和 Paper discovery live smoke，再 E3.2 从官方 OA 接口复核全文权利与合法下载，随后解析/多来源。实际千问 GPU 质量仍待用户本机。不要将已有历史待验收记录误作当前状态，以上最新记录优先。

E3.1 标准 CI 45588253788 8/8 已通过；论文联网 45588253824 因 Europe PMC HTTP 503 失败。已提交有界重试及 Retry-After 处理，保持联网断言，必须核验新提交两套 CI 后再进入 E3.2。累计 66 个单元测试方法。

E3.1 修复标准 CI 45588726018 8/8 成功，但真实 Europe PMC 45588726112 重试后仍 HTTP 503。新增 NCBI PMC 备用检索、CLI --provider auto/europe-pmc/ncbi-pmc 及独立联网 job，保留原 Europe PMC job。先核验本次标准 CI 与两个 provider 联网结果；若 Europe PMC 持续不可用，不将其标绿，需单独记录外部阻塞。累计 73 测试方法，未进入 E3.2。后续全文使用 PMC 当前 OAI-PMH / Cloud Service 等官方接口，不依赖已退役的旧 OA Web Service。

最新 E3.1 代码 97d7c3a6aaca1a88e73d514bacca9e33f03cb7bc：标准 CI 45589377280 8/8 通过，联网 45589377415 首次 attempt 中 NCBI PMC 实测 3 条成功入库，Europe PMC HTTP 503 失败。已请求仅重跑失败 job。此次仅更新文档，无功能代码变化；核验文档提交标准 CI 与代码 SHA 的联网 run，全部通过才进入 E3.2，或由用户明确授权改变外部服务门槛。不得将 NCBI 成功等同 Europe PMC 恢复。

E3.1 最新修复：标准 CI 45592551774 8/8 通过，双来源联网 45589377415 attempt 3 中 Europe PMC HTTP 503，NCBI PMC 成功。按官方 REST 文档修复 sort=P_PDATE_D desc，FIRST_PDATE 范围筛选保留，新增请求契约测试（累计 74 个）。根因未确认，需核验最新代码 SHA 对应标准 CI 和双来源真实联网全部成功才进入 E3.2。


最新用户授权覆盖历史门槛：暂缓 Europe PMC 论文检索，不再阻塞其他开发，保留独立手动真实失败测试。标准 CI 45592551774 8/8、NCBI 联网 45589377415 success；Europe PMC attempt 3 failure。E3.2 fulltext.py 官方 PMC OAI-PMH 先 pmc_fm 再 pmc，双重许可与身份核验、预算、XML 文件库、SHA256、持久状态，累计 81 测试方法。需核验最新标准 CI 与常规 NCBI 检索/全文联网；Europe PMC skipped 不计通过，后续单独复验。全文待内容权利复核，不直接训练。下一阶段 E3.3 解析/分段及语料生成，其他来源后续扩展。

并发修复合并说明：保留 6c37e2d90623806b62baafb3a9cac59e8dd50b01 的 Europe PMC 排序字段修复及测试；其标准 CI 45596188128、双来源联网 45596188201 已通过。此前失败为历史记录，最新 Europe PMC 已实测恢复。按用户要求仍暂缓其常规联网门槛，NCBI PMC 为默认来源，Europe PMC 可手动复验。E3.2 新提交待验收。

E3.2 首次标准 CI 45596496110 8/8 通过；联网 45596496006 NCBI 检索通过、Europe PMC skipped、全文 job 失败（3 条元数据被校验阻断）。新增 JATS 相关标识与嵌套许可 URI 兼容修复；保留严格许可检查和真实下载断言。先核验新提交标准/全文联网 CI，再 E3.3；若仍失败读取实际 statuses 诊断，不以放宽权利检查换取通过。

E3.2 5144ec8 CI 45597390219 8/8 + 45597390263 NCBI 2/2 success；Europe PMC 授权暂缓。实际保存 10 篇 CC BY XML，1,436,306 字节。E3.3a corpus.py 已提交：许可哈希复检、保守解析、分段、SQLite 源段和候选译文、数字筛查、来源署名、论文划分、候选 JSONL。真实 XML smoke 增加解析断言。先核验最新标准和 NCBI CI；通过后 E3.3b 数据集版本、质量门槛、断点及采集→翻译调度。不得将 screened_candidate 当成训练授权/质量认证。复杂公式、语言和术语检查仍待完善。

E3.3a 6387e7a 标准 45599371724 8/8 + NCBI 45599371716 2/2 success；真实 10 篇解析 337 段候选原文。E3.3b datasets.py/ pipeline.py 新增内容寻址候选版本、精确跨版本 split 防护、质量数量门槛、单次自动采集→候选快照、持久阶段和部分恢复；新 CI 待核验。无真实 Qwen 翻译质量、无正式训练授权、无持续调度。下一阶段 E4 必须先读取 trade3403/ai-research-pdf-reader feature/rptranslate 实际架构/分词器/包规范；不要改原仓库。Europe PMC 用户授权暂缓。未完成增量/语义/近重复等事项见 PROGRESS。

E3.3b 65619c3 标准 45601299054 8/8 success；之前 NCBI 联网 45599371716 成功且采集代码未变。E4a D 线只读审计 7f1fdb282bbdc947dc4a5d953768efaed429959d，详见 STUDENT_CONTRACT.md；新增 student.py、student-info、student extra、4 单元测试和真实 CPU 学生 job。当前仅形状契约及随机初始化，不是训练或部署，Rust loader 固定官方来源哈希，E9 须独立自训练包。先查本次最新 CI；通过后 E4b 真实 tokenizer/训练 batch，E5 参数更新。保持原 D 仓库只读，真实 GPU 本机。Europe PMC 授权暂缓。

E4a 4250379 CI 45603053723 9/9 + 45603053807 2/2 success；E4b training_data.py、student-assets/student-batch-plan、固定资产下载及候选版本分词与 masked batches，5 新单元测试、真实 CPU masked loss、新 Student tokenizer live parity workflow（D 线固定审计 SHA 只读）。先核验最新标准 CI 与真实 tokenizer parity（若 Hub 回归未触发，沿用最新成功的未变代码结果）。随后 E5 真实微型 sequence-level 蒸馏权重更新及 checkpoint，正式训练前必须复核语料/教师权利与质量，不能把 candidate_snapshot 当已认证训练集。完整尺寸 GPU 仍留本机，E9 Rust 自训练包适配，Europe PMC 按用户授权暂缓。

E4b c787152 CI 45604907365 9/9 + 45604907414 1/1 success；5 固定资产 3230522 bytes、10/10 三方 IDs、真实 masked CE 3.4788079261779785（5 tokens）。E5a distill.py CPU FP32 sequence-level AdamW、反传/裁剪、评估 loss、SafeTensors 权重 checkpoint 与重载；CLI student-distill 需精确 dataset review 与注册 teacher license review。新增 3 unit tests 和 scripts/distill_smoke.py 在 real-cpu-student job 真训练 80 steps，合成 targets、参数变化/损失下降/roundtrip/损坏拒绝；待新 CI。先核验 exact head 标准 CI，未改动的 tokenizer/Hub/论文联网沿用既有成功；若失败先修。通过后 E6a 精确优化器/RNG/进度 checkpoint、梯度积累/恢复与资源控制，CUDA 真实本机验收。当前只权重 checkpoint，非 RPModel，不能宣称真实 Qwen 质量或正式训练授权。保持 D 仓库只读，Europe PMC 用户授权暂缓。上下文交接仅在真实风险时提供。

E5a 33a5951 标准 CI 45606587882 9/9 success；真实 job 139178917662 80 steps、43 tensors changed、loss 3.482527494430542→0.002275040838867426、权重/logits roundtrip、损坏拒绝成功，合成数据非翻译质量。E6a resumable.py 完整 SafeTensors 状态、CPU RNG/AdamW/epoch/cursor、token 加权累积、单段步数和软时间/单 checkpoint 磁盘预算，CLI student-train-resumable；3 新 unit tests，scripts/resume_smoke.py 要求 7 steps vs 2+2+3 全状态与 history 位一致，待新 CI。先核验 exact head 标准 CI；未变联网路径沿用成功结果。若通过，E6b GPU/AMP/定期保存/持久调度；真实 GPU 在本机。注意 resume 仅同 CPU 环境、段末保存，强杀损失本段，时间不是硬 deadline。D 线只读，Europe PMC 用户授权暂缓，正式语料/教师权利与质量仍需复核。E9 才做自训练 Rust 包。交接仅在真实上下文风险时提供。

E6a a3fedba 标准 45608461745 9/9 success；job 139185411102 7 steps vs 2+2+3，176/176 states、history、optimizer/RNG 位一致。E6b1 CUDA/AMP 已提交：ResumeConfig device/precision/cuda_budget_bytes、显式 CUDA 不 fallback、native BF16、FP16 GradScaler/unscale/clip、CUDA RNG 与 scaler/env checkpoint，保留旧 CPU config_record；显存只是 preflight/step-boundary soft budget。新增 scripts/cuda_smoke.py 本机显式 GPU 验收（未运行）、CPU CUDA unavailable 拒绝及配置测试。先核验 exact head 标准 CI 和 tokenizer live parity（student.py 变更触发）。通过后 E6b2 持久训练队列、分段自动保存及累计预算/暂停恢复；本机 GPU 仍待验收，不阻塞已通过的 CPU 基础开发，但不可声称 GPU 已通过。正式数据/教师权利与质量须复核，E9 Rust 包待做；Europe PMC 暂缓，D 只读。上下文交接仅实际风险时。

E6b1 a91dd39 标准 45610312760 9/9 + tokenizer 45610312728 1/1 success，真实 GPU 尚未运行。E6b2 training_queue.py SQLite 队列/事件、单 worker、自动分段 checkpoint、暂停取消边界、recover 确认、累计时间/磁盘保守预留、不信任孤立文件，resumable.py should_stop，training-* CLI；5 unit tests + scripts/training_queue_smoke.py 真实 CPU pause/重开 DB/恢复 5 steps、3 checkpoints、最终状态逐位对照，待新 CI。先核验 exact head 标准 CI，未改动的 tokenizer/Hub/论文联网沿用已通过结果。若成功，E7 独立评测数据、翻译生成与指标（或先补训练→评测接口）。注意 E6b2 并未实现常驻服务、跨任务全局资源锁、完整采集→审核→训练触发、硬时间/显存限制。正式训练须用户复核教师/内容权利与质量；真实 GPU 本机。E9 D 线自训练包，原 D 仓库只读。上下文交接仅实际风险时。

E6b2 head 17efb1c CI 45611935152 9/9 success，真实 CPU queue 5 steps/3 checkpoints/176 equal tensors，pause restart resume 和预算预留通过；E6b1 GPU 未本机验收。E7a evaluation.py/benchmark-freeze/benchmark-score：独立人工参考声明、训练快照哈希与精确文本/DOI/PMCID 排除、SacreBLEU zh BLEU/chrF、科研字面/启发式检查、数量及指标 gate、冻结报告，4 unit tests 与 real-evaluation job 待 CI。外部 hypotheses 未认证模型输出、自动门槛非发布，近重复及人工评审未完成。核验新标准 CI，pyproject 变更可能触发 Hub/tokenizer live workflows，全部适用 CI success 后 E7b 真实学生 checkpoint 推理、基线与盲测/性能；COMET 如适用且许可/预算明确。真实 GPU/Qwen 在本机，原 D 仓库只读，Europe PMC 暂缓。交接仅实际风险时。

E7a 已存在 main 8c0a13e；标准 45612791270 10/10 + Hub 45612791012 2/2 + tokenizer 45612790903 1/1 success（13/13）。真实 SacreBLEU synthetic reference identical BLEU≈100/chrF100，错误 BLEU9.8071/chrF15.2033，质量门槛/覆盖/重叠/损坏拒绝。E7b1 student_evaluation.py/benchmark-student 已提交：E5 权重/E6 complete state 安全 model-only 加载、dataset binding、真实 CPU greedy 译文、自然 EOS/长度/特殊 token 筛查、真实 latency/token/s、weight bytes、可选同 benchmark 外部 baseline delta；2 unit tests + real tiny CPU 两 checkpoint formats 训练生成 smoke。先核验 exact head 标准 CI，未变 Hub/tokenizer 沿用已通过结果。生成只 CPU no cache，合成分词/目标不是实际质量；报告 release_ready=false、外部 baseline 未认证，模型本地生成非第三方签名。E7b2 近重复/独立人工盲测/正式质量门槛与真实基线、RSS/性能，COMET 适用性/许可/预算；E8 量化之后。真实 GPU/Qwen 本机，D 仓库只读，Europe PMC 用户授权暂缓。保持交接记录，实际上下文风险才输出 Prompt。

E7b1 bbc685f 标准 45613582255 10/10 success；job 139203108793 两 checkpoint format 真实 CPU 生成、EOS、合成 chrF 100/100、错误绑定/损坏/覆盖不足拒绝，续训/队列 176 tensor parity。E7b2 quality_review.py 有界 lexical overlap/匿名 A/B packet+private key/两声明独立评审完整评分/重算指标和候选 gate，CLI benchmark-leakage-audit/blind/review，Linux/macOS process peak RSS，3 unit tests + 合成盲评真实 CPU 回归；新 CI 待验收。下一 E8 权重压缩及质量回归，先核验 exact head 标准 CI；未变联网沿用成功结果。真实人评、教师/GPU、真实 baseline/正式门槛未完成，COMET 暂缓，release_ready=false。D loader 固定官方包，E9 独立自训练包不可冒充官方；原 D 仓库只读，Europe PMC 授权暂缓。保持交接，实际上下文不足风险才给 Prompt。

E7b2 5122a06 标准 45615224138 10/10 success；job 139208745858 合成 2 reviewer 盲评、lexical audit/覆盖不足拒绝、RSS 430583808，真实人评 false。E8a compression.py FP32/矩阵 FP16/逐行 symmetric INT8+FP32 scale，位置/偏置/norm F32，绑定 E5/E6 complete checkpoint & dataset，payload/errors/hash/预算/不可覆盖，load_candidate 还原 FP32；CLI student-compression-plan/student-compress，3 unit tests 与真实微型三格式压缩还原生成 smoke，待 exact head CI。D 线只读最新 5389f3f，仍官方固定 F32，rust_deployable=false。E8b 同真实冻结 benchmark 进行原 checkpoint vs 压缩候选实际质量回归，明确源权重对照/候选选择，不能凭合成数据认定正式质量；E9 独立自训练包。真实 Qwen/GPU/人工评审本机，Europe PMC 用户暂缓。先核验最新标准 CI；未变化 Hub/tokenizer 沿用成功结果。上下文风险才提供交接 Prompt。

E8a 0046e0e CI 45615777344 10/10 success，job 139210668370 三种实际微型转换/还原/生成通过；固定尺寸 payload 312033188/157391780/80601416 bytes（估算）。E8b compression_review.py/benchmark-compression：同一原 checkpoint 重新验证转换、实际同冻结 benchmark 评分、固定绝对 gate+相对 gate/逐条新增规则错误、lexical audit、最小实际 artifact 选择或 null；4 unit tests + 真微型三候选/覆盖不足/错误源与转换拒绝 smoke，待 exact head CI。未变联网路径沿用通过结果。下一 E9 必须重新读取最新 D loader，当前官方固定 F32，独立自训练包不伪造官方身份；原仓库只读，必要 D 侧修改明确记录待协调，不冒充兼容。真实 GPU/Qwen/人评留本机；Europe PMC 暂缓。仅真实上下文风险时提供交接 Prompt。

E8b de36eb9 CI 45617423525 10/10 success，job 139216341097 同源3候选、合成输出不变、覆盖不足拒选、错来源及篡改转换拒绝。E9a model_export.py、student-export-plan/student-export-candidate/student-verify-package、MODEL_CANDIDATE_FORMAT.md、3 unit tests 与独立 model-export-live.yml：独立 F32 256张量候选，5固定资产、源 checkpoint/dataset/provenance、许可声明、hash+外部 pin、不可覆盖、预算；完整尺寸真实单步合成 CPU 训练后导出并用固定 D commit cce002dd 的 raw reader 全字节流对照，官方 loader 应拒绝；未修改 D 仓库。先核验 exact head 标准 CI 和 Independent model export Rust parity，未变联网路径沿用已通过。若成功 E9b 独立自训练 Rust package 入口与真实推理对照/质量授权，须协调原 D 侧变更或在独立开发测试适配中完成，不伪造官方来源。不把 hash 当签名，候选不发布，真实 GPU/Qwen/正式人工质量本机。Europe PMC 暂缓；仅实际上下文风险时交接 Prompt。

E9a 1ce24ce 标准 45619532043 10/10 + full-export 45619531918 1/1 success；job 139223662017 实际完整尺寸训练1步、256 tensors、312033188 bytes raw reader SHA256 c4d318f999a9e00e5e03b46361d9d090e2dfd49a53a54c641601ea9a9c7cbb7e，官方 loader/错误 pin/损坏拒绝。E9b1 rust_parity.py、scripts/rpdistill_candidate_infer.rs、student-rust-parity、2 tests，固定 D 2fa70c1 临时 checkout 编译，Python full package pin + Rust weight hash/metadata/assets/shape + 实际 encoder/decoder full/cached logits、greedy 2 token/mask cases，atol=rtol=3e-4；扩展独立专项、错误 weight/checkpoint pin 拒绝。待 exact head 标准及 Independent model export Rust parity CI，未变联网路径沿用成功。若通过 E9b2 质量/权利审批与导出衔接、生产接口协调，诊断 bridge 非正式 RPTranslate 加载、不改 D、非质量/发布；本机 GPU/真实人评仍待。Europe PMC 暂缓。实际上下文风险才交接 Prompt。

E9b1 8aa263a 标准 45621311986 10/10 + Rust 45621311499 1/1 success，真实 job 139229896843 256 F32 tensors、312033188 raw bytes，2 case encoder/full/cached decoder/greedy parity，max abs 4.291534423828125e-6，错误 pin/损坏/官方拒绝。E9b2 export_review.py + CLI student-review-integration 重新核验默认质量/盲评、当前训练权利与选择、实际全部源权重、逐段重生成、重新 Rust parity，独立哈希 receipt（非生产批准/签名/法律认证）。5 unit tests + 完整尺寸真实 source binding/错误来源拒绝；先核验 exact head 标准和 Rust 专项 CI。原 D 只读，生产 loader 尚未接入，接口协调见 PRODUCTION_INTEGRATION.md；本机实际 GPU/Qwen/人工盲评/正式质量待验收。通过后 E10 性能剖析与优化，不冒充生产加载已完成。Europe PMC 暂缓。仅实际上下文风险才交接 Prompt。

E9b2 保留并行提交 07dca119 的 export_review.py，补充 student-check-handoff 双 pin 校验、嵌套质量及 Rust 报告 hash/来源绑定、full-state token data hash、签发前再核对当前本地权利与包；2 新 unit tests、微型真实 replay 与实际指标覆盖拒绝、full-size diagnostic report 非审批 receipt。核验最新 exact head 的标准及 Rust 专项 CI 后进入 E10；原 D 只读、生产加载尚未实现、正式人工/真实模型质量与 GPU 本机、无发布授权。交接检查不等于重新审核权利。

E9b2 a7582b5 标准 CI 45623637959 10/10 + Rust 专项 45623638472 1/1 success；实际微型生成重放、质量覆盖不足拒绝（job 139238005444），实际完整尺寸 Rust 诊断及诊断报告非审批凭证拒绝（job 139238007240），两组 greedy 一致、max abs logits 3.814697265625e-6。E10a rust_profile.py / scripts/rpdistill_candidate_infer.rs --profile / student-rust-profile：固定 16/64 source tokens、8/16 max new tokens、每组1 warmup+3 measured、交替 full/cache 次序、同一完整尺寸模型实际输出一致，记录实际生成 token、六项加载阶段 ns、encoder/decoder prepare/full/cache generation 分段、median/token/s/cache ratio、Linux Rust 进程生命周期 peak RSS、exe/weights/package hash 和 host 信息。性能为合成 token 诊断 workload，非翻译质量、冷缓存保证、真实用户场景或生产性能；不要求固定加速倍数，重复结果/协议不一致拒绝，可信 executable 和稳定本地文件假设。3 unit tests 与真实完整尺寸专项新增 profiling，待新标准与 Rust 专项 CI。E10b 依据实测进行优化及精度回归，不盲目重写 PyTorch；原 D 仓库不修改，生产接口仍待协调；真实 GPU/人工/质量留本机。
先核验 exact head 标准和 Independent model export Rust parity，检查实际 profile JSON 日志；若通过进入 E10b，未变其他联网路径沿用历史通过。上下文实际风险才输出交接 Prompt。

E10a 28f728459dbe502b13bd717bb748c8088c76f0e2：Rust 专项 [45625397449](https://github.com/trade3403/rpdistill/actions/runs/45625397449) 1/1 success，job 139244112848；标准 [45625397448](https://github.com/trade3403/rpdistill/actions/runs/45625397448) 4/10 success，六个跨平台 unittest job 同一 test_early_eos 失败（原 fixture 字符串替换同时命中较长序列前缀，导致 EOS 后仍有 token；解析器正确拒绝）。修复为按 case 构造提前 EOS，测试仅短/仅长/两组，新增显式 EOS 后 token 拒绝测试；不修改 runtime parser 或门槛。专项 workflow 增加 test_rust_profile.py 路径以重新验证 exact head。待新标准及专项全部通过才进入 E10b。历史实测 Linux x86_64 4 logical CPUs，16→8 tokens encoder 249720496ns/full 2595300952ns/cache 2293468055ns，64→16 encoder 381493704ns/full 5614579083ns/cache 4561371208ns；cache ratios 1.13160545/1.23089721，full token/s 3.082494/2.849724，cache token/s 3.488167/3.507717；RSS 323821568 bytes，weight hash 1122456331ns。生成 IDs 一致。合成诊断非质量或生产 SLA；优先剖析 decoder 路径，仍需细分实际瓶颈。原 D 只读。
下一次先核验新 exact head 两项工作流；标准未全部通过不得开始 E10b。

E10a 修复提交 4b320fbc21c66e2143f649c7c3531a910f7bc380：标准 [45627103978](https://github.com/trade3403/rpdistill/actions/runs/45627103978) 10/10，Rust [45627103954](https://github.com/trade3403/rpdistill/actions/runs/45627103954) 1/1 success。job 139250090350 实测 16→8 token ordinary/cache 1546349128/1279364445 ns，64→16 3481629088/2599562047 ns，cache ratio 1.208685/1.339314，cache throughput 6.2531/6.1549 token/s，RSS 323817472 bytes。跨 Runner 波动明显，不能跨机器宣称加速。E10b 固定 D 2fa70c175de7a25415489ecb12ffe3d09485f777 源审计：OutputHead::project 逐词标量 dot product（65001×512，每生成步约33280512乘加），选择词表行独立并行候选。scripts/apply_projection_experiment.py 仅修改 CI 临时 pinned D checkout，RowTable sealed + Sync、最多4 scoped workers、>=1048576 MACs 才并行，串行 fallback、同一行 FP32 升序累加和原 bias，不复制权重；原 D 仓库不写。projection_experiment.py / student-rust-compare-projection：同一候选、同 host、两个独立 trusted binary hash、完整短诊断二进制逐字节一致（含 encoder/full/cached logits/greedy），再对两种固定 profiling workload 测量；3 unit tests + D rpinfer library tests + 真实完整尺寸双构建回归，CI 待验收。无固定速度阈值；若无实际加速不建议采用，未做生产部署/真实文本/GPU 性能。仅实验性补丁，生产 D 集成依然待协调。E11 GUI 可在验收通过后推进。
下一次先核验新 exact head 标准与 Rust 专项 CI，查看 actual_projection_experiment 日志：若数值或生成不一致先修；若无实际提升记录原因，不冒充优化成功；必要时追加优化，否则进入 E11。原 D 不修改、真实 GPU/人工质量/正式加载 E12 待办。上下文不足实际风险时提供交接 Prompt。

E10b 5cfa63992e39de8d62c1ecfddc51dea16965c263：标准 [45629087050](https://github.com/trade3403/rpdistill/actions/runs/45629087050) 10/10 + Rust [45629087039](https://github.com/trade3403/rpdistill/actions/runs/45629087039) 1/1 success。job 139257120314 Rust 52/52 tests，3134424 diagnostic bytes bitwise identical；16→8 full 2.617533628→2.506918947s/cache 2.248898513→2.143470875s；64→16 full 5.889429172→5.499378759s/cache 4.504332838→4.264901802s；speedup 1.0441/1.0492/1.0709/1.0561，RSS 323809280→323764224 bytes。合成同机实测，未证明统计显著或生产收益，D 原仓库未修改。E11a 独立 Electron+React+TypeScript desktop，中文深色工作台/模型下载/科研语料/训练/评测导出页面骨架；Python studio-snapshot v1 以 SQLite mode=ro 读取真实记录与硬件探测，缺失 DB 不创建，计数+每类50条，避免暴露完整 spec；Electron main 固定无 shell 的 Python 命令、15s timeout/1MiB stdout、单请求合并，sandbox/contextIsolation/nodeIntegration=false/CSP/导航和权限限制，只读 IPC；10s刷新，无假 loss 或进度。新增 2 Python tests、三平台 TS 构建与 Linux Electron 真启动+真实持久队列 fixture IPC smoke，CI 待验收。直接依赖固定版本，npm 传递依赖 lock 尚未提交；安装包、安全更新、真实跨平台窗口、操作按钮和完整设计参考一致性未验收，E11b 继续下载/模型操作、E11c 语料/训练/监控、E11d 评测导出及安装。仍需 E12 完整自动化、正式 D 加载、真实 GPU/人评；Europe PMC 暂缓。
下一次核验 exact head 的标准、Desktop 三平台工作流；未改变 Rust 专项路径则沿用 45629087039 成功结果。若失败先修，若全绿推进 E11b 固定命令白名单的模型搜索/下载入队及显式确认。实际上下文风险才输出交接 Prompt。

E11a 387ef63：标准 CI 45631411922 10/10 success；desktop CI 45631412179 Windows/macOS build 成功，Linux build 成功但真实 Electron launch 失败（job 139265302242，Chromium SUID sandbox helper owner/mode 不符，SIGTRAP，应用尚未启动）。仅 CI Linux 临时 runner 设置 Electron chrome-sandbox root:root 4755 并断言权限，保留 sandbox 与真实持久队列 smoke，不使用 --no-sandbox、不修改应用安全设置。修复提交需重新核验 exact head 标准及 desktop CI，全部通过才进入 E11b；实际 Windows/macOS GUI 启动与安装包尚未验收。

用户明确取消 Linux GUI：自本次提交起，E11/E12 桌面端只支持 Windows/macOS，Linux GUI 构建、启动、打包及发行不再作为要求；Linux Python/Rust CLI、后端及专项计算 CI 保留，不取消 Linux 训练能力。此前修复 b59ad53 的三平台 Desktop CI 45632934256 已成功，历史结果保留。新的 Desktop CI 矩阵 Windows/macOS 两项，分别保留真实 Electron 窗口/持久队列 IPC smoke（使用 scripts/studio_desktop_smoke.py，独立临时 DB、无 shell、无禁用沙箱），取消 Linux 专属 xvfb/SUID 配置。两平台真实启动尚待新 CI 验收，不能用历史 Linux 成功代替。未改变应用安全设置或后端 CI。后续安装包仅 Windows/macOS，真实 GPU 按硬件和后端可用性验收。

## 最新范围调整：仅 Windows GUI

用户明确取消 macOS GUI（Linux GUI 此前已取消）。自本次提交起，E11/E12 桌面 GUI、原生启动 smoke、安装包和发行仅支持 Windows；macOS/Linux Python/Rust CLI、后端与计算 CI 维持原范围，不取消训练能力。历史提交 98dbde0 标准 CI [45633656271](https://github.com/trade3403/rpdistill/actions/runs/45633656271) 10/10 success，Desktop [45633656134](https://github.com/trade3403/rpdistill/actions/runs/45633656134) 首次 Windows 原生窗口/IPC success、macOS cancelled，曾请求单项重跑；macOS 自本次授权起不再是验收门槛，不将其记录为通过。保留 Windows 真实 Electron/持久队列 IPC smoke、sandbox/contextIsolation 与原后端 CI；新提交需核验标准 CI 及 Windows Desktop CI，通过后继续 E11b 模型搜索、许可和预算确认、下载队列操作。Europe PMC 继续暂缓，D 线保持只读，真实 GPU/教师质量/人工评审及正式安装包仍待验收。本节覆盖此前 Windows/macOS 双平台 GUI 计划，旧记录保留为历史。


## E11b1 教师模型中心（开发分支，待 CI）
前置验收：主分支 7011607 标准 45640523576、Windows 45640524130 success；视觉分支 ce5777f 标准 45641912839 attempt 2 success、专项 45641912992 两项 success；原始 PNG SHA-256 与 1672×941 尺寸已校验，已取得参考预览，尚未完成像素级运行截图对照。新增公开 HF/ModelScope 搜索、ModelScope 版本信息、固定 SHA、明确许可/预算确认、持久入队、暂停/恢复/取消。IPC 固定白名单，严格参数与字段检查，无 shell、固定 DB/默认缓存路径、45 秒超时、1 MiB stdout、单一短操作；后端仍执行公开性和完整性校验。Windows smoke 增加非法 ID、未授权入队拒绝、实际 SQLite fixture 暂停/恢复和新增入队检查（无下载）。GUI 尚不启动 download-run，须 CLI 执行；下一 E11b2 接入单 worker 生命周期、真实网络指标、下载调度及小模型端到端验收。ModelScope 版本信息需操作者选完整 SHA；联网搜索和真实下载均待验收。先通过本提交标准及 Windows 专项 CI，后再推进，不提前合并。Windows-only GUI，原 D 线只读，Europe PMC 暂缓。


## E11b2 自动下载队列执行器及网络快照（开发分支，待 CI）
E11b1 3622224 标准 CI 45728566337、Windows 专项 45728566313 均 success。新增 GUI 显式启动/停止调度：固定 download-run 子进程，单本地执行器，SQLite 跨进程单 active 锁；每次仅成功后调度下一项，失败/暂停/取消/空队列停止。停止调度不杀当前子进程，正常窗口退出在运行时阻止；崩溃或强制关机仍需操作者确认原 worker 已退出，现有 CLI recover 未自动调用。队列全局 queued/active 计数、旧 schema 只读兼容、HF 最近采样实际 payload bytes/rate，ModelScope 文件级恢复无网络率，ETA 为校验速率估计，不是网络 ETA。模型中心 3 秒刷新，后台 10 秒。扩展 Windows 原生 smoke：取消合成任务后启动实际空队列 Python 子进程、非法字段/重复启动拒绝；Python 测试真实 SQLite 网络字段读取及旧 schema 不迁移。未验证真实联网模型下载、实际 GUI 截图像素级对照、崩溃恢复及多进程交互，下一小阶段 E11b3 真实小模型与恢复/GUI 对照验收；新 CI 全部通过后再推进。Windows GUI only，macOS/Linux 后端保留，Europe PMC 暂缓，D 线只读。


## E11b2 Windows 测试资源释放修复（待 CI）
73999c1 的标准 CI 45734512520 为 8/10 success；Windows Python 3.11/3.12 两项均在 test_network_metrics_and_legacy_read_only 的临时目录清理时触发 WinError 32，SQLite 测试连接仍打开。sqlite3.Connection 上下文仅提交/回滚事务，不负责 close；两处测试连接改用 contextlib.closing 外层和事务内层，保留网络字段、旧 schema、数据库字节一致性全部断言。应用逻辑及安全边界不变。Windows 专项 45734512461 两项 success；本次扩展专项触发路径以覆盖 Python 后端和 smoke 测试变化，重新验收 exact head 标准及 Windows 专项 CI 后才进入 E11b3。真实联网下载和像素级截图验收仍未完成。


## E11b3 真实小模型下载与异常恢复验收（开发分支，待 CI）
E11b2 修复 26ec3cd 的标准 CI 45736731767 与 Windows 专项 45736731818 success。新增 Windows 联网验收固定模型 optimum-internal-testing/tiny-random-llama（公开 Apache-2.0 随机权重，16 MiB 上限，运行时解析并固定完整 SHA、拒绝许可/大小变化），真实 HTTPS 下载期间测试专用子进程在权重部分文件落盘后故障退出，确认进程退出后显式 recover/resume；记录 Range 206 真续传或 200 安全重下，核验真实 payload 字节、完整 manifest/上游权重 SHA-256 及 SQLite 自动登记。未执行模型权重、无质量结论。GUI 加入显式人工确认异常恢复（本地 worker 运行时拒绝；外部执行器存活须操作者验证，不自动接管），恢复清理陈旧网络速率。Windows smoke 成功时通过主进程 capturePage 保存 PNG artifact 及 JPEG 日志预览，尚未进行实际像素比对，不宣称 1:1。ModelScope 仍沿用文件级恢复/原有搜索及离线测试，真实全权重下载未验证。新 CI 通过后检查日志及截图再进入 E11c，若公共 Hub 网络故障先区分环境与代码。Windows GUI only，原 D 线只读，Europe PMC 暂缓。


## E11c1 科研语料中心（开发分支，待 CI）
前置 E11b3 920a15c 标准 CI 45738140228 和专项 45738140235 三项均 success；真实 HF 随机小模型固定 SHA ffd1b09a4fa19a9086ed4e36d57eda60fcb2c2c0，6,477,096 字节、部分 262,144 字节，HTTP 206 续传、恢复网络 6,214,952 字节、自动登记成功；不是实际翻译质量/ModelScope 全权重验收。Windows 截图 1008×655，已取得视觉证据但与设计稿差异明显，尚未像素验收。新增 GUI 单次 NCBI PMC 流水线配置：已登记教师/固定 SHA、日期关键词、篇数/分段/下载字节上限、CPU/CUDA 与精度、明确授权创建及再次确认启动；固定受限 IPC、独立长运行子进程、阻止本地下载和语料 worker 并发、正常退出保护、仅阶段>=2 的显式人工确认恢复，采集不得自动重放。论文/候选数据集/任务快照只读且各至多50项，不暴露完整 spec/manifest。候选门槛不等于训练授权，后端单次流水线无协作暂停/取消；持续自动化、训练控制、实时 Loss 及完整 GUI 视觉校准未完成。新增 SQLite 快照回归及 Windows 原生 smoke（真实持久语料创建/拒绝未授权/无效任务实际 worker 启动并失败，不联网、不执行合成教师权重）。实际科研论文及教师生成的 GUI 全链路待后续验收。下一 E11c2 训练队列、配置与监控，前提本提交 CI 全通过。Windows GUI only，Europe PMC 暂缓，D 线只读。


## E11c2 训练中心第一轮（开发分支，待 CI）
E11c1 d9f6076 标准 45739368042、专项 45739368036 success。新增固定 Marian 学生的 GUI 训练队列：精确候选版本与许可复核声明、优化器步数、批大小、学习率、累积、CPU/CUDA/精度、时间与检查点及显存软预算，固定可信启动环境资产/检查点目录（学生资产仍须 CLI student-assets 预备），创建与运行单独确认。GUI 显式启动一个 FIFO 任务，暂停/恢复/取消/人工确认异常恢复，保留 SQLite 单 worker、已验证 checkpoint、保守预算、后端每段重新核验数据与权利。本地下载/语料/训练执行器互斥、退出保护，不是系统全局锁。训练事件从已验证且原子登记的 checkpoint history 最后一步记录真实 loss，dashboard 与训练页只显示单任务最近 120 个检查点样本，非逐步实时遥测，不混合任务；旧数据无指标保持空状态。新增 SQLite 只读快照测试及原生 Windows smoke：拒绝无授权、持久队列创建/暂停/恢复/取消、实际空队列 worker，未训练合成数据。真实 CPU 训练由既有专项验收；真实 GPU、逐步遥测、学生资产 GUI 下载、完整自动串联及像素级还原待后续。下一 E11c3 实时训练遥测与运行控制中心视觉校准，先核验 exact head CI。Windows GUI only，Europe PMC 暂缓，D 线只读。


## E11c2 快照计数协议修复（待 CI）
ce815be 标准 CI 45740525104 4/10 success，六个跨平台 CPU 矩阵任务失败；已核查 Ubuntu 3.11 与 Windows 3.12 日志，均为 test_missing_db_does_not_create：将固定学生单检查点最低容量 961265388 bytes 错误放入 counts，导致空数据库计数不为零。现将容量独立为顶层 checkpoint_min_bytes，GUI 改读该字段，保留原始零计数断言并新增容量独立断言；不改变训练预算或安全门槛。专项 CI 45740525052 success。新提交标准与 Windows 专项全部通过后再进入 E11c3。


## E11c3a 逐步训练遥测与 GPU 监控（开发分支，待 CI）
E11c2 修复 fd79b35 标准 45741425689、Windows 专项 45741425763 success。实际 optimizer update 完成后向可选 on_step 回调发出真实 loss、单步计算耗时、监督 token 数；训练队列写入按 job/attempt/step 区分的 SQLite 遥测，校验 worker 所有权、连续性、边界及有限数值，checkpoint 原子登记时标记已提交，恢复后隐藏未提交点、下一次 attempt 清理旧未提交记录。不改变 checkpoint history/确定性训练数据；快照只读、仅一个任务最近120点，兼容旧 checkpoint 事件。Windows GUI 3秒轮询，区分未保存黄色点与已保存点，速度和计算 ETA 只在活跃且30秒内采样时显示（不含 checkpoint/加载/等待）；NVIDIA SMI 扩展 GPU利用率/温度/功耗，缺失为 null，旧驱动拒绝扩展字段时退回基础探测。真实微型 CPU smoke 新增逐步遥测与完整训练 loss 对照、保留原逐位相等断言；单元测试覆盖 GPU 不支持及异常恢复隐藏。未通过新 CI，真实 GPU、本机逐步性能开销、学生资产 GUI 下载、原图高保真及自动化联动待后续 E11c3b/c。Windows GUI only，Europe PMC 暂缓，D 线只读。
