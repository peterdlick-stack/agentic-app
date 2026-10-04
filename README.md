# 情境音乐推荐 · 工程修复归档 v2.1

状态 ENGINEERING_REPAIRED：当前原34项全部通过、零跳过，独立总验收exit0；P1软排序恢复，收益协议正负/边界机制验证通过。真实BPM/活动精度及推荐收益仍未证实，研究状态AWAITING_USER_EVIDENCE。

- candidate/：冻结源码、原测试和合成夹具元数据（不含任何音频）、特征侧表、协议、分支RED/GREEN记录、最终独立验收运行日志。
- windows/：本轮已验证的START/STOP/RETEST及播放脚本、报告。
- evidence/full-control/：专用副本故意损坏→恢复的完整验收日志及原34新执行凭据（1→0）。
- FILES.sha256.json：所有归档内容的逐文件SHA256；.gitattributes禁止Git自动改换行。

这是当前环境的精确作品快照，不是免配置安装包。源码和入口保留已验证的绝对路径：
R1=/home/fanzhou/octosense-ws/repair-runs/context-recommend-20261004-180749
E1=F:/context-recommend-repair-20261004-180749
原库=F:/context-player-cache-20261004/library

未包含真实歌曲、手机原始记录、Python/NumPy/FFmpeg运行时、账号/密钥、运行状态数据库或耗时测试临时副本。遵守禁止上传音频的限制，远端连24份CC0合成WAV也排除；夹具元数据和许可保留。原34项复跑需使用本地完整ZIP中的合成夹具，本远端源码包不能单独满足音频测试依赖。恢复到其他机器需先按实际环境适配路径和只读依赖并重新验收，不能把归档已有exit0当作新环境已通过。

本地提交使用自动身份 Codex Archive <codex-archive@localhost>，不冒充用户作者，不修改全局Git身份。目标远端 https://github.com/peterdlick-stack/agentic-app 。本提交不含音频或个人原始记录。

验收还依赖只读R0历史基线 F:/context-recommend-v1-20261004-154611；归档是工程成果及证据快照，不声称在全新机器免配置运行。
