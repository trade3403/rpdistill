# RPDistill Studio 功能清单

版本目标：V0.1.0 起步，E1—E12 分阶段建设。状态以 [PROGRESS.md](PROGRESS.md) 和对应 CI 为准。本表是规划，不代表功能均已实现。

| ID | 模块 | 具体功能 | 阶段 | 当前状态 |
|---|---|---|---|---|
| F01 | 基础工程 | Python 包、CLI、训练参数校验、跨平台测试 | E1.1 | CPU CI 已通过 |
| F02 | 任务管理 | 实验编号、配置持久化、任务状态、运行日志、暂停/取消 | E1.2 | 基础状态/持久化/日志 CPU CI 六环境通过；真实 worker 暂停取消待开发 |
| F03 | 硬件检测 | CPU/GPU/显存/内存/磁盘、设备选择、能力报告 | E1.2/E6 | CPU/内存/磁盘/NVIDIA 探测 CPU CI 通过；GPU 训练验证待开发 |
| F04 | 教师模型中心 | Qwen 等候选模型，本地/远程适配、在线搜索、一键下载与自动导入、版本与校验、许可记录 | E2 | E2.1 Hugging Face 搜索、固定版本下载校验与注册 CPU CI 通过；E2.2b1 ModelScope 基础适配 CPU CI 通过，E2.3 本地 SafeTensors 推理与批量翻译 CI 通过（含真实微型 CPU 推理）；真实教师质量待验收 |
| F05 | 教师模型选型 | 固定科研评测集、盲测、质量与成本对比，确定适配模型 | E2/E7 | 待开发 |
| F06 | 文档语料 | 合法开放语料在线下载、PDF、Word、TXT、JSONL 导入、论文分段、学科分类、来源许可 | E3 | 待开发 |
| F07 | 自动语料生成 | 教师批量翻译、队列、限流、失败重试、原译文关联 | E2.3/E3 | E2.3 批量翻译接口及来源记录 CI 通过；论文队列和自动语料流水线待开发 |
| F08 | 语料清洗 | 去重、语言识别、长度/质量检查、数字公式与术语保护 | E3 | 待开发 |
| F09 | 人工审核 | 原译文对照修订、审核状态、训练/验证/测试集隔离、版本化导出 | E3/E11 | 待开发 |
| F10 | 学生模型中心 | RPTranslate 架构、分词器与词表适配、初始权重、张量形状校验 | E4 | 待开发 |
| F11 | 序列级蒸馏 | 教师译文监督训练、损失计算、真实权重更新、固定种子复现 | E5 | 待开发 |
| F12 | Logits/特征/多教师蒸馏 | 教师概率分布、词表对齐、中间层适配、多教师组合；须满足权限及架构条件 | E5 | 待开发 |
| F13 | 神经网络训练 | PyTorch CPU/CUDA、混合精度、优化器、学习率调度、梯度累积 | E6 | 待开发 |
| F14 | 训练恢复与监控 | Loss、吞吐、显存、检查点、恢复、异常处理、多 GPU 按需求 | E6 | 待开发 |
| F15 | 翻译质量评测 | BLEU、chrF、适用时 COMET、人工盲测、术语/公式/数字/漏译检查 | E7 | 待开发 |
| F16 | 性能评测 | 速度、内存峰值、模型加载时间、大小、教师/学生/历史版本对照 | E7 | 待开发 |
| F17 | 模型压缩 | FP32/FP16/INT8 转换、校准和质量回归；INT4、剪枝视兼容性验证 | E8 | 待开发 |
| F18 | 模型导出 | SafeTensors 中间格式、RPTranslate 原生包、哈希与真实 Rust 推理验收 | E9 | 待开发 |
| F19 | Rust 加速 | 经性能剖析后实施数据处理、转换、互操作优化，不强制重写 PyTorch | E10 | 待开发 |
| F20 | 桌面 GUI | Electron/React/TypeScript；模型、语料、训练、评测、导出及硬件监控 | E11 | 待开发 |
| F21 | 自动化流水线 | 一键启动、定时自动检索新论文→许可过滤→下载→解析清洗→教师翻译→自动筛选→数据集版本→学生蒸馏训练→评测→量化→导出；持久化调度、断点恢复、资源预算、失败隔离、质量门槛和回滚 | E3/E5/E6/E9/E11 | 待开发（核心必选） |
| F22 | 发布与验收 | 独立安装包、跨平台验证、真实 GPU 训练、真实科研翻译质量报告 | E12 | 待开发 |
| F23 | 在线资源下载中心 | Hugging Face / ModelScope 模型与数据集搜索、一键下载、队列、实时进度、速度与剩余时间、暂停/恢复、断点续传、自动重试、完整性校验、缓存、磁盘检查、自动注册；受限资源须授权 | E2/E3/E11 | E2.1 CPU CI 通过；E2.2a 队列与文件级控制 CPU CI 通过；E2.2b1 CPU CI 通过；E2.2b2 Hugging Face 队列字节进度、Range 恢复、SDK 和联网 smoke 已通过 CI；ModelScope 字节进度待开发（必选） |
| F24 | 科研论文在线采集中心 | 按关键词、学科、日期及语言检索真实论文；批量下载允许训练使用的全文 PDF/XML/HTML；自动去重、许可核查、解析、分段并入库，支持进度和失败恢复 | E3/E11 | E3.1 初次标准 CI 通过，联网 HTTP 503 失败，重试修复标准 CI 通过但联网仍 503；NCBI PMC 备用检索标准 CI 与真实联网通过（3 条）；Europe PMC 仍 503，失败任务已请求重跑；全文下载与其他来源待开发（必选） |

