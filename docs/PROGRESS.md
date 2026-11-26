# RPDistill 研发进度与验收台账

更新时间：2026-11-25（更新）
仓库：trade3403/rpdistill；分支：main；版本：V0.1.0；当前阶段：E1.1 CPU CI 已通过，E1.2 CPU CI 六环境已通过；E2.1 CPU CI 六环境已通过；E2.2a CPU CI 六环境已通过；E2.2b1 CPU CI 六环境通过；E2.2b2 标准 CI/联网 smoke 9/9 通过；E2.3 标准 CI/联网回归 10/10 通过；E3.1 已提交待验收。

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
| E2.1 | 教师在线检索、下载校验与注册 | CPU CI 六环境通过 |
| E2.2a | 持久化队列、文件级校验进度、协作控制 | CPU CI 六环境通过 |
| E2.2b1 | ModelScope 基础搜索、固定版本下载与注册 | CPU CI 六环境通过 |
| E2.2b2 | HF 字节进度/Range、SDK 兼容及联网 smoke | 9/9 CI 通过 |
| E2.3 | 教师加载翻译、真实微型 CPU 推理 | 10/10 CI 通过 |
| E3.1 | NCBI PMC / Europe PMC 检索、许可预筛、去重 | 并发修复后双来源联网及标准 CI 通过；Europe PMC 按用户要求暂缓 |
| E3.2 | 全文 XML 下载与许可复核 | 10/10 必需 CI 通过（10 篇实测） |
| E3.3a | JATS 解析、候选双语语料 | 10/10 必需 CI 通过（337 段实测） |
| E3.3b | 数据集候选版本与单次自动采集翻译调度 | 标准 CI 8/8 通过 |
| E4a | D 线审计、Marian 学生架构及权重契约 | 标准 9/9 + Hub 2/2 CI 通过 |
| E4b | 固定真实分词器、候选训练批次及损失掩码 | 标准 9/9 + tokenizer 1/1 CI 通过 |
| E5a | 真实序列级蒸馏与权重检查点 | 标准 CI 9/9 success，真实 80 steps |
| E6a | CPU 完整训练状态、梯度累积与分段续训 | 标准 CI 9/9，176 状态张量逐位一致 |
| E6b1 | CUDA/AMP、GPU 训练状态及预算 | 标准 9/9 + tokenizer 1/1 success；真实 GPU 待本机 |
| E6b2 | 持久化训练队列与周期完整检查点 | 已提交，待 CI |
| E3 后续 | 全文许可复核、下载、解析及语料生成 | 待开发 |
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

核验 E3.1 标准 CI 与独立论文联网 smoke；通过后进入 E3.2 全文许可复核和合法 XML 下载。

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

