# 接口合同：中央 1.0.0 / Skill 1.0.0

order.schema.json 由中央 contracts.schema.json 递归提取所需 $defs；来源摘要见 provenance.json。工程 tests/build_contract.py 可重新生成。中央 Schema 与 catalog 未修改。本包不包含浏览器或宿主服务。

## 输入输出

请求 body 使用 aftercare-orderRequest：contract_version、skill_id、skill_version、call_id、task_id、expected_task_revision、mode、task_snapshot、inputs。inputs 仅 intent、platform_view、user_decision（三者均必填，最后一个可 null）。Ref 由宿主解析，不是内联数据；旁路解析上下文不属于请求新增字段。传输层可按中央协议包在 message_type=request/body 中；示例文件使用 body。

结果 body 使用 aftercare-orderResult：contract_version、skill_id、call_id、task_id、based_on_task_revision、status、data、questions、issues、user_message。原样回传身份及基准修订，不含 skill_version。data 使用 OrderSelection 四字段 candidates、selected_item_ref、selection_receipt_ref、lookup_steps；本 Skill 所有可构造结果统一使用该对象（中央 Schema 虽允许部分状态 data=null，本包无需使用）。Candidate 仅 item_ref、display_label、order_ref、evidence_refs；Step 与 Question/Issue 字段看派生 Schema，禁止随意增补 confidence、confirmed、next_skill、search_complete。

completed 要求 data 非空且 questions/issues 为空；needs_user 至少一个问题；needs_observation/blocked/failed 至少一个 issue。未选中两个字段均 null。Schema 没有强制这两个字段配对、选择属于候选或凭证真实，须另做语义校验。

## 输入拒绝与降级

宿主在调用前检查注册版本、完整 Schema、引用存在且类型/修订/任务/访问范围正确，快照与当前任务模式/修订一致。所有证据必须存在，并实际支持该候选的 item/order 映射。不能从模型文字创建这些映射。

身份外壳有效但引用缺失、跨任务、类型错误或过期：failed/contract_error，两个选择字段 null。只有 ID 无已解析正文也不能猜内容。若 call_id/task_id/版本本身无效，由宿主拒绝调用；不制造合规结果外壳。页面过期用 needs_observation/stale_observation；登录 blocked/needs_login；不支持 blocked/unsupported；无查询授权 blocked/needs_consent；暂停 blocked/user_paused；预算用尽 blocked/budget_exhausted。

意图关键歧义：blocked/missing_input，issues 向主 Agent 建议回 aftercare-intake；用户改变目标同样处理并报告失效建议。仅缺订单线索继续定位。意图为未确认草稿可以 needs_user 整理候选，但选择字段均 null。用户已确认而缺宿主整版绑定，不再追问用户，用 blocked/contract_error。

## 核实过的上游现状

已读取 aftercare-intake release-1.2.0 实际 SKILL.md、两个接口说明、候选确认门禁、SQLite 本地适配器和修订记录。包版本为 1.2.0，部分发布说明/修复记录仍写 1.1.0，应以实际文件及显式 profile 为准。中央 catalog 仍 implemented=false，不能据此否认包存在，也不能声称运行时已注册。

上游中央 v1 TaskIntent 只有 goal/scope/user_facts/requested_outcome/missing_fields，不含确认状态。local-intake-v2 才有 source_turn_refs、goal_evidence_refs、IntentConfirmation 及外壳 intent_confirmation_ref，并支持 retain_item。它的本地消费者仍是 mock。不可将 v2 产物删除字段伪装成 v1，不能凭相同 Ref.kind 就接受；必须校验被引用正文所属协议。

因此本包默认 v1 可分析和澄清候选，但不能声称已打通确认后的 remedy 交接。未来接入前需要独立契约提案、消费者迁移和可信门禁；自由文本中的“已确认”不是替代方案。
