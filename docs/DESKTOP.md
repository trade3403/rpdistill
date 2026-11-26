# E11a RPDistill Studio 桌面工程

参考 docs/assets/rpdistill-auto-distill-dashboard.png 的深色中文桌面工作台，首阶段重在真实数据和安全架构，尚未逐像素还原设计、未验收高 DPI 或安装包。五个导航页：工作台、模型与下载、科研语料、训练任务、评测与导出。只读状态页，评测页明确尚未接入；不使用模拟 loss/显存/完成状态。

## 本地开发（仅 Windows）
Python 3.11+ 已安装，项目根目录 `python -m pip install -e .`；进入 desktop 后 Node 22，`npm install`、`npm run build`、`npm start`。RPDISTILL_PYTHON 由可信操作者指定 Python executable（默认系统 python/python3），RPDISTILL_DB 指定本地 SQLite（默认 ~/.rpdistill/tasks.sqlite3）。不要从不可信目录或环境启动。直接 npm 版本固定，尚无提交的 package-lock（传递依赖需后续冻结），非发布构建。

## IPC 和数据
固定 studio-snapshot 命令，无 renderer 参数；spawn 无 shell，15s 查询超时，1MiB stdout 上限、stderr 丢弃、并发合并；IPC 检查当前窗口主 frame 来源。sandbox=true/contextIsolation=true/nodeIntegration=false，CSP 无网络、禁止弹窗/外部导航/webview/权限请求；不暴露 ipcRenderer 或文件系统。假定可信本地 Python/包/数据库，非不可信程序沙箱。读取 SQLite mode=ro、query_only、trusted_schema=OFF，不初始化/迁移缺失数据库，统计实际 count，近期任务和登记模型最多50条，摘要不含完整 spec；硬件探测不代表训练就绪。10s 定时刷新，异常保留上次快照并标记。大数据库 count 可能耗时，超时显示失败；后续增量查询。

## CI
Windows TypeScript/esbuild 构建及原生 Electron 启动 smoke；Python CLI 实际入队合成 model（不联网下载），renderer 经受限 IPC 读取实际记录、验证无 Node require、页面展示真实 fixture。Windows 原生启动待最新提交 CI 复验，未做完整窗口交互或安装器测试。Linux/macOS GUI 已按用户要求取消，两平台后端/CLI/计算 CI 保留。E11b 开始固定操作协议、用户明确许可/预算确认、任务控制；E11c 真实训练/语料/自动化；E11d 评测导出、安装与交互。

用户明确取消 Linux GUI：自本次提交起，E11/E12 桌面端只支持 Windows/macOS，Linux GUI 构建、启动、打包及发行不再作为要求；Linux Python/Rust CLI、后端及专项计算 CI 保留，不取消 Linux 训练能力。此前修复 b59ad53 的三平台 Desktop CI 45632934256 已成功，历史结果保留。新的 Desktop CI 矩阵 Windows/macOS 两项，分别保留真实 Electron 窗口/持久队列 IPC smoke（使用 scripts/studio_desktop_smoke.py，独立临时 DB、无 shell、无禁用沙箱），取消 Linux 专属 xvfb/SUID 配置。两平台真实启动尚待新 CI 验收，不能用历史 Linux 成功代替。未改变应用安全设置或后端 CI。后续安装包仅 Windows/macOS，真实 GPU 按硬件和后端可用性验收。

## 最新范围调整：仅 Windows GUI

