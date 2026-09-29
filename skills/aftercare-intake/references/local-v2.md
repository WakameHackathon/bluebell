# 本地确认接口 2.0.0

本项目最小修订，来源为 v1 原定义加工程 candidate/build_schema.py 的显式补丁；不修改全局 contracts.schema.json。仅当请求 contract_version=2.0.0 且宿主解析配置 profile=local-intake-v2 时使用，skill_version=1.2.0。其他 v2 宿主必须明确协商同一接口，不凭模型自行推断支持。

请求与结果根名称仍为 aftercare-intakeRequest/aftercare-intakeResult，字段见 intake-v2.schema.json。请求 inputs.intent_confirmation_ref 必填，可 null；结果顶层 intent_confirmation_ref 必填，非 completed 时必须 null，completed 时必须引用宿主既有确认记录。

TaskIntent 保留原五字段，新增 source_turn_refs（UserTurnRef 数组）与 goal_evidence_refs（已登记证据 ID 数组），都不可为空。宿主提供 turns 与 evidence 映射；不把 event_id 自动当 evidence_id。user_facts 仍逐项标 user_reported。新增 requested_outcome=retain_item，仅表示保留商品/不再推进原退款，不授权撤销平台申请。

理解尚不完整时可 needs_user + data=null；已有有据事实可带草稿。准备复述确认时，先形成规范化草稿，status=needs_user，questions 询问理解是否正确，intent_confirmation_ref=null。data.missing_fields 只列业务未决项（例如 target_item、platform_options）；确认状态在外壳表达，不写 intent_confirmation/confirmation_binding，避免确认后删除字段导致摘要变化。影响理解的 intent_meaning、scope_item 等必须先澄清；订单定位与平台可用办法可以留给后续。

宿主保存草稿不可变版本并向用户呈现原始依据、简短复述与完整结构化内容。用户通过本地确认控件回答后，宿主记录真实事件并产生 IntentConfirmation：意图引用、版本、摘要、呈现事件、用户输入事件、任务与修订均绑定。UI 单次凭证不会提供给模型。收到“需要纠正”或新的用户消息时，宿主先使旧确认失效，再继续分析。

后续请求解析内容包含 intent 与 intent_confirmation 时，逐项检查它们是否对应当前任务和请求确认引用；只在没有新纠正且同一已确认版本时返回 completed，原样保留被确认 data。结果 questions/issues 必须为空。不得根据自由文本“对”自行创建确认凭证，不能修改 goal 或删改 missing_fields 后仍使用旧凭证。

宿主负责最终摘要与当前状态校验，即使模型错误返回 completed 也不会放行。该协议仅完成意图交接。SQLite 本地适配器和模拟 S02/S03 在工程 local_host/；真实生产 Agent、平台方案与执行工具未实现。
