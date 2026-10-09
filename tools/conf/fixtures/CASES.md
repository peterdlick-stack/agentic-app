# 假模型用例

全部是合成夹具。索引从 0 起；错误位置 pick 从 1 起，0 表示顶层错误。
基线 `9919c0f` 的 SEED 实际有 **46** 首，语种值为 `zh/en/instr`。

`cases.json` 固定前置条件、每轮错误位置和引用、回调配对、最终 res 与提示。
下表的错误码比较按集合；每个错误的 pick/ref 另按 cases.json 核对。不要依赖错误数组顺序。

## 逐案执行

1. 只在测试副本打开 DEV_FAKE_MODEL；原工作树保持 false。
2. 运行 `python tools/conf/fixtures/verify_fixtures.py --export-case <id>`。
   生成 `tools/conf/fixtures/generated/<id>/`，内含该案 dev_fake_model.json、仅用户追加歌的 library.json、feedback.json 和 setup.json。
3. 给每案一个新的测试 accounts/device 目录，导入导出的三个数据文件；不要把 catalog.json 写成 library.json，否则会把内置曲库重复追加。
4. 以 setup.json 的 prefs/motion/here/ctx/raw 设置测试场景。setup 的 it 是 parse_intent 预期值，不可替换生产解析器以绕过测试。
   默认先确认“散步”，天气与 GPS 关闭，时间开；在测试副本启用 sim（全部测试事件必须 sim:true）。
   catalog_changed 另在请求发出后、回调前交换 songs[0] 与 songs[1]；仅此案允许该测试动作。
5. 冷启动或显式重置假队列读指针，发起一次推荐，核对 rec 事件、歌单、提示，再截图。
6. late_100s/retry_late_100s 等待至少 105 秒并确认只有一个 rec 事件；迟到回调不得改歌单或提示。
   invalid_60s 的等号边界须在单元层固定 ms1=60000，不能用有抖动的 UI 秒表判失败。

**禁止把整个 fake_model.json 直接连续播放来验证所有场景。** 每案的上下文和调用次数不同，必须先按 id 导出。
`fake_model.json` 是索引化回调总表，按 cases.json 的 queue_offset/queue_count 切出一案后才顺序消耗。

local_* 回退的具体排序有随机抖动，不固定歌曲顺序；检查数量、唯一性及仍在当前可选曲库即可。
ai/ai_retry 的歌曲顺序则必须与 playlist_indices_exact 一致。

## 场景与期望

