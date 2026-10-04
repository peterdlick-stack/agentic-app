# C 收益协议修复结果

工程实现已完成。API仍为 pilot_metrics(rows, plan)；空缺、NaN/无穷、非法类型或不完整证据返回 NO_USER_BENEFIT_EVIDENCE 和 reasons，不靠异常替代检查。正式真实资料仍为不足；未生成任何真实试验结果、训练新P2或调用付费服务。

旧冻结数值未变：6次/策略/会话、seed 20261004、10000次会话配对bootstrap、缺失<=20%、P2-P0>=10pp、收益与最不利缺失下界>0、打扰上界<=0。完整合法合成夹具返回 SYNTHETIC_TEST_PROTOCOL_SUPPORTED，real_benefit_supported=false；真实来源分支可达并由结构测试覆盖，故无全局永远不通过开关。所有本分支测试均为合成机制检查，单元测试内构造的real_user字段只测分支，不是真人证据，不会写入正式效果报告。

协议证据包按 protocol-schema.md 冻结，review后追加 protocol-addendum-v2.1.md：源工件摘要与内容、独立开发6会话原始曝光复算方差/N、生产EvidenceStore训练bundle完整链及资格复算、生产model文件哈希/参数/转换/权重及独立创建时点记录、预注册session IDs/随机排程/版本、预测-快照-曝光-反馈引用/摘要/时间、每策略独立更新状态、完整会话集合及独立unit隔离。模型哈希和训练摘要与实际model.train字段兼容，不额外训练模型。

来源检查核验原始记录和工件之间的一致性；没有外部签名信任根，任何离线程序都无法仅凭完全伪造且自洽的工件证明真人真实性。因此报告明确此边界，不把provenance字符串、合成数据或摘要当人类真值。

## 实测
当前候选经guarded launcher：
- python3 -B -m unittest discover -s eval -p test_metrics.py -v：5项通过、0跳过、exit 0。
- python3 -B -m unittest discover -s eval -p test_protocol.py -v：44项通过、0跳过、exit 0。
- 逐项N/20%/10pp/收益下界/最不利下界/打扰上界低等高边界独立检查，其余门槛保持合法。每数值门槛另测NaN、正负无穷和非法类型。
- 独立参考重新分组计算接受率、均值、逐次bootstrap与线性分位数，复核P2-P0/P2-P1/缺失最不利/打扰区间。参考首次揭露输入会话顺序影响固定随机数结果；改为按session_id排序，复查一致并加行序不变测试。
- 正向完整合法协议、伪次序、缺资格/训练过晚/P2回退、变要求/跨版本、孤立/重复曝光/重复内容/非6次、快照篡改/未来反馈/未来标签更新、缺失过多、删会话、伪N/方差/冻结时间、开发重叠、重复训练曝光、独立unit改名绕过、来源摘要/内容/缺失/类型均有专项检查。

red.log保留旧5项中的synthetic异常断言失败：旧断言要求抛ValueError；按本轮明确授权改为structured不足并核验evidence_bundle_missing。其它4项原意保留，原34项不触碰。初次shell外层退出码记录受PowerShell展开影响不能当验收；green.log最终两次使用Python subprocess.returncode直接保存真实命令和exit 0。

B已只读交叉审查独立12反例；最终小改（dev content_id合法哈希与畸形字段路径原因）通知B补核。C对A只读独立复跑3资源释放测试exit 0，见review-A.md。首次reviewer临时目录未建导致导入前错误也保留，创建本轮允许目录后通过。

本分支不声称真实BPM/活动精度或用户收益。缺真实材料继续 NO_USER_BENEFIT_EVIDENCE，工程验收由主代理与新的独立审查统一判定。

## 当前源码SHA256
eval/metrics.py cbfea55f6fdb24b2635b35cb0b9134e5951cd438536e566d16cc4b62a586affe
eval/test_metrics.py 96ced807e284cdbdbdfcf7b6e9c20f4c9f65b23608af7f7abc1ab4576d820045
eval/test_protocol.py 0e5cdfd7b12944763e8b274156efac73258fcedeb8bcfbb119ea453611f5f73a

Independent review found non-string dict keys reached str.endswith after recording invalid_key. Reproduced full API regression: 45 tests, 9 new subcase errors, exit 1 in red.log. Minimal fix descends into the invalid-key value then skips string-key-specific checks (two lines); no threshold/algorithm change. Full guarded metrics5 + protocol45 pass exit 0, including int/None/tuple keys at plan/row/source depths.
eval/metrics.py SHA256 a3c48b4694020be171332151ce739b771b2d3b68d285d999ee3e2e30393baa18
eval/test_protocol.py SHA256 18dd5a21e29d2e59fe48e00720f5170076263f9c7bb3ebf5fb5f003fbaea737c

Independent review huge-integer boundary: numerical_gates valid stats with p2_p0_difference=10**1000 and freeze_sample_size([10**1000]*6) each raised OverflowError. New two production-API regressions reproduce RED: 47 tests, 2 errors, exit1. number() now catches only OverflowError from finite representation and returns False; no threshold or variance-algorithm change. Guarded metrics5 + protocol47 GREEN exit0, zero skips. Implementation frozen, no further expansion.
eval/metrics.py SHA256 6efa238cc463462cc24655d4aaeb87963f02ab794c57a7d5ae1530517812fd21
eval/test_protocol.py SHA256 32ed8ddb14a1b0a5a36a49659b496ca9763c385e4c02b314994e583dd646b35e
