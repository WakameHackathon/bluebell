# 当前接口与兼容边界

references/evidence.schema.json 从中央 contracts.schema.json 递归提取，定义逐项不改；来源摘要见 provenance.json。包 1.0.0、契约 1.0.0。中央 catalog 仍是 design_not_implementation。intake 1.2.0 的 local-intake-v2 仅在其本地宿主实现；order 的 SelectionBinding 和 remedy 的 RemedyAssessment 等仍为提案。不能按相同版本号混用，也不能删字段降级确认意图。

请求 body：contract_version、skill_id、skill_version、call_id、task_id、expected_task_revision、mode、task_snapshot、inputs。inputs 恰为 remedy:RemedyPlanRef、platform_view:PlatformViewRef、approved_file_refs:string[]、user_turn:UserTurnRef|null。空文件列表合法，只能解释要求及指导补充。

结果 body：contract_version、skill_id、call_id、task_id、based_on_task_revision、status、data、questions、issues、user_message。外层传输为 {message_type:request|result,body:...}。本包比 Schema 更严格：任何合法结果的 data 都是 EvidenceBundle，不返回 null。

EvidenceBundle 六字段：original_file_refs、derived_files、requirement_checks、capture_guidance、statement_draft、review_receipt_ref。derived_files 项恰为 file_ref、source_refs、transforms（crop/compress/rotate/redact）、preview_ref。requirement_checks 项恰为 requirement_key、state（met/missing/uncertain）、evidence_refs。不存在的文件/预览/证据不得引用；派生文件须实际产生并完成登记，模型不自行分配 ID。

Issue.code 仅用中央枚举：missing_input、stale_observation、target_unconfirmed、policy_unknown、needs_login、needs_consent、unsupported、ambiguous_result、budget_exhausted、contract_error、tool_failure、user_paused。技术原因写 issues，面向用户用简单话。needs_user 必有问题，needs_observation/blocked/failed 必有 issue；completed 不得带问题或 issue。

## v1 能做与不能做

RemedyPlan.material_requirements 是 Fact[]，Fact.key 不是全局唯一材料 ID。仅在宿主已验证同一不可变 plan_ref/revision 内 key 唯一且与当前页面一致时，将其 key 原样用于 requirement_key；跨版本不能按相同文字/数组下标猜映射。重复 key 或映射未明时 needs_observation，不生成貌似稳定的键。建议不得混入平台强制缺件判断；v1 无法完整结构化表达分类、条件、原因、文件状态和说明来源，不能靠自由文本当运行时门禁。

TaskSnapshot.related_artifact_refs 只有字符串；UserDecision 有 review_material，但没有明确绑定文件内容与说明版本的类型。scope_grant_refs 也不证明授权的动作、数据类别、接收方。没有已生效扩展解决这些缺口，因此默认 review_receipt_ref=null；不得把 user_turn 的“对”或任意字符串当有效核对。宿主若只在外部拥有记录，仍须先协商可验证的正式协议，不能默默采用 candidate。

不凭 original_file_refs 推断拟用集合（可能包含派生来源）。正式交接缺口用 blocked/contract_error 表达；若本轮是补拍或解释，则按实际需要返回 needs_user/needs_observation/completed，不让工程缺口遮蔽用户能做的事。当前任何状态都不放行上传准备。说明原件或草稿不会产生许可。

## 宿主义务

验证版本、请求/结果身份、任务修订、模式、暂停；解析引用存在/类型/版本/归属/授权；核验真实用户事件与意图、商品、方案选择；核验页面新鲜度、平台账户目标范围和要求来源。跨任务文件只有显式跨任务授权且登记到本任务范围才可使用。重传 call_id 复用记录、迟到结果拒收，由宿主负责，不由提示词保证。

本地脚本不实现以上身份认证。文件工具还需限制解析资源、锁定/快照字节，原件前后校验，派生预览登记，避免路径与内容切换；登记失败时不能在 EvidenceBundle 中发布成功文件。拟议结构和合成验证在工程 candidate/tests，既不是正式消息也不是生产服务。
