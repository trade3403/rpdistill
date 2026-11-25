# RPDistill Studio

独立科研翻译模型训练与知识蒸馏工作台（E 线路）。

RPDistill 负责教师模型、语料、训练、评测和模型导出。RPTranslate 保持独立 Rust 推理，不依赖训练环境。

## 当前状态
E3.1：E2.3 标准 CI（含真实微型 CPU 推理）与联网回归 10/10 已通过；新增 Europe PMC 论文检索、元数据预筛及去重（待 CI）。真实千问质量/GPU 验收待本机。

## 快速开始
```sh
python -m pip install -e .
python -m rpdistill
python -m unittest discover -s tests -v
```

研发计划：[ROADMAP](docs/ROADMAP.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [HANDOFF](docs/HANDOFF.md)

公开仓库不提交私有论文、模型权重、API 密钥或训练数据。使用教师模型前须核查模型许可证与训练数据使用权限。

## 功能与进度
- [完整功能清单（FEATURES.md）](docs/FEATURES.md)
- [研发进度与 CI 验收台账（PROGRESS.md）](docs/PROGRESS.md)

## 内置在线下载（规划中的必选功能）
教师模型及合法公开训练数据集支持软件内搜索、一键下载、断点续传、完整性校验与自动入库；正常联网使用无需手动下载文件。E2.1 Hugging Face 基础搜索/下载/注册 CPU CI 已通过；E2.2a 队列及文件级进度 CPU CI 已通过；E2.2b1 ModelScope 基础适配待 CI，实时网络字节与数据集仍待开发。

## 科研论文在线采集（必选，E3.1 开发中）
直接在软件内按关键词、学科、日期搜索论文，批量下载许可允许的全文并自动解析、分段入库，由教师模型生成高质量双语训练语料。不需要手动逐篇下载 PDF。E3 实现核心、E11 集成 GUI。

## 全自动蒸馏（核心目标，待实现）
一次设置，自动搜索论文、下载合法全文、教师翻译、清洗生成训练集、触发学生蒸馏、评测量化及导出。[自动化规范](docs/AUTOMATION.md)。支持单次和预先授权的持续增量运行。

## GUI 设计参考
[全自动蒸馏控制中心设计稿与 E11 界面要求](docs/assets/README.md)（高清设计稿，非运行截图）。

![RPDistill Studio 全自动蒸馏控制中心](docs/assets/rpdistill-auto-distill-dashboard.png)


### E1.2 本地基础功能
```sh
python -m rpdistill devices
python -m rpdistill create --teacher Qwen-candidate --student RPTranslate
python -m rpdistill list
python -m rpdistill show <task-id>
python -m rpdistill events <task-id>
``
默认数据库为 ~/.rpdistill/tasks.sqlite3；可在子命令前使用 --db 指定路径。创建实验仅保存配置并排队，不会下载模型或开始训练。NVIDIA 探测不等于 CUDA 训练验收。

### E2.1 教师模型管理
```sh
python -m pip install -e ".[hub]"
python -m rpdistill model-search Qwen --limit 10
python -m rpdistill model-list
``
选择搜索结果的实际 model_id 和完整 revision，核查许可证允许预定用途后，使用 `python -m rpdistill model-download MODEL_ID --revision FULL_COMMIT_SHA --reviewed-license LICENSE_ID --max-bytes BYTES`。软件下载、校验并登记，不需手动下载权重。只支持公开非 gated SafeTensors 模型；不会加载或执行模型代码。SDK 管理缓存，本阶段尚无应用级下载队列/暂停控制及实际在线验收。

### E2.2a 下载队列
将 model-download 替换为 download-enqueue（参数相同），再执行 `python -m rpdistill download-run` 处理一个排队任务。另一终端可执行 download-list、download-show ID、download-pause ID、download-cancel ID。暂停/取消在文件间检查，不强制中断 SDK 正在传输的单个文件；download-resume ID 重新排队，SDK 缓存复用，实际字节断点能力待联网验证。download-recover ID --worker-stopped 仅在确认原 worker 已退出时使用。rate/eta 是已校验文件字节的处理速率及估算，包含缓存命中，不是网络带宽。单次 run 仅执行一个任务，持续调度待后续。

### E2.2b1 ModelScope
```sh
python -m pip install -e ".[modelscope]"
python -m rpdistill model-search Qwen --source modelscope
python -m rpdistill model-revisions Qwen/Qwen3-0.6B
python -m rpdistill model-list --source modelscope
``
用实际完整 commit SHA、已核查的许可证和字节预算执行 model-download 或 download-enqueue，加 --source modelscope。只接收明确公开且每个选中文件具备上游 SHA-256 的模型；不能确认时拒绝下载，不自动降级到浮动分支。ModelScope 记录与 Hugging Face 隔离。当前模拟 SDK CI；实际在线响应、SDK 版本及网络速度需 E2.2b2 验证。仍使用文件级进度及 SDK 缓存，不是实时网络带宽。

### E2.2b2 下载监控与联网验收
Hugging Face 队列默认采用公开固定 revision HTTPS 逐块传输，network_bytes 为本次实际读取的响应体字节（不含缓存或恢复前的字节），network_rate 为最近更新窗口速率；done_bytes 仍为已校验文件字节。支持块间暂停和有上游 SHA-256 的部分文件 Range 恢复，服务器返回 200 时重新下载，不拼接错误范围。无上游哈希的部分文件重新下载。SDK 直接下载 CLI 与 ModelScope 暂保留文件级控制；不并行操作相同缓存目录。标准 CI 增加 SDK 安装/接口检查，独立 Public Hub live smoke 只下载 MIT GPT-2 的小 config（最多 64 KiB）及 ModelScope 查询，不下载权重。真实外网状态独立记录。

### E2.3 本地教师翻译
安装适合本机 CPU/CUDA 的 PyTorch 后，`python -m pip install -e ".[inference]"`。先使用下载中心注册已核查许可的指令模型（需要 chat template、SafeTensors 和受支持的 causal 架构）。准备 UTF-8 JSON 字符串数组，例如 `["The sample was heated to 300 K."]`，运行 `python -m rpdistill teacher-translate MODEL_ID --revision FULL_SHA --input source.json --source-language English --target-language Chinese --device cpu`。GPU 使用显式 --device cuda:0 及适配 dtype。模型仅本地读取、重新核验清单、禁用远程自定义代码；不截断超长输入。输出为候选翻译及来源/版本，截断或空输出进入待审核，仍需 E3 清洗和 E7 评测。CI 临时创建随机微型模型验证真实 CPU 加载与生成，不测试翻译能力。

### E3.1 论文检索
```sh
python -m rpdistill paper-search --keyword malaria --subject vaccine --start-date 2024-01-01 --end-date 2024-12-31 --language eng --limit 20
python -m rpdistill paper-list --limit 20
``
Europe PMC 官方 API（生命科学/医学优先），多个 keyword 取 OR，subject 是额外关键词而非正式学科分类。日期采用来源 FIRST_PDATE，语言由来源检索字段筛选；limit 限制检查记录数，并非新增论文保证。默认仅检索 OA；CC BY/CC0 且有 PMCID 的元数据仅进入待全文许可复核，其他阻断；不下载全文、不授权训练、不保存摘要。下一步全文许可验证及合法下载，之后扩展其他学科来源。官方文档：https://europepmc.org/RestfulWebService 与 https://europepmc.org/downloads/openaccess 。

E3.1 联网测试首次返回 HTTP 503，已加入有限重试及 Retry-After 支持，真实联网验收仍待复验。

E3.1 备用来源：paper-search --provider auto（默认）在 Europe PMC 首个请求发生可重试网络失败且重试耗尽后改用 NCBI PMC ESearch/ESummary；--provider europe-pmc / ncbi-pmc 可单独选择。返回 provider、fallback_from 和 fallback_reason，不隐藏原始故障。已部分完成的检索不自动重新消耗预算。NCBI 默认使用 OA 与 CC BY/CC0 查询筛选，确切许可仍须全文复核；不下载全文。官方文档：https://pmc.ncbi.nlm.nih.gov/about/userguide/ 与 https://pmc.ncbi.nlm.nih.gov/tools/get-metadata/ 。原 Europe PMC 真实联网测试保留。

E3.1 最新代码验收：标准 CI 8/8 通过，NCBI PMC 真实检索 3 条并成功入库；Europe PMC 仍返回 HTTP 503，已请求仅重跑失败任务。E3.2 尚未开始，具体记录见 PROGRESS.md。

Europe PMC 日期检索按 FIRST_PDATE 筛选，使用官方 P_PDATE_D desc 排序（打印出版日期），不保证按首次发表日期全局严格排序。修复版待 CI 及真实联网复验。


### E3.2 全文自动下载
用户授权暂缓 Europe PMC，NCBI PMC 成为 CLI 默认论文来源；Europe PMC 代码及真实测试保留（手动触发，不参与常规推进门槛）。`python -m rpdistill paper-download --max-bytes 8388608 --limit 3` 依照已入库候选通过官方 OAI-PMH `pmc_fm` → `pmc` 获取元数据再获取全文；检查 PMCID/DOI、明确 CC BY/CC0 许可证 URI、记录时间及前后许可一致性。仅保存通过检查的 XML，哈希、来源、许可及状态写入 SQLite。`python -m rpdistill paper-fulltexts` 查看记录。每次最多 50 候选、单响应最多 16 MiB、累计接收字节预算（含元数据，超限探测最多额外 1 字节）、逐篇单线程；同一库不要多进程或跨数据库共用目录。原始 XML 可能包含第三方内容，不标为训练可用；E3.3 必须排除无授权内容并保留署名。默认 CLI 检查前 500 条目录记录，后续增加分页和持续调度。官方规范 https://pmc.ncbi.nlm.nih.gov/tools/oai/ 。

并发修复合并说明：保留 6c37e2d90623806b62baafb3a9cac59e8dd50b01 的 Europe PMC 排序字段修复及测试；其标准 CI 45596188128、双来源联网 45596188201 已通过。此前失败为历史记录，最新 Europe PMC 已实测恢复。按用户要求仍暂缓其常规联网门槛，NCBI PMC 为默认来源，Europe PMC 可手动复验。E3.2 新提交待验收。

E3.2 首次真实全文 smoke 发现 JATS 多种标识和许可表达兼容问题，已修复并保持明确 CC BY/CC0 URI 和身份一致性检查，等待重新验收。

### E3.3a 论文解析和候选双语语料
E3.2 修复版标准 CI 8/8、NCBI 联网 2/2 通过，真实下载 10 篇 CC BY 全文，接收 1,436,306 字节。Europe PMC 授权暂缓。E3.3a 新增 `paper-download` 后的 `corpus-parse`、`corpus-list`、`corpus-translate MODEL_ID --revision FULL_SHA`、`corpus-export --output candidates.jsonl`。提取正文/摘要中保守允许的英文拉丁字符比例较高的纯文本段落，保留署名及许可、源文件哈希、论文级固定划分；排除复杂公式、图表、引用块、明确第三方权利标记及超长不可安全切分句子，不截断。教师译文经完成状态、数字、长度、原文复写检查后仅生成候选 JSONL（training_ready=false）；不保证语义正确、语言或版权完全核实。真实教师与训练数据集门槛在后续 E3.3b/E7，需加入语言识别、术语/公式和语义检查、可恢复调度及版本化数据集。CLI 目前分阶段调用，不是一键自动蒸馏。新增真实联网 XML 解析断言，待 CI。

### E3.3b 候选数据集快照与单次流水线
E3.3a 标准 CI 8/8 与 NCBI 真实联网 2/2 通过，实际下载 10 篇并提取 337 段候选原文。新增 `dataset-create MODEL_ID --revision FULL_SHA`（固定教师、选项与最低 train/validation/test 数量）、`dataset-list`、`dataset-export VERSION --output dataset.jsonl`。内容寻址不可覆盖快照，保留成员和哈希，持久化精确源文本 split 约束防止跨版本精确重复泄漏；不是语义近重复检测或正式冻结评测集。快照仅为历史候选，training_ready=false，后续训练前仍须复核当前权利与质量。
`pipeline-create MODEL_ID --revision FULL_SHA --keyword malaria --start-date 2024-01-01 --end-date 2024-12-31 --max-bytes 8388608` 返回任务 ID；`pipeline-run ID` 一次串联 NCBI 搜索→项目目录内已有/新增候选下载→解析→教师批量翻译→候选快照；`pipeline-show ID` 查看持久阶段；`pipeline-resume ID` 后接 `pipeline-run ID` 从解析/翻译/快照失败处恢复。采集阶段失败需创建新授权预算周期，避免重复消耗未记账流量；崩溃恢复需确认 worker 停止。当前共享目录的单次循环与有限任务预算，不是持续定时任务，不保证严格只处理当次检索记录；完整增量分页、跨来源、正式训练门槛、语义与许可验收待后续。真实教师质量在本机验收，CPU CI 为合成样例/模拟教师加已有真实微型模型推理。

### E4a 学生模型契约
E3.3b 标准 CI 8/8 已通过；E4a 依据 D 线固定提交审计 Marian 6+6 层、512 hidden、8 heads、FFN 2048、65001 词表，建立 PyTorch 学生架构与 canonical 权重验证。`python -m rpdistill student-info` 查看契约，`--assets PATH` 验证已在本地准备的固定 tokenizer/config 文件；`pip install -e '.[student]'` 安装学生依赖。学生是随机初始化，尚未训练、未通过真实 tokenizer/Rust 对照。当前 D 线仅接受固定官方审计包，新学生不能冒充原始模型；详见 [STUDENT_CONTRACT](docs/STUDENT_CONTRACT.md)。新 CI 待验收。

### E4b 固定分词器与候选训练批次
E4a 4250379 标准 CI 9/9、Hub 2/2 成功。`student-assets --root PATH --max-bytes 4194304` 自动获取固定 OPUS-MT revision 的 5 个配置/分词器文件（仅约 3.23 MB，不下载权重），哈希校验、限额、缓存、有限重试。`student-batch-plan VERSION --assets PATH --split train` 从不可覆盖候选快照验证版本/成员/当前全文资格与哈希，分词、动态 padding、源和 decoder mask、shift-right labels=-100 忽略填充、按 token/logits 限制构建批次。报告仅候选计划 training_ready=false；不更新权重。CI 增加固定真实 SPM/网络词表与 Python MarianTokenizer、D 线固定 Rust 分词器三方对照，以及微型 Marian masked CE loss 验证。D 仓库只读，不下载大型模型。仍需 E5 权重更新和正式训练授权、完整质量复核，E9 自训练包 Rust 验收。

### E5a 序列级蒸馏（CPU FP32）
E4b c787152 标准 CI 9/9、真实分词器 CI 1/1 通过：5 个固定资产共 3,230,522 bytes，10/10 三方 ID 一致；真实 masked loss 3.4788079261779785（合成样本，非质量指标）。E5a `student-distill VERSION --assets PATH --output NEW_DIR --reviewed-dataset VERSION --reviewed-teacher-license LICENSE --steps 20` 仅在操作者明确核查该版本内容权利、教师蒸馏权利及译文质量后使用，不能自动认定候选数据已认证。固定 Marian 学生随机初始化，train split only，CPU FP32 AdamW/交叉熵/反向传播/梯度裁剪/步数上限、实际损失历史、SafeTensors 权重检查点及 SHA256/严格形状复核。检查点只保存权重及训练记录，不保存 optimizer/RNG，不支持精确断点续训，不是 RPModel 部署包。CI 真实微型 CPU 权重更新、合成样本 loss 下降、权重与 logits roundtrip、损坏拒绝，待验收。正式 GPU、混合精度、梯度累积、精确续训、持久调度在 E6；真实教师译文质量与独立评测在本机/E7。无需下载大型权重。

### E6a 同环境 CPU 精确续训与梯度累积
E5a 33a5951 标准 CI 9/9 success，实际合成微型训练 80 steps、43 tensors changed、loss 3.482527494430542→0.002275040838867426，权重/ logits roundtrip 与损坏拒绝通过，非翻译质量指标。
`student-train-resumable VERSION --assets PATH --output NEW_DIR --reviewed-dataset VERSION --reviewed-teacher-license LICENSE --steps 100 --run-steps 20 --accumulation 4` 保存优化器步边界的完整状态；用完全相同的数据/训练配置及本地运行环境、不同新输出目录、`--resume PREVIOUS_DIR` 继续。完整状态 SafeTensors 含 canonical weights、AdamW FP32 moments/step、CPU RNG；manifest 含数据哈希、软件/线程配置、epoch/cursor/history，强校验与不可覆盖；按监督 token 数加权梯度累积。`--max-seconds` 为每段软时间限制（初始化、步骤、保存可超过），`--max-checkpoint-bytes` 为单检查点文件预算，默认 1 GiB；预检约 3×权重加元数据上限，不是总内存或累计磁盘预算。单次命令结束才保存；进程强杀可能丢失本段，旧 checkpoint 保留。精确续训只在相同 CPU/软件/硬件环境下测试，不保证跨机器或 CUDA。新增实际 CPU 连续 7 steps 与 2+2+3 steps 恢复的逐位比较 smoke，待 CI。CUDA、AMP、定期自动保存、资源实时监测及统一持久调度在 E6b；训练权利和语义质量仍需明确复核，未执行真实 Qwen/GPU。新格式不属于 Rust 部署包。

### E6b1 CUDA 与混合精度训练（待本机 GPU 验收）
E6a a3fedba 标准 CI 9/9 success，真实 7 steps vs 2+2+3，176/176 state tensors、history、optimizer/RNG 位一致。E6b1 `student-train-resumable` 新增 `--device cuda:0 --precision float32|float16|bfloat16 --cuda-budget-bytes N`；CUDA 必须显式选择，启动 worker 前设置 `CUBLAS_WORKSPACE_CONFIG=:4096:8`，拒绝不可用设备和不支持的原生 BF16，不自动 CPU fallback。AMP autocast，FP32 master weights / AdamW moments；FP16 GradScaler，unscale 后裁剪，非有限梯度失败而非计入成功 step。GPU checkpoint 增加 CUDA RNG/GradScaler/environment/peak allocation，CPU E6a 格式保持兼容。预算预检 4×权重与当前 free VRAM，优化器步边界读取 PyTorch peak allocated；不是硬显存限制，不含 reserved/其他进程，可先 OOM 或超过预算。真实 GPU 本地执行 `python scripts/cuda_smoke.py --precision float16 --cuda-budget-bytes 1073741824`（另测 float32、原生支持时 bfloat16；数字仅微型测试示例，完整模型需重新估算）。脚本真实 GPU 训练并比较连续/续训，未执行，不保证 CUDA 位一致或完整尺寸可运行。免费 CPU CI 保留原 176 张量对照并测试不可用 GPU 拒绝。周期自动保存、累计资源预算与持久 worker 在 E6b2。正式训练仍需数据/教师权利与质量复核。
