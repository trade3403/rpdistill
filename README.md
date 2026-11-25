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

## 内置在线下载（规划中的必选功能）
教师模型及合法公开训练数据集支持软件内搜索、一键下载、断点续传、完整性校验与自动入库；正常联网使用无需手动下载文件。E2/E3 实现核心，E11 集成 GUI；尚未实现。

## 科研论文在线采集（必选，待开发）
直接在软件内按关键词、学科、日期搜索论文，批量下载许可允许的全文并自动解析、分段入库，由教师模型生成高质量双语训练语料。不需要手动逐篇下载 PDF。E3 实现核心、E11 集成 GUI。

## 全自动蒸馏（核心目标，待实现）
一次设置，自动搜索论文、下载合法全文、教师翻译、清洗生成训练集、触发学生蒸馏、评测量化及导出。[自动化规范](docs/AUTOMATION.md)。支持单次和预先授权的持续增量运行。
