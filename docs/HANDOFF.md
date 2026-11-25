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
