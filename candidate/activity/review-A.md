# C → A 只读交叉审查

检查时 pilot 仍在运行；未修改 A 文件、未运行 A 的写入入口。审查覆盖 extract.py、run_audio.py、test_extract.py、README.md，并在 C/tmp 建1帧短 WAV 调用只读 extract，实际返回 FAILED 且4字段均null，probe exit0，见 review-A-probe.log。

通过项：按完整 WAV 字节 SHA256 关联；未以文件名或合成音频作为真实人声标签；vocal 一律null。采样区间明示，30秒段内独立节奏分析，没有拼段周期伪影；RMS按通道平方均值避免反相抵消。失败保留null/原因。全部特征含单位、版本、来源、kind、未校准quality；ACF非概率。真实BPM真值不存在，因此不开硬约束、不报真实命中率。JSON写边界限制audio；launcher子进程超时1790秒、临时与缓存在分支。

需要作者处置的可复跑可靠性问题：
1. manifest存在时完全信任旧content_id，未在提取前核验源字节；源文件原地变化会把新音频特征错误关联到旧内容哈希。README提示使用者复核不能防止实际入口误关联。建议提取每个将处理的文件前重算并拒绝不符；已有features复用前也应有冻结输入核验/明确失败机制。
2. 初次544曲全文件哈希阶段不检查budget_seconds，且完整inventory结束前没有manifest检查点；外层1790秒可止作业，但超时失去已完成inventory进度。建议每曲检查预算并保存部分清单，完整盘点结束才按哈希选48；不得拿不完整清单做试点。

不是准确度通过：pilot/全量覆盖与真值门槛待实际产物核对；没有独立封存≥30有标签曲目。本审查不将机制测试升级为精度证据。

复审：A iteration2已加入源哈希校验与逐曲inventory断点，方向解决上述两点。追加要求：预算中断resume核验时必须exit2且报告verified条数，不能因旧features已齐就exit0；已通知作者。最终产物核验待A实际完成。
