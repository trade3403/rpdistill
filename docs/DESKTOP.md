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
