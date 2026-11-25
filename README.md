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

### E6b2 持久训练队列与周期检查点
E6b1 a91dd39 标准 CI 9/9 与真实 tokenizer 1/1 成功；真实 CUDA 仍待本机验收。`training-enqueue VERSION --assets PATH --root CHECKPOINT_ROOT --reviewed-dataset VERSION --reviewed-teacher-license LICENSE --steps 100 --segment-steps 20 --segment-seconds 300 --total-seconds 1800 --total-checkpoint-bytes 6442450944` 创建训练任务（示例预算，按机器和实际需求配置）。`training-run` 抢占一个排队任务并自动连续执行分段训练、完整 checkpoint、登记进度，直至完成/暂停/取消/预算耗尽/失败；另一个终端 `training-show ID`、`training-events ID`、`training-pause ID`、`training-resume ID`、`training-cancel ID`。进程被强制终止后，确认原 worker 已退出才 `training-recover ID --worker-stopped`，再 resume/run。每段重新检查已审核数据与教师许可，按 optimizer 边界响应控制，保存后原子登记 SQLite 游标。每次尝试预先扣除段时间与单 checkpoint 容量，失败/崩溃不退还，保留所有已有与孤立文件，不自动回收；这是累计保守预留，不是实际执行时长/磁盘使用硬限制。强杀可能损失当前段，未登记 checkpoint 不自动接纳。每数据库仅一个队列 worker，不是系统全局 GPU 锁；单独 CLI 与其他进程不应并行抢占设备。新增真实 CPU 微型队列暂停、重开数据库、自动恢复及连续训练逐位对照 smoke，待 CI。未接入自动语料流水线的审核批准与训练触发，尚无常驻服务、GUI 或真实 GPU 质量验收。

### E7a 独立参考译文与自动质量评测
E6b2 17efb1c 标准 CI 9/9 success；实际 CPU 队列 5 steps、3 checkpoint、暂停重启恢复后 176 状态张量一致。E7a `pip install -e '.[evaluation]'`；`benchmark-freeze TRAIN_DATASET_VERSION --input human.jsonl --review-note '已核查参考译文和使用权利' --output benchmark.json` 验证完整训练快照、排除训练 split 的规范化精确文本与已申报 DOI/PMCID 重合，冻结独立人工参考。每行 JSONL 字段 id、paper_id、source、reference、rights_note，选填 pmcid/doi、terms（source/targets 数组）、protected（源与参考均出现的公式/单位等字面串）。`benchmark-score --benchmark benchmark.json --hypotheses outputs.jsonl --label LABEL --output report.json`；hypotheses 每行 id/hypothesis，完全匹配案例 ID；可用 --gate JSON 覆盖默认阈值。SacreBLEU zh corpus BLEU、chrF (beta2)、数字/引用字面计数、术语目标变体、保护字面串、空译/原文复写/长度/非中文启发式检查，冻结报告、版本与哈希。默认数量及指标门槛是初始研发参数，不是行业认证；自动 gate pass 不等于 release_ready，外部译文来源未经模型认证，人工参考与权利由操作者声明，精确去重不是语义去重。E7b 接真实学生检查点推理、固定基线对照、独立人工评审与速度/内存；COMET 等需另行模型/许可/预算核查。新 CI 待验收，synthetic fixtures 不代表真实科研翻译质量。

