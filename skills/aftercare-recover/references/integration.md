# 接入及实际边界

当前交付是可加载说明、纯校验代码与离线测试，不是运行中的售后执行服务。v1 wire不变；check_plan.py 的 host 为本地集成/测试上下文，不能塞入 inputs，不可由模型/网页生成后当可信见证。

已读取 interact 实际成果：InteractionPlan 仅提案，auto至多一个Action；self/guided无自动动作。executor_stub.py 仅内存 events/ledger，将 dispatch_started 后置为 simulated_sent_unknown；无真实浏览器发送、持久事务或完整 ExecutionReceipt 服务。不能把它当生产执行层。

已读取 verify 实际成果：通过平台证据和宿主关联见证区分 confirmed_success/confirmed_failure/unknown/not_attempted；check_report.py 为纯检查器，缺关联、部分成功、暂查无记录保留未知。verification-assessment 与 interact runtime-binding 均为候选，不是已部署协议。

中央Action枚举没有独立close/refresh/back操作。可逆的关闭弹窗建议仍不代表现有interact能形成正确动作；不得用navigate伪装关闭/刷新。主Agent应保留说明、请求用户操作或报告操作枚举缺口，待正式协商后接入。证据/方案/订单现有包也保留意图确认与材料版本绑定缺口，recover不能越过这些门禁。

在本次检索的项目成果中未发现可用 platform-main/secondary/sandbox Skill 或官方客服 handoff Skill。catalog的 implemented=false 是原设计快照，不能据此否认已存在的6个包，也不能据已有包宣称生产平台接通。平台适配只有契约和合成上下文；当前不开展真实浏览器业务恢复。

主 Agent：解析请求 → recover 分析 → 校验/登记计划 → 新观察/P层 → interact 当前Step及业务引用 → 执行层 → 新Observation/P层 → verify → 宿主关联实际效果。未知动作优先verify；需打开记录页时仍走interact和执行层，不能让verify直接操作。业务缺口交对应Skill，未实现接收者由主Agent保留明确待办，不伪造调用。

宿主必须用代码落实：可信引用与证据登记；不可变提案与摘要关联；发送前持久化；同任务互斥及业务实例去重；call_id摘要/缓存；预算原子扣减与截止；暂停/接管租约撤销；目标/模式/任务/页面变化失效；登记结果版本比较；计划、动作与核实效果的追踪。当前纯检查函数不实现这些服务。

check(request,result,host) 返回 errors、hold_external_write、automatic_execution_allowed=false；空errors不是许可。检查引用结构/归属、响应绑定、证据新颖性、阶段冲突、预算、停止、可逆见证和快照失效。语义见证由独立宿主/适配器核实，检查器不从DOM识别事实、不认证输入、不释放锁、不扣预算。历史和证据必须完整；缺失保守拒绝。

样例和测试见完整交付包examples/tests；请求/结果均为中央body。独立部署只需aftercare-recover目录；不全局安装。使用Python与scripts/requirements.txt列出的依赖；测试只读并在指定输出目录写结果。生产接入前落实交付目录的契约修订提案与宿主待实现项，版本协商后再开启自动业务推进。
