# 状态、效果、完成

| platform_state | 证据所允许的意思 |
|---|---|
| not_started | 明确尚未开始；空列表本身不足 |
| draft | 平台明确保存草稿 |
| submitted | 明确收到提交，尚无更具体状态 |
| pending | 已受理待审核/处理 |
| needs_evidence | 本售后明确要求补件 |
| return_required | 本售后明确要求寄回 |
| pickup_booked | 预约记录成立，不能推断已取件 |
| in_transit | 与本退件关联的物流在途 |
| refund_processing | 正在退款，未证明完成或到账 |
| refund_reported_complete | 平台报告退款完成；不是独立到账核验 |
| rejected | 平台拒绝；终局另判 |
| closed | 平台关闭记录；关闭原因和终局另判 |
| unknown | 无法对应、缺证、冲突或新状态不支持 |

effect_result：not_attempted 要有本次明确未发送且未开始的依据；confirmed_success 需要本次预期业务效果全部成立；confirmed_failure 需要明确相反业务依据；其余 unknown。v1 缺 partial/in_progress/not_applicable，不把这些塞进合法枚举，也不把部分成功强行改成失败。只查询时用 unknown 并说明动作效果不适用的表达限制。

stage_complete=true 必须知道本次步骤及完成条件并有证据。申请受理可完成提交步骤，不能完成“收到退款”步骤。上传全套步骤需所有指定材料完成。条件未知时 false 表示未核实完成，需说明而非宣称已证实没完成。

case_terminal 与 business_result：明确平台退款完成可为 true/refund_reported；明确最终拒绝且无待处理复核或未决选择才 true/final_rejection；用户明确终止当前任务有可信事件才 true/user_withdrawn（不等于平台撤销动作已执行）；其他确切终局 true/other_final。通常 false/not_final；终局依据不明 false/unknown。拒绝且存在复核路径、用户尚未选择，不自动结案；暂离保持当前状态。

actual_receipt_confirmed=yes 需项目认可的到账证据链；no 需明确尚未收到依据；无证据为 unknown。平台完成只能决定平台报告结果，不能自动决定此字段。yes 的用户陈述来源必须在用户说明中明确，不能写“已独立核验银行”。当前v1无法机器区分来源，候选字段待协商后启用。

用户理解不属于这两个布尔字段的推论。宿主/评测器使用真实理解核验记录计算产品完整成功；助手解释过、用户离开或外层 completed 均不代表理解通过。