### E7b1 本地学生检查点评测
E7a 8c0a13e 标准 CI 10/10、Hub 2/2、tokenizer 1/1 success；真实 SacreBLEU 合成参考自对照 BLEU≈100/chrF=100，错误样本被拒绝，不是模型质量。`pip install -e '.[student,evaluation]'` 后，`benchmark-student --benchmark BENCHMARK.json --checkpoint CHECKPOINT_DIR --assets ASSET_DIR --output REPORT.json`：读取 E5 权重或 E6 已完成训练状态，严格哈希/形状/绑定训练 dataset 验证（完整训练状态只加载模型张量）；用固定分词器从独立 source 真实 CPU FP32 greedy 生成，检测 EOS/未知词/语言 token/长度限制，未完成生成不通过自动 gate；输出逐条译文及指标、延迟、生成 token/s、canonical weight bytes。可选 `--baseline OUTPUTS.jsonl` 对同一评测集的外部基线评分并比较差值，外部来源未经认证。当前参考实现无 KV cache、无 GPU 性能测量，权重 bytes 非进程内存，报告 release_ready=false、model_output_authenticated=false、model_output_generated_locally=true。新增真实 tiny CPU 训练→两个检查点格式→生成/评分 smoke（合成分词与目标，非正式质量）。E7b2 后续近重复、人工盲测/评审报告、正式评测覆盖与质量门槛校准、真实基线及实测内存/性能，COMET 视适用性与许可。新 CI 待验收。

### E7b2 近重复审计与人工盲测流程
E7b1 bbc685f 标准 CI 10/10 success：两个 checkpoint 格式真实微型 CPU 生成、EOS、合成 chrF 100/100，错误 dataset、损坏及覆盖不足拒绝；非真实翻译质量。E7b2 `benchmark-leakage-audit --benchmark BENCHMARK.json --output AUDIT.json` 检查训练与评测及评测内部 token equality、word trigram Jaccard>=0.8/containment>=0.9（至少 6 个 distinct trigrams），倒排索引与资源限额，超限拒绝通过；非语义/跨语言近重复证明。`benchmark-blind --benchmark BENCHMARK.json --student-report STUDENT.json --baseline-report BASELINE.json --packet PACKET.json --key PRIVATE.json` 验证报告与实际重算指标，生成随机匿名 A/B packet 与独立私有映射；仅把 packet 给评审者，映射须自行安全保管（不是加密访问控制）。`benchmark-review` 使用相同 benchmark/student-report/baseline-report/packet/key，加 `--reviews REVIEWS.json --output REVIEW.json`；reviews 为 JSON 数组，每个 reviewer 唯一标识、packet_id、independent_review_asserted:true、scores 列表（id、A/B 各 adequacy/fluency 0–4 整数、critical_error bool、preference A/B/tie），至少两名声明独立评审、完整覆盖、按实际映射统计；默认自动质量门槛重新计算，近重复与未完成生成阻断候选通过。门槛是研发假设；身份/基线来源未认证，报告始终 release_ready=false。CPU Linux/macOS 报告增加进程生命周期峰值 RSS，非独立模型内存；Windows 暂无该指标。真实 GPU、真正人工盲评、正式基线与校准仍待本机，COMET 可选暂缓（尚未确定许可/预算与适用性）。新增 3 unit tests 与真实微型 CPU + SacreBLEU + 合成评审回归，待 CI。下一阶段 E8 权重压缩与质量回归，不将候选通过冒充发布授权。

### E8a 权重压缩候选
E7b2 5122a06 标准 CI 10/10 success，合成盲评、词面审计与覆盖不足拦截通过。`student-compression-plan --mode fp32|fp16|int8` 查看固定模型有效载荷估算；`student-compress VERSION --checkpoint CHECKPOINT_DIR --mode int8 --output NEW_DIR --max-bytes 134217728` 生成独立 SafeTensors 压缩候选（预算为示例）。支持 E5 权重及 E6 complete 训练状态，绑定原 checkpoint 与 dataset，FP16 矩阵存储或逐行对称 INT8 + FP32 scales，偏置、归一化与位置表保留 FP32，严格检查有限值、布局、哈希、字节预算、禁止覆盖；记录还原误差和实际文件大小。参考加载将权重还原 FP32，不是 INT8 原生推理或显存/速度提升。只读核对 D 线 5389f3fc33ab45b93f6cab7c7e5bfd17fe43e8e9，Rust loader 仍限官方 FP32 包；所有候选 rust_deployable=false、release_ready=false。真实微型 CPU 压缩/还原/生成一致性 smoke 和 3 单元测试待 CI；固定完整尺寸目前为 payload 计算，实际完整模型压缩与独立评测待本机。E8b 接同一真实冻结 benchmark 的逐版本质量回归与候选选择；E9 独立自训练 RPModel 格式，不伪造官方身份。

