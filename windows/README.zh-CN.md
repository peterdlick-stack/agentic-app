# 情境音乐工程修复候选
候选源码 R1=/home/fanzhou/octosense-ws/repair-runs/context-recommend-20261004-180749，Windows入口 E1=F:/context-recommend-repair-20261004-180749。R0保留只读。

双击 E1/START.cmd 启动本地终端；策略默认P0，P1可显式选择，P2仍UNTRAINED并显示实际P0回退。手动选择场景/要求；选曲后播放20秒，反馈分别询问“此场景愿意听”和“单纯喜欢”。回车为缺失，不算不喜欢；q退出。场景状态与偏好存R1/integration/state，播放进程记录存E1；不改旧播放器或正式偏好。
E1/STOP.cmd 仅停止本轮PID、启动时间、可执行路径均匹配的播放进程。E1/RETEST.cmd 每次真正运行原34项及新增检查，不使用旧退出码；完整新日志在R1/eval/runs。

真实BPM精度、活动精度、用户收益继续待证据。P1只用估计BPM软排序，不能满足硬BPM约束。当前工具是开发反馈控制台，不是已安排的三策略正式收益试验，也没有改变旧平台界面。P2训练未执行；不新增付费模型调用。
合成协议完整正例只返回SYNTHETIC_TEST_PROTOCOL_SUPPORTED，不产生真实收益。正式评估要提供冻结协议和源证据链；来源哈希证明内容完整与相互一致，不能证明伪造记录确由真人产生。全局真实性仍需独立采集核验。

历史副本说明：eval内从R0复制的candidate-original34-exit.json等旧结果仅为历史输入，不能代表本轮结果。当前验收只引用eval/acceptance.json指向的eval/runs/<run_id>新日志。RETEST不读取旧退出码。

最终工程状态 ENGINEERING_REPAIRED（独立复验退出0，34/34零跳过）；详细命令、哈希与限制见REPORT.zh-CN.md。