## 验收原则

- 一次设置后，正常工作流不得要求逐篇搜索、下载、翻译、审核或手动启动各训练阶段。人工干预仅用于首次授权、异常或可选复核；低质量和许可不明样本自动隔离。

- 在线下载为必选功能：正常联网流程无需用户先手动下载论文、模型文件或公开语料再导入；保留离线导入作为备用。
- 训练与推理分离，RPTranslate 最终不依赖 Python/PyTorch/CUDA。
- 教师候选模型必须实测，并核查权重与数据许可；Qwen 具体版本暂未锁定。
- 学生模型须与 D 线真实网络、分词器及模型包格式兼容。
- 公开仓库禁止提交私人论文、密钥及大型训练权重；远程处理语料需要明确授权。
- CPU CI 不等于真实 GPU 训练通过；演示数据不得当作实测。
- 新功能必须有测试、文档和可核验结果，状态区分规划、开发、已提交、CI 通过、实际验收。

E3.1 Europe PMC 排序参数兼容修复：使用官方 P_PDATE_D 排序字段，保留 FIRST_PDATE 过滤；待真实联网复验，不视为恢复。


E3.2：经用户授权 Europe PMC 联网暂缓（非通过），NCBI PMC 真实检索已通过并成为默认来源。F24 全文 OAI-PMH 许可复核、XML 下载、预算与哈希文件库已提交待 CI；内容筛选、解析及持续调度待后续。

并发修复合并说明：保留 6c37e2d90623806b62baafb3a9cac59e8dd50b01 的 Europe PMC 排序字段修复及测试；其标准 CI 45596188128、双来源联网 45596188201 已通过。此前失败为历史记录，最新 Europe PMC 已实测恢复。按用户要求仍暂缓其常规联网门槛，NCBI PMC 为默认来源，Europe PMC 可手动复验。E3.2 新提交待验收。

E3.2 初次标准 CI 通过，真实全文下载被 JATS 字段校验阻断；已提交标识与明确许可 URI 兼容修复，待复验。

E3.2 修复 CI 10/10 必需任务通过，真实保存 10 篇 CC BY XML。F06/F07/F08/F09：E3.3a JATS 源段、教师翻译候选、基础筛查、署名与论文级划分/JSONL 已提交待验收；真实训练数据集质量认证和完整自动流水线待开发。

E3.3a CI 10/10 必需任务通过，真实提取 337 段。E3.3b F09/F21：候选快照、计数门槛、单次采集翻译阶段自动串联已提交待 CI；训练数据认证、持续周期、语义筛查、完整增量分页待完善。

E3.3b 标准 CI 8/8 通过。E4a 学生模型审计、Marian 网络与权重形状验证已提交待 CI；真实 tokenizer 对照、训练及 Rust 自训练包部署尚未完成。

E4a 标准与 Hub CI 11/11 success。E4b 固定分词器自动下载、训练数据候选版本读取与动态批次/损失 mask 已提交待 CI，新增真实 Rust/Python/HF 分词 ID 对照；权重更新在 E5。

