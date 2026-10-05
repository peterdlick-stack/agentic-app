# 情境 DJ v0.2 计划书：情境感知 + 按情境选曲

版本：2026-10-05 17:00（北京时间）　负责人：Claude（应用代码）、GPT（本机部署与测试）、Fano（决策与人工步骤）

目标：今天做完"自动情境感知 → 按情境选曲"这条核心链路，并在真实环境里验证；明天专心做 UI。
初赛只交仓库地址（已登记），所以今天不打 tag，也不提交 App Hub。

---

## 0. 结论先行

| 问题 | 结论 |
|---|---|
| 原来的感知方案（P40 加速度计 APK） | **放弃**。脚本应用读不到加速度计和陀螺仪，单独的 APK 也不算参赛作品；而且那套方法本身对 33 个步行窗口全部判不出来 |
| 新的感知方案 | 用平台真正开放的信号：**GPS（速度 + 地点）、时间、天气、用户说的那句话**，融合后推断活动；每一项都标明来源和可信度，手动选择永远优先 |
| 选曲 | 已有"情境 + 意图 + 反馈 → 选歌 + 理由"。v0.2 要做三件事：接入自动感知结果；让 AI 同时推断情境和选歌；在真实的 AI 服务上验证 |
| 手机 | P40 可以装 OctoSense Home（官方 APK，Android 8+，arm64），**但目前没有办法把我们的应用直接装到手机上**（官方文档 QUICKSTART §9）。只有在 App Hub 正式上架之后，手机商店里才能装。所以**今天不承诺手机上的 GPS 演示**；手机只用来验证 OctoSense 和 GPS 在 P40 上能不能用，为之后上架做准备 |

---

## 1. 目录与磁盘规则（必须遵守）

### 1.1 你的电脑

```
F:\context-dj-work\                 ← 本轮所有新文件的根目录（只用 F 盘）
├─ repo\                            agentic-app 的 git 工作副本（GPT 用）
├─ downloads\                       OctoSense 安装包、APK
├─ octosense-win\                   Windows 版 OctoSense 安装目录（安装程序允许选目录时）
├─ octosense-data\                  测试用的 OCTOSENSE_HOME 和 OCTOSENSE_APP_DATA
├─ mirror\                          本地 App Hub 目录
│  └─ keys\                         一次性测试密钥（不是正式发布者密钥，不进 git）
├─ evidence\
│  ├─ G0-disk\  G1-ai\  G2-phone\    每个任务的日志、截图和 REPORT.md
└─ tmp\                             临时文件，每个任务结束时清空
```

**C 盘规则**

