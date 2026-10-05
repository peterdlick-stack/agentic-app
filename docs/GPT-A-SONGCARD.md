# GPT-A 任务书：实现《I LOVE U》歌曲卡

版本：2026-10-05 晚　发给：GPT-A　上级文档：`docs/DEMO-ILOVEU.md`（规格以它为准）、`docs/PLAN.md` 第 1 节（磁盘规则）

你负责**把歌曲卡做出来**。资料核实、素材处理、`main` 上的测试归 GPT-B，你们两个同时在 Fano 的电脑上工作，**严格按下面的隔离规则，不要碰对方的目录和端口**。

---

## 1. 你的工作区（和 GPT-B 完全分开）

| 项目 | 你用 | GPT-B 用（不要碰） |
|---|---|---|
| 仓库副本 | `F:\context-dj-work\repo-demo\`（分支 `demo/iloveu`） | `F:\context-dj-work\repo\`（`main`） |
| card-host 端口 | `8151` | `8141` |
| 测试用应用存储 | `F:\context-dj-work\octosense-data-demo\`（`--app-data`） | `F:\context-dj-work\octosense-data\` |
| 报告和截图 | `F:\context-dj-work\demo-iloveu\G7-rotate\`、`G8-gesture\`、`G9-impl\`、`G10-test\` | `G6-facts\`、`assets\`、`G11-issue\` |
| OctoSense 桌面版（MiniMax） | **不用** | GPT-B 用 |

- WSL 里的命令输出一律写到 `/mnt/f/context-dj-work/...`，不往 WSL 的 home 写大文件（PLAN 1.1 的 C 盘规则）。
- 启动 card-host 用 `--hidden`，结束时用 `curl -s 127.0.0.1:8151/quit` 关掉自己启动的那个，不要 `pkill`。

## 2. 准备

1. 把仓库克隆到 `repo-demo\`，从 `main` 拉出 `demo/iloveu` 分支。**只推这个分支，绝不推 `main`。**
2. 读三份文件：`docs/DEMO-ILOVEU.md`（规格）、`AGENTS.md`（尤其"本应用"一节的坑）、OctoScript-App-Design-Flow 的 `docs/SCRIPT-API.md`。
3. 视觉稿在 Claude 的 Design 画布上，由 Fano 截图给你。**配色方向（A 夜空 / B 晴空）Fano 还没定**，先按 A 夜空实现，颜色全部写成文件顶部的常量，之后换方向只改常量。

## 3. 任务

**G7 封面旋转调研（今晚，限时 45 分钟）**
在 makepad 源码（`widgets/src/`、`draw/`）里查：脚本应用能不能让 `Image` 或 `RoundedView` 旋转，或者让 `draw_bg` 随时间变化。能做就写最小示例并在 card-host 跑通；不能就写"不支持"，附源码依据。→ `G7-rotate\REPORT.md`

**G8 手势实测（今晚，30 分钟）**
最小测试：`GestureView`（`on_swipe` 左右翻页）里面套一个能上下滚动的 `ScrollYView`。记录：左右滑能否翻页、上下滚能否用、两者是否互相干扰。→ `G8-gesture\REPORT.md`

**G9 实现歌曲卡（10-07 起）**
1. 从歌单点一首歌，进入歌曲卡。
2. 按 DEMO-ILOVEU §3 实现四页卡片、页码圆点、控制栏。控制栏五个按钮接现有的 `feedback()` 和 `play()`；"✕ 不喜欢"在记反馈后自动切到下一首。
3. 按 §4.1 读 `accounts/device/cards.json`。没有卡片内容的歌只显示第 1、4 页内容，第 2、3 页显示空状态。
4. 第 4 页读 `accounts/device/encounters.json`。这个文件由 Claude 在 `main` 上加的记录逻辑写入（D4）。D4 合并之前，你用手写的测试文件，**文件里标 `sim: true`**。
5. 把《I LOVE U》加进内置曲库 `SEED`：`{t: "I LOVE U" a: "洛天依" en: 4 vo: true md: "欢快" lg: "zh"}`（DEMO-ILOVEU §3.6）。**这条取代 Fano 之前说的"能量、情绪去掉"**：两个字段保留给算法用，只是界面上不显示数字。
6. 素材（歌词、官方封面；**AI 封面已砍掉**）由 GPT-B 放在 `F:\context-dj-work\demo-iloveu\assets\`，你**复制**到自己的 `octosense-data-demo\` 里。**素材绝不进仓库。**
7. 每次修改后跑 `tools/octo check bundle`，必须 `PASSED`。
8. 截图：四页各一张、封面背面一张、每页空状态各一张，放 `G9-impl\shots\`。截图里不能出现歌词全文。

**G10 验收**：跑 DEMO-ILOVEU §6 的 T1–T10、T13、T14（T11、T12 归 GPT-B）。→ `G10-test\REPORT.md`

## 4. 规则

- **没有亲眼观察到的，不能写"通过"。**
- 代码遵守 `AGENTS.md` 的坑：读字段用 `pick()`、反馈用 `fb_get` / `fb_set`、`ok` 不能当键名、颜色写 `#x`、背景用 `SolidView` / `RoundedView`、`ButtonFlat` 里不放子组件。
- 改动集中在新增的函数和界面里，**尽量不改现有的推荐、感知逻辑**，方便之后合并。
- 合并到 `main` 由 Claude 审查，你不要自己合并。
- 卡住超过 30 分钟就停下，把现象和日志写进报告。

## 5. 交付

每个任务完成后，在对应目录写 `REPORT.md`，告诉 Fano 路径。格式：做了什么 → 结果（原文引用命令输出）→ 没验证的 → 需要人做的。
