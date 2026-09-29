# 宿主接入与运行限制

本 Skill 是分析说明及纯检查器，没有本地任务数据库、浏览器、授权服务或跨会话恢复服务。完整交付中的 examples/tests 均为合成快照输入。现有 interact 内存 executor_stub 与独立浏览器装置不可当生产宿主；后者确有 SQLite dispatch/business 表，但任务、提案、确认等仍为装置内存状态，没有已核实的生产 TaskSnapshot/OperationLedger 仓库。

主 Agent 加载获准历史记录，校验存储格式/迁移版本/完整性和 lineage，建立当前 TaskSnapshot；解析仅必要记录，取得当前观察/P层/verify，再传本 Skill。结果校验后用 expected revision 比较登记新不可变产物；同任务写入互斥、当前模式/暂停与 session epoch 必须在消费和执行前再次检查。历史原件保留，不静默升级损坏记录。schema 不兼容 blocked/unsupported；引用结构/归属错误 failed/contract_error。无合法请求外壳使用宿主错误通道。

本地恢复路径还需：崩溃一致性、发送前持久化、call_id 请求摘要及缓存、业务效果去重、未知动作保留、租约过期/接管撤销、文件与授权撤销、数据迁移及失败回滚。不能由文本说明声称已实现；本包不更新数据库或发起后台检查。

`scripts/check_plan.py` 提供 `check(request_body,result_body,host)`，依赖 jsonschema。host 是宿主独立建立的只读本地验证上下文，非 wire 扩展、非模型输出。完整形状见完整交付 examples/*/host.json 与 tests/build_cases.py；registry 存中央正文及元数据，evidence 存最小出处，selection/outcome_binding/changes 等是合成见证。必须由真实宿主/适配器生成和认证，不能从待验证结果回填。脚本不识别照片/页面语义、不证明 host 的真实性。

返回 `errors`（无效计划/输入）、`blockers`（已知阻碍）、`planning_disposition`（hold/review_only/eligible_for_host_review）和 `automatic_execution_allowed=false`。这是本地诊断 API，不是新增 Result 字段。空 errors 不是执行许可；eligible 仅可送宿主审查。当前未完成生产绑定时必须 `runtime_ready=false`，不得按合成正例开启自动推进。未知/冲突/目标或版本变化默认 hold，即使模型返回 completed 也拒绝。

v1 缺机器化冲突与观察绑定，兼容策略为非 completed + 仅查证步骤 + 宿主独立阻断。完整交付 candidate/resume-v2.schema.json 和《契约修订提案.md》只用于讨论/测试；需统一协商中央新版本及所有消费者，不能自行对现行请求添加字段。
