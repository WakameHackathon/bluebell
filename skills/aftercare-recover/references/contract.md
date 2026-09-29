# 当前接口（每次读取）

Skill 1.0.0；contract_version=1.0.0。recover.schema.json 从中央权威 Schema 机械提取传递依赖，provenance.json 记录来源及摘要；不手工维护派生定义。

请求 body：contract_version、skill_id、skill_version、call_id、task_id、expected_task_revision、mode、task_snapshot；inputs 恰为 failure:FailureEvent引用、platform_view:PlatformView引用、ledger:OperationLedger引用、outcome:OutcomeReport引用或null。引用为 artifact_id/kind/revision。信封为 message_type=request/result 加 body，脚本校验 body。

结果 body：contract_version、skill_id、call_id、task_id、based_on_task_revision、status、data、questions、issues、user_message。data 五字段：failure_class、strategy、new_evidence_refs、next_steps、reason。中央允许部分错误结果 null，本包收窄为始终对象；连合法任务外壳都没有时走宿主错误通道，不造 ID。

failure_class：layout_changed/stale_target/overlay/navigation_lost/network_error/ambiguous_write/unsupported/other。
strategy：reobserve/relocalize/reversible_explore/check_records/ask_user/handoff/stop。
Step：intent、reason、required_evidence（已登记依据ID数组）、next_skill_hint（ID或null）。Step不是动作，intent不是工具命令。为保持单步恢复清晰，本包最多提出一个当前步骤；后续条件写说明，由宿主重新调度，不输出批量执行序列。

completed 的 questions/issues 均为空；needs_user 的 questions 非空；needs_observation/blocked/failed 的 issues 非空。Issue.code 只能为 missing_input/stale_observation/target_unconfirmed/policy_unknown/needs_login/needs_consent/unsupported/ambiguous_result/budget_exhausted/contract_error/tool_failure/user_paused；retryable=false，避免通用重试器把查证需求当重提许可。

所有引用由宿主解析并核实类型、任务、版本、访问权与来源。ExecutionReceipt 不在 recover inputs 中，需由 FailureEvent.execution_ref/台账索引经宿主同任务解析，不新增 receipt 字段。FailureEvent 没有预算字段，预算实际在 TaskSnapshot.remaining_budget。call_ref 不等于 proposal_id，缺关联不能猜原动作。

new_evidence_refs 要相对上次恢复所用证据和原失败观察判断新颖性，登记时间变新不等于事实变新。同一观察复制新ID、换提案ID、重述错误均不是新证据。没有新增观察时允许空数组并请求重观察；有历史无进展且无新条件时停止，不无限请求同一观察。

reason 解释事实/假设、差异、预期验证及停止条件；机器门禁信息由宿主独立持有，不能解析 reason 作为授权、预算或去重依据。当前 v1 不能完整表达这些机器信息，见接入说明及交付目录的契约修订提案。
