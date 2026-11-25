# E 线路研发路线

目标：独立 AI 蒸馏训练工作台，首先为 RPTranslate 科研翻译学生模型提供可复现训练流程。

| 阶段 | 功能与验收 |
|---|---|
| E1.1 | Python 基础工程、配置验证、CLI、跨平台 CPU CI |
| E1.2 | 实验清单、任务状态、日志、可复现配置及设备探测 |
| E2.1 | Hugging Face 搜索、固定 revision、许可/预算预检、SafeTensors 下载、校验和 SQLite 注册 |
| E2.2a | SQLite 下载任务、文件级验证进度、协作暂停/取消与恢复、瞬态重试 |
| E2.2b1 | ModelScope 搜索、版本查询、固定 SHA 下载、来源隔离 |
| E2.2b2 | SDK 安装、真实小配置与检索 smoke、HF 逐块字节进度和 Range 恢复；ModelScope 字节级控制后续完善 |
| E2.3 | 本地已注册 SafeTensors 教师模型加载、科研批量翻译、真实微型 CPU 推理；Qwen 候选质量与 GPU 验收留本机/E7 |
| E3.1 | NCBI PMC 为当前默认来源；Europe PMC 用户授权暂缓（手动验收）、元数据许可预筛、SQLite 目录与 DOI/PMCID 去重 |
| E3.2 | PMC 官方 OAI-PMH 元数据/全文双重许可检查、XML 下载、完整性和预算控制；内容权限筛选在 E3.3 |
| E3.3a | JATS 保守解析、分段、教师批量翻译与候选语料持久化 |
| E3.3b | 候选数据集内容寻址版本、数量门槛、单次自动采集翻译及持久阶段；持续增量、跨来源和完整质量门槛后续完善 |
| E2 总体 | 教师模型适配器；Qwen 候选；内置在线搜索与一键下载（Hugging Face / ModelScope）、下载队列、断点续传、缓存、校验、自动注册、许可证记录、本地/远程推理 |
| E3 | 可无人值守的论文采集与语料流水线； 优先实现科研论文在线检索、许可过滤、批量全文下载及自动入库；开放许可数据集在线搜索与一键下载、PDF/Word/TXT/JSONL 语料导入、分段、双语生成、清洗去重、术语保护、人工审核、数据集版本 |
| E4a | 只读审计 D 线固定 Marian 规范、学生网络及权重契约、真实 CPU 初始化/微型前向 |
| E4b | 真实固定分词器对照、训练 batch、mask、labels 与数据适配 |
| E5a | 序列级蒸馏真实 CPU 参数更新、损失、SafeTensors 权重检查点；正式数据须有明确权利/质量授权 |
| E5 后续 | 正式数据门槛与训练自动触发；按分词器兼容性研究 logits/特征蒸馏、多教师 |
| E6a | 同 CPU 环境完整训练状态、优化器/RNG/数据游标、梯度累积、分段续训及单检查点预算 |
| E6b1 | CUDA、FP16/BF16 AMP、GPU RNG/GradScaler 完整状态、显存软预算；CPU 回归及真实 GPU 本机 |
| E6b2 | SQLite 训练队列、自动分段检查点、暂停/取消/恢复、累计预留预算；常驻服务及全局资源管理后续完善 |
| E7a | 独立人工参考评测集冻结、精确防泄漏、BLEU/chrF、术语/数字/公式字面/引用与疑似漏译检查、自动门槛 |
| E7b1 | 实际学生检查点 CPU 推理、冻结 benchmark 评分、外部基线对照、延迟与吞吐 |
| E7b2 | 有界词面近重复审计、匿名 A/B 盲测流程、候选门槛、Linux/macOS peak RSS；实际人工评审/真实基线/正式质量校准本机，COMET 视许可和适用性 |
| E8a | FP32/FP16/逐行 INT8 存储候选、误差/体积/完整性、FP32 还原生成测试 |
| E8b | 同冻结 benchmark 量化前后真实质量回归与候选选择；原生量化、INT4 与剪枝须验证 D 线支持 |
| E9a | 独立自训练 FP32 诊断候选包、资产/来源/许可/版本哈希、完整尺寸 Rust raw reader 对照 |
| E9b1 | 独立候选包可信 pin 诊断桥、真实 Rust Encoder/Decoder/full+cached logits 与 greedy 对照 |
| E9b2 | 导出候选源权重、权利与质量复核、实际生成重放、Rust 诊断和独立集成凭据；生产入口协调见 PRODUCTION_INTEGRATION.md（未接入） |
| E10a | 完整尺寸 Rust CPU 诊断性能基准：加载分段、Encoder、Decoder、KV cache、RSS、吞吐量 |
| E10b | 固定 D 临时构建词表行并行实验、同源双构建 bitwise parity 和同机性能实测；生产采用须协调，不强制重写 PyTorch |
| E11a | Electron/React/TypeScript 中文深色只读工作台、安全 IPC、真实状态与硬件快照、Windows build/启动 smoke |
| E11b | 模型搜索与下载中心、许可预算确认、下载任务控制 |
| E11c | 科研语料、训练配置及任务控制、真实监控、自动流水线 |
| E11d | 评测导出界面、Windows 安装与交互验收；远程训练管理需独立安全设计 |
| E12 | 从自动检索到真实蒸馏与导出的无人值守端到端验收； Windows 完整安装包、真实 GPU 蒸馏、质量及性能对照、综合发布验收 |