1. 开始前记录 C 盘和 F 盘的剩余空间（`G0`）。**本轮 C 盘总共最多多用 1 GB；C 盘剩余空间一旦低于 5 GB，立刻停下并报告**，不要自行清理。
2. **WSL 不编译、不克隆大仓库、不往 WSL 的 home 里写大文件。** WSL 的虚拟磁盘（ext4.vhdx）在 C 盘上，**写进去的空间删了也不会还给 C 盘**。WSL 里的命令如果有输出，一律写到 `/mnt/f/context-dj-work/...`。
3. 可以调用 WSL 里已有的工具（`~/octosense-ws` 里的 `octo`、`hub`、桌面版），但**不重新编译**。需要重新编译的话，先停下来问。
4. 下载的文件放 `downloads\`，不放 C 盘的"下载"文件夹。
5. 不动这些已有目录：`F:\context-player-cache-20261004`（旧缓存，23 GB）、`C:\Users\admin\Downloads\Agentic Apps`（旧的 GPT 工程）。要清理的话以后单独决定。

### 1.2 仓库里每个文件归谁

| 路径 | 负责人 | 说明 |
|---|---|---|
| `bundle/**`、`BRIEF.md`、`README.md`、`PRIVACY.md`、`AGENTS.md` | **Claude** | 只有 Claude 改。GPT 改 `bundle/` 会让应用包的摘要和审查结果失效 |
| `docs/PLAN.md` | Claude | GPT 想改的话，经 Fano 转达 |
| `tools/**`、`docs/test-reports/**` | **GPT** | 本机部署和测试脚本、测试报告 |

- Claude 直接推送 `main`。GPT **不推 `main`**：它的脚本推到 `gpt/tools` 分支，报告写在 `F:\context-dj-work\evidence\`。
- 交接方式：GPT 写完 `REPORT.md` → Fano 告诉 Claude 路径 → Claude 读取（需要 Fano 把 `F:\context-dj-work` 授权给 Claude）。

---

## 2. v0.2 应用设计（`bundle/main.splash`）

### 2.1 总体数据流

```
sys.gps（每 10 s）──► S1 采样 ──► S2 速度估计 ──► 移动状态 motion
                                └─► S3 地点匹配 ──► place
设备时钟 ─────────────────────────────────────────► time
Open-Meteo（按 GPS 坐标，取不到时按城市）────────────► weather
手动选择 ─────────────────────────────────────────► manual
                                   ▼
                     C1 融合 infer_activity()  ──► ctx（情境快照，含来源和理由）
                                   ▼
输入框里的那句话 ──► R1 本地意图解析 / R2 AI 选歌（同时推断情境）
                                   ▼
                     歌单 [{i, why}] ──► 反馈 F1 ──► 偏好（按活动分开记）
```

### 2.2 活动集合（7 个，取代 v0.1 的 6 个）

| id | 名称 | 目标能量（1–5） | 偏纯音乐加分 | 偏好情绪 |
|---|---|---|---|---|
| `study` | 学习 | 1.5 | +1.5 | 专注 |
| `work` | 工作 | 2.5 | +0.8 | 专注 |
| `commute` | 通勤 | 3.4 | 0 | 欢快 |
| `walk` | 散步 | 3.0 | 0 | 温暖 |
| `workout` | 运动 | 4.7 | 0 | 振奋 |
| `relax` | 放松 | 2.0 | +0.3 | 温暖 |
| `sleep` | 睡前 | 1.0 | +1.5 | 平静 |

反馈记录相应增加 `walk` 字段（`fb = {g, study, work, commute, walk, workout, relax, sleep}`，取值都是 -3..3 的整数）。旧版保存的反馈缺少 `walk` 字段，读取时补 0。

### 2.3 S：感知

**常量**

| 名称 | 值 | 理由 |
|---|---|---|
| `GPS_POLL_S` | 10 | 安卓的定位监听每 2 s、每移动 5 m 更新一次；10 s 一采足够，脚本计算量也小 |
| `FIX_KEEP_S` | 120 | 内存里只保留最近 2 分钟的定位点 |
| `WIN_S` | 60 | 速度估计窗口 |
| `MIN_FIXES` | 4 | 窗口里至少 4 个有效点才估计速度 |
| `ACC_MAX_M` | 50 | 精度比这个差的点丢掉 |
| `STILL_FLOOR_M` | 20 | 净位移小于 max(20 m, 1.5 × 精度中位数) 视为静止，避免把定位抖动当成移动 |
| 速度分档（m/s） | 静止 < 0.5 ≤ 步行 < 2.2 ≤ 跑步或骑行 < 7 ≤ 乘车 | 约等于 1.8、8、25 km/h |
| `HOLD_N` | 2 | 连续 2 次估计一致才切换状态（滞后 ≥ 10 s，防止来回跳） |
| `PLACE_R_M` | 200 | 离已标记地点 200 m 以内算"在那儿" |
| `UNCHANGED_S` | 300 | 定位点 5 分钟没变：可能是静止，也可能是信号没更新，所以可信度减半 |

**数据结构**

```text
Fix    = {t: number(秒) lat: number lon: number acc: number(米)}
Motion = {state: "unknown"|"still"|"walk"|"run_bike"|"vehicle"
          speed: number(m/s，unknown 时为 0)  conf: 0..1  n: int(用到的点数)
          source: "gps"|"sim"|"none"  note: string(给人看的一句话)}
Place  = {id: string  kind: "home"|"school"|"work"|"gym"  name: string  lat lon: number}
Here   = {place: Place|nil  dist: number(米，没有地点时为 -1)}
```

**函数**

| 函数 | 输入 → 输出 | 行为 |
|---|---|---|
| `dist_m(lat1, lon1, lat2, lon2)` | → 米 | 等距矩形近似：dy = Δlat × 111320，dx = Δlon × 111320 × cos(lat 的弧度)，结果取 √(dx²+dy²)。只用于几公里以内的距离 |
| `read_fix()` | → `Fix` 或 nil | 模拟模式下返回 `sim_next()`；否则当 `sys.gps("ok") >= 1` 且精度 ≤ `ACC_MAX_M` 时返回 `{t: time_now() lat lon acc}`，否则返回 nil |
| `gps_poll()` | 无 | 每 `GPS_POLL_S` 秒调用一次：取一个点，放进 `fixes`，删掉超过 `FIX_KEEP_S` 的旧点，然后调用 `update_motion()`、`update_here()`；位置变化超过 5 km 时刷新天气 |
| `estimate_speed()` | → `{ok, speed, n, acc_med}` | 取窗口内的点；点数少于 `MIN_FIXES` 或时间跨度小于 30 s 时 `ok: false`；净位移 d 小于 `STILL_FLOOR_M` 规则时速度记为 0，否则速度 = d ÷ 时间跨度 |
| `classify(speed)` | → state | 按上面的速度分档 |
| `update_motion()` | 无 | 新状态连续 `HOLD_N` 次一致才写入 `motion`；没有定位时 state 为 `unknown`，note 写"没有定位"；可信度 = min(1, n/6) × (精度中位数 ≤ 20 m ? 1 : 0.7)，点位 5 分钟没变时再 × 0.5 |
| `mark_place(kind)` | 无 | 用当前点保存地点。每种类型只保留一个（新的覆盖旧的），所以最多 4 个；没有定位时提示，不保存。模拟模式下标记的地点只保存在内存里 |
| `remove_place(id)` | 无 | 删除一个地点 |
| `update_here()` | 无 | 找最近的地点，在 `PLACE_R_M` 以内就记下 |
| `sim_set(kind)` | kind ∈ `off`/`still`/`walk`/`bike`/`bus` | 模拟模式：从基准点（有真实定位时用真实定位，否则用北京 39.9042, 116.4074）出发，分别以 0 / 1.3 / 4.5 / 9 m/s 前进，加 ±8 m 抖动，精度 10 m |

**模拟模式的规则**：界面顶部一直显示橙色的"模拟定位中"；推荐历史里 `source` 记为 `"sim"`。只用于电脑上测试和演示的兜底，**不能当成真实感知来宣传**。

### 2.4 C：情境融合

```text
Ctx = {at: number  hour: int  minute: int  weekday: int(0 = 周日)  slot: string  weekend: bool
       weather: {state: "loading"|"ok"|"fail"  text  temp  code  coords: "gps"|"city"}
       motion: Motion   here: Here
       activity: {id: string|""  source: "manual"|"intent"|"place"|"motion"|"time"|"none"
                  conf: 0..1  why: [string]}}
```

`infer_activity(sig)` 按优先级取第一个成立的规则：

| 优先级 | 条件 | 结果 | 可信度 |
|---|---|---|---|
| 1 | 手动选择还没过期（90 min） | 手动选的那个 | 1.0 |
| 2 | 那句话里有明确的情境词（见 R1 的 `act_words`） | 对应的活动 | 0.9 |
| 3 | 静止 + 在某个地点 | gym→运动，school→学习，work→工作，home→23:00–06:00 为睡前、其他时间为放松 | 0.8 |
| 4 | 乘车 | 通勤 | 0.75 × motion.conf |
| 5 | 跑步或骑行 | 不在健身房，且是工作日 7–9 点或 17–19 点 → 通勤；否则 → 运动 | 0.6 × motion.conf |
| 6 | 步行 | 工作日 7–9 点或 17–19 点 → 通勤；否则 → 散步 | 0.65 × motion.conf |
| 7 | 打开了"用时段" | 沿用 v0.1 的时段表 | 0.35 |
| 8 | 其他情况 | 没有活动（`""`） | 0 |

`why` 每条写一句给人看的理由，例如：`GPS：近 1 分钟约 1.3 m/s → 步行`、`位置：距「学校」80 m`、`你说「在地铁上」`。

**AI 的情境判断**：R2 返回的 `activity` 只在两种情况下采用——优先级 1 和 2 都不成立，并且 AI 给的不是 `unknown`；采用时 `source` 记为 `"ai"`（实现时从初稿的 `"intent"` 改过来：AI 也会参考传感器信号，标成"你说的"会误导）、可信度 0.85，理由写 AI 给的 `activity_why`。这样**手动选择永远最优先**，传感器推断可以被你的原话纠正。

### 2.5 R：选曲

| 函数 | 输入 → 输出 | 说明 |
|---|---|---|
| `parse_intent(raw)` | → `It` | v0.1 的字段加上 `act: string`（从 `act_words` 里匹配，默认 `""`）。`act_words`：地铁/公交/开车/打车/通勤/上班路上→commute；跑步/健身/撸铁/骑车→workout；散步/遛弯→walk；睡觉/失眠/助眠→sleep；学习/复习/写作业/刷题/看书→study；上班/开会/写代码/加班→work；休息/放空/躺着→relax |
| `score_song(s, ctx, it)` | → `{sc, why}` | 和 v0.1 相同；活动取 `ctx.activity.id` |
| `local_pick(ctx, it)` | → `[{i, why}]` × 8 | 和 v0.1 相同 |
| `ask_model(raw, it, ctx)` | 无（异步） | 一次调用同时完成"推断情境"和"选歌"。输出格式见下 |
| `model_answer(r, …)` | 无 | 先校验：编号合法、不重复、至少 3 首；然后采用 `activity`（按 2.4 的规则）；不合格就退回本地规则，并显示原因 |

**`model.complete` 的输入**（不发送原始坐标）：

```json
{"signals": {"time": "工作日下午 16:40", "weather": "小雨 18°C",
             "motion": "步行 1.3 m/s（GPS，可信度 0.7）", "place": "距「学校」80 m",
             "rule_activity": "commute（工作日傍晚 + 步行）", "manual": ""},
 "intent": "<原话>", "recent": ["歌名|歌手", "..."],
 "songs": [{"i": 0, "title": "...", "artist": "...", "energy": 3, "vocal": false,
            "mood": "欢快", "lang": "instr", "like": 0}]}
```

**输出格式（schema）**：

```json
{"type": "object", "required": ["understood", "activity", "activity_why", "picks"],
 "additionalProperties": false,
 "properties": {
   "understood":   {"type": "string", "maxLength": 80},
   "activity":     {"type": "string", "enum": ["study","work","commute","walk","workout","relax","sleep","unknown"]},
   "activity_why": {"type": "string", "maxLength": 40},
   "picks": {"type": "array", "minItems": 3, "maxItems": 8,
             "items": {"type": "object", "required": ["i","why"], "additionalProperties": false,
                       "properties": {"i": {"type": "integer", "minimum": 0, "maximum": "<songs.len-1>"},
                                      "why": {"type": "string", "maxLength": 40}}}}}}
```

### 2.6 F：反馈（同 v0.1，扩成 7 个活动）

`feedback(i, v)`：v = +1 或 -1。总体分和当前活动下的分都加 v，限定在 -3..3。**按活动读写必须用 `fb_get` / `fb_set`**，不要写 `f[id] = v`（实测运行时会追加一个重复的键，而不是覆盖）。

### 2.7 存储（都在 `accounts/device/` 下）

| 文件 | 内容 | 变化 |
|---|---|---|
| `prefs.json` | `{city act act_until use_weather use_time use_gps sim}` | 新增 `use_gps`（默认 true）和 `sim`（默认 "off"，**不持久化为开启**：重启后自动回到 off） |
| `places.json` | `[Place]` | 新文件。只存你自己标记的地点。**放在存储根目录，不放在 `accounts/device/`**（实现时发现：应用助手能读 `accounts/device/`，放在那里坐标可能经助手发给 AI） |
| `feedback.json` | `[{k fb}]` | `fb` 增加 `walk` 字段 |
| `library.json` / `last.json` | 同 v0.1 | — |
| `history.json` | 最近 30 条 `{at how intent ctx_text act act_source motion place_kind picks sim}` | **不存坐标** |

原始定位点只保存在内存里，不写文件。

### 2.8 界面（今天只做功能，样式留到明天）

- **主页情境卡**：时段 / 天气 / 移动（新增）/ 地点（新增）/ 活动（显示来源和可信度，下面列出 `why`）。开关增加"用定位"。
- **新页面「感知」**：原始信号（最近几个定位点的精度、估计速度、点数）、地点标记按钮（家 / 学校 / 公司 / 健身房）和已标记地点列表、模拟模式按钮。
- 歌单、曲库、播放页沿用 v0.1。

### 2.9 manifest 与 listing

- `capabilities` 增加 `location`（只读取定位；没有授权时 `sys.gps` 一直显示"没有定位"，应用照常运行）。
- `listing.json` 和 `PRIVACY.md` 补充：定位只用来估计移动速度和匹配你标记的地点；坐标不写入历史；查天气时会把坐标发给 Open-Meteo。

---

## 3. 任务分配

### Claude

| 编号 | 内容 | 完成标准 |
|---|---|---|
| C1 | 按第 2 节实现 v0.2 | `tools/octo check` 显示 PASSED；日志里没有 `[E] splash` |
| C2 | 在电脑上用 card-host 跑 T1–T10（见第 4 节） | 每项都有截图或数据文件作为证据 |
| C3 | 推送 `main`，通知 GPT 开始 G1 | — |
| C4 | 修复 G1 / G2 报告里的问题（最多 2 轮） | — |
| C5 | 代码和测试结果的对抗性审查 | 写成审查记录 |

### GPT（在 Fano 的电脑上，严格遵守第 1 节）

**G0 准备工作区（15 分钟）**
1. 建好 1.1 节的目录。
2. 记录 C 盘和 F 盘的剩余空间，以及 WSL 虚拟磁盘 ext4.vhdx 的大小，写入 `evidence\G0-disk\disk.txt`。
3. 把 `https://github.com/peterdlick-stack/agentic-app` 克隆到 `F:\context-dj-work\repo`。
4. 告诉 Fano：把 `F:\context-dj-work` 授权给 Claude。

**G1 在真实 AI 服务上验证（先用 v0.1 把流程跑通，等 C3 通知后再测 v0.2）**
1. 判断 WSL 里那套桌面版能不能用 `model.complete`：在 `~/octosense-ws` 下的 OctoSense 源码目录里查是否包含 OctoSense PR #95（`git log --oneline | grep -i "model"`，或者检查 `apps/ai-providers/host-service/src/complete/` 是否存在）。
   - 包含 → 用 WSL 桌面版（已接 MiniMax）。
   - 不包含 → 下载 Windows 版 `octosense_0.1.0-beta.1_x64-setup.exe` 到 `downloads\`，安装到 `F:\context-dj-work\octosense-win\`（安装程序不能选目录的话，先停下问）。在桌面版的 AI 设置里由 **Fano 本人**填 MiniMax 密钥。**密钥不得写进任何文件、日志或截图。**
2. 按 OctoScript-App-Design-Flow `docs/PUBLISHING.md` §4，用**一次性测试密钥**建本地目录 `F:\context-dj-work\mirror`，用 `hub publish` 发布 `repo\bundle`。
3. 用 `OCTOSENSE_HUB` 和 `OCTOSENSE_HUB_ANCHOR` 指向这个目录启动桌面版，`OCTOSENSE_APP_DATA` 设为 `F:\context-dj-work\octosense-data`，在 App Hub 里安装并打开情境 DJ。
4. 依次跑场景（v0.2 版本）：
   - A：不输入任何话，点"推荐"
   - B："写代码，不要人声"
   - C："在地铁上，有点困"（看 AI 推断的活动是不是 commute）
   - D："下雨天有点丧，想听点中文歌"
   - E：曲库添加"夜曲 - 周杰伦"后点"AI 补标签"

   每个场景记录：状态行的完整文字、前 3 首歌和理由、截图、日志里含 `model` 或 `splash` 的行。
5. 写 `evidence\G1-ai\REPORT.md`：每个场景**通过 / 失败 / 未能运行**，失败时附原始错误。**没有观察到 AI 真实返回的，不能写"通过"。**

**G2 手机准备（限时 90 分钟，超时就停下报告）**
1. 下载 `OctoSenseHome_0.1.0-beta.1_arm64.apk` 和 `OctoSenseBridge_0.1.0-beta.1_arm64.apk` 到 `downloads\`，用 `adb install` 装到 P40。
2. 记录 P40 的系统版本，确认 OctoSense Home 能启动。
3. 打开系统自带的地图应用，看能不能拿到定位，判断 P40 没有谷歌服务（GMS）时 GPS 是否可用。
4. **只调查、不编译**：Home 里有没有办法装本地应用包（开发者设置、App Studio、导入）。有就记下步骤，没有就写"没有找到"。
5. 写 `evidence\G2-phone\REPORT.md`。**不要编译 APK，不要往 WSL 里装 Android SDK 或 NDK。**

### Fano

- 把这份计划里 G0–G2 的部分交给 GPT。
- G0 完成后，把 `F:\context-dj-work` 授权给 Claude。
- 在桌面版里填 MiniMax 密钥（G1 第 1 步需要时）。
- 收到报告后把路径告诉 Claude。

---

## 4. 验收测试（C2，电脑上用 card-host 跑）

| # | 场景 | 期望 |
|---|---|---|
| T1 | 首次启动，没有定位 | 移动显示"没有定位"；活动按时段推测，标明"时段 · 0.35"；不报错 |
| T2 | 模拟：静止，60 s | 移动显示"静止"，可信度 > 0 |
| T3 | 模拟：步行，非通勤时段 | 约 1.3 m/s → 步行 → 活动为散步，来源 motion |
| T4 | 模拟：乘车 | 约 9 m/s → 乘车 → 活动为通勤 |
| T5 | 静止时标记"学校"，再推荐 | 地点显示"学校"，活动为学习，来源 place；歌单偏纯音乐、低能量 |
| T6 | 手动选"运动" | 来源 manual，覆盖地点推断；歌单高能量 |
| T7 | 那句话里说"在地铁上"（未手动选择） | 活动为通勤，来源 intent |
| T8 | 状态从步行切到乘车 | 至少 2 次估计后才切换，中间不来回跳 |
| T9 | 重启 | 地点、反馈、偏好保留；模拟模式回到 off；历史里没有坐标 |
| T10 | 在"运动"下点喜欢，再在"学习"下推荐 | 这首歌在学习下没有被加分（只有总体分 +1 那部分） |

---

## 5. 时间表（10 月 5 日）

| 时间 | Claude | GPT | Fano |
|---|---|---|---|
| 17:00–17:30 | C1 开始 | G0 | 交任务、授权文件夹 |
| 17:30–20:30 | C1 → C2 → C3 | G1 第 1–3 步（用 v0.1）、G2 | 填密钥 |
| 20:30–22:00 | C4 | G1 第 4–5 步（用 v0.2） | 转交报告 |
| 22:00–23:00 | C5，推送当天的最终版 | 收尾 | 看结果 |
| 10 月 6 日 | UI 设计（另写计划） | 配合截图和测试 | 定 UI 方向 |

---

## 6. 风险与兜底

| 风险 | 兜底 |
|---|---|
| 手机装不上我们的应用 | 电脑演示用模拟定位（明确标注），README 写明真机 GPS 未验证；决赛前争取 App Hub 上架 |
| WSL 桌面版没有 `model` 服务，Windows 版又装不上 | AI 这条路保持"未验证"，本地规则照常工作；不为了跑通去重新编译 |
| 公交慢速行驶被判成跑步或骑行 | 规则 5 结合时段和地点修正；那句话、AI 和手动选择都可以纠正 |
| 定位点长时间不变（信号没有更新） | 5 分钟没变就把可信度减半，界面显示"位置未变化" |
| C 盘空间 | 第 1 节的硬性规则；低于阈值立即停下 |

---

## 7. 对抗性审查（针对这份计划本身）

写完初稿后，我从"哪里会出错、哪里不合常理"的角度逐条挑刺，以下是发现的问题和已经改进的地方：

1. **"手机上演示 GPS"不现实。** 初稿把手机测试和桌面测试并列。查官方文档后确认：商店应用目前没有侧载路径，手机只能装官方商店里已上架的应用。→ 已改：今天手机只做"能不能装 Home、GPS 能不能用"，不承诺演示；演示用模拟模式，并强制标注。
2. **GPS 定位点没有时间戳。** 平台只提供最近一次的经纬度和精度。如果信号断了，旧的点会一直被读到，看起来像静止。→ 增加 `UNCHANGED_S` 规则（5 分钟没变，可信度减半，并提示）。
3. **抖动会被当成移动。** 精度 30 m 的点来回跳，按路径长度算会得出"步行"。→ 改用窗口内**净位移**，并设 `STILL_FLOOR_M` 下限。
4. **速度阈值区分不了公交和自行车。** 城市公交平均常低于 25 km/h。→ 不硬分，"跑步或骑行"结合时段和地点二次判断；用户的话、AI 和手动选择可以覆盖。
5. **AI 和传感器结论冲突时听谁的？** 初稿没写。→ 明确优先级：手动 > 那句话里的明确情境（本地关键词或 AI）> 地点 > 移动 > 时段。理由是：用户自己说的比传感器推断更可靠，但不能盖过用户的手动选择。
6. **隐私。** 初稿打算把坐标写进历史，方便应用助手读取。→ 去掉：历史只记移动状态和地点类型，原始点只留在内存里；天气请求会发送坐标，这一点在隐私说明里写清楚。
7. **模拟模式可能被误当成真实感知。** → 界面一直显示橙色横幅，历史标记 `sim`，重启自动关闭，README 写明。
8. **C 盘会被悄悄占满。** WSL 虚拟磁盘只会变大、不会自动变小，最容易出事。→ 第 1 节明确禁止在 WSL 里编译和写大文件，输出一律写到 F 盘，并设了停止阈值。
9. **两边同时改同一个文件。** GPT 并行写代码，最可能和我在 `main.splash` 上冲突，还会让应用包摘要失效。→ 按文件划分归属，GPT 不推 `main`。
10. **"AI 路径通过"的标准太松。** 初稿写的是"没有报错就算通过"。→ 改成：必须看到 AI 真实返回的歌单和 `understood`；"本地规则 · AI 不可用"算失败。
11. **API 是否真的存在。** `sys.gps` 在系统地图应用（`apps/maps/bundle/main.splash`）中有实际使用，说明 shell 里可用；`cos` 在文档中列出，实现时还要先用 card-host 实测一次再依赖它。
12. **密钥安全。** MiniMax 密钥只由 Fano 在桌面版的设置界面里填，GPT 不经手、不记录。
13. **时间太紧，GPT 可能在手机上耗掉整个晚上。** → G2 限时 90 分钟，只调查、不编译。

**仍未解决的问题**（如实列出）：P40 上 OctoSense 的定位权限是否会弹窗、弹窗是什么样，要等 G2 报告；`hub publish` 做本地发布在 Windows 版桌面上是否被识别，要等 G1 报告。

---

## 8. C1–C2 实施记录（2026-10-05 晚）

- **完成**：第 2 节全部实现，v0.2.0。T1–T10 全部通过（电脑上用 card-host 和模拟定位），另加两项：v0.1 数据迁移（旧反馈缺 `walk`、旧偏好缺 `use_gps`）正常；`places.json` 读取、跳过非法条目、删除后持久化正常。`tools/octo check` 显示 `context-dj 0.2.0 — PASSED`。
- **实测发现**：
  - 直接访问缺失字段会报错，并中断整个处理函数；改用 `pick()`。
  - `ok` 是保留字，不能当对象的键。
  - 每个处理函数的指令上限确实生效（30 万次的循环被拦下）。0.1 秒一次的压力测试跑了约 2400 次采样，没有触发会话级预算，按真实的 10 秒间隔折算约 6–7 小时。
- **已知行为**：从步行切到公交时，60 秒窗口会先经过约 20 秒的"跑步或骑行"，再变成"乘车"。工作日通勤时段内，两者都推断为通勤，不影响结果；其他时段会被短暂推断为运动。
- **仍未验证**：真机 GPS（要等手机能装上应用）、AI 推断情境（要等 G1）、天气请求成功时的显示（本环境访问不到 Open-Meteo）。

---

# 第二部分：v0.3 计划（2026-10-05 晚定稿，10-06 至 10-12 执行）

## 9. 对齐后的算法设计

### 9.1 已经定下来的事

| 事项 | 结论 |
|---|---|
| AI 用哪个 | **MiniMax**（赛方提供）。它已经配在 OctoSense 桌面版里，应用通过平台的 `model.complete` 调用，**应用和仓库里都不放任何密钥**（平台规则禁止，检查器会拒绝；仓库公开，放了就会泄露） |
| 联网搜索 | `model.complete` 只能一问一答，没有搜索工具；商店应用的 Agent 也不能用 `web_search`。歌曲信息改用 **MusicBrainz**（免费、无密钥）+ AI 自身知识补全，补全的字段标注"AI 推断" |
| 读蓝牙或耳机信息 | **平台不支持**：脚本接口和权限清单里都没有，已逐项核对。改为向平台提 issue，申请开放这个接口（技术加分项，见 G4） |
| 扫描本机曲库 | **平台不支持**：应用只能读写自己的沙盒，没有文件选择器，也不能读剪贴板。改为批量粘贴导入"歌名 - 歌手" |
| 规律学习 | 两层：**本地统计为主**（可解释、离线、不花钱），**AI 负责总结**成人能看懂的"你的规律" |
| 模板 | 同类情境确认满 3 次，就提示"要不要存成模板"；也可以手动把这次存成模板 |
| 演示数据 | 你从 10-06 起每天真实使用、积累数据（优先）；同时准备一份**明确标注为"演示数据"**的导入包作为兜底 |

### 9.2 新的推荐流程

```
感知信号 → 个人规律统计 → 候选活动前 3 名（带概率）+「其他」
   → 你点一下确认（或者直接点某个模板）
   → 补充要求（可以留空）→「下一步」
   → 选曲 → 歌单和逐首理由 → 喜欢 / 不喜欢
   → 确认记录和反馈都回流到统计
AI 定期：总结"你的规律"、建议新模板
```

### 9.3 数据（都在 `accounts/device/` 下，助手可以读；不含坐标）

| 文件 | 结构 | 用途 |
|---|---|---|
| `labels.json` | 最近 500 条 `{at, day: "weekday"\|"weekend", slot: 时段名, place_kind: ""\|home\|school\|work\|gym, motion: still\|walk\|run_bike\|vehicle\|unknown, chosen: 活动id, top: [候选id×3], how: "tap"\|"manual"\|"template"\|"intent"}` | 每次确认的活动，也就是你的真实标签 |
| `templates.json` | `[{id, name, day, slot, place_kind, act, req: {instr, energy, mood, lang}, extra: 补充要求文字, uses, created}]` | 场景模板 |
| `routine.json` | `{at, text: AI 写的规律总结, n_labels}` | 缓存 AI 的总结，避免重复调用 |

### 9.4 规律统计（候选排序）

- **情境桶** b = (day, slot, place_kind, motion)；**粗桶** b' = (day, slot)。
- **先验** prior(a | b)：v0.2 融合规则推断出的活动取 0.55，其余 6 个活动平分 0.45。
- **后验**：P(a | b) = (n(b, a) + α·prior(a | b)) / (n(b) + α)，取 α = 3。n(b) < 3 时，用粗桶 b' 的计数代替（回退）。
- **候选**：取 P 最大的前 3 个显示，另加"其他"（展开为 7 个活动）。
- **什么时候主动问**：P 最大值 < 0.7、情境桶变了、或者你主动点"推荐"时，才显示候选卡；否则直接用最大的那个，并留一个"不对？"让你改。
- **AI 总结**：每新增 20 条确认、或者你点"看看我的规律"时，把各桶的计数表（不含时间戳明细，大约 2 KB）交给 `model.complete`，返回 `{text ≤ 120 字, patterns: [{day, slot, act, share}]≤5}`，存进 `routine.json`。

### 9.5 模板

- **提示条件**：同一个 (day, slot, chosen) 组合在最近 14 天内确认满 3 次，并且这几次补充要求解析出的约束有过半一致，就提示"要不要存成模板"。你同意后才保存。
- **使用**：点模板 → 补充要求输入框，预填模板里的 extra，可以改、可以清空 → "下一步" → 生成歌单。`uses` 加 1，同时也算一次确认，写入 labels。
- **管理**：可以改名、删除。

### 9.6 歌曲信息（P2）

- **导入**：输入框支持一次粘贴多行或用"；"分隔的"歌名 - 歌手"，去重后加入曲库。
- **MusicBrainz**：`network.hosts` 加 `musicbrainz.org`；请求 `/ws/2/recording?query=recording:"<歌名>" AND artist:"<歌手>"&fmt=json&limit=1`，User-Agent 写成 `ContextDJ/0.3 ( https://github.com/peterdlick-stack/agentic-app )`；每秒最多 1 次，后台排队并显示进度。能拿到的字段：时长、艺人、专辑、年份；语种只在一部分条目里有。
- **AI 补全**：能量 1–5、是否人声、情绪、语种（MusicBrainz 缺的话），一律标注"AI 推断"。**不追求精确 BPM**（免费、无密钥的 BPM 来源基本没有了）。

## 10. 任务分配（v0.3）

### Claude（只改 `bundle/**` 和文档）

| 编号 | 时间 | 内容 | 完成标准 |
|---|---|---|---|
| C6 | 10-06 | **P0**：候选排序卡 + 一键确认 + `labels.json`；新的推荐流程（候选 / 模板 → 补充要求 → 下一步）；**整体 UI 重做**，顺便合并主页上两处不一致的活动显示 | card-host 实测通过，截图都打开看过，检查器 PASSED |
| C7 | 10-07 | **P1**：规律统计 + AI 规律总结卡；模板的提示、保存和使用 | 用模拟确认数据测试概率和模板提示 |
| C8 | 10-08 | **P2**：批量导入 + MusicBrainz 补全 + AI 补标签 | 依赖 G3 的网络结论 |
| C9 | 随时 | 按 G1、G2、G3 的报告修复 | — |
| C10 | 10-10 | 演示数据包（标注清楚）、README、决赛演示脚本 | — |

### GPT（在 Fano 的电脑上，第 1 节的磁盘和目录规则继续有效；**不改 `bundle/`，不推 `main`**）

**G0–G2 照第 3 节继续做。** 说明两点：
- G1 的 MiniMax 已经配在 WSL 桌面版里（见 `C:\Users\admin\Downloads\Agentic Apps\MINIMAX-SETUP-STATUS.txt`）。第 1 步只需要确认这个桌面版**有没有 `model` 服务**，也就是是否包含 OctoSense PR #95，不需要重新配置密钥。
- 不得读取、复制、打印或转存任何密钥文件的内容。

**G3 网络可达性（30 分钟）**
在你的网络环境下，分别从 Windows 和 WSL 用 curl 测这三个地址能不能访问、延迟多少，结果写入 `evidence\G3-net\REPORT.md`：
1. `https://api.open-meteo.com/v1/forecast?latitude=31.82&longitude=117.23&current=temperature_2m`
2. `https://musicbrainz.org/ws/2/recording?query=recording:%22%E6%99%B4%E5%A4%A9%22%20AND%20artist:%22%E5%91%A8%E6%9D%B0%E4%BC%A6%22&fmt=json&limit=1`，请求头带 `User-Agent: ContextDJ/0.3 ( https://github.com/peterdlick-stack/agentic-app )`
3. 同一个 MusicBrainz 请求，换成英文歌 `Blinding Lights` / `The Weeknd`

每条记录 HTTP 状态码、耗时、返回内容的前 500 个字符，以及第 2、3 条是否返回了 length、release、date 字段。只用 curl，不装任何软件。

**G4 起草平台 issue（30 分钟，只写不提交）**
写到 `evidence\G4-issue\ISSUE.md`，由 Fano 自己去 `OctoSense-org/makepad` 或 `OctoSense-org/OctoSense` 提交。内容：
- 请求让脚本应用读取**当前音频输出设备的类型**（扬声器、有线耳机、蓝牙），只读、粗粒度、不含设备地址；
- 说明用途：情境感知音乐推荐，戴耳机和外放应该推荐不同的歌；
- 指出平台底层已经有音频设备事件 `Event::AudioDevices`，只是没有开放给脚本；
- 给出建议的接口，例如 `sys.audio_route()` 返回 `"speaker"|"wired"|"bluetooth"|"unknown"`，以及隐私说明。

**G5 每日使用记录（10-06 起，配合 Fano）**
每天结束时，把 WSL 或桌面版里情境 DJ 的 `accounts/device/labels.json` 和 `history.json` **复制**一份到 `F:\context-dj-work\evidence\G5-usage\<日期>\`（只复制，不改），并统计条数写进 `count.txt`。等 Fano 真正开始用桌面版里的情境 DJ 再开始。

### Fano

- 把这份计划第 10 节里 GPT 的部分（G0–G5）交给 GPT。
- `F:\context-dj-work` 建好后授权给 Claude。
- 10-06 起每天真实用几次（通勤、学习、睡前各用一次就够），每次都点一下候选活动确认。这些就是决赛演示的真实数据。
- G4 的 issue 由你自己提交。
