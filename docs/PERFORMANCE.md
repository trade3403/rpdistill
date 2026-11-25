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

## 首次真实 Runner 结果与回归修复

E10a 28f728459dbe502b13bd717bb748c8088c76f0e2：Rust 专项 [45625397449](https://github.com/trade3403/rpdistill/actions/runs/45625397449) 1/1 success，job 139244112848；标准 [45625397448](https://github.com/trade3403/rpdistill/actions/runs/45625397448) 4/10 success，六个跨平台 unittest job 同一 test_early_eos 失败（原 fixture 字符串替换同时命中较长序列前缀，导致 EOS 后仍有 token；解析器正确拒绝）。修复为按 case 构造提前 EOS，测试仅短/仅长/两组，新增显式 EOS 后 token 拒绝测试；不修改 runtime parser 或门槛。专项 workflow 增加 test_rust_profile.py 路径以重新验证 exact head。待新标准及专项全部通过才进入 E10b。历史实测 Linux x86_64 4 logical CPUs，16→8 tokens encoder 249720496ns/full 2595300952ns/cache 2293468055ns，64→16 encoder 381493704ns/full 5614579083ns/cache 4561371208ns；cache ratios 1.13160545/1.23089721，full token/s 3.082494/2.849724，cache token/s 3.488167/3.507717；RSS 323821568 bytes，weight hash 1122456331ns。生成 IDs 一致。合成诊断非质量或生产 SLA；优先剖析 decoder 路径，仍需细分实际瓶颈。原 D 只读。
