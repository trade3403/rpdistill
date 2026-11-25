# 技术架构

- GUI：计划 Electron + React + TypeScript，独立桌面发布。
- 训练：Python 3.11+、PyTorch、Transformers；CUDA 由实际硬件决定。按规模选择 Accelerate 或 DeepSpeed。
- 任务管理：Python 本地 worker，后续使用有版本的 JSON 消息协议；持久化实验配置、日志及检查点。
- 数据：JSONL/Parquet，SQLite 元数据，训练集与独立测试集隔离，记录语料来源和使用许可。
- 教师：统一适配器；Qwen 为候选而非已确定的最优模型。固定模型版本、生成参数、许可；只有可访问兼容输出时才启用 logits/特征蒸馏。
- 学生：以 D 线真实架构、词表、张量布局、模型包版本为准；不可把任意缩小的 Qwen 直接用于现有 Rust 推理。
- 导出：SafeTensors 中间格式，验证 RPTranslate 原生格式；Rust 互操作模块按需要实现。
- 安全：默认本地语料；远程教师调用需要明确授权；密钥与真实数据不进入公开 Git。禁止默认执行不受信任模型代码。
- CI：Windows/Linux/macOS × Python 3.11/3.12 CPU 测试；真实 GPU 训练另行在有权限的硬件上验收。

E1.1 仅实现标准库基础配置和 CLI；以上其余模块为计划。
