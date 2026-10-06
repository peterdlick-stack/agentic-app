# G14 歌曲故事 AI

从 main `cf9cc9b` 开发，分支 `feat/story-ai`；本变更不修改推荐逻辑。

第 3 页按需调用 MiniMax-M3 的服务端 web_search。只发送歌名、歌手和本机已有的歌词；异步结果按歌曲键缓存，空结果和失败也缓存。已有故事不再请求，失败只能手动重试。

## 本机配置

应用存储 `accounts/device/ai.json` 放置 `base_url`、`key`、`model` 三个字符串；本轮验证的 base_url 为 `https://api.minimaxi.com/anthropic`，model 为 `MiniMax-M3`。只接受该域名的 `/anthropic` 或 `/v1` base_url。配置由用户在本机管理，绝不提交真实文件或凭据。缺失、不可读或格式不合要求时静默关闭。修改配置后重启应用。

`net` 能力原已具备，manifest 只新增 `api.minimaxi.com` 域名。`api.minimax.cn` 在本机脚本运行时发生 TLS unexpected EOF，改用 MiniMax 原国内域名后真实调用成功；不关闭 TLS 校验、不经过中转服务。

## 验证与边界

使用仓库 AGENTS.md 的 tools/octo check、run、截图接口。G14 REPORT 和无歌词截图保存在本地交付目录，由 Fano 转交 Claude，材料不进入 bundle 或 Git。

- 检索 trace 必须含真实返回的 URL；archive 再过滤字段、空 URL 和未在本次检索结果出现的网址。网址出现不代表事实已经核实，正文质量仍需人工抽查。
- 宿主 parse_json 容忍坏 JSON，应用增加规范化后重新序列化比对；坏 JSON 不会作为成功缓存。
- UI 总超时 120 秒。宿主脚本 HTTP API 未提供取消函数，超时后不接收迟到结果；底层传输未结束时，同首歌的重试不另发请求，以维持单请求约束。底层返回后可重试。永久无回调的情况需退出重启；该限制交 Claude 审查，不宣称传输层超时已解决。
- cards 只在启动完成后写，序列化与磁盘写分开；写入 watchdog 会重试。未做磁盘满、进程强杀时写入原子性或大曲库压力验证。
- 对旧 story.reading 和 archive 对象保持兼容。旧 archive 对象按旧显示方式处理；新数组条目必须有来源网址。

§8 的新版预制数据单独交付。Fano 已确认审查通过、升级应用时再替换日常版与录制目录，保留 cf9cc9b 可用回退。

不得自行合并 main。21:30 为测试闸门；审查通过后由 Fano 决定是否合并，最晚 23:00。
