# 接口与已生效边界

本文件摘录以 2026-09-27 项目中央 `contracts.schema.json`、`skill-catalog.json` 与 Skills 衔接规范为准。中央合同为 1.0.0，注册清单状态 `design_not_implementation`；14 个目录项均 `implemented:false`。本交付包是 Skill 文件包，不表示其被宿主注册或连入运行时。

## 正式请求/结果

传输信封 `{message_type:request|result,body:{...}}`。请求 body 必需：`contract_version`、`skill_id`、`skill_version`、`call_id`、`task_id`、`expected_task_revision`、`mode`、`task_snapshot`、`inputs`。inputs 必需且严格包含 `outcome:OutcomeReportRef`、`platform_view:PlatformViewRef`、`evidence:EvidenceBundleRef`、`ledger:OperationLedgerRef`。引用形状为 `artifact_id`、`kind`、`revision`。结果 body 必需：`contract_version`、`skill_id`、`call_id`、`task_id`、`based_on_task_revision`、`status`、`data`、`questions`、`issues`、`user_message`。status 为 `completed|needs_user|needs_observation|blocked|failed`。

`data` 的非空型为七字段 `AppealDraft`：`reason_evidence_refs`、`grounds:Fact[]`、`draft_text:string|null`、`file_refs`、`missing_evidence`、`available_route_refs`、`recommendation`。`Fact` 恰为 `key,value,evidence_refs,certainty`；certainty 为 `observed|user_reported|inferred`，证据引用至少一个。推荐枚举为 `prepare|collect_more|handoff|stop`。

schema 允许非 completed 情况 `data=null`；completed 必须是 AppealDraft 且 questions/issues 为空；needs_user 至少一个 question；needs_observation/blocked/failed 至少一个 issue。Issue code 只能用中央既有枚举，不能自造。Schema 检查仅证明结构，不证明语义或真实性。

## 正式能力边界

verify 的实际交付版本区分处理中、补证、拒绝与终局：`rejected` 本身不是最终拒绝；`needs_evidence` 是补件；状态未知应先核对，不转成申诉结论。evidence 的实际交付仅处理获准真实文件、需求检查、补拍指导及用户核对，不会声称材料齐全；v1 review_receipt 默认空，因为现行宿主合同没有核对事件及内容版本绑定。remedy 的实际交付区分推荐方案、用户所选方案与动作授权，不把建议或用户选择视为执行许可。

此处引用相邻 Skill 的工作成果，不意味着项目运行时已经接通。当前全局已存在 evidence/remedy 包，本地项目输出已存在 verify 包；本项目中央 catalog 仍标记设计、未实现。执行台账和宿主机制亦未由上述文件证明已实现。
