# 情境音乐推荐：工程修复报告

最终状态：ENGINEERING_REPAIRED。冻结v2.1经新只读代理独立实跑通过；真实研究结论不升级。

R1 `/home/fanzhou/octosense-ws/repair-runs/context-recommend-20261004-180749`；E1 `F:/context-recommend-repair-20261004-180749`。R0原候选只读，81冻结文件实际复核不变。两个新目录创建前确认不存在；R1位于ext4，E1位于exFAT/WSL 9p，初始可用空间分别约796/1237GiB。复制小体积源码、原测试、夹具与协议约45MB，没有复制23GB曲库或整个平台。

## 已修复内容

1. **环境和连接释放。** 原F盘不支持该符号链接操作；测试临时根改用R1原生ext4，没有修改Windows设置。独立损坏数据库探针另外证实生产FeedbackStore初始化异常后连接仍打开，不能将旧ENOTEMPTY全部归于文件系统。修复仅在初始化异常时关闭连接并重新抛出；真实损坏字节及异常类型保持。修前3项中2失败，修后3项全过。原34项及全部夹具字节不变，feedback.py获授权修改的前后SHA与统一差异单列ledger/differences.json。
2. **P1软排序。** 删除context_evidence布尔首排序键，保留原权重；静止明确回P0。实际rank固定反例现为未知BPM/+100的0.34313725排在BPM60/-100的0.21686275之前。原17项保留、新增6项；A独立审B通过后恢复P1。默认P0，P2仍UNTRAINED并明确回P0；估计BPM不会满足硬约束。
3. **收益协议。** 核验开发原始会话记录复算方差/N、生产训练bundle资格与模型绑定、预注册seed平衡次序、每策略6曝光/无重复、共享版本、实际策略与预测→快照→曝光→反馈引用/哈希/时间/更新链。重复训练曝光、变更版本、伪N/方差/冻结时间、未来标签、选择性删会话等返回明确原因。旧5项保留，仅授权的“合成输入必须抛异常”断言改为结构化不足；新增47项覆盖合法正例、单项负例、独立参考数值及边界。有效低收益数据可通过协议但不通过数值；合法合成数据仅TEST_ONLY，未用永不通过开关。

## 实际验证

- 原34：当前候选真实子进程执行34/34、零跳过、退出0。命令为 `python3 -B -m unittest discover -s context_player/tests -p 'test_*.py' -v`，cwd是R1/integration。每次RETEST都重新执行；保存当前命令、起止时间、退出码及源码hash。
- 主进程和从test-fixtures cwd启动的子进程，backend/feedback均实际导入R1/integration/context_player，按PID记录路径与SHA。唯一候选Finder防夹具源码抢先。
- learner23、audio7机制检查、metrics5、protocol47、资源3均退出0；五类负对照各为0→1→0。旧活动22诊断只按哈希保留，本轮未重跑活动算法；已有评分行分母/混淆矩阵做了新复算，退出0。
- 临时/符号链接/SQLite创建关闭清理及写入守卫正负探针通过。仅子进程设置TMP/TEMP/TMPDIR/XDG路径，HOME不变，无源码pycache。Python审计守卫覆盖R1/E1以及SQLite连接；它不是任意原生程序的内核沙箱。
- 原生2秒静音播放、START输入q退出、精确PID/启动时间/可执行路径匹配STOP、空闲STOP均退出0。另真实production compare.select→play→E1脚本→FFplay一路实跑退出0。人的实际听感未核验。首次PowerShell退出码句柄丢失的失败记录保留；持有Handle后复测通过。
- 专用副本中故意损坏生产FeedbackStore初始化，使总验收退出1，原34当前子进程也退出1；恢复同一副本后总验收退出0、原34退出0。冻结交付未被注入损坏，完整日志见ledger/engineering-red-green.json。

## 冻结与结论边界

R1源码/配置/特征/模型共81个hash已冻结，R0旧81个hash单独核对；两者数量相同不代表内容相同。逐文件源码白名单与差异清单保留，测试运行的随机临时文件限定预登记运行目录并做清单。旧34/夹具/契约原文不改；修复例外见repair-amendment.md。

FEATURES_ESTIMATED、ACCURACY_UNVERIFIED、NO_USER_BENEFIT_EVIDENCE继续保持；停止于研究部分AWAITING_USER_EVIDENCE。没有真人反馈、不训练真实P2、不做音频再提取、不操作手机、不新增依赖或付费模型，JEV_NOT_RUN仅信息说明。
来源工件哈希能核对完整性和引用一致性，不能独自证明一套自洽伪造记录来自真人；正式收益结论仍需要可信采集和独立核验。界面未盲测，结果作用范围仅该用户和已测场景。交付为独立本地控制台，旧平台界面未修改或声称已闭环验证。

独立审查补丁：首个冻结版在非字符串字典键和超大整数输入下可能抛异常。已由作者最小修复并补完整API回归（9个键类型子例、2个数值API例），分别保留修前RED与修后GREEN；当前为工程v2.1，旧v2源哈希及专用副本仍保留。数值门槛和方差计算未改。

最终独立验收：verify.py实际退出0，run `acceptance-a9e70a3254384b9eb3d9dedd17b669a7`，耗时11.96秒；12个当前验收项均退出0。原34/34零跳过，协议47项。审查者未参与实现，独立反例、正常与低收益输入、边界修复均通过。完整审查结论见ledger/independent-review.md。工程修复到此停止；研究停于AWAITING_USER_EVIDENCE。
