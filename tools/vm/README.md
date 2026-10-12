# 裸 VM 数值验收（不启动 card-host）

把 `bundle/main.splash` 里真实的 `[PREF]` / `[EXPLORE]` 函数和曲库抽出来，放进 OctoSense 所用的同版脚本引擎
（OctoSense-org/makepad @ `1f3b1de`，`platform/script`）里直接运行，和参考实现的期望值逐位比较。

## 一次性准备

```bash
git clone --filter=blob:none --no-checkout https://github.com/OctoSense-org/makepad.git
cd makepad && git checkout 1f3b1de -- platform/script libs
mv Cargo.toml Cargo.toml.ws                     # 只编 script 测试包，不要整个 workspace
printf '\n[workspace]\n' >> platform/script/test/Cargo.toml
cp <repo>/tools/vm/run_file.rs platform/script/test/src/bin/
cd platform/script/test && cargo build --release --bin run_file
```

## 跑

```bash
RUN=<makepad>/platform/script/test/target/release/run_file
# PREF：46 首特征 + fixture_A / fixture_B 学习结果
python3 tools/vm/mk_harness.py  bundle/main.splash tools/pref/PREF-EXPECTED.json     /tmp/h.splash && $RUN /tmp/h.splash > /tmp/o.txt
python3 tools/vm/cmp_harness.py tools/pref/PREF-EXPECTED.json /tmp/o.txt
# EXPLORE：V2 均匀数/θ/封顶、X2 演示选歌、V4 票数改变抽样、X4 不出探索位
python3 tools/vm/mk_xharness.py bundle/main.splash tools/explore/EXPLORE-EXPECTED.json /tmp/hx.splash && $RUN /tmp/hx.splash > /tmp/ox.txt
python3 tools/vm/cmp_x.py tools/explore/EXPLORE-EXPECTED.json /tmp/ox.txt
```

## 实测到的运行时坑（2026-10-12）

- 内建 `floor`、`clamp`、`min`、`max` 走 f32：`clamp(0.10000000000100001)` → `0.10000000149011612`，
  `floor(878922.99)` → `878923`。需要 f64 的地方用 `pref_exp64` / `pref_sqrt64` / `x_floor64` 和 if 分支。
- 对脚本构造的对象，`for k v in o` 迭代出的 `k` 是 id，`k == "study"` 恒假（要 `"" + k`），所以 `pick()` 恒返回默认值；
  读动态键用 `o[key]`。`pick` 只对 `parse_json` 出来的对象有效。
- 空格分隔的数组字面量里，`[a] [b]` 会被当成下标、`[k1 X - k1]` 有歧义：元素里有运算就先算成变量。
- 界面区（`ButtonFlat` 之后）需要真实组件类型，裸 VM 只能检查到那里为止，界面改动要上真机看。
