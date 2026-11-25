# 技术架构

- GUI：计划 Electron + React + TypeScript，独立桌面发布。
- 训练：Python 3.11+、PyTorch、Transformers；CUDA 由实际硬件决定。按规模选择 Accelerate 或 DeepSpeed。
- 任务管理：Python 本地 worker，后续使用有版本的 JSON 消息协议；持久化实验配置、日志及检查点。
- 数据：JSONL/Parquet，SQLite 元数据，训练集与独立测试集隔离，记录语料来源和使用许可。
- 教师：统一适配器；Qwen 为候选而非已确定的最优模型。固定模型版本、生成参数、许可；只有可访问兼容输出时才启用 logits/特征蒸馏。
- 学生：以 D 线真实架构、词表、张量布局、模型包版本为准；不可把任意缩小的 Qwen 直接用于现有 Rust 推理。
- 导出：SafeTensors 中间格式，验证 RPTranslate 原生格式；Rust 互操作模块按需要实现。
- 安全：默认本地语料；远程教师调用需要明确授权；密钥与真实数据不进入公开 Git。禁止默认执行不受信任模型代码。
- CI：Windows/Linux/macOS × Python 3.11/3.12 CPU 测试；真实 GPU 训练另行在有权限的硬件上验收。

E1.1 仅实现标准库基础配置和 CLI；以上其余模块为计划。

## 内置在线资源下载（必选）

- Python 下载服务适配 Hugging Face Hub 与 ModelScope 官方接口；后端实现后通过 CLI 和 GUI 统一调用，支持资源搜索、固定 revision、文件清单、大小和许可证展示。
- 用户选择模型或数据集、确认下载和必要许可后，软件自动下载权重、配置、分词器及必要资源，完成校验并注册到本地资源库，无需手动解压或搬运文件。
- 支持任务持久化、队列、实时字节进度/速度/ETA、暂停恢复、断点续传（服务端支持时）、退避重试、可配置缓存目录、磁盘预检查、重复文件复用。
- 下载使用临时文件，验证文件大小及可信哈希（来源提供时），完成后原子发布；拒绝路径穿越，限制不安全重定向，默认不执行远程代码；授权令牌不得写入日志或 Git。
- 对 gated 或非公开资源先取得用户授权；仅从许可允许的来源下载论文、数据集及模型。网络不可用时提供离线导入，不自动下载未经授权的大文件。
- E2 验收：本地 HTTP 测试覆盖中断、重试、校验失败、缓存复用；再进行小型公开真实模型的联网下载、加载验证。E3 验收公开数据集下载及来源许可记录，E11 验收图形界面全流程。

## 科研论文在线采集与语料生成（E3 必选，F24）

- 候选数据源：arXiv、Europe PMC、PubMed Central 开放获取子集；OpenAlex、Crossref、Unpaywall 用于发现论文和合法全文链接。具体接口、认证、限流和许可规则须在接入时核实；元数据索引不等于全文授权。
- 用户在软件内设置关键词、学科、语言、年份范围（支持最新发表论文）、论文数量上限和存储预算，即可检索并批量下载，无需在浏览器逐篇查找或保存 PDF。
- 默认选择明确允许预定训练、复制与翻译用途的资源；记录 DOI、来源、发布日期、版本、全文链接、许可证、检索时间与哈希。无法确认许可或全文不可得时跳过并说明原因，不绕过付费墙、登录限制及访问控制。
- 下载队列支持限流、重试、暂停恢复、缓存、去重、格式检查、磁盘预算及失败报告。优先结构化全文 XML/HTML，兼容 PDF；下载后自动解析标题、摘要、正文及段落，保护公式、数字和术语，避免把参考文献和页眉页脚混入训练文本。
- 流程：检索→许可过滤→下载→解析→分段→教师模型生成译文→质量过滤/人工审核→双语训练集导出。按照论文级别隔离训练/验证/测试集合，避免数据泄漏。保留人工导入作为离线备用。
- E3 验收：在明确许可的小规模真实论文样本上完成从在线检索到下载及自动解析入库，并记录来源与许可；测试重复论文、不可下载、限流、中断、损坏文件及许可未知等异常。E11 验收用户无需浏览器手动下载即可操作完整采集流程。

