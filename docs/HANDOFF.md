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
