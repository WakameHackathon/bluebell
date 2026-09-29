# v1 接口合同与兼容边界

权威来源为项目中央 contracts.schema.json（1.0.0）；本目录 remedy.schema.json 是递归提取的原定义，provenance.json 记录来源与摘要。包版本 1.0.0，不接收未协商的 2.0.0。工程目录的 candidate 是提案，不是本包可用的第二协议。

传输使用 {message_type: request|result, body: ...}；body 严格按 aftercare-remedyRequest/Result。统一请求字段为 contract_version、skill_id、skill_version、call_id、task_id、expected_task_revision、mode、task_snapshot、inputs。inputs 仅 intent:TaskIntentRef、order:OrderSelectionRef、platform_view:PlatformViewRef、user_decision:UserDecisionRef|null。统一结果为 contract_version、skill_id、call_id、task_id、based_on_task_revision、status、data、questions、issues、user_message。不要在正式消息增加 host、ready、confirmed、availability 等字段。

本 Skill 的合法结果 data 始终给 RemedyPlan，包括失败时六字段空草稿；中央 Schema 也允许非 completed 时 null，但本包不需要借 null 掩盖交接状态。RemedyPlan 恰为 options、recommended_option_id、chosen_option_id、choice_receipt_ref、material_requirements、next_steps。Option 恰为 option_id、kind、explanation、conditions、consequences、missing_facts。conditions/consequences/material_requirements 是 Fact 数组；Fact 的 evidence_refs 至少一个，certainty 只能 observed/user_reported/inferred。缺证据不能造 Fact，未知事项放 missing_facts 或 issues，不造证据 ID。

Option.kind 虽允许 supplement/appeal/withdraw/accept_offer/contact_support，也不证明当前订单有对应入口。本版新申请只处理 refund_only/return_refund；换货维修 blocked/unsupported。撤销、接受处理结果等不在本包执行范围，交主 Agent 另行核验。

Issue.code 使用既有枚举：missing_input、stale_observation、target_unconfirmed、policy_unknown、needs_login、needs_consent、unsupported、ambiguous_result、budget_exhausted、contract_error、tool_failure、user_paused。不要造 code。Step 为 intent、reason、required_evidence、next_skill_hint；hint 为建议，模型不能借它调用 Skill。

## 宿主必须落实

1. 请求/结果身份、允许版本、当前 task revision、mode、pause 一致；拒绝迟到结果。解析所有引用并校验存在、类型、版本、同任务、授权、有效性，证据还须关联当前平台、账户与目标。
2. 验证上游整版意图确认及商品选择，不以 completed、空 missing_fields 或候选唯一代替。
3. option_id 唯一；推荐/选择属于 options；选择与凭证成对；从真实用户事件核验当前呈现、商品和关键内容，不信任模型自填的“有效”。
4. 规则是否适用、证据冲突、材料性质、费用与金额是否已知、下一阶段条件必须有机器可读状态。v1 的 Fact 文本不能代替这些检查。
5. 中央 v1 缺上述结构，默认禁止正式 evidence/interact 申请准备交接。可以返回解释、重新观察或返回上游建议。若用户已有有效选择但只是宿主缺机制，用 blocked/contract_error，不让用户重答代替工程修复。
6. 即使未来迁移通过，方案选择也不授权上传、提交、撤销、接受方案、客服发送或寄件预约。执行层按当时具体动作单独核验授权、页面、暂停、去重与文件范围。

本包没有运行时服务。工程 tests 的检查器仅对合成宿主夹具检验不变量；它不认证事件来源，也不证明页面语义。接入前须实现独立验证器并测试，不能把自由文本 reason 当可执行门禁。