每阶段提交独立测试与交接记录，CI 成功后再进入下一阶段。CPU CI 不能代替 GPU 训练实测。所有演示数据须明确标记，不虚报准确率。教师模型不预先锁死，使用前核查许可、评测效果与硬件预算。

用户明确取消 Linux GUI：自本次提交起，E11/E12 桌面端只支持 Windows/macOS，Linux GUI 构建、启动、打包及发行不再作为要求；Linux Python/Rust CLI、后端及专项计算 CI 保留，不取消 Linux 训练能力。此前修复 b59ad53 的三平台 Desktop CI 45632934256 已成功，历史结果保留。新的 Desktop CI 矩阵 Windows/macOS 两项，分别保留真实 Electron 窗口/持久队列 IPC smoke（使用 scripts/studio_desktop_smoke.py，独立临时 DB、无 shell、无禁用沙箱），取消 Linux 专属 xvfb/SUID 配置。两平台真实启动尚待新 CI 验收，不能用历史 Linux 成功代替。未改变应用安全设置或后端 CI。后续安装包仅 Windows/macOS，真实 GPU 按硬件和后端可用性验收。

## 最新范围调整：仅 Windows GUI

用户明确取消 macOS GUI（Linux GUI 此前已取消）。自本次提交起，E11/E12 桌面 GUI、原生启动 smoke、安装包和发行仅支持 Windows；macOS/Linux Python/Rust CLI、后端与计算 CI 维持原范围，不取消训练能力。历史提交 98dbde0 标准 CI [45633656271](https://github.com/trade3403/rpdistill/actions/runs/45633656271) 10/10 success，Desktop [45633656134](https://github.com/trade3403/rpdistill/actions/runs/45633656134) 首次 Windows 原生窗口/IPC success、macOS cancelled，曾请求单项重跑；macOS 自本次授权起不再是验收门槛，不将其记录为通过。保留 Windows 真实 Electron/持久队列 IPC smoke、sandbox/contextIsolation 与原后端 CI；新提交需核验标准 CI 及 Windows Desktop CI，通过后继续 E11b 模型搜索、许可和预算确认、下载队列操作。Europe PMC 继续暂缓，D 线保持只读，真实 GPU/教师质量/人工评审及正式安装包仍待验收。本节覆盖此前 Windows/macOS 双平台 GUI 计划，旧记录保留为历史。
