# E11a RPDistill Studio 桌面工程

参考 docs/assets/rpdistill-auto-distill-dashboard.png 的深色中文桌面工作台，首阶段重在真实数据和安全架构，尚未逐像素还原设计、未验收高 DPI 或安装包。五个导航页：工作台、模型与下载、科研语料、训练任务、评测与导出。只读状态页，评测页明确尚未接入；不使用模拟 loss/显存/完成状态。

## 本地开发
Python 3.11+ 已安装，项目根目录 `python -m pip install -e .`；进入 desktop 后 Node 22，`npm install`、`npm run build`、`npm start`。RPDISTILL_PYTHON 由可信操作者指定 Python executable（默认系统 python/python3），RPDISTILL_DB 指定本地 SQLite（默认 ~/.rpdistill/tasks.sqlite3）。不要从不可信目录或环境启动。直接 npm 版本固定，尚无提交的 package-lock（传递依赖需后续冻结），非发布构建。

## IPC 和数据
固定 studio-snapshot 命令，无 renderer 参数；spawn 无 shell，15s 查询超时，1MiB stdout 上限、stderr 丢弃、并发合并；IPC 检查当前窗口主 frame 来源。sandbox=true/contextIsolation=true/nodeIntegration=false，CSP 无网络、禁止弹窗/外部导航/webview/权限请求；不暴露 ipcRenderer 或文件系统。假定可信本地 Python/包/数据库，非不可信程序沙箱。读取 SQLite mode=ro、query_only、trusted_schema=OFF，不初始化/迁移缺失数据库，统计实际 count，近期任务和登记模型最多50条，摘要不含完整 spec；硬件探测不代表训练就绪。10s 定时刷新，异常保留上次快照并标记。大数据库 count 可能耗时，超时显示失败；后续增量查询。

## CI
三平台 TypeScript/esbuild 构建；Linux xvfb 真 Electron 启动，Python CLI 实际入队合成 model（不联网下载），renderer 经受限 IPC 读取实际记录、验证无 Node require、页面展示真实 fixture。首次 CI 待验收，未做真实 Windows/macOS 窗口交互或安装器测试。E11b 开始固定操作协议、用户明确许可/预算确认、任务控制；E11c 真实训练/语料/自动化；E11d 评测导出、安装与交互。
