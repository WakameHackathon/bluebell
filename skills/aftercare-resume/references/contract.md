# 中央 v1 接口

包版本 1.0.0。resume.schema.json 是中央 contracts.schema.json 相关定义的递归提取，provenance.json 保留来源摘要；不得手改派生 Schema。完整交付 tests/extract_contract.py 可重新生成。共享接口和 catalog 未修改，候选修订不自动生效。

信封 `{message_type:"request"|"result",body:...}`；按 aftercare-resumeRequest / aftercare-resumeResult 校验 body。请求有 contract_version、skill_id、skill_version、call_id、task_id、expected_task_revision、mode、task_snapshot、inputs。inputs 严格只有 saved_task:TaskSnapshotRef、platform_view:PlatformViewRef、current_outcome:OutcomeReportRef、ledger:OperationLedgerRef。四者必填，不允许 null；记录缺失时仍不得伪造 Ref。宿主应在调度前报告加载失败；合法请求外壳下引用不可访问可 blocked/missing_input。

结果：contract_version、skill_id、call_id、task_id、based_on_task_revision、status、data、questions、issues、user_message。data 五字段：mismatches、confirmed_target_item_ref、latest_outcome_ref、next_steps、historical_consent_reusable=false。中央失败结果允许 data=null，本包采用始终对象的更窄约定。未确认目标/无有效新结果用 null。latest_outcome_ref 在 v1 只是字符串 ID，须由宿主绑定到请求 current_outcome 的精确 revision，不得解析成“同ID最新版本”。

mismatch 的 field 是 ID 字符串（不是带方括号的 JSONPath）；previous_evidence_ref/current_evidence_ref 是证据 ID 或 null；resolution 非空说明。Step 四字段 intent/reason/required_evidence/next_skill_hint；required_evidence 只能列已有登记证据，尚待获取的证据写 reason。不得添加 status/resolved/allowed 等 wire 字段。

completed 要求非空 data 且 questions/issues 为空；needs_user 至少一个 question；needs_observation/blocked/failed 至少一个 issue。Issue.code 只用中央枚举，常用 missing_input/stale_observation/target_unconfirmed/needs_login/needs_consent/unsupported/ambiguous_result/contract_error/user_paused。retryable=false，避免通用重试器把核对需求当重提许可。

TaskSnapshot.task_revision、Ref.revision、OperationLedger.ledger_revision、页面版本是不同版本域。当前 snapshot.task_revision 必须等于 expected_task_revision；saved_task 由宿主证明属于当前 lineage 的历史祖先，不靠数字大小或更新时间判断。产物 revision 只与 Ref 比较。登记/消费结果时 current revision 变化则只归档、重建当前请求；不得改写结果的 based_on_task_revision 伪装新鲜。

TaskSnapshot 和 PlatformView 没有标准账户/售后实例绑定；OutcomeReport 没有明确观察时间、目标或核对对象；Ledger 仅事件索引，不含足以独立判断动作效果的完整正文。宿主必须从获准的实际记录解析这些关联。相关产物索引不是任意扩展字段或绕过访问授权的途径。缺失可信关联时只回顾，不进入业务推进。
