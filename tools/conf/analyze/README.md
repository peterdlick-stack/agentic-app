# 决策日志离线分析

输入为 `accounts/device`，只读全部 `decisions-*.json`。仅依赖 Python 标准库和 matplotlib，不启动 card-host、不调用模型、不访问网络。运行结束即停止，没有后台进程。

```powershell
python tools/conf/analyze/analyze.py F:\path\accounts\device --check-dstats --output F:\context-dj-work\research\confidence\analysis\2026-10-09\run-01
python tools/conf/analyze/analyze.py F:\path\accounts\device --include-sim --archive F:\snapshots\before-wrap --archive F:\snapshots\next --check-dstats --output F:\analysis\run-02
python -m unittest discover -s tools/conf/analyze -p test_analyze.py -v
```

没有指定 `--output` 时，输出目录为 `F:/context-dj-work/research/confidence/analysis/<Asia/Taipei 当前日期>/`。重跑应指定新的目录，程序拒绝覆盖既有 REPORT.md、metrics.json 或 reliability.png。

输出包含中文 `REPORT.md`、完整机器可读指标/差异 `metrics.json`、三箱可靠性图 `reliability.png`。图上为空箱写“无数据”；无可用中文字体时图中使用 `No data / n=0`，报告仍写“无数据”。缺 matplotlib 时先保存数字和报告，再报图形缺失并退出 2，不能当完整交付。

退出码：0 = 指标生成完成，且如请求核验则完整历史 PASS；2 = 输入/依赖错误；3 = 核验 FAIL 或 HISTORY_INCOMPLETE。默认展示先排除 `sim:true` 事件再重放，模拟撤销/改票不能改变真实记录；核验始终使用完整历史分别复算 `real` 和 `sim` 两组。

## 累计统计和环形快照

**2026-10-09 用户已批准：保留累计 dstats，用覆盖前的全量快照补齐历史后核验。** `--archive` 可以重复，接受快照目录或单个分片 JSON；目录只读取直接子文件 `decisions-*.json`。每条事件先按 id 排序，同 id、内容完全相同则去重；任何同 id 异文、重复 JSON 键、非法类型直接报错，不猜哪个版本正确。只可合并同一设备、同一日志世代的快照，不能把重置 seq 后的另一次实验混进来。

`--check-dstats` 检查 1 到 `dstats.seq-1` 连续存在，也检查日志是否已写入不早于 seq 的事件（可能汇总写盘滞后）。缺快照时状态为 **HISTORY_INCOMPLETE / 历史不完整**，即使所有残留事件恰好无计数贡献、字段差异为零，也不会 PASS。保留残留窗口指标供排查，不把它当累计结果。当前环形上限为 16×25 条，单片以 16384 字节为提前换片目标，长事件可能使保留窗口更小；单条本身超过目标时仍完整独立保存并警告。900 条事件必须用覆盖前快照补回丢失部分。

应在实际分片即将覆盖旧片前，将全部分片复制到新的离线快照目录。当前一圈最多 400 条；字节限制可能使覆盖提前，因此不能只按第 401 条作为保存时点。长测试可以在每次将覆盖旧片前保存该片，或按实际旋转进度定期保存全量分片且间隔小于一圈。应在应用停止写入并完成汇总落盘后复制设备目录，避免读取两次异步写盘之间的不一致。不要覆盖以前的快照。这里不修改 dstats 格式，也不自动从当前残片猜测丢失历史。

逐字段比较 `real/sim` 全部计数，包括缺字段、多字段和浮点和；浮点容差 `abs=1e-8, rel=1e-9`。`seq` 验证连续性；`v` 校验版本；`shard/shard_n` 校验类型和非负。合并后的历史不保留物理写盘调度信息，本脚本**没有独立复核物理片号/片内游标**；D/INT 的重启和环形写盘验收另做。

## 计数口径

- `dup:true` 的 act 只贡献 dup；跳过贡献 n、skip、展示档，标签和 Brier 不计；撤销将目标 act 的全部贡献减回，并给目标所属 real/sim 的 undo 加一。重复撤销只减一次且报异常；撤销目标不在历史中也报异常。act_undo 与其目标的 sim 不同、或 rate/click 与曝光的 sim 不同均为异常，累计核验不能 PASS；含模拟展示保留完整历史效果，默认展示只重放真实事件。全部快照合并后处理，因此跨片与重启边界不会改变离线结果。
- top-1、规则、多数类均用冻结预测与 y 独立算命中；dstats 复算按事件内 hit/rhit/mhit、br/bp 累加，并检查它们与向量的明显矛盾。当前 B 先将 q/pr 冻结为三位小数，再用这两组完整七维向量计算 br/bp；图表分别列全向量重算和日志标量均值。分析器兼容历史数据及负例测试中的三项截短向量，但不会补零、重新归一化或冒充完整 Brier；当前应用始终保存七维。
- 三档覆盖率分母是撤销/去重后全部 act，错误率分母是该档有标签的 act；跳过保留在覆盖分母中，未确认单列。空分母为 N/A。eh 独立于展示高档开关，不开启任何产品功能。
- 首轮返回文本由 `e1` 非空、`res=ai/ai_retry` 或 `att=2` 识别；首轮不合格由 `e1` 非空识别。首轮网络失败为 `res=local_net && att=1`。**总调度已约定：第二次网络失败使用 `local_fail`，net 保留错误摘要；`local_net` 只给首次网络失败。** 输入校验拒绝 att=2/local_net，避免 C 的回退计数与首轮网络计数冲突。研究比例分母排除 `local_nomodel/local_insuff`；调试页 net/n 另列，避免混用。重试成功 `ai_retry/att=2`。最终回退分子为 fail/net/timeout/insuff，分母为全部已结束 rec；nomodel 单列。仅有结束事件，pending=UNKNOWN。
- `err` 按 e1/e2 中每次出现累计；ms1/ms2 排除根本没发模型请求的决定，ms2 仅 att=2。mact 不进入任何统计。
- 改票按 `(rec id, 歌曲键)` 跨片保留末票，先减旧票原来的组/档，再加新票。曲库 `fb=""` 不计。相同票重复点击不重复加票；“去听”计点击事件次数。未评=曝光−末票♥−末票✕，正评价率分母♥+✕；残缺历史可能出现负未评，必须补齐，不能夹成 0。

D 使用有界 `dstate.json` 保存最近一条可撤销活动、最新歌单及其最多 6 首歌曲的末票，支持当前流程跨片和重启恢复；这不保证任意旧歌单重新回放时仍可改票。分析器按完整历史重放，并如实报告与累计汇总的差异，不能通过清空离线缓存迎合错误汇总。D/INT 另有跨片/重启改票及撤销缓存恢复验收。

## 验证范围

单测包含报告 Q3 的全部七行 Wilson 数值、28/30 与 29/30 的高档检查、空数据、箱边界、跳过/重复/撤销/模拟、全向量 Brier、截短向量、四个选歌分母、重试网络失败、延迟、跨片改票、相同票重复点击、库页反馈、900 条覆盖缺快照失败与补全通过、同 id 冲突和损坏数据拒绝。

T 的 `labels_seed.json` 只有旧标签，没有 q/pr。`synthetic_demo.py` 可用这些标签生成**明确标为合成**的假事件，预测是人为设定，不是重放真实应用，也不能证明推荐效果。运行示例与证据见 O/REPORT.md；真实日志和彩排仍需 INT 验收。
