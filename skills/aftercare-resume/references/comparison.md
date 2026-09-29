# 状态、证据与差异

先看证据的对象、来源、核对范围，再看时序：同账户/平台/订单项/售后实例；实际 Observation 的 captured_at/page revision；是否官方记录、缓存/旧弹窗、采集是否在可疑发送之后。产物 created_at 是登记时间，不是平台事实发生时间；时钟不可比保留未知。

OutcomeReport 必须由本次 verify 的合法请求/结果登记，来源调用与输入观察可追溯，证据同目标且足够新；不能仅因 skill_id=verify 就接受。verify 的 completed 也可能 effect_result=unknown。动作归因未知与“平台已有申请”可同时成立：不声称某旧动作成功，但仍阻止重复申请。只在宿主核实对应业务效果后，建议撤去旧待办；模型不能自己释放在途锁。

| 对比 | 本轮建议 |
|---|---|
| pending → pending | 告知仍待审核，无新操作；用户回来再查，不创建定时任务 |
| pending → needs_evidence | 引用当前要求，evidence 准备真实材料；已上传部分不重传 |
| 旧计划提交 → 当前已有申请 | 丢弃旧提交待办，不重放；未知归因仍待核对 |
| 超时 → 精确成功记录 | 说明已核实，按当前状态继续，不重提 |
| 超时 → 暂无记录/冲突/缺回执 | unknown，needs_observation → verify；无法查询 blocked/handoff |
| 用户自行上传/寄件 | 用当前关联材料/运单记录撤去对应旧待办，不将其归因于 Agent |
| 新费用/期限/地址/方案 | 比较变化，重新核对适用选择；地址或寄件安排交 logistics，条件决策交 remedy |
| 文件删除/替换/权限撤销 | 不读取被撤权文件；核对存在性、字节摘要、派生链和呈现内容，交 evidence |
| 平台退款完成 | 可明确平台结果；到账 unknown 仍保留，不新申请，不读银行账户 |
| rejected 且仍有复核待办 | 不是终局；verify 核对路径，必要时 appeal/handoff |

历史已核实事实不能被当前“未显示”抹除。保留前后证据，说明当前查询覆盖不足、缓存或归属冲突。mismatches 只写差异；一致部分以 user_message 简述，v1 没有结构化一致项字段，不擅加。

台账按 execution/business effect 关联所有 dispatch_started、tool_returned、verified 和缺口。单有 verified 事件不证明成功，必须解析其具体证据及核对范围；单有 planned 不证明没发送。多个未知动作即使其中一个查到成功也不能整体放行。上传、申请、预约、撤销、发送各自核对，不因状态相同而重复生成待办。只保留下一项必要前置步骤；相同请求重传应由宿主返回缓存。