### E8b 压缩质量回归与候选选择
E8a 0046e0e CI 10/10 success：完整尺寸 payload FP32 312033188、FP16 157391780、INT8 80601416 bytes；真实微型文件 29752/19216/17016 bytes，三种合成译文不变。`benchmark-compression --benchmark BENCHMARK.json --checkpoint ORIGINAL --assets ASSETS --candidate FP32_DIR --candidate FP16_DIR --candidate INT8_DIR --output REVIEW.json` 使用同一原检查点，重算每个压缩候选的规范转换与逐张量还原，实际 CPU FP32 greedy 生成，统一默认绝对质量 gate 与相对 BLEU/chrF/变化率及逐条数字/引用/术语/保护串/疑似错误回归，词面泄漏审计。仅在源和候选均过绝对质量门槛、无新增规则错误且回归通过时，从合格者按实际权重+manifest 文件大小选择最小候选；否则 selected=null。可指定相对 gate JSON，绝对 gate 不可由 CLI 降低。最多三个不同模式、完整评测不截取，case 与软时间预算；单次计算可超时，报告未标发布，真实人评仍必需。新增 4 项单元测试与实际同源微型三格式对照/错误绑定/篡改转换/覆盖不足拒选 smoke，待 CI。下一阶段 E9 独立自训练候选包、许可/来源、RPTranslate Rust 兼容验收；原官方格式不伪造。当前存储压缩而非低精度原生计算。

### E9a 独立自训练模型候选包
E8b de36eb9 标准 CI 10/10 success，真实同源三候选评测、错误 checkpoint/篡改转换拒绝、覆盖不足不选择。E9a `student-export-plan`、`student-export-candidate VERSION --checkpoint DIR --assets DIR --output NEW_DIR --license-label LABEL --rights-note NOTE --max-bytes 340000000 --acknowledge-candidate-only`、`student-verify-package --root DIR --expected-package-id HASH`。固定 F32 256 canonical tensors 与 5 个配置/tokenizer 文件，独立 schema、source checkpoint/dataset/provenance hash、许可声明、文件哈希、外部指定 package ID、不覆盖与预算。仅诊断候选，不自动认定权利、质量或发布授权；D 线官方 loader 仍拒绝，E9b 协调独立加载入口与真实 Rust 模型推理/质量 gate。新增真实全尺寸单步合成 CPU 训练与 Rust 312033188-byte 权重流对照 workflow，未下载官方模型权重，待 CI。详见 [候选格式规范](docs/MODEL_CANDIDATE_FORMAT.md)。

### E9b1 独立候选包 Rust 神经网络对照
E9a 1ce24ce 标准 CI 10/10 与 full-export Rust 1/1 success：完整尺寸真实单步合成训练、256 tensors、312033188 bytes 全权重 SHA256 位一致、官方 loader/错误 pin/损坏拒绝。E9b1 固定 D 最新 2fa70c175de7a25415489ecb12ffe3d09485f777 的临时 checkout 编译 scripts/rpdistill_candidate_infer.rs 到 rpinfer examples；Python `student-rust-parity --root DIR --expected-package-id HASH --executable TRUSTED_LOCAL_BRIDGE --output REPORT.json` 先校验全包与外部 pin，Rust 再检查独立权重 hash/metadata/固定资产/形状，调用真实六层 Encoder/Decoder、KV cache 与 greedy；对照两个固定 token/mask 测例的 encoder memory、完整/缓存 logits（atol=rtol=3e-4）、三步以内 greedy IDs，禁用强制 EOS 以匹配 Python 参考策略。专项 CI 追加同源 full-size 训练→导出→真实 Rust 计算、错误权重和 checkpoint pin 拒绝；待验收。只适用于可信本地构建的诊断程序和稳定文件，不是正式 RPTranslate API、性能基准、质量授权或完整文本推理；不修改原 D 仓库，不签名，不发布。E9b2 将质量审批与最终导出衔接并准备生产加载接口/原 D 集成变更协调。

