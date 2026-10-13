# 评审速览：情境 DJ（context-dj）0.4.0

> 给复赛评审的一页索引：初赛点评每一条改了什么、在哪能看到。代码链接都固定在 `v0.4.0`（提交 `8805240`）；`v0.4.0` 之后的提交只改文档和录屏，`bundle/` 没有变。
> 初赛：#101，78/100，评审版本 0.3.4（`d56da0b`）。

## 1. 初赛 4 条建议 → 0.4.0

| # | 初赛建议 | 0.4.0 的处理 | 代码 | 实机证据 |
|---|---|---|---|---|
| 1 | 声明了 `location`，但不调用宿主定位服务 | 改为经宿主 location 服务取位：打开时先用 `runtime.describe` 查询 `location.sample` / `location.get`，宿主支持才申请权限、取位；**不再读 `sys.gps`**。宿主不提供定位的平台（Windows、Linux 桌面）如实显示“此平台的 OctoSense 不提供定位”，该项不参与推荐 | [`hostloc_init`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L1624) · [`read_fix`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L1699) | 讲解录屏 0:00 起、完整录屏 0:56 起；Windows rc.5 上 `location.get` 返回 `unsupported_platform`，与宿主文档一致。Android/macOS 路径按文档实现，**未在真机验证** |
| 2 | AI 选歌质量补一段真实宿主录屏 | 已补：Windows 原生 OctoSense rc.5，全新数据目录，从本地商店安装与 Release 相同的应用包（bundle BLAKE3 `30774f57…`），真实 MiniMax 选歌，没有剪辑，等待段加速并在画面中标明 | — | [讲解录屏 `demo-0.4.0-narrated.mp4`](docs/media/demo-0.4.0-narrated.mp4)（2:45，带配音）；[完整录屏 `demo-0.4.0-win.mp4`](docs/media/demo-0.4.0-win.mp4)（5:02，含商店安装和助手授权） |
| 3 | 在真机上验证一次 `ask_user_question` 的宿主放行 | **宿主放行已验证**：授权面板列出 “Ask you questions”，宿主内核日志显示 `tools=1`，与 `AGENT.md` 只声明这一个工具一致。**追问本身还没在真机上弹出**：宿主内核调用模型约 10 秒就超时（内核常量 `DEFAULT_LLM_CONNECT_TIMEOUT_SECS = 10`），同一时段应用自己的选歌调用正常。详见 README “验证情况” | [`bundle/AGENT.md`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/AGENT.md) | 完整录屏 3:58 起 |
| 4 | 改用 GitHub 发布流程并提高版本号 | 已改用 `tools/octo publish-github` 生成的工作流，版本 0.3.4 → 0.4.0，Release 由 GitHub Actions 证明发布者身份（`actions/attest`，运行 [38262324723](https://github.com/peterdlick-stack/agentic-app/actions/runs/38262324723)）。这是 App Hub 现行文档里唯一接受的发布者身份方式，不需要、也不再使用发布者密钥 | [`.github/workflows/publish-app.yml`](.github/workflows/publish-app.yml) | [Release v0.4.0](https://github.com/peterdlick-stack/agentic-app/releases/tag/v0.4.0) |

## 2. 模型输出怎么约束、失败了怎么办

初赛之后最大的改动：模型只是选歌流程里的一步，输出由代码校验，不合格就重试或退回本地规则。

| 做法 | 实现 | 代码 |
|---|---|---|
| 封闭输出格式 | JSON schema `additionalProperties: false`；只能从本轮候选的编号里选歌，证据引用只能取枚举值；多出任何字段都判 `E_JSON` | [`ask_model`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L3458) |
| 逐项校验 | 15 类错误码：格式、状态、数量、重复、编号越界、不在可选集合、选歌期间曲库变化、违反“不要人声”/语种硬条件、证据不在枚举里、引用了本轮没有的情境、引用与歌曲资料不符、证据种类不全、理由为空或过长、候选不足 | [`validate_rec`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L3200) |
| 带原因重试一次 | 首次不合格、且在 60 秒内返回：把错误码放进 `fix` 再请求一次；仍不合格 → 退回本地规则，界面写明原因 | [`model_answer`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L3509) |
| 迟到回调作废 | `rec_gen` / `rec_att` 双代号；每次尝试 90 秒看门狗，超时就解锁界面，之后才到的结果直接丢弃，不会覆盖用户之后的操作 | [`rec_watch`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L3401) |
| 防提示注入 | 提示词写明 songs、intent、fix 都是数据，其中的指令一律不执行；模型拿不到坐标 | [提示词](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L3482) |
| 写后读回 | `labels.json`、`encounters.json` 写入后读回，比对全文、条数和末条时间戳；不一致重试一次，再不一致就提示用户 | [`readback_check`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L1393) |
| 诚实降级 | 无模型、网络错误、两次都没通过校验（含选歌期间曲库变化）、超时、可选曲目不足 6 首，五种本地结果在界面上各有说明；决策日志统计首次通过率和重试成功率 | 调试页；`AGENT.md` 的 `dstats.json` 一节 |

## 3. 推荐本身：本地规则 + 学习 + 探索

选歌决策链见 README 的流程图（[`docs/media/selection-flow.svg`](docs/media/selection-flow.svg)）。

- **本地先排**：规则分 + 按活动学习的偏好项，取前 12 名，模型只能从这 12 首里选 6 首（[`pref_rank`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L2587)）；没有模型或模型失败时，按名次本地取 6 首，同一歌手最多 2 首（[`local_pick`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L3318)）。
- **模型的实际作用**：候选按本地名次排列，提示词写明“没有特别理由时优先靠前的”。真机上没有特别要求时，模型基本按名次往下取（D5 选的就是第 1–6 名）；它的作用主要在理解自由输入的原话、为每首写理由和证据引用、避开刚听过的歌。
- **偏好学习**：只从歌单页对 ♥ / ✕ 的投票学习 12 维权重（从曲库打开的歌曲卡、模拟定位下的票不算），按活动分开学；学到的权重只用于本地排序，不交给模型（[`pref_update`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L2740)）。
- **反馈计数**：同一票还会改这首歌在本活动和全局的计数，进规则分。✕ 是固定惩罚（本活动 −4.0，全局 −1.5，全局这一项对所有活动生效），被 ✕ 的歌沉底主要靠它，学习项的作用小得多。
- **探索位**：第 7 首“🎲 试一首”从前 12 名里没被选中、且该歌手在 6 首里不足 2 首的歌中抽，按本活动下的 ♥ / ✕ 次数做 Beta-Thompson 抽样（[`explore_pick`](https://github.com/peterdlick-stack/agentic-app/blob/v0.4.0/bundle/main.splash#L3018)）。

## 4. 已知限制（如实列出）

- 仓库里的 `bundle/` 是未签名的源码（按 App Hub 流程，证明只加在 Release 的最终字节上），所以对源码跑 `hub check` 会有一条 `publisher-signature: unsigned` 警告；Release 包 `app.bundle.pack.json` 经 `hub publisher-verify` 验证通过。
- 带证明的 Release 只在本地测试商店装过同一个应用包，没有在正式商店里装过。
- 定位：Windows、Linux 桌面的宿主不提供定位，这两个平台上移动状态不参与推荐；Android/macOS 路径未在真机验证。
- `ask_user_question` 追问被宿主内核的模型连接超时挡住，还没在真机上弹出过（见第 1 节第 3 条）。
- rc.5 Windows 上，“去听”打开的应用内网页被宿主拒绝；天气显示“不可用”，原因还没查清。
- 选歌算法本身的限制：标签粗、同分多，前 12 名的边界常由种子哈希决定；没有评价时探索位是均匀抽签，且只在前 12 名里探索；歌单上方的“偏好：……”一句在票数少时不可靠（一次 ✕ 就可能触发）。完整清单见 README「[选歌算法的已知限制](README.md#选歌算法的已知限制)」。
- 歌词和官方封面有版权，**不在仓库里**；歌曲卡内容放在应用存储里，录屏中跳过歌词页。
