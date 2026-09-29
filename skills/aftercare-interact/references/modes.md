# 模式与表达

| 模式 | presentation | 高亮 | actions |
|---|---|---|---|
| self | explain_only | null | [] |
| guided | explain_only 或 highlight | explain_only 时 null；highlight 时当前可靠引用 | [] |
| auto | explain_only / highlight / propose_action | 有当前依据才可引用 | propose_action 恰好一项，其余为空 |

高亮不是执行许可。宿主应将高亮绑定 observation_id/page_revision 和接管 epoch；导航、弹窗、重绘、用户操作后撤销。高亮不得遮挡按钮、金额、费用或关键提示，不修改按钮文案或视觉含义。宿主布局检查不能证明安全时取消高亮，回 explain_only。

说明例如“点击蓝色杯子下方的‘申请售后’。”只在该文字及商品上下文确实存在时使用。提案说明可用“准备提交蓝色杯子的退货退款申请，请先核对本次内容。”，不能写成已经提交。动作未明时可说“先停在这一页，需要确认这个按钮会做什么。”

暂停时说“先停在这里。”已发送时补充“刚才的请求结果还需要核对。”不声称撤回。语音录制、识别、播报和正式确认呈现均由宿主实现。
