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
