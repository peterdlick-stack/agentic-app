# GPT-B 任务书：资料、素材与 `main` 上的测试

版本：2026-10-05 晚　发给：GPT-B　上级文档：`docs/DEMO-ILOVEU.md`、`docs/PLAN.md`（第 1 节磁盘规则，第 10 节 G5）

你负责**核实资料、处理素材、测试 Claude 在 `main` 上的改动、记录每日使用数据**。GPT-A 同时在做歌曲卡，**严格按隔离规则，不碰对方的目录和端口**。你**不改 `bundle/`**。

---

## 1. 你的工作区

| 项目 | 你用 | GPT-A 用（不要碰） |
|---|---|---|
| 仓库副本 | `F:\context-dj-work\repo\`（`main`，只拉不推） | `repo-demo\` |
| card-host 端口 | `8141` | `8151` |
| 测试用应用存储 | `F:\context-dj-work\octosense-data\` | `octosense-data-demo\` |
| 报告 | `F:\context-dj-work\demo-iloveu\G6-facts\`、`assets\`、`G11-issue\`；测试报告放 `F:\context-dj-work\evidence\` | `G7`–`G10` |
| OctoSense 桌面版（MiniMax） | **你用** | 不用 |

- WSL 里的输出一律写到 `/mnt/f/context-dj-work/...`。
- card-host 用 `--hidden` 启动，用 `curl -s 127.0.0.1:8141/quit` 关。
- **不得读取、复制、打印任何密钥文件。**

## 2. 任务

**G6 资料核实（今晚，60 分钟）** → `G6-facts\REPORT.md`
1. 找到《I LOVE U》的原始投稿（B 站），记录：标题、投稿日期、BV 号、作词、作曲、编曲、调教、演唱、曲绘和 PV 制作者、投稿简介全文。
2. 查萌娘百科「I LOVE U」「阿良良木健」条目，以及作者公开说过的和创作有关的话（投稿简介、动态、采访）。
3. 区分**一手来源**（作者本人）和**二手来源**（百科、评论），每条附链接和截图。
4. **不要摘抄歌词。** 查不到的写"没有找到"，不推测。
5. 写完告诉 Fano，Claude 会据此写故事文案（D3）。

**素材准备（Fano 交给你之后）** → `F:\context-dj-work\demo-iloveu\assets\`
1. 官方封面：从原始投稿获取。
2. ~~AI 另类封面~~：已砍掉（Fano 10-05），不用等。
3. 歌词：Fano 提供文本，存成 UTF-8 的 `iloveu.txt`。
4. 图片一律压缩到 **300 KB 以内**（应用存储单个文件上限 1 MiB、总量 16 MiB），存成 `iloveu-front.jpg`。
5. 写一个 `assets\README.md`，列出每个文件的来源和大小。
6. **这个目录的内容绝不进任何 git 仓库。**

**G11 起草平台 issue（30 分钟，只写不提交）** → `G11-issue\ISSUE.md`
- 请求开放一个**只读的单张图片选择器**：用户主动选一张照片，复制进应用存储；应用读不到相册的其他内容
- 用途：用户给一首对自己有意义的歌配上自己的照片
- 隐私：每次都由用户主动选择，不授予相册整体读取权限
- 参考 PLAN 第 10 节 G4 那份 issue 的写法

**T-main：测试 Claude 在 `main` 上的改动（Claude 推送后，Fano 通知你）** → `evidence\T-main-<日期>\REPORT.md`
1. 拉最新 `main`，跑 `tools/octo check bundle`，原文记录结果。
2. **D4 第一次相遇记录**：跑 DEMO-ILOVEU §6 的 T11、T12、T13，并检查 `accounts/device/encounters.json` 的内容和 §4.2 的格式一致、**不含坐标**。
3. **C7 规律和模板**（10-07 之后）：测试用例由 Claude 推送时写在 PLAN 里，照着跑。
4. 涉及 AI 的部分（`model.complete`）只能在桌面版（MiniMax）里测，card-host 里必然走本地规则。

**G5 每日使用记录（10-06 起，每天结束时）**
照 PLAN 第 10 节 G5：把桌面版里情境 DJ 的 `labels.json`、`history.json`，**以及新增的 `encounters.json`**，**复制**一份到 `F:\context-dj-work\evidence\G5-usage\<日期>\`，统计条数写进 `count.txt`。只复制，不修改。

## 3. 规则

- **没有亲眼观察到的，不能写"通过"。**
- 不改 `bundle/`，不推任何分支。
- 卡住超过 30 分钟就停下，把现象写进报告。
- 报告格式：做了什么 → 结果（原文引用输出）→ 没验证的 → 需要人做的。