| id | 场景 | e1 | e2 | 模型调用 | res |
|---|---|---|---|---:|---|
| `valid_6` | 合法六首 | — | — | 1 | `ai` |
| `count_5` | 只有五首；重试补为六首 | E_COUNT | — | 2 | `ai_retry` |
| `duplicate` | 六项中重复同一索引 | E_DUP | — | 2 | `ai_retry` |
| `range_high` | 索引等于曲库长度（46） | E_RANGE | — | 2 | `ai_retry` |
| `range_negative` | 负数索引 | E_RANGE | — | 2 | `ai_retry` |
| `range_fractional` | 非整数索引 | E_RANGE | — | 2 | `ai_retry` |
| `hard_vocal` | 纯音乐硬条件排除的人声歌曲 | E_HARD_VOCAL, E_NOT_ELIG | — | 2 | `ai_retry` |
| `hard_lang` | 英文硬条件下选了中文歌 | E_HARD_LANG, E_NOT_ELIG | — | 2 | `ai_retry` |
| `ref_enum` | 引用不在 EV 枚举里 | E_REF_ENUM | — | 2 | `ai_retry` |
| `ref_weather_absent` | 天气不可用却引用 weather | E_REF_ABSENT | — | 2 | `ai_retry` |
| `ref_mood_mismatch` | 开心意图引用了平静曲目的情绪 | E_REF_MISMATCH | — | 2 | `ai_retry` |
| `ref_no_context` | 每首证据缺少情境类 | E_REF_KIND | — | 2 | `ai_retry` |
| `ref_no_song` | 每首证据缺少歌曲类 | E_REF_KIND | — | 2 | `ai_retry` |
| `ref_like_mismatch` | 无正反馈却引用 history.like | E_REF_MISMATCH | — | 2 | `ai_retry` |
| `why_long` | 理由 31 个 ASCII 字符，避开中文长度歧义 | E_WHY | — | 2 | `ai_retry` |
| `why_empty` | 理由为空 | E_WHY | — | 2 | `ai_retry` |
| `status_invalid` | status 不在枚举中 | E_STATUS | — | 2 | `ai_retry` |
| `insuff_false` | 可选曲目足够却声称不足 | E_INSUFF | — | 2 | `ai_retry` |
| `json_not_object` | output 是字符串而非对象 | E_JSON | — | 2 | `ai_retry` |
| `json_missing_field` | 缺少必需的 understood | E_JSON | — | 2 | `ai_retry` |
| `retry_success` | 首轮五首，第二轮六首 | E_COUNT | — | 2 | `ai_retry` |
| `retry_exhausted` | 两轮都是五首，最多重试一次 | E_COUNT | E_COUNT | 2 | `local_fail` |
| `network_first` | 首轮网络失败，不重试 | — | — | 1 | `local_net` |
| `invalid_70s` | 70 秒返回不合格，不重试 | E_COUNT | — | 1 | `local_fail` |
| `late_100s` | 100 秒返回合法结果，90 秒看门狗先回退 | — | — | 1 | `local_timeout` |
| `valid_70s` | 70 秒返回合格结果，正常采用 | — | — | 1 | `ai` |
| `invalid_60s` | 重试门槛等号：60 秒不合格仍重试 | E_COUNT | — | 2 | `ai_retry` |
| `retry_late_100s` | 第二次尝试也有独立 90 秒看门狗 | E_COUNT | — | 2 | `local_timeout` |
| `catalog_changed` | 曲库长度相同但键顺序改变，不重试 | E_CAT | — | 1 | `local_fail` |
| `local_insuff_0` | 纯音乐与英文语种交集为空，不调用模型 | — | — | 0 | `local_insuff` |
| `local_nomodel` | 无模型服务，直接本地规则 | — | — | 0 | `local_nomodel` |
| `unknown_metadata_retained` | vo/lg 为 null 的用户歌曲保留；正反馈可作歌曲证据 | — | — | 1 | `ai` |
| `ref_song_absent` | 歌曲 en 为 null 却引用 song.energy | E_REF_ABSENT | — | 2 | `ai_retry` |
| `injection_intent` | 意图内指令仅作数据 | — | — | 1 | `ai` |
| `injection_song_title` | 用户歌名内指令仅作数据 | — | — | 1 | `ai` |
| `injection_url_why` | 理由网址只以纯文本显示 | — | — | 1 | `ai` |
| `injection_outside_index` | 注入使假模型输出库外索引仍被拒绝 | E_RANGE | E_RANGE | 2 | `local_fail` |

## 界面提示

| res | 期望提示 |
|---|---|
| `ai` | AI 选歌 |
| `ai_retry` | AI 选歌（第一次输出没通过检查，已重新生成） |
| `local_fail` | AI 结果没通过检查（<首个错误码中文说明>），改用本地规则 |
| `local_net` | AI 不可用：fixture-network-error |
| `local_timeout` | 这次选歌没有完成（AI 没有响应或读写太慢），可以再试一次 |
| `local_insuff` | 按你说的「不要人声，英文歌」，曲库里只有 0 首符合 |
| `local_nomodel` | 本地规则 |

local_fail 的首错误中文说明由 A 的映射表给出；若同一首同时违反可选集和硬条件，两个码都要记录。
状态、JSON 顶层和越界索引错误不继续访问无法判定的歌曲字段，以免产生无依据的连带错误。
`network_first` 不做输出校验，`late_100s` 的过期结果不做输出校验。
`catalog_changed` 优先返回 E_CAT，无论候选键仍在曲库里都不得采用旧索引结果。

`local_insuff_0`/`local_nomodel` 不调用模型，但日志格式 att 只有 1|2，因此 expect.attempts_logged=1；实际调用数为 0。

## 固定曲库索引

