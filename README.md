# RPDistill Studio

独立科研翻译模型训练与知识蒸馏工作台（E 线路）。

RPDistill 负责教师模型、语料、训练、评测和模型导出。RPTranslate 保持独立 Rust 推理，不依赖训练环境。

## 当前状态
E1.1：Python 基础工程和 CPU 自动化测试。尚未接入真实教师模型或 GPU 训练，GUI 为后续阶段。

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