## 全自动蒸馏流水线
见 [AUTOMATION.md](AUTOMATION.md)。F21 为核心产品能力，E3 起逐段接入，不推迟到 GUI 阶段才开发。持久化任务状态与幂等操作、限定资源和预算、自动筛选与失败隔离，质量不过关时保留旧模型。所有自动训练均须由用户启动或预先授权，不代表默认无限运行。

## E2.3 教师推理接口
`TeacherTranslator` 消费固定版本 TeacherRegistry 记录，重校验清单并通过本地 Transformers causal 模型生成候选双语段落，默认英文到中文、CPU float32，可显式选择 CUDA。禁止远程自定义代码与 pickle 权重。输出保留源文本、模型来源/版本、提示版本、配置和结束原因，E3 只在质量过滤后将候选纳入训练集。超长输入拒绝而不截断；E3 负责分段。免费 Runner 使用随机微型模型做真实 CPU 推理，不能代替科研翻译质量验证。

## E3.1 论文发现接口
`PaperQuery` 构造有界 Europe PMC 官方 REST 查询，`discover` 分页检查记录并入库 `PaperCatalog`。DOI/PMCID/source ID 去重，标识冲突不自动合并，许可冲突降级。只存元数据（不存摘要），默认 OA 筛选。CC BY/CC0+OA+PMCID 仅标为 pending_fulltext_license；E3.2 必须复核具体全文许可及第三方内容限制，不自动将发现结果用于训练。检索领域先覆盖生命科学/医学，其他来源后续扩展。参考 https://europepmc.org/RestfulWebService 。

E3.1 增加 NCBI PMC E-utilities 备用来源：ESearch（OA 与 CC BY/CC0 搜索过滤）→ ESummary → PaperCatalog，保留来源及查询筛选证据，不伪造具体许可；只在 Europe PMC 首次请求瞬态失败时自动切换，部分成功后失败不重新消耗预算。官方文档 https://pmc.ncbi.nlm.nih.gov/about/userguide/ 。后续全文优先当前 PMC OAI-PMH/Cloud 官方接口，旧 OA Web Service 已退役，参见 https://pmc.ncbi.nlm.nih.gov/tools/developers/ 与 https://pmc.ncbi.nlm.nih.gov/about/new-in-pmc/ 。

E3.2：NCBI PMC 默认，Europe PMC 暂缓。FulltextLibrary 消费 PaperCatalog 候选，经官方 OAI-PMH pmc_fm→pmc 验证身份及许可 URI，一致才原子保存原始 XML 并记录哈希、来源、许可、状态。SQLite 单篇写事务串行，累计响应字节及单篇大小限制，缓存基于哈希。原始 XML 状态 downloaded_pending_content_review，E3.3 需排除第三方限制材料，保持署名和许可，不自动训练。官方：https://pmc.ncbi.nlm.nih.gov/tools/oai/ 。

E3.3a CorpusStore：输入已登记 PMC XML 和 PaperCatalog，检查当前资格、哈希、许可、日期；仅提取保守正文/摘要文本段，排除复杂结构和明确限制标记。每段存来源、署名、许可、论文级固定划分及哈希；教师版本/选项/提示与质量策略共同生成候选译文幂等键。数字和长度等基础筛查仅为候选筛选，候选 JSONL 不作为训练认证。后续 E3.3b 增加更完整的权利、语义、语言和数据集版本/冻结/自动调度能力。

E3.3b DatasetStore 保存不可覆盖的内容寻址候选快照与成员，按固定教师配置筛选、重新哈希当前全文、精确源文本跨版本 split 防护，计数门槛不足不生成版本；导出校验哈希且不覆盖。CorpusPipeline 单次循环串联检索到候选快照，持久阶段，单 worker，解析/翻译/快照恢复；采集失败不自动重放预算。现有共享目录候选不严格按本次查询隔离，持续运行、增量分页、语义质量与训练授权留后续。

E4a：student.py 固定 D 线 Marian 6+6/512/8/2048/65001 契约，PyTorch 训练侧随机初始化、canonical 权重验证、固定 SPM/词表文件校验及共享 network ID 映射；测试小 profile 不作为部署模型。真实 Rust loader 当前固定官方来源及哈希，E9 需自训练 package profile；见 STUDENT_CONTRACT.md。

E4b training_data.py：固定 tokenizer assets 下载与完整性；DatasetStore 不可变候选成员→当前全文/许可元数据/版本校验→StudentCodec→按 split 和 token/logits 预算组 batch，labels padding=-100、Marian decoder start PAD 保持 attention=1。训练计划不更新参数或认证数据；E5 接真实训练器。

