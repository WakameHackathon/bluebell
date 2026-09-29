# 接口与宿主约束

包 1.0.0，中央 contract_version=1.0.0；[派生 Schema](verify.schema.json) 定义来自权威文件，摘要见 provenance.json。按 $defs/aftercare-verifyRequest、aftercare-verifyResult 校验 body；信封为 {message_type:request|result,body:...}。

请求字段：contract_version、skill_id、skill_version、call_id、task_id、expected_task_revision、mode、task_snapshot、inputs。inputs 严格只有 platform_view:PlatformView引用、receipt:ExecutionReceipt引用或null、ledger:OperationLedger引用。引用为 artifact_id/kind/revision；不能偷偷加 goal_step、host、user_turn 或 expected_result。

结果字段：contract_version、skill_id、call_id、task_id、based_on_task_revision、status、data、questions、issues、user_message。data 八字段为 platform_state、effect_result、stage_complete、case_terminal、business_result、actual_receipt_confirmed、evidence_refs、user_todos。中央错误包允许null，本包采用更窄的始终对象规则；无法形成合法外壳走宿主错误通道。Issue.code 只能用已有 missing_input/stale_observation/target_unconfirmed/policy_unknown/needs_login/needs_consent/unsupported/ambiguous_result/budget_exhausted/contract_error/tool_failure/user_paused，retryable=false 防止通用重试器把查证需求当重提许可。

ExecutionReceipt 含 proposal_id、action_payload_digest、目标、dispatch_state/tool_state、started_at/finished_at、结果证据；没有 operation、expected_result 或明确发送时间。宿主须通过 proposal_id 找到不可变 Action（并核对任务、目标、内容摘要及记录版本），不能靠网页提供同名 JSON。当前实际 executor_stub 只有内存模拟事件，没有生成真实 ExecutionReceipt，不能据此声称已经接通。

PlatformView.state_facts 是 Fact(key/value/evidence_refs/certainty)，并无标准状态事实键、售后实例、账户或每项时间字段。须回溯真实 Observation 和源证据；PlatformView.created_at 不等于页面采集时间。controls 为空时也不能丢失观察来源。当前尚无已核实生产适配器，因此支持的状态解释必须由宿主明确提供，缺失则 blocked/unsupported。

TaskSnapshot.related_artifact_refs 可索引相关产物，但不是任意扩展槽：宿主仍需解析类型、授权和不可变版本。纯查询或手动动作缺少显式核对目标时只能报告有根据的状态，动作归因 unknown。无法从台账证明完整尝试史时不得 not_attempted。

宿主必须实现：
1. 可信登记与受限解引用，校验来源/账户/任务/商品/实例/有效期，所有 evidence_refs 均可追溯。标记 runtime_record 不能认证网页内容。
2. 保留提案、内容摘要算法及版本，dispatch_started 发送前持久化；未知发送不能按未发送处理。时钟域不可比则时序未知，不能比较页面版本号代替时间。
3. 任务版本比较更新、模式与目标变更失效、同任务互斥、在途业务效果去重。重复调用缓存同一结果，不新增业务事件；新call也不改变业务效果身份。
4. 记录独立的核对结果与回执关联，OutcomeReport 不覆盖原回执，不因模型说成功解除未知动作；按官方证据和完整关联核验后由宿主改变状态。
5. unknown 的门禁由宿主与 recover/interact 共同消费；v1 文本不足以实现机器门禁。缺少上述机制时关闭自动业务推进，允许只读解释。
6. 用户陈述/理解事件必须真实采集并绑定任务和时间；不读取未经授权银行、支付或其他订单。账户变化需重核目标，不借用前账户结果。

`scripts/check_report.py` 的 host 是本地已解析测试上下文，包含宿主提供的语义见证，不能从模型输出回填。脚本只核对关系、不判断截图真假/语义；生产必须由适配器及宿主独立建立见证。返回 errors 与 hold_external_write，不执行或修改任何记录。hold_external_write 只是保守诊断，不是持久锁或解锁令牌。
