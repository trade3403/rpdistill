# RPDistill 研发进度与验收台账

更新时间：2026-11-25（更新）
仓库：trade3403/rpdistill；分支：main；版本：V0.1.0；当前阶段：E1.1 CPU CI 已通过，E1.2 CPU CI 六环境已通过；E2.1 已提交待 CI。

## 当前阶段

E1.1 基础工程已提交，对应 CPU CI 已成功。

| 项目 | 状态 | 证据 |
|---|---|---|
| 独立公开仓库 | 已完成 | trade3403/rpdistill |
| Python 基础包与版本 | 已提交 | pyproject.toml、src/rpdistill/__init__.py |
| CLI 运行入口 | 已提交 | src/rpdistill/__main__.py |
| 不可变训练参数与校验 | 已提交 | src/rpdistill/config.py |
| 基础单元测试 | 已提交 | tests/test_bootstrap.py（5 个测试方法，包含参数子测试） |
| 跨平台 CI 配置 | 已提交 | .github/workflows/ci.yml（3 OS × 2 Python 版本） |
| CI 实际运行 | 成功（查询时） | [Run 45578676242](https://github.com/trade3403/rpdistill/actions/runs/45578676242) |
| 研发路线、架构、交接 | 已提交 | docs/ROADMAP.md、ARCHITECTURE.md、HANDOFF.md |
| 功能清单、进度台账 | 已提交 | docs/FEATURES.md、PROGRESS.md |

E1.1 基础代码提交：[ae58ef6](https://github.com/trade3403/rpdistill/commit/ae58ef6e2e718dc3b8b4ad6a27bd54f0d8402685)。
CI 目标：5 个测试方法 × 6 个环境 = 30 次测试方法执行；对应 CI workflow 已成功（未逐项复核测试日志）。CI 状态是记录时快照，须以最新 Actions 查询更新。

## 阶段进度

| 阶段 | 工作 | 状态 |
|---|---|---|
| E1.1 | 基础工程、CLI、配置、CPU CI | CPU CI 已通过 |
| E1.2 | 实验任务、日志、设备探测 | CPU CI 六环境通过；真实 worker 控制待后续 |
| E2.1 | 教师在线检索、下载校验与注册 | 已提交，待 CI |
| E2.2/E2.3 | 下载任务与 ModelScope、教师加载翻译 | 待开发 |
| E3 | 科研语料生成清洗 | 待开发 |
| E4 | 学生模型及 D 线适配 | 待开发 |
| E5 | 知识蒸馏算法 | 待开发 |
| E6 | GPU 训练及断点恢复 | 待开发 |
| E7 | 质量与性能评测 | 待开发 |
| E8 | 模型压缩量化 | 待开发 |
| E9 | RPTranslate 模型导出 | 待开发 |
| E10 | Rust 高性能优化 | 待开发 |
| E11 | 桌面 GUI 及自动化 | 待开发 |
| E12 | 安装包及真实训练发布验收 | 待开发 |

## 未解决事项

- E1.1 基础代码 CPU CI 已通过；后续提交仍须独立核验。
- 教师具体版本、GPU 硬件、软件开源许可证未确定。
- 真实训练、真实模型、GUI、模型导出尚未实现；无翻译质量实测数据。
- 不用未验证百分比表示整体完成度。

## 下一步

核验 E2.1 CPU CI；通过后推进 E2.2 下载管理与 ModelScope，随后 E2.3 教师翻译适配和 E3 论文采集。

## 强制维护约定

每阶段开始、代码提交、CI 结束及实测验收时更新本台账；同时同步 FEATURES.md 和 HANDOFF.md（若涉及范围或交接变化）。记录日期、阶段、功能 ID、提交 SHA、测试方法数、CI 链接、实际结果、失败与修复、下一阶段。禁止把待实现或仅提交的功能标成已验收。文档提交引发的新 CI 须区分对应 SHA。

## 需求变更：2026-11-25

新增 F23 内置在线下载中心，为必选功能。E2 实现模型在线搜索、一键下载、断点续传、校验、自动注册与缓存；E3 扩展到合法公开训练语料；E11 提供 GUI 下载管理。禁止将手动下载并导入作为正常联网工作流的前置条件。目前仅需求与验收规范已记录，功能尚未实现。

## 需求澄清：2026-11-25

用户明确在线下载主要指科研论文。新增 F24（必选）：E3 科研论文在线检索、批量合法全文下载、自动解析入库及教师翻译语料生成；E11 集成论文采集界面。支持按学科、关键词、日期和数量筛选，尤其是新发表论文。F23 模型/数据集下载保留。当前仅需求文档更新，实际论文采集引擎待开发，未进行联网实测。

## 全自动化需求确认：2026-11-25

F21 升级为核心必选要求：自动搜索论文、下载、翻译、清洗、蒸馏训练、评测与导出，无需用户逐段操作。新增 AUTOMATION.md 规定一次性配置、持续/单次运行、自动触发、停止条件、质量门槛及端到端验收。当前仅文档更新，自动化引擎尚未开发。E1.1 对应 Actions run 45578676242 已查询到 success；此前两个文档提交 CI 也成功；最新论文需求提交 run 45579213090 查询时运行中。

## GUI 设计稿
高清 PNG 已上传到 `docs/assets/rpdistill-auto-distill-dashboard.png`，仓库已核实文件存在，大小 2,007,512 字节。README 引用正式设计稿。此为设计资产，不代表 E11 GUI 已开发或验收。

## E1.2 基础实现与测试策略
新增 tasks.py（SQLite、配置持久化、原子状态转换、事件记录）、devices.py（只读硬件探测）、CLI create/list/show/events/devices。新增 10 个测试方法，总计 15 个；包括并发抢占、状态冲突、持久化、CLI 及模拟 GPU 探测。尚未确认本次 CI 结果。免费 GitHub 托管标准 CPU Runner 测试，不运行真实大模型和 GPU 训练；真实下载、训练、显存/性能验收使用用户自己的电脑。创建任务不代表启动训练，当前状态接口不控制真实 worker。

## E1.2 CI 修复记录
[首次运行 45581459305](https://github.com/trade3403/rpdistill/actions/runs/45581459305) 六个环境全部失败。已检查 macOS/Linux 日志：TaskStore.list 方法遮蔽内置 list，后续 events 返回类型注解在类定义时触发 TypeError，导致两个测试模块无法导入。四个设备测试在已查看日志中通过。修复：tasks.py 使用延迟注解求值（from __future__ import annotations），不改变任务接口或删除测试。重新运行原六环境 CI，全部通过后才能推进 E2；本次修复尚未验收。

## E1.2 修复验收与 E2.1 开发
修复提交 ae2da3dca1d1a5f7c2f826068831ba43a87d0b29 对应 [CI 45581701119](https://github.com/trade3403/rpdistill/actions/runs/45581701119) 已确认六个 job 全部 success。E2.1 新增 teachers.py、可选 Hub SDK、CLI model-search/model-download/model-list、固定 revision、许可证确认、预算/磁盘预检、安全文件清单、大小及上游可用 SHA-256 校验、本地哈希记录与 SQLite 自动注册。新增 8 个测试方法，总计 23 个，全部使用模拟 Hub 客户端/合成文件，不是实际模型权重。当前 E2.1 新提交待 CI；尚无真实在线下载/加载、应用级进度与暂停、ModelScope 或 GPU 训练结果。免费 Runner 不下载大模型；实际联网和大模型验收留给用户电脑。
