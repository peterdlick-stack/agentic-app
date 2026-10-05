# Developing this OctoSense app

> **Any coding agent, or none.** These instructions work the same for Codex, Claude Code, Cursor, Gemini CLI, GitHub Copilot or a person at a terminal: every step is a shell command or a file edit, and nothing here needs a particular agent, model or vendor. `AGENTS.md` is the one source of truth; `CLAUDE.md` and `GEMINI.md` only import it for agents that look for those names.

This repository is one OctoSense script app. `bundle/` is the app and the only
thing submitted to the App Hub; everything else stays outside it.

Follow the harness, and do not invent requirements or APIs:

- How to build, run and test: [QUICKSTART](https://github.com/OctoSense-org/OctoScript-App-Design-Flow/blob/main/docs/QUICKSTART.md)
- The language and every API an app may use: [SCRIPT-API](https://github.com/OctoSense-org/OctoScript-App-Design-Flow/blob/main/docs/SCRIPT-API.md)
- Capabilities: [CAPABILITIES](https://github.com/OctoSense-org/OctoScript-App-Design-Flow/blob/main/docs/CAPABILITIES.md)
- Publishing, step by step, with the human checkpoints: [PUBLISHING](https://github.com/OctoSense-org/OctoScript-App-Design-Flow/blob/main/docs/PUBLISHING.md)

The loop, with `OCTO=<path to OctoScript-App-Design-Flow>/tools/octo` (the CLI
lives in the harness repository, not here), run from this directory: edit
`bundle/main.splash` → `$OCTO run bundle --port 8141 --detach` → drive it
(`/click`, `/t`, `/snap`) and `$OCTO shot 8141 out.png` → `curl -s 127.0.0.1:8141/quit`
→ `$OCTO check bundle`.

Rules:

- Ask only for capabilities a screen uses; declare every `https://` host in
  `network.hosts`; never `http://`.
- Never collect a password, PIN or code; accounts go through a host service.
- Screenshots are real captures you looked at. Never a dummy.
- Restamp after every edit (`tools/octo check` does it). After signing, any
  edit needs a new stamp and signature.
- Keys, `.local-state/`, `build/` and review packets never enter `bundle/` or git.
- Stop at human steps: publisher key, publisher details, platform claims, submission.

Add this app's own requirements, data sources and tests below.

## 本应用

- 设计、接口、阈值：`docs/PLAN.md` 第 2 节（v0.2）。数据存放在 `accounts/device/`（prefs、library、feedback、history、last）；地点 `places.json` 放在存储根目录，应用助手读不到。
- 反馈分按活动读写时，必须用 `fb_get` / `fb_set` 访问固定字段。不要写 `f[id] = v`：运行时会追加一个重复键，而不是覆盖原来的值（已实测）。
- 判断意图时，"不要人声"包含"要人声"：先匹配"要人声"，再用"不要人声"覆盖。
- `card-host` 中没有 `model` 服务，也没有 Linux 上的内置网页，这两条路径必须在 Shell 或真机上验证。
- 读取已保存的数据时一律用 `pick(o, key, 默认值)`：直接访问不存在的字段会报错，并中断整个处理函数（已实测）。
- `ok` 是保留字，不能用作对象的键（`{ok: true}` 会解析失败），本应用改用 `valid`。
- `card-host` 中没有 GPS：用"感知"页的模拟定位测试，界面会一直显示模拟提示，历史里也记 `sim: true`。
- 每个处理函数最多执行 20 万条指令（已实测会触发）。定位轮询的计算量随窗口内的点数增长，修改 `GPS_POLL_S` 或 `WIN_S` 之前，先算一下最坏情况的点数。
- 启动加载必须分批（`run_chunks`）：500 条确认记录一次性读入，会超过 20 万条指令的上限（已实测）；曲库、反馈也会随使用增长。新增会增长的数据文件时，照同样的方式分批读。
- 原话里说明的情境或 AI 判断出的情境，会在同一情境桶里沿用 30 分钟（`session_act`），保证情境卡和歌单显示同一个活动。
