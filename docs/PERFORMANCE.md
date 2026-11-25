# E10a Rust CPU 诊断性能基准

## 使用
构建与 E9b1 相同固定 D revision 的可信本地 Rust bridge（参见 model-export-live.yml），执行 `student-rust-profile --root PACKAGE --expected-package-id HASH --executable TRUSTED_BRIDGE --timeout-seconds 300 --output PROFILE.json`。先完成独立包验证；Rust 再核对固定资产、权重 hash、metadata、shape 并加载。报告记录 executable SHA256（非签名或可信认证），调用者必须独立信任本地构建。假定文件稳定无并发修改。

## 测量范围
- 加载计时：资产/config、weight SHA256、header/shapes、embeddings、encoder weights、decoder weights。单进程一次，不主动清除 OS 文件缓存；并非真正冷启动。
- 合成固定 token 序列长度 16/64，最后 EOS，全部 source mask true，最大新 token 8/16。greedy beam 1，不强制 EOS，实际 EOS 可以提前停止。每组预热 1 次（不计入），测量 3 次，交替 full/cached 的先后次序；两路径和所有重复生成 IDs 一致方可报告。
- 单独计时 encoder forward、MarianEncoded prepare、generate、generate_cached；后两项不含 encoder/prepare。输出每次 ns、median、实际生成 tokens（含 EOS，不含 start）、token/s、full median/cache median 比值。比值小于 1 也可通过 CI；不设性能门槛，不能把比值当作端到端加速。
- Linux /proc/self/status VmHWM（Rust 进程生命周期 RSS 峰值，非模型独占内存），其他平台 unavailable；Python 校验时间和 Rust 子进程耗时单独报告，后者包含 warmup、所有测量与加载。
- 固定协议 2 cases × 3 runs，最大解析 16 KiB，子进程 timeout。可信程序才可执行，临时文件输出大小事后检查，不是沙箱。
- report_id 为 canonical JSON hash，不是签名；不声明原生低精度、生产 loader、质量认证或发布许可。

## E10b 决策
读取实际完整尺寸 CI profile 结果后，先识别加载与解码阶段瓶颈，选择一个可独立验证的优化；保留精度和生成一致性测试，对照同工作负载，测量而非承诺固定加速。真实 GPU、长文/真实科研文本、正式 D 生产加载及跨平台性能仍待后续。原 D 仓库不修改。