### E9b2 自主模型生产集成前审查（仍非正式发布）
E9b1 8aa263a 标准 CI 10/10 与 Rust 专项 1/1 success；完整尺寸实际 CPU 合成训练/导出 256 F32 tensors、312033188 raw bytes；2 个 Rust encoder/full/cached decoder logits 与 greedy cases 通过，最大 absolute error 4.291534423828125e-6。E9b2 `student-review-integration --root CANDIDATE --checkpoint CHECKPOINT --benchmark BENCHMARK --student-report STUDENT --baseline-report BASELINE --packet PACKET --key KEY --reviews REVIEWS_JSON_ARRAY --expected-package-id PIN --reviewed-dataset VERSION --reviewed-teacher-license LICENSE --reviewed-model-license LICENSE --rights-note NOTE --reviewer OPERATOR --executable TRUSTED_RUST_BRIDGE --output NEW_RECEIPT --acknowledge-local-candidate-only`；训练选择与训练时一致（必要时 --training-limit）。核验独立 pin/256 tensors/source provenance、当前训练语料权利与完整性/注册教师许可、固定默认自动质量及两位声明独立人工盲评门槛、实际逐段重生成与已审查译文一致、重新运行 Rust parity，保存不可覆盖哈希审批凭据。仅本地集成候选，权利和评审者为声明而非法律/身份认证、基线身份未验证、非数字签名、非生产 loader、禁止自动发布/替换。实际人工评审/GPU/正式质量待本机；CI 单测 mock 审批逻辑与真实完整张量源绑定/错误绑定拒绝，尚未实测完整审批成功。原 D 仓库只读；生产加载器须另行协调独立 profile，官方包继续严格核验，不冒用身份。

E9b2 交接校验：`student-check-handoff --root PACKAGE --receipt RECEIPT.json --expected-package-id HASH --expected-receipt-id HASH` 使用两项独立可信 pin，校验凭证自身及嵌套质量、权利、生成重放和 Rust 诊断绑定。生成凭证前增加最终候选及当前本地权利复核，完整续训 checkpoint 另核对实际 token 数据哈希。交接检查不重新审核当前权利，不授权发布，不是生产加载器。

### E10a Rust 性能剖析基准
E9b2 a7582b5 标准 CI 10/10 + Rust 专项 1/1 success，真实生成重放及拒绝诊断报告冒充审批凭证通过。`student-rust-profile --root PACKAGE --expected-package-id HASH --executable TRUSTED_BRIDGE --timeout-seconds 300 --output PROFILE.json` 使用更新后可信 Rust bridge 的 `--profile` 模式，16/64 源 tokens、8/16 最大生成 tokens，每组预热1次、测量3次，普通与缓存解码交替顺序，逐次输出一致方可报告；计时六项加载阶段、Encoder、Decoder prepare、full/cache generation、median/实际 token/s/cache ratio、Linux Rust process peak RSS。保留原 `student-rust-parity` 协议。报告绑定包/权重/可执行文件哈希与机器基础信息；不控制 OS 文件缓存，非冷启动 SLA、实际翻译或生产性能；真实完整尺寸 CI 待验收，E10b 按实测选择优化点。详见 [性能基准说明](docs/PERFORMANCE.md)。