E5a distill.py：经过操作者明确复核的候选版本 train split→StudentCodec→masked batch→Marian CPU FP32→CE/AdamW/backprop/grad clipping→真实 loss history→不可覆盖 SafeTensors 权重检查点与哈希 manifest。加载严格校验 canonical tensors/alias、恢复权重并重现 logits。仅权重恢复，不是 optimizer/RNG 精确恢复或 Rust 部署格式；E6 继续完整训练状态。合成微型 CPU 真实训练 smoke 非真实翻译质量。

E6a resumable.py：复用 reviewed snapshot 预检，确定性 epoch shuffle 与 cursor；microbatch loss 按有效目标 token 加权累积，优化器边界更新与持久 history；完整 SafeTensors state（权重/AdamW moments+step/CPU RNG）+ hash manifest 绑定数据、配置、环境、进度；不可覆盖并严格恢复。同 CPU 环境验收，调用末保存，软时间预算非硬限制；非 CUDA、非持续调度、非 RPModel。

E6b1：ResumeConfig 支持显式 cuda:N 与 FP32/FP16/BF16 autocast，FP32 master/AdamW；FP16 scaler 状态、CUDA RNG 与环境进入 checkpoint，原 CPU checkpoint config 兼容。CUDA 预检 free VRAM、步边界 peak allocated 软门槛，非硬显存限制。真实 GPU 本机 smoke 尚未执行；周期保存和持久 worker 在 E6b2。

E6b2 TrainingQueue：已审核 dataset version → SQLite 训练 spec/事件、单 worker 原子认领 → 每段预留时间及磁盘预算 → run_segment（step boundary should_stop）→ 完整 checkpoint 哈希验证 → 原子登记 cursor → 自动继续或终态。失败/强杀保留已登记 checkpoint，recover 须确认旧 worker 退出，不采纳孤立文件，累计预留不退款。仅单数据库队列 worker，非全局资源锁或硬限制；常驻服务、完整采集审核触发后续整合。

E7a evaluation.py：训练快照全量哈希→规范化精确源文与声明 DOI/PMCID 排除→独立参考 benchmark hash→外部 hypothesis ID 对齐→SacreBLEU zh BLEU/chrF 与科学字面/启发式指标→覆盖/指标门槛与哈希报告。人工参考权利为操作者声明，外部输出未认证，自动门槛不授权发布，真实学生推理及基线/人工评测后续。

E7b1 student_evaluation.py：冻结 benchmark → 绑定训练 dataset 的已完成 checkpoint（E5 weights/E6 full-state，哈希/shape 严格验证，仅模型权重）→ CPU FP32 greedy generation（源文本，不输入 reference）→ 网络词表解码/完成状态 → SacreBLEU 与科研规则 → 可选外部基线同 benchmark delta、实际延迟与吞吐、报告 SHA；无 KV cache，权重字节非 RSS，未签名外部输出，release_ready=false。真实独立质量/性能待 E7b2/本机。

E7b2 quality_review.py：冻结 benchmark + 训练快照 → 有界 trigram 倒排审计；两个同 benchmark 报告的内容 hash 与指标重算 → 随机匿名 A/B packet、独立私有映射 → 声明独立评审完整双侧评分 → 默认自动质量/生成状态/词面泄漏与人工候选 gate。身份和来源未认证，release_ready=false；Linux/macOS RSS 为进程生命周期峰值，非模型独占内存。COMET 及真实正式质量仍待本机。

E8a compression.py：已完成训练 checkpoint → canonical FP32 权重 → FP32/矩阵 FP16/rowwise symmetric INT8+FP32 scale（位置/偏置/norm 保留 FP32）→ SafeTensors 压缩候选与内容哈希、误差、源 identity、预算 → 严格 FP32 参考还原。D 线最新 5389f3f 仅官方 F32，候选非 RPModel、无原生低精度推理；E8b 质量回归，E9 自训练包。

E8b compression_review.py：原训练 checkpoint + 冻结 benchmark + 压缩候选 → 严格读取与重算源转换 → 相同 CPU FP32 greedy/指标 → 固定绝对门槛、相对回归、新增逐条规则错误及词面泄漏审计 → 按实际 artifact bytes 最小合格候选，失败则 null；有界 case/软时间预算、报告内容 hash，release_ready=false。
