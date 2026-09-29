# 动作阶段、未知及冲突

1. 确定未发送必须有宿主发送前记录、完整关联历史且无相反在途事件。只有 FailureEvent.not_sent、空台账或缺回执不够。
2. confirmed_failure 还须关联原提案预期效果与无业务效果证据；工具 failed 不是业务失败。部分上传/处理中在当前 v1 保持未知，不重发整个包。
3. sent/unknown、dispatch_started、快照 pending_execution_refs 或未解决业务键意味着可能产生效果。优先 check_records → verify；记录路径未知则请求观察，无法查询则 ask_user/handoff/stop。说明待核对对象、内容、接收方、时间及不确定性。
4. confirmed_success 要有宿主核实的同动作关联与平台证据；成功后停止恢复该动作，不能把分析 completed 当成功。

FailureEvent/回执/台账/OutcomeReport 冲突时先标注冲突，check_records 或停止交接；禁止选择 not_sent 以继续发送。请求尚未发送与业务结果未知要分开。verify 输出仍是不可信产物，需要宿主语义校验，不能自动解锁。

暂查不到记录可能是异步、缓存或匹配不足；等待时间、模型直觉、“应该失败了”都不能证明无效果。查询本身也必须经 scope 与实际效果核对；无可靠查询渠道保留未知，不无限轮询。

后续只有新证据明确原效果未发生、宿主核对所有在途尝试且允许、当前目标/内容/授权有效时，才可能准备新的尝试。新proposal_id或内容变化不解除同售后实例的去重。OutcomeReport没有原动作关联字段，不能单独用它解除未知状态。
