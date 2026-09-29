# 当前契约与实现边界

权威来源是项目 `售后Agent-Skills接口-v1/contracts.schema.json`，版本 1.0.0；本 Skill 包版本 1.0.0。请求字段为 `contract_version, skill_id, skill_version, call_id, task_id, expected_task_revision, mode, task_snapshot, inputs`。`inputs` 恰含 `outcome: OutcomeReportRef`、`ledger: OperationLedgerRef`、`platform_view: PlatformViewRef`、`evidence: EvidenceBundleRef|null`。结果外层为 `contract_version, skill_id, call_id, task_id, based_on_task_revision, status, data, questions, issues, user_message`。`data` 在完成时是六字段 `HandoffDraft`：`official_channel_ref|null, summary, timeline_evidence_refs[], unresolved_questions[], message_draft, file_refs[]`。空 `file_refs` 合法；不额外增加属性。

中央 Schema 的 status 条件要求 completed 有非空 HandoffDraft 且 questions/issues 为空；needs_user 至少有一个 Question；needs_observation/blocked/failed 至少有一个 Issue。Issue.code 只能使用中央枚举。没有合法身份外壳时由宿主错误通道处理，不编造 call/task ID。

`OutcomeReport` 只概括当前业务结果，`OperationLedger` 事件包括 planned/authorized/dispatch_started/tool_returned/verified 等及其时间和证据引用，`PlatformView` 的 Fact 有 certainty 与 evidence_refs。Schema 没有赋予这些对象可信性：按证据本身和来源核验。Ledger 中 authorized 仅是执行记录事件，不是本轮可复用发送授权。已实施上游成果：当前能读取 `aftercare-evidence`、`aftercare-remedy` Skill 包；它们均警示引用/权限由宿主核验，且目录契约仍有提案缺口。`aftercare-verify/recover/appeal/interact` 在清单中是接口角色，本次可读目录中未发现其 Skill 包实现。中央 catalog 状态为 `design_not_implementation`，所有项 `implemented:false`。因此以下流程为衔接设计，不能声称已集成运行。

## 宿主必须实现

身份、任务/商品/修订/暂停检查；每条来源引用实际解析和跨任务拒绝；附件授权/字节快照/有效性；渠道身份与时效核验；用户核对事件与发送授权的区别；授权对当前草稿/收件方/附件绑定并在内容变更后失效；发送前原子占用、持久化台账、发送超时结果核查及重复发送阻断；执行回执与客服受理状态。Skill 自检或提示词不能替代这些门禁。