## E2.1 验收与 E2.2a 下载队列
提交 cdce0d4787a46a5dfb6df56f9ff86f65226177a7 对应 [CI 45582334642](https://github.com/trade3403/rpdistill/actions/runs/45582334642) 六个 job 全部 success。E2.2a 新增 SQLite 下载队列、去重、单 worker 原子抢占、每文件校验进度、处理速率与 ETA、可恢复状态、文件间协作暂停取消、有限瞬态重试、CLI。新增 9 个测试方法，累计 32 个。使用模拟 SDK 与合成文件；不宣称实际网络断点、字节实时带宽或 ModelScope 已验收。SDK 单文件传输期间不能立即暂停；异常退出需确认 worker 停止后恢复。下一阶段 E2.2b 处理多来源及联网验收；大模型留用户电脑。

## E2.2a 验收与 E2.2b1
提交 6ab0537454675dbb7e26709fbe0217cf75edd61f 对应 [CI 45582666202](https://github.com/trade3403/rpdistill/actions/runs/45582666202) 六个 job 全部 success。E2.2b1 新增 ModelScope Hub SDK 适配、公开模型查询、版本查询、固定 commit SHA 下载、许可/容量/哈希检查、独立注册表及下载队列来源选择；7 个新增测试，累计 39 个。接口参考官方 modelscope/modelscope_hub 的 api.py 与 types.py。仅模拟 SDK 验证，实际 SDK 安装、公开服务字段、固定 SHA 与联网下载仍待验证；严格拒绝缺少 SHA-256 的文件，不降级为浮动版本。实时网络字节进度与在线测试拆为 E2.2b2；不在免费 Runner 下载大型模型。

## E2.2b1 验收及 E2.2b2
提交 45fcba663c68c09593d988c7333053f7e7479546 对应 [CI 45585519890](https://github.com/trade3403/rpdistill/actions/runs/45585519890) 六环境全部 success。E2.2b2 新增 transfer.py、队列 network_bytes/network_rate 字段迁移、Hugging Face 固定 revision 逐块 HTTPS 传输、SHA-256 部分文件 Range 恢复、块间控制、真实本地 HTTP socket 测试；新增 7 个测试方法，累计 46 个。CI 新增 SDK 安装兼容 job，独立 hub-live.yml 执行 HF 公共小配置（64 KiB 上限）及 ModelScope 在线搜索。待核验两个 workflow。未下载真实模型权重；ModelScope 字节进度、队列 streaming 集成专项测试、真实大文件中断恢复待补，外网失败不能伪报通过。下一步先检查本次 CI/联网 smoke，再推进教师翻译。

## E2.2b2 验收与 E2.3 开发
提交 dbe106f1c112215e884cce9e30f6c1ab8c45a86e：[标准 CI 45586043352](https://github.com/trade3403/rpdistill/actions/runs/45586043352) 7/7、[联网 smoke 45586043462](https://github.com/trade3403/rpdistill/actions/runs/45586043462) 2/2 全部 success。仅小配置下载及真实检索，无真实大模型下载。E2.3 新增 inference.py、注册表精确版本查询、清单再校验、本地 SafeTensors 加载、CPU/CUDA 显式选择、确定性生成、输入/输出 token 预算、批量翻译及来源元数据；新增 6 个单元测试方法，累计 52 个。CI 新增实际 PyTorch CPU 随机微型模型推理，不下载预训练权重；本次新提交仍待 CI。Qwen 具体版本、真实翻译质量、GPU/显存实测待用户电脑及 E7；ModelScope 字节级控制仍待完善。下一步 E3.1 论文搜索及许可过滤。

## E2.3 验收与 E3.1 开发
提交 b1fce260eda9af4676a25192daf6fa665834c3a6：[标准 CI 45586949170](https://github.com/trade3403/rpdistill/actions/runs/45586949170) 8/8（含真实微型 CPU 推理），[联网回归 45586948901](https://github.com/trade3403/rpdistill/actions/runs/45586948901) 2/2 全部 success。E3.1 新增 papers.py、Europe PMC REST 官方 API 查询、关键词/主题词、日期、语言、OA 筛选、分页上限、DOI/PMCID/provider ID 去重、许可预筛与 SQLite 目录、CLI paper-search/paper-list。新增 9 个单元测试方法，累计 61 个，独立论文联网 smoke 最多检查 3 条记录。不下载全文、保存摘要或授权训练；CC BY/CC0 仅为待全文权利复核候选。来源学科覆盖以生命科学/医学为主，其他平台后续接入。新提交待 CI；下一步 E3.2 合法全文许可复核/下载，之后解析、翻译清洗与跨来源扩展。

## E3.1 联网失败与修复
提交 fadf2ab3e3307923e57451da0e601cfae6774d0b 对应 [标准 CI 45588253788](https://github.com/trade3403/rpdistill/actions/runs/45588253788) 8/8 success；[论文联网 smoke 45588253824](https://github.com/trade3403/rpdistill/actions/runs/45588253824) failure，真实日志 Europe PMC HTTP 503。新增有界瞬态重试（默认 4 次尝试、2/4/8 秒退避，遵守 Retry-After，超过 60 秒则终止以免过早请求；永久 HTTP 错误、TLS 错误不重试）。保持真实联网测试的成功断言，不吞掉失败或改用模拟结果。新增 5 个测试方法，累计 66 个；新修复待标准与联网 CI 复验。未进入 E3.2。

## E3.1 重试验收与备用来源
提交 e2cfef89cc08b6bca1636fcf6ad9258abbf07a97 对应 [标准 CI 45588726018](https://github.com/trade3403/rpdistill/actions/runs/45588726018) 8/8 通过；[论文联网 45588726112](https://github.com/trade3403/rpdistill/actions/runs/45588726112) 仍失败，日志显示 HTTP 503 重试耗尽。新增 ncbi_papers.py：NCBI PMC 官方 ESearch/ESummary、语言与日期、OA/CC BY/CC0 查询过滤、PMCID/DOI、目录去重、可选自动备用来源（仅首个请求暂时失败，无部分检索预算重置），报告原失败原因。新增 7 个单元测试，累计 73 个。保留 Europe PMC 独立真实测试，增加 NCBI PMC 独立联网 smoke，均须核验，不把备用成功当作 Europe PMC 恢复。NCBI 许可筛选不等于具体全文许可，待 E3.2 验证。未进入 E3.2。新提交待 CI。

## E3.1 双来源实际验收（仍有阻塞）
代码提交 97d7c3a6aaca1a88e73d514bacca9e33f03cb7bc：[标准 CI 45589377280](https://github.com/trade3403/rpdistill/actions/runs/45589377280) 8/8 success；[双来源联网 45589377415](https://github.com/trade3403/rpdistill/actions/runs/45589377415) 首次 attempt：NCBI PMC job 139119203251 success（实际日志 inspected=3, inserted=3, duplicate=0, conflict=0, invalid=0），Europe PMC job 139119202890 failure（HTTP 503，重试后仍失败）。已确认官方 REST URL 与公开文档一致；官方论坛曾报告 HTTP 503 与流量上升，但本次具体原因未知。未改变验收门槛或测试代码，已成功请求仅重跑此 workflow 的失败 job；等待实际结果。文档提交单独触发标准 CI，论文联网结果仍以对应代码 SHA 的上述 run 为准。E3.2 尚未启动。若持续不可用，需用户明确同意调整外部服务验收门槛，不能直接将失败判为通过。

## E3.1 Europe PMC 排序参数修正
文档提交 5ddb3b25f10cd7cb17635b74fae18e4334d7fbcf 的标准 CI 45592551774 8/8 success；联网 run 45589377415 attempt 3 再次 failure，Europe PMC job 139138835459 HTTP 503，NCBI PMC success。进一步对照 Europe PMC REST 官方 Sorting Results（https://staging.europepmc.org/RestfulWebService）及公开 EBI-Metabolights 实例，修正 sort 从 FIRST_PDATE desc 为 P_PDATE_D desc；保留 FIRST_PDATE 日期范围过滤，保留真实联网断言、重试与原验收门槛。打印出版日期排序与首次发表日期筛选语义不同，不承诺按首次发表日期全局严格排序。新增请求契约测试 1 项，累计 74 个测试方法。503 是否由旧排序字段引起尚未确认；新提交待两套 CI 实测。未进入 E3.2。


## E3.1 授权暂缓与 E3.2
用户明确要求跳过 Europe PMC 论文检索先做其他功能。最新文档 CI 45592551774 8/8 success；联网 run 45589377415 attempt 3：NCBI PMC success、Europe PMC failure，保留真实失败记录，不认定为通过。Europe PMC job 改为手动 workflow_dispatch，常规推进要求其余标准 CI 及 NCBI 联网全部通过。NCBI PMC 成为默认 CLI 来源。E3.2 新增 fulltext.py、官方 OAI-PMH pmc_fm 预检与 pmc 全文下载、明确 CC BY/CC0 URI、标识/记录日期/许可一致性检查、预算、原子文件保存、哈希与 SQLite 状态、缓存复用。新增 8 测试方法累计 81，新增真实小规模全文 smoke（8 MiB，最多 3 候选），待 CI。原始全文不是训练授权，第三方材料和内容过滤留 E3.3，PDF 下载及多来源后续。未运行真实 GPU 或下载大型模型。下一步核验 E3.2 CI，再进入解析分段及双语语料生成。

并发修复合并说明：保留 6c37e2d90623806b62baafb3a9cac59e8dd50b01 的 Europe PMC 排序字段修复及测试；其标准 CI 45596188128、双来源联网 45596188201 已通过。此前失败为历史记录，最新 Europe PMC 已实测恢复。按用户要求仍暂缓其常规联网门槛，NCBI PMC 为默认来源，Europe PMC 可手动复验。E3.2 新提交待验收。

## E3.2 首次真实全文验收与修复
提交 64353e110e4f44259c647b4aef2c2db12806b355 对应 [标准 CI 45596496110](https://github.com/trade3403/rpdistill/actions/runs/45596496110) 8/8 通过；[联网 45596496006](https://github.com/trade3403/rpdistill/actions/runs/45596496006) NCBI 检索成功，Europe PMC 按授权 skipped，全文 job 139143823890 失败：实际检索 5 条、预检 3 条，0 保存，3 阻断（1 条许可 URI 不在白名单、2 条重复标识冲突），累计响应 36773 字节。修复 JATS 仅对 PMCID/DOI 做身份一致性检查，允许无关出版商 ID 重复；规范化相同 DOI/PMCID，支持许可节点内明确 CC BY/CC0 链接（不接受缺失、混合、限制许可）。新增 4 个单元测试；真实 smoke 候选检查上限 10，维持 8 MiB 总预算及至少一篇成功的断言。真实 XML 原文未能通过当前浏览工具读取，具体字段修复基于日志及 JATS 结构，待实际 CI 验证。未进入 E3.3。

## E3.2 验收与 E3.3a
提交 5144ec8e7a2446641b0af05a173c0c112d2b5173：[标准 CI 45597390219](https://github.com/trade3403/rpdistill/actions/runs/45597390219) 8/8、[联网 45597390263](https://github.com/trade3403/rpdistill/actions/runs/45597390263) NCBI 检索/全文 2/2 success，Europe PMC 授权 skipped。全文日志 job 139146958985：10 检索、10 保存、0 阻断、0 失败、1,436,306 字节，全部 CC BY，状态待内容复核。E3.3a 新增 corpus.py：本地哈希/许可重检、保守正文与摘要解析、分段、第三方权利标记/复杂公式图表隔离、署名来源、确定性论文级划分、SQLite 候选源段/译文、教师批量调用、数字/长度/完成状态筛查、幂等复用、候选 JSONL 导出与精确文本去重。新增 8 个测试方法；扩展真实联网 smoke 至实际论文解析。仅候选，不标训练就绪；公式复杂内容暂排除、语言仅启发式、无真实 Qwen 质量测试，版本化数据集/跨版本泄漏检查/自动调度待 E3.3b。新 CI 待核验。

## E3.3a 验收与 E3.3b
提交 6387e7abae01a8a3824e1c72340b66d257b7c995：[标准 CI 45599371724](https://github.com/trade3403/rpdistill/actions/runs/45599371724) 8/8、[真实联网 45599371716](https://github.com/trade3403/rpdistill/actions/runs/45599371716) NCBI 2/2 success，Europe PMC 授权 skipped；真实 job 139153869385 下载 10 篇、解析 337 段、0 阻断，均为候选原文，非真实双语质量结果。E3.3b datasets.py 固定教师/配置、最低样本门槛、重新检查源文件哈希、精确源文本跨版本 split 防护、内容寻址快照、完整性导出；pipeline.py 单次 NCBI 搜索→下载→解析→翻译→候选快照，SQLite 持久化阶段、单 worker 原子抢占、解析及之后失败可恢复、采集失败新授权周期。新增 7 个测试方法；CI 待验收。候选快照 training_ready=false，不标正式训练许可；历史快照不能直接作为当前权利证据。持续调度、跨来源与完整增量分页、真正语言/语义/公式质量和近重复泄漏、冻结评测集待后续。E4 读取实际 RPTranslate Rust 规范及学生网络适配，不能先假设架构。

## E3.3b 验收及 E4a
提交 65619c3286ad047ab177d3e7ee66d0fac25afcd1：[CI 45601299054](https://github.com/trade3403/rpdistill/actions/runs/45601299054) 8/8 success；论文联网路径未变，上次 45599371716 NCBI 2/2 通过。E4a 只读审计 D 线 feature/rptranslate 固定 7f1fdb282bbdc947dc4a5d953768efaed429959d；新增 student.py、StudentProfile、canonical 形状/共享权重验证、固定资产哈希、保守分词 ID 映射、student-info、4 个单元测试、新增 real-cpu-student job：真实小 Marian 前向及完整尺寸随机初始化。256 canonical tensors、312033188 FP32 payload bytes，非实测总内存。D loader 仍固定官方来源/哈希，rust_deployable=false；不伪造包。E4b 真实 tokenizer 资产对照与训练 batch/labels/mask，E5 真实参数更新；E9 自训练包 Rust 验收。详情 docs/STUDENT_CONTRACT.md。新 CI 待验收。

## E4a 验收与 E4b
提交 4250379ba05c096073e11952a859617faabb1d3b：[标准 CI 45603053723](https://github.com/trade3403/rpdistill/actions/runs/45603053723) 9/9、[Hub 联网 45603053807](https://github.com/trade3403/rpdistill/actions/runs/45603053807) 2/2 success；真实学生小网络前向与完整尺寸 256 张量初始化通过。E4b training_data.py：5 个固定哈希小资产自动下载，不下载权重；从 candidate snapshot 检查完整版本/成员/当前全文哈希许可预筛，选定 split 进行分词，动态 batch、mask/decoder shift/labels=-100、token/logits 预算；CLI student-assets/student-batch-plan。新增 5 个单元测试方法（4 training_data + 1 snapshot），真实 CPU smoke 增加 masked loss 对照；新增真实固定资产 Python/HF/Rust 三方 ID 对照 workflow，D 线 checkout 固定审计 SHA 只读。新 CI 待验收。候选数据仍 training_ready=false，未更新模型权重、未测试真实 Qwen/GPU；正式训练权利/语义质量门槛、完整自动调度及自训练包部署留后续。

## E4b 验收与 E5a
提交 c7871527b66b78377eab4a019969f866fce06e8e：[标准 CI 45604907365](https://github.com/trade3403/rpdistill/actions/runs/45604907365) 9/9、[分词器 45604907414](https://github.com/trade3403/rpdistill/actions/runs/45604907414) 1/1 success。job 139173180582 下载 5 资产 3230522 bytes、10/10 三方 network IDs 一致、0 unknown rejection、未下载权重；job 139173180974 masked loss 3.4788079261779785、5 supervised tokens，与显式 CE 一致。E5a distill.py 新增 DistillConfig、真实 CPU FP32 AdamW/反传/梯度裁剪、确定性 shuffle/seed、token 加权 eval loss、SafeTensors 不覆盖检查点（权重、历史、来源、配置、哈希）及安全重载；student-distill CLI 要求操作者确认精确候选版本内容权利/质量与注册教师许可，使用 train split 且当前资格/哈希/分词通过、达到计数门槛。新增 3 个单元测试方法与真实 tiny CPU synthetic-target 80-step 训练 smoke（实际参数变化、loss 降低至少 50%、权重/ logits roundtrip、损坏及覆盖拒绝）；待 CI。未运行真实 Qwen 译文蒸馏或完整尺寸训练，无准确率声明。只权重 checkpoint，不保存优化器和 RNG，无精确续训；E6 添加真实 CUDA、资源预算、混合精度、积累、持久训练状态和精确恢复。自动触发仅在权利/质量授权及正式数据门槛完成后；无 logits/feature 蒸馏跨分词器假设。

## E5a 验收与 E6a
提交 33a5951d8c88180487b6feb12d270b9558c86883：[标准 CI 45606587882](https://github.com/trade3403/rpdistill/actions/runs/45606587882) 9/9 success，真实 job 139178917662：80 steps、43 tensors changed、初始 loss 3.482527494430542、最终 0.002275040838867426、checkpoint roundtrip true、corruption rejected true，synthetic token targets、quality_test=false、exact_resume=false。E6a resumable.py 新增 ResumeConfig、确定性 epoch 顺序/cursor、按有效目标 token 归一化梯度累积、AdamW 单步更新、完整 SafeTensors 权重+优化器 moments/step+CPU RNG，hash manifest/数据/配置/环境绑定、禁止覆盖、磁盘与单 checkpoint 字节预算、每段优化器步数与软时间门槛；review helper 复用，CLI student-train-resumable，需精确 dataset 与 teacher license review。新增 3 个单元测试方法与真实 CPU 7 steps 连续 vs 2+2+3 分段逐位全部状态和 history 对照，拒绝数据顺序变化与损坏。新 CI 待核验。边界：只同环境 CPU FP32，非 CUDA/AMP；只在调用结束保存（强杀可损失本段），无实时 RAM/VRAM/累计磁盘控制或持续 worker；E6b 增加 GPU、混合精度及持久调度/定期保存。历史 E5 权重 checkpoint 仍保留，不能当完整续训状态；新 checkpoint 不是 RPModel。真实翻译质量本机/E7。

## E6a 验收及 E6b1
提交 a3fedbadc863dd00f1a338cfa91e11e116f3a73f：[CI 45608461745](https://github.com/trade3403/rpdistill/actions/runs/45608461745) 9/9 success；job 139185411102 真实 CPU 7 steps、2 interruptions、accumulation 2、176 state tensors 位一致、history/optimizer/RNG 一致，改变数据及损坏拒绝；合成样本非翻译质量。E6b 分为 b1 CUDA/AMP 与 b2 持久调度/周期保存。b1 修改 resumable.py/student.py，显式 CUDA index、FP32/FP16/BF16、native BF16 检测、autocast/GradScaler、unscale 后裁剪、非有限失败、GPU RNG/scaler checkpoint、环境绑定，CPU 原 checkpoint manifest 格式兼容；CUDA free VRAM 预检与步边界 peak allocated 软预算，不是硬限制。新增配置测试、CPU 无 CUDA 拒绝、独立本机 scripts/cuda_smoke.py（真实 GPU 7-step 连续/恢复对照，未运行）。新标准 CI 与因 student.py 改动触发的 tokenizer parity 待验收。真实 GPU/AMP 运行仍待用户本机，不能凭 CPU CI 宣称 GPU 成功。E6b2 接持久化 worker、自动定期 checkpoint、累计磁盘/时间预算和暂停恢复，保留单段旧 checkpoint。正式训练数据仍需复核。原 D 仓库只读。

## E6b1 验收与 E6b2
提交 a91dd39f823f3c36ee34ce1ce1992d6fb57a9c07：[标准 CI 45610312760](https://github.com/trade3403/rpdistill/actions/runs/45610312760) 9/9、[tokenizer CI 45610312728](https://github.com/trade3403/rpdistill/actions/runs/45610312728) 1/1 success。真实 CUDA/AMP 尚未执行。E6b2 training_queue.py 新增 SQLite 训练任务与事件、单数据库单 worker 原子抢占、去重、按 segment 自动保存完整检查点并继续、optimizer-step pause/cancel、失败/中断控制、显式确认旧 worker 停止后 recover、先预留累计秒数和 checkpoint bytes（不退还）、校验已登记 checkpoint、历史保留；CLI training-enqueue/run/list/show/events/pause/resume/cancel/recover。修改 resumable.py 增加 should_stop 边界回调。5 个新单元测试和真实 CPU training_queue_smoke，验证暂停后重新打开数据库、继续到 5 steps、3 个 checkpoint、最终状态等于连续训练。新 CI 待验收。限额为保守预留及软边界，不是实际累计运行时间硬上限；无全局 GPU 锁、无常驻 worker、无自动清理、未接自动语料到正式训练的审核触发。强杀丢本段，未登记孤立文件不自动采纳。真实 Qwen/GPU 留本机，E7 独立评测。D 线只读，Europe PMC 授权暂缓。

## E6b2 验收及 E7a
提交 17efb1c130b955a67a6957bffe664e2844231b59：[CI 45611935152](https://github.com/trade3403/rpdistill/actions/runs/45611935152) 9/9 success；job 139197420690 实际 CPU queue 5 steps、3 checkpoints、176 equal state tensors、pause/restart/resume 与 budget reservations true；此前 E6b1 45610312760、45610312728 success，真实 CUDA 未运行。E7a evaluation.py 新增训练快照完整性检查、训练精确文本及声明 DOI/PMCID 防泄漏、人工参考/权利声明、不可覆盖 benchmark、严格 hypothesis IDs、真实 SacreBLEU zh BLEU/chrF、科研数字引用/术语/保护字面串/疑似漏译启发式、覆盖和指标 gate、哈希与版本报告；CLI benchmark-freeze/benchmark-score；4 个新单元测试及真实 SacreBLEU smoke，新增 CI job real-evaluation。当前自动评分仅外部输出且 model_output_authenticated=false、release_ready=false，非真正学生质量；近重复、真实 checkpoint 推理与基线、独立人工评审、速度内存、COMET 适用性在 E7b 后续。默认门槛是研发假设，必须在真实独立评测上校准。新 CI 待验收。

## E7a 验收及 E7b1
最新 main 8c0a13ea3bfb0e5ac474da8f62eac021192dc8e8 是在 E6b2 之后已经存在的 E7a 提交，保留不重复实现。[标准 45612791270](https://github.com/trade3403/rpdistill/actions/runs/45612791270) 10/10、[Hub 45612791012](https://github.com/trade3403/rpdistill/actions/runs/45612791012) 2/2、[tokenizer 45612790903](https://github.com/trade3403/rpdistill/actions/runs/45612790903) 1/1 success。real-evaluation job 139200380347：合成 authored reference 自对照 BLEU 100.00000000000004（浮点舍入）、chrF 100；错误样本 BLEU 9.807068765986307、chrF 15.203315203315205、数字/术语/保护串 0，错误/覆盖不足/训练重叠/损坏均拒绝，非模型质量。E7b1 student_evaluation.py：真实 CPU greedy generation、E5 权重与 E6 complete full-state 安全模型读取、训练 dataset binding、固定 SPM network-ID decode、自然 EOS 与截断/未知词失败、同冻结 benchmark 指标和可选外部 baseline delta、实际逐条延迟与 token/s、权重体积、报告哈希；CLI benchmark-student。2 个新单元测试与真实微型 CPU 训练→两格式读取→生成与 SacreBLEU smoke，CI 待验收。无 KV cache 优化，不是实际 GPU/Rust 性能，未测 RSS/VRAM；合成分词/目标非真实独立翻译质量。外部基线未认证，release_ready=false；E7b2 近重复与盲测/正式质量门槛、实测内存及真实基线，COMET 视许可/预算；E8 后续。原 D 仓库只读，真实 Qwen/GPU 仍本机。

## E7b1 验收及 E7b2
提交 bbc685f8550819f17b2a40813ba6db2bd2fd7ed9 [CI 45613582255](https://github.com/trade3403/rpdistill/actions/runs/45613582255) 10/10 success；job 139203108793 实际 checkpoint_formats=2、actual_generation=true、eos=true、synthetic_chrf=[100.0,100.0]、wrong_dataset/corruption/insufficient coverage rejected，model_quality_test=false；续训及队列 176 张量位一致回归通过。未改动 Hub/tokenizer 继续沿用上一成功 CI。E7b2 quality_review.py：有界倒排 lexical near-duplicate audit（token equality/word trigram Jaccard/containment，训练→评测与评测内部，超限拒绝）、重算报告 metrics 及内容哈希、随机 A/B packet 与私有 mapping、声明独立评审完整双侧评分/critical/preference、绑定报告与默认自动 gate/生成/泄漏审计、候选 review report；新增 benchmark-leakage-audit/benchmark-blind/benchmark-review CLI，Linux/macOS 真实 process peak RSS，非模型独占内存；3 unit tests 和 CPU 真实生成评分+合成盲测 smoke，待 CI。人工身份/真实 baseline 未认证，近重复只词面非语义，reviewer fixture 非实际人工评审，release_ready=false；门槛需实测校准，COMET 暂缓未确定许可/预算/适用性，真实 GPU/实际基线和正式质量认证留本机/E12。下一 E8 FP32/FP16/INT8 候选压缩/质量回归，D loader 兼容性需验证，不改变原仓库。

## E7b2 验收及 E8a
提交 5122a065e962b3d97090b0880946219e7ca82c01：[CI 45615224138](https://github.com/trade3403/rpdistill/actions/runs/45615224138) 10/10 success，job 139208745858 lexical audit/盲测 roundtrip、2 synthetic reviewers、自动覆盖不足拒绝，process lifetime peak RSS 430583808 bytes；真实人评=false，非正式翻译质量。E8a 只读审计 D 线最新 5389f3fc33ab45b93f6cab7c7e5bfd17fe43e8e9 RPMODEL_FORMAT_V1.md、marian_weights.rs、package.rs：F32 与固定官方来源/哈希仍强约束。compression.py：固定 profile 的 FP32、矩阵 FP16、逐行 INT8 + FP32 scale，位置/偏置/norm FP32，规范共享权重、布局、payload、有限数值、还原误差、实际 bytes/hash、源 checkpoint+dataset identity、不可覆盖、预算和严格加载回 FP32；CLI student-compression-plan/student-compress。3 unit tests + 现有真实微型 CPU 训练评测 smoke 加三格式转换/加载/合成生成一致、异常 scale/源身份/损坏拒绝。待 CI。候选不是 RPModel 或原生量化推理，完整尺寸仅估算、真实质量回归待 E8b，正式人评/GPU 留本机；E9 独立自训练 Rust 包。原 D 仓库未修改。

## E8a 验收及 E8b
提交 0046e0eec951d3d95c6ad7088fc12889dc9127a4：[CI 45615777344](https://github.com/trade3403/rpdistill/actions/runs/45615777344) 10/10 success；job 139210668370 实测微型 FP32/FP16/INT8 文件 29752/19216/17016 bytes、max abs 0/0.00012129545211791992/0.0017775893211364746，合成译文一致，错误 source 与损坏拒绝；完整尺寸理论 payload 312033188/157391780/80601416 bytes，INT8 比 FP32 减少约74.17%，非真实完整模型测量。E8b compression_review.py：同源重算转换、实际冻结评测生成与绝对 gate、相对 BLEU/chrF/文本变化率、逐条新增规则错误、泄漏审计、按实测 artifact bytes 选择最小合格候选；预算与报告哈希；CLI benchmark-compression。新增 4 unit tests + 真实微型同源三候选评测/错误绑定/改动转换/覆盖不足不选择回归，待新 CI。选中仅工程候选非人评/发布；FP32 参考计算，不是原生 INT8 推理。E9 自训练包规范、实际 Rust 验收；D 当前仅固定官方 F32，须协调独立加载路径，原仓库不修改。真实 Qwen/GPU/完整质量仍留本机。

## E8b 验收及 E9a
提交 de36eb9cdf4cd2e6c91e3f325ec4633c427dfe55 [CI 45617423525](https://github.com/trade3403/rpdistill/actions/runs/45617423525) 10/10 success，job 139216341097 同源三候选生成不变、覆盖不足不选择、错 checkpoint 与篡改转换拒绝，release_ready=false。E9a 只读 D 线最新 cce002dd2667e6fcd0ec4c86c9b41a3da144b26e，官方 package 仍固定来源/revision/F32/哈希。新增 model_export.py 独立候选 schema、固定 256 FP32 canonical 与 5 资产、源 checkpoint/dataset/provenance、操作者许可和权利说明、文件与 package hash、外部预期 pin、预算/不覆盖/严格验证，CLI student-export-plan/student-export-candidate/student-verify-package；docs/MODEL_CANDIDATE_FORMAT.md；3 unit tests；独立 model-export-live.yml 固定 D checkout 中编译 CI-only raw reader bridge，完整尺寸真实单步合成 token CPU training→checkpoint→候选包→全部 Rust little-endian stream SHA256/byte parity，官方 loader 拒绝、外部 pin/损坏拒绝。待标准和专项 CI。尚非生产 Rust package load/模型推理，无正式权利/质量/发布授权；E9b 需协调独立 D 加载入口、模型推理对照和正式质量 gate；原 D 仓库未修改。真实 Qwen/GPU/人评本机。

## E9a 验收及 E9b1
提交 1ce24ce4d8d1015b03de4fbb0893480770c0c3a5 [标准 CI 45619532043](https://github.com/trade3403/rpdistill/actions/runs/45619532043) 10/10、[独立专项 45619531918](https://github.com/trade3403/rpdistill/actions/runs/45619531918) 1/1 success；job 139223662017 实际完整尺寸单步合成 CPU training，256 tensors，312033188-byte Rust raw stream SHA256 c4d318f999a9e00e5e03b46361d9d090e2dfd49a53a54c641601ea9a9c7cbb7e，weights file 312062580 bytes，错误外部 pin、损坏和官方 loader 拒绝；未做神经网络 Rust inference。E9b1 只读最新 D 2fa70c175de7a25415489ecb12ffe3d09485f777；scripts/rpdistill_candidate_infer.rs 诊断桥：独立校验固定 asset、权重 SHA256/metadata/shape，同一打开的权重文件读取，调用真实 Marian embeddings/encoder/decoder/MarianEncoded；rust_parity.py 先验证独立 package ID、通过可信本地 executable 对照两固定 token/mask 测例的 encoder memory/full+cached logits/greedy IDs，atol=rtol=3e-4，3 generated tokens max、无 forced EOS，报告 hash；新增 CLI student-rust-parity、2 unit tests，扩展全尺寸专项 CI，错误权重/来源 pin 拒绝。新 CI 待验收。并非生产 loader、文本翻译质量或发布授权，无 D 仓库写入；E9b2 质量/权利审批与候选导出衔接，生产加载接口仍需独立协调。真实 GPU/Qwen/人工质量本机。

## E9b1 验收及 E9b2
提交 8aa263af7f13541f87cf84b83ec7cacec0477602：[标准 CI 45621311986](https://github.com/trade3403/rpdistill/actions/runs/45621311986) 10/10、[Rust 专项 45621311499](https://github.com/trade3403/rpdistill/actions/runs/45621311499) 1/1 success。job 139229896843 完整尺寸 synthetic CPU 1 step、256 F32 tensors、312033188 raw bytes、SHA256 88fdda8bce31907efe845f6954720917f7dbe76b1ada2fd4ab7c3eccaef20fa7；Rust 两个 encoder/full/cached decoder logits/greedy 对照，最大 abs 4.291534423828125e-6，错误 weight/checkpoint pin/损坏/官方 loader 拒绝成功，production_loader_verified=false。E9b2 export_review.py/student-review-integration：默认自动/人工质量 gate 重算、独立 pin、实际全部 canonical tensor 与已完成 checkpoint 对照、当前训练 selection/teacher license/权利声明复核、实际 generation 与盲评输出一致、重新运行 Rust diagnostics、不可覆盖哈希凭据；5 单元测试（审批成功路径为 mock）和完整尺寸专项新增真实 source binding/错误来源拒绝。新标准+Rust专项 CI 待验收。未运行真实人工/正式质量全链审批，未授权发行，生产入口未实现，D 线保持只读。E10 按实测定位性能问题；E9b2 生产 loader 协调待单独授权/实施，见 PRODUCTION_INTEGRATION.md。真实 GPU/Qwen 留本机。

E9b2 补充：并行提交 07dca11949fc47bb5864ec01266a627a54a2d672 已建立 export_review.py；保留原实现，不重复另建审批模块。新增双外部 pin 的 student-check-handoff，嵌套报告/来源/权利/重放校验；正式完整训练状态的 data_sha256 复核，签发前再次核对候选与当前本地权利。2 个新单测及实际微型生成重放/质量覆盖拒绝、完整尺寸诊断报告不可冒充凭证的回归，待新标准与 Rust 专项 CI。正向人工审批仍仅 mock，生产加载未接入。

## E9b2 验收及 E10a

E9b2 a7582b5 标准 CI 45623637959 10/10 + Rust 专项 45623638472 1/1 success；实际微型生成重放、质量覆盖不足拒绝（job 139238005444），实际完整尺寸 Rust 诊断及诊断报告非审批凭证拒绝（job 139238007240），两组 greedy 一致、max abs logits 3.814697265625e-6。E10a rust_profile.py / scripts/rpdistill_candidate_infer.rs --profile / student-rust-profile：固定 16/64 source tokens、8/16 max new tokens、每组1 warmup+3 measured、交替 full/cache 次序、同一完整尺寸模型实际输出一致，记录实际生成 token、六项加载阶段 ns、encoder/decoder prepare/full/cache generation 分段、median/token/s/cache ratio、Linux Rust 进程生命周期 peak RSS、exe/weights/package hash 和 host 信息。性能为合成 token 诊断 workload，非翻译质量、冷缓存保证、真实用户场景或生产性能；不要求固定加速倍数，重复结果/协议不一致拒绝，可信 executable 和稳定本地文件假设。3 unit tests 与真实完整尺寸专项新增 profiling，待新标准与 Rust 专项 CI。E10b 依据实测进行优化及精度回归，不盲目重写 PyTorch；原 D 仓库不修改，生产接口仍待协调；真实 GPU/人工/质量留本机。

## E10a 实际性能及测试修复

E10a 28f728459dbe502b13bd717bb748c8088c76f0e2：Rust 专项 [45625397449](https://github.com/trade3403/rpdistill/actions/runs/45625397449) 1/1 success，job 139244112848；标准 [45625397448](https://github.com/trade3403/rpdistill/actions/runs/45625397448) 4/10 success，六个跨平台 unittest job 同一 test_early_eos 失败（原 fixture 字符串替换同时命中较长序列前缀，导致 EOS 后仍有 token；解析器正确拒绝）。修复为按 case 构造提前 EOS，测试仅短/仅长/两组，新增显式 EOS 后 token 拒绝测试；不修改 runtime parser 或门槛。专项 workflow 增加 test_rust_profile.py 路径以重新验证 exact head。待新标准及专项全部通过才进入 E10b。历史实测 Linux x86_64 4 logical CPUs，16→8 tokens encoder 249720496ns/full 2595300952ns/cache 2293468055ns，64→16 encoder 381493704ns/full 5614579083ns/cache 4561371208ns；cache ratios 1.13160545/1.23089721，full token/s 3.082494/2.849724，cache token/s 3.488167/3.507717；RSS 323821568 bytes，weight hash 1122456331ns。生成 IDs 一致。合成诊断非质量或生产 SLA；优先剖析 decoder 路径，仍需细分实际瓶颈。原 D 只读。

## E10a 验收及 E10b

E10a 修复提交 4b320fbc21c66e2143f649c7c3531a910f7bc380：标准 [45627103978](https://github.com/trade3403/rpdistill/actions/runs/45627103978) 10/10，Rust [45627103954](https://github.com/trade3403/rpdistill/actions/runs/45627103954) 1/1 success。job 139250090350 实测 16→8 token ordinary/cache 1546349128/1279364445 ns，64→16 3481629088/2599562047 ns，cache ratio 1.208685/1.339314，cache throughput 6.2531/6.1549 token/s，RSS 323817472 bytes。跨 Runner 波动明显，不能跨机器宣称加速。E10b 固定 D 2fa70c175de7a25415489ecb12ffe3d09485f777 源审计：OutputHead::project 逐词标量 dot product（65001×512，每生成步约33280512乘加），选择词表行独立并行候选。scripts/apply_projection_experiment.py 仅修改 CI 临时 pinned D checkout，RowTable sealed + Sync、最多4 scoped workers、>=1048576 MACs 才并行，串行 fallback、同一行 FP32 升序累加和原 bias，不复制权重；原 D 仓库不写。projection_experiment.py / student-rust-compare-projection：同一候选、同 host、两个独立 trusted binary hash、完整短诊断二进制逐字节一致（含 encoder/full/cached logits/greedy），再对两种固定 profiling workload 测量；3 unit tests + D rpinfer library tests + 真实完整尺寸双构建回归，CI 待验收。无固定速度阈值；若无实际加速不建议采用，未做生产部署/真实文本/GPU 性能。仅实验性补丁，生产 D 集成依然待协调。E11 GUI 可在验收通过后推进。

## E10b 验收与 E11a

E10b 5cfa63992e39de8d62c1ecfddc51dea16965c263：标准 [45629087050](https://github.com/trade3403/rpdistill/actions/runs/45629087050) 10/10 + Rust [45629087039](https://github.com/trade3403/rpdistill/actions/runs/45629087039) 1/1 success。job 139257120314 Rust 52/52 tests，3134424 diagnostic bytes bitwise identical；16→8 full 2.617533628→2.506918947s/cache 2.248898513→2.143470875s；64→16 full 5.889429172→5.499378759s/cache 4.504332838→4.264901802s；speedup 1.0441/1.0492/1.0709/1.0561，RSS 323809280→323764224 bytes。合成同机实测，未证明统计显著或生产收益，D 原仓库未修改。E11a 独立 Electron+React+TypeScript desktop，中文深色工作台/模型下载/科研语料/训练/评测导出页面骨架；Python studio-snapshot v1 以 SQLite mode=ro 读取真实记录与硬件探测，缺失 DB 不创建，计数+每类50条，避免暴露完整 spec；Electron main 固定无 shell 的 Python 命令、15s timeout/1MiB stdout、单请求合并，sandbox/contextIsolation/nodeIntegration=false/CSP/导航和权限限制，只读 IPC；10s刷新，无假 loss 或进度。新增 2 Python tests、三平台 TS 构建与 Linux Electron 真启动+真实持久队列 fixture IPC smoke，CI 待验收。直接依赖固定版本，npm 传递依赖 lock 尚未提交；安装包、安全更新、真实跨平台窗口、操作按钮和完整设计参考一致性未验收，E11b 继续下载/模型操作、E11c 语料/训练/监控、E11d 评测导出及安装。仍需 E12 完整自动化、正式 D 加载、真实 GPU/人评；Europe PMC 暂缓。

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
