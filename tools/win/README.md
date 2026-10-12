# 在 Windows 原生 OctoSense（0.1.0-rc.5）上开发情境 DJ

复赛要求用最新版 OctoSense。情境 DJ 还没有被官方 App Hub 收录，在桌面版里安装它只能走官方文档里的**本地商店彩排**：把 `bundle/` 用一次性密钥签名，发布到本机的一个商店目录，再让桌面版读这个目录（[PUBLISHING.md §4](https://github.com/OctoSense-org/OctoScript-App-Design-Flow/blob/main/docs/PUBLISHING.md)）。这里的三个脚本把这件事做成了一条命令。

2026-10-11 在泛舟的 Windows 笔记本上实测通过：安装、打开、真实 AI 选歌、更新后数据保留，结果见主 README 的[验证情况](../../README.md#验证情况)。

| 文件 | 在哪里跑 | 作用 |
|---|---|---|
| `build-hub.sh` | WSL | 编译和 rc.5 配套的 `hub` 命令（App Hub `8347a489`），只需要做一次 |
| `republish.sh` | WSL | 签名并发布到本地商店；第一次运行会生成一次性密钥；版本号自动递增 |
| `start-dev.ps1` | Windows PowerShell | 让桌面版读本地商店，数据都放进同一个目录 |

## 目录布局

```
<上级目录>\                       例：F:\work\
├─ agentic-app\                  本仓库。建议检出在 Windows 盘上，WSL 里用 /mnt/f/work/agentic-app 访问
└─ context-dj-win\               本地数据，不进 git（脚本默认放在仓库旁边）
   ├─ mirror\                    本地商店（republish.sh 写入）
   ├─ anchor.pub                 商店的信任锚（公钥）
   ├─ home\                      这个 OctoSense 实例的设置，包括 AI providers 里你的 API key
   ├─ apps\                      情境 DJ 的数据：♥、相遇记录、决策日志
   └─ logs\                      每次启动的输出日志

WSL：~/.context-dj-local/
   ├─ bin/hub                    build-hub.sh 的产物
   └─ keys/                      一次性密钥（私钥，只留在本机，权限 700）
```

数据目录想放别处时：WSL 里设 `CDJ_WIN_ROOT`（WSL 写法，如 `/mnt/d/cdj`），Windows 里给 `start-dev.ps1` 传 `-Root D:\cdj`，两边必须指向**同一个目录**。

## 一次性准备

1. **装桌面版**：从 [OctoSense 的 GitHub Releases](https://github.com/OctoSense-org/OctoSense/releases) 下载 `desktop-v0.1.0-rc.5` 的 Windows 安装包，按默认装好（程序在 `%LOCALAPPDATA%\OctoSense\octosense.exe`）。
2. **WSL 里准备工具**：Ubuntu + `git` + `python3` + Rust（[rustup](https://rustup.rs)）。
3. **克隆仓库**到 Windows 盘，例如 `F:\work\agentic-app`。`.gitattributes` 已经规定 `bundle/` 的文本文件和这里的 `.sh` 一律用 LF，不用改 git 的换行设置。
4. **编译 hub**（WSL，5–10 分钟，WSL 虚拟盘上约占 1.5 GB，可以先设 `CARGO_TARGET_DIR` 到别的盘）：
   ```bash
   cd /mnt/f/work/agentic-app
   bash tools/win/build-hub.sh
   ```
   最后一行是 `OK: ~/.context-dj-local/bin/hub`。
5. **第一次发布**（WSL）：
   ```bash
   bash tools/win/republish.sh
   ```
   期望看到 `published context-dj 0.3.4-local.1 (catalog sequence 1)` 和 `catalog sequence 1 verified, 1 entries`。
6. **启动**（Windows PowerShell，在仓库目录下）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File tools\win\start-dev.ps1
   ```
   脚本会先关掉正在运行的 OctoSense。以后要用情境 DJ 都从这里启动；直接点桌面图标打开的是默认配置，里面没有情境 DJ。
7. **安装**：Dock 里打开 App Hub，列表里只有“情境 DJ”（说明读的是本地商店）→ Get → 往下滚到 Install（会列出 storage、net、web、model、location 五项权限）→ Open。第一次打开会弹应用助手的确认面板，点 Allow。
8. **配 AI**（每人用自己的 key）：AI providers → Add model。实测官方的 MiniMax 路由（`api.minimax.io`、`api.minimaxi.com`）都返回 401，能用的是 **Custom endpoint**：base URL 填 `https://api.minimaxi.com/v1`，协议保持 OpenAI，模型选 MiniMax M3。向导的密钥框会保留上次的输入，再粘贴会叠成两倍长，粘贴前先 Ctrl+A 全选。配置存在 `context-dj-win\home\` 里，不会进 git，也不要拷进仓库。

## 日常开发

1. 改 `bundle/main.splash`。界面和逻辑的快速迭代照常用 `card-host`（见 [AGENTS.md](../../AGENTS.md)）。
2. 要在真桌面版上看效果时，在 WSL 里发布：
   ```bash
   bash tools/win/republish.sh              # 发布已提交的 HEAD
   bash tools/win/republish.sh --worktree   # 或者：直接发布工作区里没提交的改动
   ```
   版本号自动变成 `<manifest 版本>-local.<下一个序号>`。
3. 重新运行 `start-dev.ps1` → App Hub → 情境 DJ → Update → Install → Open。♥、相遇记录、决策日志都会保留（2026-10-11 实测）。

`republish.sh` 只在临时副本里改版本号、盖戳、签名，**不会改仓库里的 `bundle/`**。提交 PR 前，仓库里的 `bundle/` 仍然要按 AGENTS.md 重新盖戳（`tools/octo check bundle`）。

退出这个实例：`curl.exe -s http://127.0.0.1:8399/quit`。它开着远程控制桥（端口 8399，`/snap`、`/click`、`/g?raw=1` 截图），可以用来做自动化测试；注意 OctoSense 窗口里模拟键盘输入不生效，只有点击生效。

## 常见问题

- **App Hub 里是官方应用（Repo Radar 等），没有情境 DJ**：不是用 `start-dev.ps1` 启动的，或者 `-Root` 和 `CDJ_WIN_ROOT` 指的不是同一个目录。
- **`republish.sh` 报“不是用这组密钥签的”**：密钥和商店目录不配套。不要只删一部分密钥；真要重来，就换一个新的数据目录，旧的整个放弃。
- **`republish.sh` 报 CRLF**：`bundle/` 里有文件被转成了 CRLF。运行 `git add --renormalize bundle` 后再提交。
- **WSL 里 git 报 `dubious ownership`**：`git config --global --add safe.directory /mnt/f/work/agentic-app`。
- **报 `downgrade refused`**：`apps` 目录被别的商店目录格式用过。换一个新的数据目录。
- **点“去听”只显示链接**：rc.5 的内嵌浏览器拒绝打开外部网页（`Navigation is not permitted in this embedded browser`），是宿主的策略，不是应用的错误。
- **天气显示“不可用”**：2026-10-11 实测也是这样，原因还没查，应用会如实降级、天气不参与推荐。

## 密钥和隐私

- 这里的密钥只用于本机彩排，和官方 App Hub 的提交没有关系。私钥（`*.key`）不能进 git、不能贴到聊天或报告里；`.gitignore` 已经排除了 `*.key` 和 `*.cert`。
- `context-dj-win\` 整个目录都不进 git：`home\` 里有 API key，`apps\` 里是你自己的使用数据。
