# 中央接口与交接

本包 1.0.0，wire contract_version=1.0.0。`interact.schema.json` 是从权威 Schema 递归提取的未修改定义；来源与 SHA-256 见 provenance.json。校验 body 使用 `$defs/aftercare-interactRequest` / `aftercare-interactResult`；传输信封为 `{message_type:request|result,body:...}`。样例文件保存 body。

请求固定包含 contract_version、skill_id、skill_version、call_id、task_id、expected_task_revision、mode、task_snapshot、inputs。inputs 仅 goal_step、platform_view、source_artifacts。Step 仅 intent、reason、required_evidence、next_skill_hint。宿主按真实登记记录解析引用，不允许在请求塞入任意 host 扩展。

结果固定包含 contract_version、skill_id、call_id、task_id、based_on_task_revision、status、data、questions、issues、user_message。虽然中央错误结果允许 data=null，本 Skill 采用更窄的始终 InteractionPlan 约定。无合法请求时不伪造外壳。

InteractionPlan 五字段：presentation、instruction、highlight_control_ref、actions、refresh_required。Action 全字段及枚举以 Schema 为准，不能增加 approved、坐标、确认收据或自造 operation。

现有 Issue.code 无专门 route 字段：用现有 missing_input/target_unconfirmed/contract_error/ambiguous_result 等配合技术 message 指明返回职责，但宿主不能把自由文本当作可执行路由。路由仍由主 Agent 决定；可检查路由与预期结果的结构化改进见交付契约提案。

上游实际状态：intake 1.2.0 本地 2.0.0 产物不兼容中央 v1；order、remedy、evidence 的正式确认链未接通。EvidenceBundle.completed 或 review_receipt_ref 非空本身均不证明可上传。不能删字段降级、将候选协议冒充中央协议或从旧报告重建授权。

下游 verifyRequest 只有 platform_view、receipt、ledger，不能偷偷添加 expected_result。宿主须通过 ExecutionReceipt.proposal_id 找回不可变 Action/InteractionPlan，将期望与新观察关联提供给核对流程；新协议显式 VerificationTarget 的提案尚未生效。