E10a 首次完整尺寸 Rust 专项成功：缓存解码比普通解码 1.13/1.23 倍（合成短序列），RSS 323821568 bytes。标准 CI 六环境因提前 EOS 测试 fixture 前缀替换错误失败；已修正 fixture 并新增非法 EOS 后 token 拒绝回归，runtime 校验不变。待新标准及专项通过后进入 E10b。

### E10b 词表投影性能实验
E10a 修复后标准及专项 11/11 success。E10b 在临时固定 D checkout 中尝试最多四线程 FP32 词表行并行，保留每行累加顺序和共享权重，不修改原 D 仓库。`student-rust-compare-projection --root PACKAGE --expected-package-id HASH --baseline-executable TRUSTED_BASELINE --experiment-executable TRUSTED_EXPERIMENT --output REPORT.json`：相同包双构建完整诊断字节一致后，同机实测两组吞吐、延迟、RSS；不要求固定加速比。CI 新增真实对照与 D library 回归，尚未验收；实验不是生产部署或正式翻译质量。详见 [性能基准](docs/PERFORMANCE.md)。

### E11a 桌面工作台
E10b 11/11 CI success，完整尺寸词表投影实验同机合成生成加速 4.4–7.1%，3134424 诊断字节一致，Rust 52/52 tests。桌面首次接入 Electron + React + TypeScript，在可信本机 Python 环境先 `python -m pip install -e .`，再 `cd desktop && npm install && npm run build && npm start`。可用 RPDISTILL_PYTHON（可信 executable）、RPDISTILL_DB（本地 SQLite 路径）环境变量。只读快照读取真实记录、自动刷新、硬件探测，未接入训练/下载控制或实时 loss；无假进度。Desktop CI 仅 Windows 构建与真实窗口 IPC smoke，待最新提交 CI 验收。Linux/macOS GUI 取消，后端保留。直接依赖固定，传递 lock/正式安装包尚未完成。见 [桌面工程说明](docs/DESKTOP.md)。

用户明确取消 Linux GUI：自本次提交起，E11/E12 桌面端只支持 Windows/macOS，Linux GUI 构建、启动、打包及发行不再作为要求；Linux Python/Rust CLI、后端及专项计算 CI 保留，不取消 Linux 训练能力。此前修复 b59ad53 的三平台 Desktop CI 45632934256 已成功，历史结果保留。新的 Desktop CI 矩阵 Windows/macOS 两项，分别保留真实 Electron 窗口/持久队列 IPC smoke（使用 scripts/studio_desktop_smoke.py，独立临时 DB、无 shell、无禁用沙箱），取消 Linux 专属 xvfb/SUID 配置。两平台真实启动尚待新 CI 验收，不能用历史 Linux 成功代替。未改变应用安全设置或后端 CI。后续安装包仅 Windows/macOS，真实 GPU 按硬件和后端可用性验收。

## 最新范围调整：仅 Windows GUI

用户明确取消 macOS GUI（Linux GUI 此前已取消）。自本次提交起，E11/E12 桌面 GUI、原生启动 smoke、安装包和发行仅支持 Windows；macOS/Linux Python/Rust CLI、后端与计算 CI 维持原范围，不取消训练能力。历史提交 98dbde0 标准 CI [45633656271](https://github.com/trade3403/rpdistill/actions/runs/45633656271) 10/10 success，Desktop [45633656134](https://github.com/trade3403/rpdistill/actions/runs/45633656134) 首次 Windows 原生窗口/IPC success、macOS cancelled，曾请求单项重跑；macOS 自本次授权起不再是验收门槛，不将其记录为通过。保留 Windows 真实 Electron/持久队列 IPC smoke、sandbox/contextIsolation 与原后端 CI；新提交需核验标准 CI 及 Windows Desktop CI，通过后继续 E11b 模型搜索、许可和预算确认、下载队列操作。Europe PMC 继续暂缓，D 线保持只读，真实 GPU/教师质量/人工评审及正式安装包仍待验收。本节覆盖此前 Windows/macOS 双平台 GUI 计划，旧记录保留为历史。
