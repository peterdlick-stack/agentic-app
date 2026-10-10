# 合成测试夹具

**labels_seed.json 文件头说明：全部 60 条记录均为合成数据，sim 全为 true；不是用户行为，不是模型校准证据。** JSON 本身不插入注释，保持顶层数组以兼容现有 labels.json 加载器。

文件均位于 T 的授权目录内，基线为 `9919c0f`。

- `fake_model.json`：假回调总表，每项含 name、delay_s、is_ok、error、data.output。
- `cases.json`：逐案前置上下文、期望解析结果、曲库追加项、可选索引、回调切片、逐轮错误及最终结果。
- `catalog.json`：从基线 SEED 提取的 46 首歌；索引从 0 起。只用于核对，不能直接导入 library.json。
- `CASES.md`：逐案执行方法、重试配对、界面提示和固定曲库索引。
- `injection.md`：注入场景和 UI/链接检查。
- `labels_seed.json`：现有标签格式的 60 条模拟确认记录，覆盖 2 类日期、7 时段、5 移动状态、7 活动。
- `build_fixtures.py` / `verify_fixtures.py`：标准库生成器、独立契约核对与逐案导出器，无网络或宿主调用。

运行与验证：

```powershell
python tools/conf/fixtures/build_fixtures.py
python tools/conf/fixtures/verify_fixtures.py
python tools/conf/fixtures/verify_fixtures.py --export-case hard_vocal
```

所有输出只在 fixtures 内。生成器写入本目录的受控生成文件；逐案导出会拒绝覆盖被修改的同名导出文件。脚本同步运行，结束即停止，没有后台服务。

Python 检查通过只说明夹具内部一致；A/INT 的 Splash 守卫、真实计时、界面截图与迟到回调丢弃仍需运行验收。没有真实模型调用。

## B 的标签导入与三档设置

把 labels_seed.json 复制为隔离测试数据目录中的 labels.json，启动测试副本。**基线 load_label 会丢弃 sim 字段**，而新事件的 sim 来源于运行中的 sim.kind；测试前必须开启模拟状态。禁止把这些记录导入真实用户配置，禁止仅凭源 JSON 的 sim:true 推断事件仍为模拟。

固定时间、地点和移动状态后再刷新候选排序，清除手动活动与 session_act 的覆盖。以下数值来自任务书保留的 ALPHA=3 公式；它们是测试期望值，须由 B 在应用内验证。

| 场景 | 上下文 | 匹配标签 | 支持度期望 | 展示 |
|---|---|---|---|---|
| 低档 | 关闭时间、天气，motion=unknown，place=null | 任意 | rule 来源 none 优先触发 | low，不高亮 |
| 中档 | 工作日 15:00，work 地点，still，规则 work | 20 条，其中 work=12、study=5、relax=3 | q1=0.599068，q2=0.242547，gap=0.356522 | mid，三项同等标记 |
| 潜在高档 | 工作日 10:00，school 地点，still，规则 study | 20 条全 study | q1=0.946894，q2=0.025155，gap=0.921739 | eh=true；默认仍 mid |
| 高档代码路径 | 同上，只在测试副本临时 TIER_HIGH_ON=true | 同上 | 同上 | high，只标第一项；测完恢复 false |

20 条周末补充记录覆盖其余时段、活动和移动值，不干扰上面两个工作日完整桶。at 使用 +08:00 的固定合成时间，按时间升序排列，未存坐标或用户原话。

## O 的使用边界

labels_seed.json 具有 chosen/top 等旧标签字段，没有确认前的 q/pr/rule/maj，也没有事件 id。它不是 decisions 分片，不能补造 q/pr 后冒充真实事件。O 可从中选择确定的标签与桶，另外生成明确 sim:true 的假事件测试分析程序。真实分析仍默认排除模拟事件。

## 口径与未冻结点

- hard_lang 使用 parse_intent 的 `en`，hard 列表为 `lang:en`；界面可显示中文说明。任务书的“国语”只作为人类可读示例，不能拿它与歌曲 lg 比较。
- E_NOT_ELIG 与违反的硬条件错误同时出现。E_CAT 单独优先判定且不重试。
- malformed output 顶层缺字段或不是对象统一用 E_JSON；索引非法后不访问歌曲字段。
- 每项 ev 数量均在 2–4 范围；任务书没有冻结数量本身错误的专用码，本夹具不自行规定这个映射。
- local_nomodel/local_insuff 的模型调用数为 0，事件 att 因冻结格式只允许 1|2，期望为 1；不要用 att 统计是否发起过模型调用。
- 首次契约失败、第二次网络失败用 att=2、res=local_fail，保留 net 摘要和 e1，e2 为空；仅首次网络失败才归 local_net，避免把重试失败计入“首轮网络失败”。
