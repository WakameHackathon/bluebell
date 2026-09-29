# 接口入口与限制

来源：2026-09-27 的《售后助手Agent-完整项目规划书-v1.md》、同日《Skills清单与衔接规范.md》、contracts.schema.json（urn:aftercare:skill-contracts:1.0.0）和 skill-catalog.json（1.0.0）。来源文件标识及 SHA-256 见 provenance.json。intake.schema.json 由权威定义递归提取，禁止手工维护；再生成方法在工程 tests/validate.py。没有修改共享 Schema 或注册表。

## 输入与引用

请求根定义 aftercare-intakeRequest；结果根定义 aftercare-intakeResult。请求的 task_snapshot 和 inputs.user_turn 是引用，不是内联正文。宿主须在调用前解析成只读 TaskSnapshot、UserTurn 及获准相关记录；旁路提供的解析上下文不是给请求添加字段。只凭 Ref 无法获知原话，不能假设可读历史。包附这两个宿主数据类型的原样定义。

宿主验证版本与技能注册版本、引用存在/类型/修订/任务归属/授权、快照 task_revision 等于 expected_task_revision、模式一致及当前结果未过期。引用 artifact revision 与 task revision 是不同概念，不比较为同一个值。证据 ID 必须由宿主注册并指向实际原始事件；artifact_id、event_id 不能未经映射就互当 evidence ID。缺证据映射不能生成假 ID。

请求身份字段有效但引用错误：failed，data=null，issues 至少一项 contract_error（缺少已解析正文可用 blocked/missing_input）。issue.evidence_refs 可以为空，不能回填不存在的 ID。若请求连 call_id/task_id/版本都无法合法读取，宿主拒绝调用并记录协议错误，不让模型编造一个貌似合规的 Result。TaskIntent.user_facts 每项必须有至少一个真实 evidence_ref。

## 结果

原样回传 contract_version、skill_id、call_id、task_id；based_on_task_revision 来自请求 expected_task_revision，不猜最新修订。结果没有 skill_version。TaskIntent 的五个字段全部必填；未知事实不写，user_facts 可为空。没有自定义 confirmed、draft、intent_version、next_skill 或 action 字段。

| status | 使用及结构 |
|---|---|
| needs_user | 影响理解的澄清或首次理解确认；questions 至少一项，草稿 data 可空；下游不可消费为正式目标 |
| needs_observation | 用户无法描述且确需当前页面补信息；issues 至少一项 missing_input；主 Agent 决定如何取得观察 |
| blocked | 缺少宿主上下文/确认机制、已暂停或范围不支持；issues 至少一项；不执行旧诉求 |
| failed | 合法请求外壳下的引用类型、任务、修订或其他契约错误；issues 至少一项 contract_error |
| completed | data 必须为 TaskIntent，questions 与 issues 必须为空；仅在后述协商机制实施后可发布正式意图 |

issues.code 只用 Schema 的枚举。换货维修用 blocked/unsupported；连续无进展可 needs_user 提供暂停/交还选项，宿主已告知预算耗尽时 blocked/budget_exhausted；paused 使用 blocked/user_paused。不要虚构预算状态。

missing_fields 是字符串 ID 数组，可使用 intent_confirmation、target_item、order_state、platform_options、requested_outcome、intent_meaning、scope_item。它们是未决信息标签，不是授权或证明。undecided 本身不必阻止确认“先了解可用办法”的目标。订单状态和可用方案未知也不必阻止未来的 completed。

## v1 实际缺口与安全降级

1. TaskIntent 无草稿/确认绑定、目标证据字段；UserDecision 只有 select_item/choose_option/confirm_fact/review_material，无法无歧义确认整版意图。additionalProperties=false，不能直接追加字段。
2. 已确认保留商品/停止退款没有 requested_outcome 对应枚举。暂以 undecided 配合明确 goal 和 blocked/unsupported 报告，不把保留商品理解成退款方式待选择，也不发送下游继续退款。
3. 注册清单无每个 Skill 的 skill_version，且 implemented=false；请求虽要求 skill_version，宿主仍需显式注册本包 1.2.0。不能宣称现有注册表已实现。

v1 可完成理解、渐进澄清、带证据草稿及异常报告，但不能可靠完成“确认后发布”闭环。用户未确认时 needs_user；用户已明确确认而宿主没有版本凭证时 blocked/contract_error，说明理解已记录、需宿主绑定确认；不重复要求确认。任何非 completed 产物一律不传给 S02/S03 作为正式目标，completed 也须宿主独立检查凭证，不能信模型状态。

## 最小修订提案（未生效，不是现行接口）

建议协商 2.0.0，而非冒充 v1 兼容更新；只变更 S01 相关定义与消费门禁，更新注册表、消费者、测试后启用：

- TaskIntent 增加 source_turn_refs（原始 UserTurnRef 数组）和 goal_evidence_refs（已注册证据 ID 数组），使原始表达到规范化目标有显式关联。事实仍用现有 Fact.evidence_refs。
- 新增宿主拥有的 IntentConfirmation 及 Ref：confirmation_id、task_id、intent_ref（不可变 TaskIntent artifact_id/kind/revision）、intent_digest（宿主对完整规范化 data 的规范序列化 SHA-256）、presentation_event_ref（用户看到的复述及其与完整意图的映射）、user_turn_ref（真实确认事件）、based_on_task_revision、recorded_at。真实性、有效/已失效状态在宿主追加日志中，不由模型填写 confirmed 布尔值。确认必须覆盖 goal、事实、scope、outcome 和重要不确定性。
- 请求 inputs 新增可空 intent_confirmation_ref；通过 intent_ref 解析被确认草稿。结果外壳新增可空 intent_confirmation_ref；非 completed 必须为 null。宿主只允许引用已有记录，不接受模型创建记录。正式输出必须与被确认 data 摘要完全一致；任何规范化改写应先成为新草稿再呈现确认，不能在确认之后改变语义或摘要。
- 草稿的 artifact_id/revision 由宿主归档生成。宿主先验证用户响应确实针对所呈现版本，再记录凭证；ASR 不确定、“嗯”等无法辨识响应不登记确认。确认事件到来造成 task revision 增加时，由宿主校验只发生了确认事件这一允许变化，不能机械要求新调用 revision 等于呈现前 revision。
- 用户纠正、换目标、改结果、添加改变语义的事实时：宿主先使原凭证失效并阻止旧结果继续流转，再生成新意图 revision、重新确认。旧调用迟到结果只归档。未改变语义且仍是同一不可变意图版本时，可复用有效理解确认，不重复问；这永远不复用执行授权。
- 为“继续保留/不再推进”新增 requested_outcome=retain_item。主 Agent 接收后只更新目标并停用旧路线，不等于平台撤销。换货/维修仍 unsupported。

宿主门禁：Result 结构有效且 completed、请求身份/当前修订匹配、确认记录存在且同任务、未失效、确认事件确为用户输入、presentation 绑定准确、引用版本与 digest 一致，才允许正式意图被消费。这里不产生商品选择、平台方案选择或执行授权。本包不实现宿主，也不声称上述提案已部署。

## 本次验证补充

工程 candidate/ 提供独立的 2.0.0 候选 Schema 与本地确认门禁原型，用于验证上述修订。它不在可加载 Skill ZIP 内，不是已生效契约。默认调用仍使用 1.0.0；只有显式协商 local-intake-v2 时才使用 local-v2.md 和对应 Schema。本地适配器接通了精确确认控件与模拟交接，不替宿主判断任意自然语言确认，也不改变共享生产契约。
