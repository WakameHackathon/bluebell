# 结果状态与主 Agent 交接

- `completed`：本轮分析完成；不是申诉已提交、已核对、可发送或成功。
- `needs_user`：只问关键争议点、用户陈述事实或草稿/材料核对；先简短复述已知信息。
- `needs_observation`：缺拒绝原因、最新申诉状态、路径或引用来源；给出需观察的具体信息。
- `blocked`：登录、权限、支持范围或有效路径/宿主机制阻碍。
- `failed`：契约、引用或分析异常。

status 以中央结果 Schema 为准。对 `needs_user` 不能仅用 user_message 代替 question；对其他失败状态使用已有 Issue code。若无合法引用或 envelope，交宿主错误通道，不自造身份字段。

典型交接只作为给主 Agent 的提示，Skill 不直接调用：状态未知/发送后超时→`aftercare-verify`；针对性补证→`aftercare-evidence`；诉求/方案改动→上游核对；草稿材料都经核对且宿主 gate 满足→`aftercare-interact` 生成动作提案；规则解释/人工处理→`aftercare-handoff`；页面变化→主 Agent 安排新观察或 `aftercare-recover`。真实提交后必须 `aftercare-verify` 核验，结果未知则宿主持有去重阻断。
