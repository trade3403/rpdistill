# E11a RPDistill Studio 桌面工程

参考 docs/assets/rpdistill-auto-distill-dashboard.png 的深色中文桌面工作台，首阶段重在真实数据和安全架构，尚未逐像素还原设计、未验收高 DPI 或安装包。五个导航页：工作台、模型与下载、科研语料、训练任务、评测与导出。只读状态页，评测页明确尚未接入；不使用模拟 loss/显存/完成状态。

## 本地开发（Windows/macOS）
Python 3.11+ 已安装，项目根目录 `python -m pip install -e .`；进入 desktop 后 Node 22，`npm install`、`npm run build`、`npm start`。RPDISTILL_PYTHON 由可信操作者指定 Python executable（默认系统 python/python3），RPDISTILL_DB 指定本地 SQLite（默认 ~/.rpdistill/tasks.sqlite3）。不要从不可信目录或环境启动。直接 npm 版本固定，尚无提交的 package-lock（传递依赖需后续冻结），非发布构建。

## IPC 和数据
固定 studio-snapshot 命令，无 renderer 参数；spawn 无 shell，15s 查询超时，1MiB stdout 上限、stderr 丢弃、并发合并；IPC 检查当前窗口主 frame 来源。sandbox=true/contextIsolation=true/nodeIntegration=false，CSP 无网络、禁止弹窗/外部导航/webview/权限请求；不暴露 ipcRenderer 或文件系统。假定可信本地 Python/包/数据库，非不可信程序沙箱。读取 SQLite mode=ro、query_only、trusted_schema=OFF，不初始化/迁移缺失数据库，统计实际 count，近期任务和登记模型最多50条，摘要不含完整 spec；硬件探测不代表训练就绪。10s 定时刷新，异常保留上次快照并标记。大数据库 count 可能耗时，超时显示失败；后续增量查询。

## CI
Windows/macOS TypeScript/esbuild 构建及原生 Electron 启动 smoke；Python CLI 实际入队合成 model（不联网下载），renderer 经受限 IPC 读取实际记录、验证无 Node require、页面展示真实 fixture。两平台真实启动待新 CI，未做完整窗口交互或安装器测试。Linux GUI 已按用户要求取消，Linux 后端/CLI/计算 CI 保留。E11b 开始固定操作协议、用户明确许可/预算确认、任务控制；E11c 真实训练/语料/自动化；E11d 评测导出、安装与交互。

用户明确取消 Linux GUI：自本次提交起，E11/E12 桌面端只支持 Windows/macOS，Linux GUI 构建、启动、打包及发行不再作为要求；Linux Python/Rust CLI、后端及专项计算 CI 保留，不取消 Linux 训练能力。此前修复 b59ad53 的三平台 Desktop CI 45632934256 已成功，历史结果保留。新的 Desktop CI 矩阵 Windows/macOS 两项，分别保留真实 Electron 窗口/持久队列 IPC smoke（使用 scripts/studio_desktop_smoke.py，独立临时 DB、无 shell、无禁用沙箱），取消 Linux 专属 xvfb/SUID 配置。两平台真实启动尚待新 CI 验收，不能用历史 Linux 成功代替。未改变应用安全设置或后端 CI。后续安装包仅 Windows/macOS，真实 GPU 按硬件和后端可用性验收。