E4b 标准与 tokenizer CI 10/10 success（10/10 真实分词 ID）。E5a 序列级 CPU 蒸馏、权重更新、实际 loss 和安全权重检查点已提交待 CI；精确优化器/RNG 恢复、GPU 与正式质量认证待后续。

E5a 真实 CPU 80 steps 与权重检查点 CI 9/9 通过（合成数据，非翻译质量）。E6a 梯度累积、完整优化器/RNG 状态与同环境 CPU 分段恢复已提交待 CI；CUDA/AMP/定期调度及完整资源监控待后续。

E6a CPU 精确续训 CI 9/9，176 张量位一致。E6b1 CUDA/AMP 与 GPU 状态保存已提交待 CI，实际 GPU 待本机；周期检查点与持久 worker 在 E6b2。

E6b1 10/10 必需 CI success，GPU 本机验收待做。E6b2 持久训练队列/事件、周期完整 checkpoint、暂停/取消/恢复、累计保守预算已提交待 CI；正式数据审核触发、常驻调度、全局资源管理尚未完成。

E6b2 标准 CI 9/9 success（真实 CPU 队列、3 checkpoints、176 states 一致）。E7a 独立参考评测集、BLEU/chrF、数字/术语/引用/公式字面检查与自动评分 gate 已提交待 CI；真实模型评测与人工质量认证后续。

E7a 13/13 CI success；E7b1 真实学生检查点评测、CPU greedy、双检查点格式、同 benchmark baseline delta 与延迟/吞吐记录已提交待 CI。正式人工评测、近重复/真实基线及内存实测待 E7b2；未宣称真实科研翻译质量或可发布。

E7b1 标准 CI 10/10 success；E7b2 有界近重复审计、匿名 A/B 盲测流程、完整双评审候选门槛和 Linux/macOS peak RSS 已提交待 CI；真实人工评审、基线来源认证、语义独立性、COMET 与真实 GPU/质量仍待实际验收。

E7b2 CI 10/10 success（合成盲评）。E8a FP32/FP16/INT8 存储候选、误差/体积/哈希与 FP32 参考还原已提交待 CI；非原生 INT8 推理，正式量化质量回归 E8b、Rust 自训练包 E9。

E8a 10/10 CI success；E8b 同源压缩实际生成回归、绝对/相对门槛及候选选择已提交待 CI。真实完整尺寸质量和人工验收未完成，非 Rust 原生低精度推理。

E8b 10/10 CI success。E9a 独立自训练 FP32 候选包、权重与固定分词器资产、来源/许可/文件哈希及外部 pin 已提交待 CI；真实全尺寸单步训练和 Rust raw reader 全字节对照新增专项 workflow；生产 Rust 加载、质量授权 E9b。

E9a 11/11 CI success，完整尺寸单步合成训练+Rust 312033188 bytes 全读取通过。E9b1 真实 Rust encoder/decoder/full/cached logits 与 greedy 诊断对照已提交待 CI；非生产 loader，质量与权利审批 E9b2。

E9b1 标准及 Rust 专项 11/11 success，真实完整尺寸诊断推理一致。E9b2 本地集成候选审批链及独立凭据已提交待 CI，实际正式人工审批/生产加载/发行未完成。

E9b2 补充双外部 pin 交接校验、签发前权利及包再次核查、完整训练状态 token 数据哈希；真实微型重放与覆盖拒绝、完整尺寸诊断报告拒绝作为审批凭证，待最新 CI。

E9b2 11/11 CI success；E10a 完整尺寸 Rust CPU 分段性能剖析/缓存对照/峰值 RSS 已提交待 CI，实际优化 E10b。非生产加载或正式质量验收。

E10b 11/11 CI success，词表投影实验同机合成生成加速 4.4–7.1%、诊断字节一致。E11a 只读桌面工作台、真实数据库/硬件状态、受限 IPC、跨平台构建与真实 Electron smoke 已提交待验收；任务控制和实时训练指标未接入。