| i | 歌曲键 | en | vo | md | lg |
|---:|---|---:|---|---|---|
| 0 | I LOVE U · 洛天依 | 4 | true | 欢快 | zh |
| 1 | Summer · 久石让 | 3 | false | 欢快 | instr |
| 2 | One Summer's Day · 久石让 | 1 | false | 怀旧 | instr |
| 3 | Nuvole Bianche · Ludovico Einaudi | 2 | false | 平静 | instr |
| 4 | Experience · Ludovico Einaudi | 3 | false | 振奋 | instr |
| 5 | River Flows in You · Yiruma | 1 | false | 平静 | instr |
| 6 | Gymnopédie No.1 · Erik Satie | 1 | false | 平静 | instr |
| 7 | Clair de Lune · Debussy | 1 | false | 平静 | instr |
| 8 | Cello Suite No.1 Prelude · J.S. Bach | 2 | false | 专注 | instr |
| 9 | On the Nature of Daylight · Max Richter | 1 | false | 伤感 | instr |
| 10 | Aruarian Dance · Nujabes | 2 | false | 专注 | instr |
| 11 | An Ending (Ascent) · Brian Eno | 1 | false | 平静 | instr |
| 12 | Time · Hans Zimmer | 3 | false | 振奋 | instr |
| 13 | Merry Christmas Mr. Lawrence · 坂本龙一 | 2 | false | 怀旧 | instr |
| 14 | 琵琶语 · 林海 | 1 | false | 平静 | instr |
| 15 | Waltz for Debby · Bill Evans | 2 | false | 温暖 | instr |
| 16 | 晴天 · 周杰伦 | 3 | true | 怀旧 | zh |
| 17 | 稻香 · 周杰伦 | 3 | true | 温暖 | zh |
| 18 | 双截棍 · 周杰伦 | 5 | true | 振奋 | zh |
| 19 | 十年 · 陈奕迅 | 2 | true | 伤感 | zh |
| 20 | 孤勇者 · 陈奕迅 | 4 | true | 振奋 | zh |
| 21 | 倔强 · 五月天 | 4 | true | 振奋 | zh |
| 22 | 突然好想你 · 五月天 | 3 | true | 伤感 | zh |
| 23 | 消愁 · 毛不易 | 2 | true | 伤感 | zh |
| 24 | 平凡之路 · 朴树 | 3 | true | 怀旧 | zh |
| 25 | 成都 · 赵雷 | 2 | true | 温暖 | zh |
| 26 | 贝加尔湖畔 · 李健 | 1 | true | 平静 | zh |
| 27 | 光年之外 · 邓紫棋 | 3 | true | 振奋 | zh |
| 28 | 江南 · 林俊杰 | 3 | true | 温暖 | zh |
| 29 | 红豆 · 王菲 | 2 | true | 温暖 | zh |
| 30 | 有何不可 · 许嵩 | 3 | true | 欢快 | zh |
| 31 | 云烟成雨 · 房东的猫 | 2 | true | 平静 | zh |
| 32 | 演员 · 薛之谦 | 2 | true | 伤感 | zh |
| 33 | 爱人错过 · 告五人 | 4 | true | 欢快 | zh |
| 34 | Don't Stop Me Now · Queen | 5 | true | 欢快 | en |
| 35 | Eye of the Tiger · Survivor | 5 | true | 振奋 | en |
| 36 | Believer · Imagine Dragons | 5 | true | 振奋 | en |
| 37 | Get Lucky · Daft Punk | 4 | true | 欢快 | en |
| 38 | Viva la Vida · Coldplay | 4 | true | 振奋 | en |
| 39 | Shake It Off · Taylor Swift | 4 | true | 欢快 | en |
| 40 | Don't Know Why · Norah Jones | 1 | true | 温暖 | en |
| 41 | Paris in the Rain · Lauv | 2 | true | 温暖 | en |
| 42 | Wake Me Up · Avicii | 4 | true | 振奋 | en |
| 43 | Blinding Lights · The Weeknd | 5 | true | 欢快 | en |
| 44 | Happy · Pharrell Williams | 4 | true | 欢快 | en |
| 45 | My Funny Valentine · Chet Baker | 1 | true | 伤感 | en |

## 验证边界

Python 验证器只证明夹具内部一致和基线索引一致，不证明 Splash 守卫、宿主定时器或 UI 已通过。
本 T 任务未启动 card-host，未调用模型，也未生成截图。A/INT 必须实际运行并把截图及事件结果写入各自报告。