用户明确取消 macOS GUI（Linux GUI 此前已取消）。自本次提交起，E11/E12 桌面 GUI、原生启动 smoke、安装包和发行仅支持 Windows；macOS/Linux Python/Rust CLI、后端与计算 CI 维持原范围，不取消训练能力。历史提交 98dbde0 标准 CI [45633656271](https://github.com/trade3403/rpdistill/actions/runs/45633656271) 10/10 success，Desktop [45633656134](https://github.com/trade3403/rpdistill/actions/runs/45633656134) 首次 Windows 原生窗口/IPC success、macOS cancelled，曾请求单项重跑；macOS 自本次授权起不再是验收门槛，不将其记录为通过。保留 Windows 真实 Electron/持久队列 IPC smoke、sandbox/contextIsolation 与原后端 CI；新提交需核验标准 CI 及 Windows Desktop CI，通过后继续 E11b 模型搜索、许可和预算确认、下载队列操作。Europe PMC 继续暂缓，D 线保持只读，真实 GPU/教师质量/人工评审及正式安装包仍待验收。本节覆盖此前 Windows/macOS 双平台 GUI 计划，旧记录保留为历史。

## E11a 高保真布局第一轮（独立视觉分支）
依据 docs/assets/README.md 对 1672×941 中文深色设计稿的文字规范，重构左导航、中间流水线/六项真实指标/Loss 空状态/GPU 显存快照/任务错误摘要、右侧任务配置和单次/持续控制；未接入的配置与启动按钮禁用。窗口默认 1672×941，较窄窗口响应式排列，保留安全 IPC、实际下载/训练记录及 Windows 原生 smoke，扩展 smoke 检查三栏结构和禁用控制。未读取原 PNG 像素、未获得实际运行截图，不能称 1:1 还原；需在真实 Windows 运行、以原 PNG 逐项对照，核对 DPI 与字号、色值、尺寸及滚动。实时 Loss/利用率/事件流和操作仍待 E11b/E11c 接入。此分支不推进主分支 CI 门槛。


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


## E11c3b 学生资源下载与训练预检（开发分支，待 CI）
前置 ba6a99c 标准 45741902280、Windows 专项 45741902265 success。GUI 新增授权固定公开 OPUS-MT 五文件下载，4 MiB 单次预算，复用 revision/hash/续传及缓存校验，不下载权重；专用子进程及本地 worker 互斥、正常退出保护。只读快照核验学生资源哈希、实际资产/检查点目标磁盘可用量及四依赖发现状态（不导入 ML、不证明运行环境），GUI 创建/启动训练前阻止缺资源/依赖/最低检查点空间不足，配置页另检查选择设备空闲显存。后端原有每段数据、资产、设备及预算验证不变；外部进程不属于本地互斥。修复下载启动遗漏训练互斥。新增缺失/损坏/正确哈希测试、原生 IPC 拒绝未经授权和注入路径；Windows 专项实际 CLI 下载并校验固定五文件（GUI 实际联网点击尚未验收）。下一 E11c3c 原图高保真及任务联动，仍须逐项验证真实截图、实际 GPU/自动蒸馏全链路；Windows GUI only，Europe PMC 暂缓，D 线只读。


## E11c3c1 参考稿控制中心布局重建（开发分支，待 CI）
前置 04e7120 标准 45742953498、Windows 专项 45742953537 success。原始 1672×941 参考 PNG 已复查。重建控制中心：70px 顶栏、200px 十项侧导航、八段流程、五指标、训练 Loss/评测/GPU/速度切换、显存圆环/真实资源、日志、400px 任务配置和54px状态栏；小屏响应式。导航保留既有模型/语料/训练页面，评测与发布仍为占位，计划/自动化进入语料页、设置暂为说明。右侧已接入真实固定教师+关键词/日期/篇数/预算确认后创建并启动单次 NCBI PMC CPU FP32 语料；训练预算跳转训练页；唯一活动下载或训练可协作暂停/取消，语料无此接口；持续自动蒸馏、自动训练/评测/发布未实现，明确禁用。所有图表、日志、阶段状态来自快照，无虚构样本，语料阶段独立于训练，候选未授权训练。清空仅隐藏当前视图，保留数据库。原生 smoke 更新十导航、八流程、五指标及初始控制禁用检查；尝试 offscreen 原尺寸截图，实际尺寸/像素对照仍待 CI，不能宣称 1:1。下一阶段按截图对照继续校准，Windows-only，Europe PMC 暂缓，D线只读。


## E11c3c2 截图对照与细节校准（开发分支，待 CI）
871675c 标准 45744209353、专项 45744209392 全 success，已从 reference 139656217883 与 Windows 139656218229 日志取得两图并人工对照；实际 offscreen Electron 1672×941，主面板结构接近但非1:1。本轮校准右栏/中央分界、标题字体、导航 SVG 线性图标、卡片/日志字号、显存双色环、训练进度条、底栏及原生 Windows titleBarOverlay（offscreen capture 不保证捕获 OS 窗口控件）；实际训练模型优先显示，候选语料不称有效语料。新增原生 smoke 8区域完整可见及 viewport 尺寸断言；CI 保存同尺寸原始/实际并排 PNG、绝对差异图及平均 RGB 差异 JSON，诊断而非像素相等门槛。保留真实数据、许可确认、持续自动化禁用；运行总时长暂无可靠记录显示未知，不虚构样例值。仍待新 CI、实际窗口人工验收、真实 GPU 与持续全链路；下一阶段视新截图校准结果进入 E11d 评测导出。Windows only，Europe PMC 暂缓，D 线只读。


## E11d1 本地质量评测中心（开发分支，待 CI）
前置 c36b581 标准45745414468、专项45745414607均 success；Windows offscreen 1672×941、8区域完整，原稿RGB平均绝对差27.3101，非1:1，右栏仍需滚动。新增完成训练登记检查点+人工审核JSONL原生文件选择+明确授权；本地 CPU FP32 评测最多200条/128新token，复用冻结评测、训练重叠拒绝、完整检查点核验及默认质量门槛，不降低覆盖要求。持久SQLite评测记录、冻结集/完整报告本地独立目录、只读摘要与BLEU/chrF/数字/术语等，报告身份校验、显式异常恢复，不自动发布；本地执行器互斥，评测无协作暂停，其他独立CLI进程不受全局锁保护。新增后端持久记录测试（注入测试报告，非真实评分）及Windows IPC拒绝未授权/路径注入；真实模型评测已有CPU微型专项，完整GUI人工真实评测尚未执行。E11d2量化候选及导出验证待本提交CI通过。Windows-only GUI，Europe PMC暂缓，D线只读。


## E11d1 跨平台评测测试路径修复（待 CI）
ca1760b 标准 CI 45746734363 为6/10 success，四个 macOS/Windows Python 3.11/3.12 CPU矩阵全部在 test_persist_report_and_recovery 触发 checkpoint outside registered job root；已核查四份日志。训练队列登记 spec.root 时使用 Path.resolve()，实际 worker 从该规范路径构造 checkpoint；测试却直接从 TemporaryDirectory 原始路径构造，跨平台临时目录别名导致字面不等。修正测试从真实登记 spec.root 构造 checkpoint，保留生产路径安全检查和所有原断言，补充越界路径必须拒绝且不创建评测目录的回归；Windows 专项路径过滤加入新增测试，重新验收。原专项 45746734341 success；新提交 exact head 标准和专项全部通过后进入 E11d2，真实人工评测/GPU/像素级验收仍未完成。Windows GUI only，Europe PMC 暂缓，D线只读。


## E11d2a 本地量化候选、回归及FP32导出（开发分支，待CI）
前置8137f32标准45747939872、Windows专项45747939909 success。新增候选任务登记与只读摘要；仅接受默认自动门槛通过且身份匹配的本地评测、冻结集及已登记完整检查点。复用FP32/FP16/INT8存储转换、同源冻结集CPU FP32回归（200条、用户软时间预算），未通过回归仍保存研究记录但不选择；独立FP32本地候选包显式权利声明、预算、校验包ID和来源，非官方RPModel v1。固定可信输出目录、严格IPC及本地执行器互斥，显式异常恢复，不自动采用残留文件或发布。新单元测试覆盖预算/授权、异常状态、模拟回归记录，Windows smoke拒绝注入路径；真实转换及回归已有微型CPU专项，完整GUI真实质量通过模型及Rust兼容仍待验收。下一E11d2b Rust诊断/人工质量复核和发布门槛，再进入Windows安装包；先核验exact head CI。Windows GUI only，Europe PMC暂缓，D线只读。


## E11d2b1 Rust诊断与人工盲审入口（开发分支，待CI）
前置4127886标准45749266579、专项45749266543 success。新建持久复核任务：已验证FP32候选包绑定原评测/检查点，固定可信启动环境RPDISTILL_RUST_BRIDGE执行原有Rust logits/greedy parity及固定token profile，保存完整报告、可执行文件哈希与首项吞吐，非生产加载器或真实翻译质量；外部基线JSONL原生选择、匿名A/B packet和独立private/key、评审JSON导入、默认人工门槛与词汇泄漏复核，持久摘要不暴露私密映射。仅交付packet给评审者，私密文件仍由本地用户保管（不宣称文件系统访问隔离）。固定输出目录、明确授权、异常恢复及本地互斥。新增持久盲审模拟测试与Windows拒绝执行路径注入。实际Rust桥接需可信本地构建并设置环境，真实人工复核和GUI真实模型尚未验收；下一E11d2b2接入完整本地集成回执（原评测重放/权利复核/Rust诊断）及最终发布门槛，随后安装包。Windows GUI only，Europe PMC暂缓，D线只读，未合并主分支。


## E11d2b2 本地集成验收及回执复核（开发分支，待 CI）
前置 b612583 标准45750560517、专项45750560533 success。新增集成任务：已通过的登记collect→blind→同一评测→已验证FP32导出包，核对基线、匿名包、映射、原人审与分数哈希；明确数据集SHA/教师及模型许可证/权利声明/复核人/训练选择与软时间预算，复用既有review_integration重新评审默认门槛、当前权利/训练来源、权重一致、全部译文重放、Rust诊断，桥接程序哈希前后核对，保存receipt.json及登记双ID。历史回执校验使用登记的包/回执ID，明确不重新审核权利或认证身份。GUI允许选同源最近50项记录，可信启动环境指定桥接，无任意路径IPC；异常恢复沿用复核队列。新增跨源拒绝及历史回执双pin模拟回归、Windows IPC拒绝未授权与注入路径。真实GPU、真实人审、完整集成/生产加载器与分发均未验收，任何回执release_ready=false。下一E11d3 Windows安装包，须新CI全部通过；Windows GUI only，Europe PMC暂缓，D线只读，未合并main。


## E11d3a Windows x64 安装候选（开发分支，待 CI）
前置8fd6d57标准45772434850、专项45772434894 success。新增 electron-builder 26.0.12 NSIS 当前用户安装，目录可选、桌面/开始菜单快捷方式、卸载保留应用数据，明确禁止自动发布；未签名候选。构建从可信 Windows x64 setup-python 3.11 runtime 分离复制 Python EXE/DLL/标准库及许可证、安装本仓库基础包到隔离 packages，._pth 限定导入路径，不包含 pip/第三方 ML依赖或权重，安装版默认绝对路径内置后端，RPDISTILL_PYTHON可信覆盖保留。设置页显示可选依赖发现。新增分支及未来 main 的 Windows installer CI：实际生成NSIS EXE、静默安装、检查快捷方式、隔离PATH且无外部Python覆盖的真实Electron IPC smoke、卸载及外部测试数据保留检查，上传EXE和SHA-256验收JSON（7天）。不宣称安装已通过，待本次CI；不含CUDA/PyTorch/教师SDK/评测依赖/Rust桥接，使用可信外部Python环境，图形化依赖部署、升级/真实用户安装、代码签名/传递依赖锁定及GPU完整流程后续验收。Windows GUI only，Europe PMC暂缓，D线只读，未合并main。

### 安装候选与完整训练环境
仅在新安装器CI通过后，从对应 run artifact `windows-x64-unsigned-installer-candidate` 获取EXE并核对report SHA-256；这是未签名的本地开发候选，不是正式发行。内置后端可离线查看/管理本地基础记录，不能直接进行完整模型下载、训练或评测。完整环境：安装可信64位Python 3.11/3.12，创建独立venv，按硬件从可信渠道安装合适的 PyTorch CPU/CUDA，再从本仓库对应提交安装 `python -m pip install ".[hub,modelscope,student,evaluation]"`；启动前在PowerShell设置 `$env:RPDISTILL_PYTHON = 'C:\\path\\to\\venv\\Scripts\\python.exe'`（替换真实路径），启动已安装 EXE。Rust诊断另需可信本地构建的桥接程序并设置 RPDISTILL_RUST_BRIDGE。数据库及模型等默认位于用户 home/.rpdistill，不与程序安装目录混放；卸载不会主动清理这些数据。请自行备份重要资料。未验收升级迁移/完整环境一键部署。


## E11d3b1 独立训练环境部署（开发分支，待 CI）
前置11f5cd5标准45775088310、专项45775088292全通过；安装验收 job139756704221实际EXE 106190202字节 SHA256 fa6be9d9fe78156f7a3a23855ece0e99666b3256cf56ba9f0d529046619cc820，安装/快捷方式/隔离PATH内置后端/卸载/外部数据均通过，未签名候选。新增设置页固定 CPU 或 CUDA12.8 PyTorch2.7.1，预装可信Win x64 Python3.11/3.12后通过原生选择及再次确认；独立新venv、12/25GiB空闲空间预检（非硬配额）、固定官方torch索引/PyPI二进制依赖、隔离pip/Python环境，逐阶段状态；pip check、真实CPU张量/选CUDA则真实CUDA张量、全部SDK导入及后端快照校验后写 verified.json，绑定安装包精确wheel SHA256。主进程原子登记active.json，后续启动恢复验证过的独立环境，版本/wheel变更回退基础，外部RPDISTILL_PYTHON优先且禁止部署；失败不替换旧环境、保留未完成目录供人工核对，正常关闭保护、本地执行器互斥。新增Windows专项实际CPU联网部署（无GUI点击/激活验收）及拒绝无授权/路径注入测试。尚未通过新CI；用户需预装Python，不自动安装系统Python；CUDA实际硬件/GUI完整部署/升级和回滚、硬预算/依赖锁定/签名仍待后续。E11d3b2完善环境切换、修复及安装体验，后续E12真实GPU/人审全链路。Windows GUI only，Europe PMC暂缓，D线只读，未合并main。


## E11d3b2 历史环境切换、回滚与首次使用引导（开发分支，待 CI）
前置4c79974标准45777901058 success；专项45777901054 attempt1仅NSIS安装0xC0000005失败，未改代码重跑attempt2全success，不能确认根因。实际CPU环境部署job139765948256完成PyTorch2.7.1+cpu、七依赖发现、真实张量、后端快照与wheel绑定。新增设置页最多50个历史目录（按ID），切换前离线recheck：固定注册ID、精确wheel hash、收据、pip check、实际CPU/按profile CUDA张量、后端协议，失败不改原active指针；基础回滚保留所有历史目录，修复以新建环境替代就地修改。已选环境查询失败时内置基础后端提供只读快照、锁定普通任务、允许在设置中恢复；持久任务或本地执行器活动时拒绝切换。首次使用工作台底栏引导进入设置，未自动联网；外部Python覆盖继续优先。Windows专项实际CPU环境重复验证、篡改wheel pin拒绝、恢复后再验；安装器增加同版本覆盖安装及外部测试数据、快捷方式保留，再实际启动卸载。GUI点击切换/回滚、真实跨版本迁移、系统Python安装、CUDA/真实GPU训练仍待验收；本轮无签名/完整传递依赖锁定。下一阶段新CI全绿后，进入E12真实GPU/教师/质量与全自动链路剩余缺口验收（持续调度尚未完整实现），Windows GUI only，Europe PMC暂缓，D线只读，未合并main。