用户明确取消 Linux GUI：自本次提交起，E11/E12 桌面端只支持 Windows/macOS，Linux GUI 构建、启动、打包及发行不再作为要求；Linux Python/Rust CLI、后端及专项计算 CI 保留，不取消 Linux 训练能力。此前修复 b59ad53 的三平台 Desktop CI 45632934256 已成功，历史结果保留。新的 Desktop CI 矩阵 Windows/macOS 两项，分别保留真实 Electron 窗口/持久队列 IPC smoke（使用 scripts/studio_desktop_smoke.py，独立临时 DB、无 shell、无禁用沙箱），取消 Linux 专属 xvfb/SUID 配置。两平台真实启动尚待新 CI 验收，不能用历史 Linux 成功代替。未改变应用安全设置或后端 CI。后续安装包仅 Windows/macOS，真实 GPU 按硬件和后端可用性验收。

## 最新范围调整：仅 Windows GUI

用户明确取消 macOS GUI（Linux GUI 此前已取消）。自本次提交起，E11/E12 桌面 GUI、原生启动 smoke、安装包和发行仅支持 Windows；macOS/Linux Python/Rust CLI、后端与计算 CI 维持原范围，不取消训练能力。历史提交 98dbde0 标准 CI [45633656271](https://github.com/trade3403/rpdistill/actions/runs/45633656271) 10/10 success，Desktop [45633656134](https://github.com/trade3403/rpdistill/actions/runs/45633656134) 首次 Windows 原生窗口/IPC success、macOS cancelled，曾请求单项重跑；macOS 自本次授权起不再是验收门槛，不将其记录为通过。保留 Windows 真实 Electron/持久队列 IPC smoke、sandbox/contextIsolation 与原后端 CI；新提交需核验标准 CI 及 Windows Desktop CI，通过后继续 E11b 模型搜索、许可和预算确认、下载队列操作。Europe PMC 继续暂缓，D 线保持只读，真实 GPU/教师质量/人工评审及正式安装包仍待验收。本节覆盖此前 Windows/macOS 双平台 GUI 计划，旧记录保留为历史。


## E11b1 教师模型中心（开发分支，待 CI）
前置验收：主分支 7011607 标准 45640523576、Windows 45640524130 success；视觉分支 ce5777f 标准 45641912839 attempt 2 success、专项 45641912992 两项 success；原始 PNG SHA-256 与 1672×941 尺寸已校验，已取得参考预览，尚未完成像素级运行截图对照。新增公开 HF/ModelScope 搜索、ModelScope 版本信息、固定 SHA、明确许可/预算确认、持久入队、暂停/恢复/取消。IPC 固定白名单，严格参数与字段检查，无 shell、固定 DB/默认缓存路径、45 秒超时、1 MiB stdout、单一短操作；后端仍执行公开性和完整性校验。Windows smoke 增加非法 ID、未授权入队拒绝、实际 SQLite fixture 暂停/恢复和新增入队检查（无下载）。GUI 尚不启动 download-run，须 CLI 执行；下一 E11b2 接入单 worker 生命周期、真实网络指标、下载调度及小模型端到端验收。ModelScope 版本信息需操作者选完整 SHA；联网搜索和真实下载均待验收。先通过本提交标准及 Windows 专项 CI，后再推进，不提前合并。Windows-only GUI，原 D 线只读，Europe PMC 暂缓。


## E11b2 自动下载队列执行器及网络快照（开发分支，待 CI）
E11b1 3622224 标准 CI 45728566337、Windows 专项 45728566313 均 success。新增 GUI 显式启动/停止调度：固定 download-run 子进程，单本地执行器，SQLite 跨进程单 active 锁；每次仅成功后调度下一项，失败/暂停/取消/空队列停止。停止调度不杀当前子进程，正常窗口退出在运行时阻止；崩溃或强制关机仍需操作者确认原 worker 已退出，现有 CLI recover 未自动调用。队列全局 queued/active 计数、旧 schema 只读兼容、HF 最近采样实际 payload bytes/rate，ModelScope 文件级恢复无网络率，ETA 为校验速率估计，不是网络 ETA。模型中心 3 秒刷新，后台 10 秒。扩展 Windows 原生 smoke：取消合成任务后启动实际空队列 Python 子进程、非法字段/重复启动拒绝；Python 测试真实 SQLite 网络字段读取及旧 schema 不迁移。未验证真实联网模型下载、实际 GUI 截图像素级对照、崩溃恢复及多进程交互，下一小阶段 E11b3 真实小模型与恢复/GUI 对照验收；新 CI 全部通过后再推进。Windows GUI only，macOS/Linux 后端保留，Europe PMC 暂缓，D 线只读。


## E11b3 真实小模型下载与异常恢复验收（开发分支，待 CI）
E11b2 修复 26ec3cd 的标准 CI 45736731767 与 Windows 专项 45736731818 success。新增 Windows 联网验收固定模型 optimum-internal-testing/tiny-random-llama（公开 Apache-2.0 随机权重，16 MiB 上限，运行时解析并固定完整 SHA、拒绝许可/大小变化），真实 HTTPS 下载期间测试专用子进程在权重部分文件落盘后故障退出，确认进程退出后显式 recover/resume；记录 Range 206 真续传或 200 安全重下，核验真实 payload 字节、完整 manifest/上游权重 SHA-256 及 SQLite 自动登记。未执行模型权重、无质量结论。GUI 加入显式人工确认异常恢复（本地 worker 运行时拒绝；外部执行器存活须操作者验证，不自动接管），恢复清理陈旧网络速率。Windows smoke 成功时通过主进程 capturePage 保存 PNG artifact 及 JPEG 日志预览，尚未进行实际像素比对，不宣称 1:1。ModelScope 仍沿用文件级恢复/原有搜索及离线测试，真实全权重下载未验证。新 CI 通过后检查日志及截图再进入 E11c，若公共 Hub 网络故障先区分环境与代码。Windows GUI only，原 D 线只读，Europe PMC 暂缓。


## E11c1 科研语料中心（开发分支，待 CI）
前置 E11b3 920a15c 标准 CI 45738140228 和专项 45738140235 三项均 success；真实 HF 随机小模型固定 SHA ffd1b09a4fa19a9086ed4e36d57eda60fcb2c2c0，6,477,096 字节、部分 262,144 字节，HTTP 206 续传、恢复网络 6,214,952 字节、自动登记成功；不是实际翻译质量/ModelScope 全权重验收。Windows 截图 1008×655，已取得视觉证据但与设计稿差异明显，尚未像素验收。新增 GUI 单次 NCBI PMC 流水线配置：已登记教师/固定 SHA、日期关键词、篇数/分段/下载字节上限、CPU/CUDA 与精度、明确授权创建及再次确认启动；固定受限 IPC、独立长运行子进程、阻止本地下载和语料 worker 并发、正常退出保护、仅阶段>=2 的显式人工确认恢复，采集不得自动重放。论文/候选数据集/任务快照只读且各至多50项，不暴露完整 spec/manifest。候选门槛不等于训练授权，后端单次流水线无协作暂停/取消；持续自动化、训练控制、实时 Loss 及完整 GUI 视觉校准未完成。新增 SQLite 快照回归及 Windows 原生 smoke（真实持久语料创建/拒绝未授权/无效任务实际 worker 启动并失败，不联网、不执行合成教师权重）。实际科研论文及教师生成的 GUI 全链路待后续验收。下一 E11c2 训练队列、配置与监控，前提本提交 CI 全通过。Windows GUI only，Europe PMC 暂缓，D 线只读。


## E11c2 训练中心第一轮（开发分支，待 CI）
E11c1 d9f6076 标准 45739368042、专项 45739368036 success。新增固定 Marian 学生的 GUI 训练队列：精确候选版本与许可复核声明、优化器步数、批大小、学习率、累积、CPU/CUDA/精度、时间与检查点及显存软预算，固定可信启动环境资产/检查点目录（学生资产仍须 CLI student-assets 预备），创建与运行单独确认。GUI 显式启动一个 FIFO 任务，暂停/恢复/取消/人工确认异常恢复，保留 SQLite 单 worker、已验证 checkpoint、保守预算、后端每段重新核验数据与权利。本地下载/语料/训练执行器互斥、退出保护，不是系统全局锁。训练事件从已验证且原子登记的 checkpoint history 最后一步记录真实 loss，dashboard 与训练页只显示单任务最近 120 个检查点样本，非逐步实时遥测，不混合任务；旧数据无指标保持空状态。新增 SQLite 只读快照测试及原生 Windows smoke：拒绝无授权、持久队列创建/暂停/恢复/取消、实际空队列 worker，未训练合成数据。真实 CPU 训练由既有专项验收；真实 GPU、逐步遥测、学生资产 GUI 下载、完整自动串联及像素级还原待后续。下一 E11c3 实时训练遥测与运行控制中心视觉校准，先核验 exact head CI。Windows GUI only，Europe PMC 暂缓，D 线只读。
