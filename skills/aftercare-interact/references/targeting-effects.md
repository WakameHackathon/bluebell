# 定位与实际效果

PlatformView.controls 是候选证据，不是可执行定位器。宿主登记表应额外核实控件唯一性、当前可见/启用/未遮挡、角色/标签/商品上下文、观察来源、页面身份、有效期及操作效果。仅名字相同不等于同一控件。

结构定位优先；结构不足请求当前截图与宿主视觉登记。登记必须有证据来源、观察与页面版本，坐标只留在执行适配器，不拼进 control_ref。没有正式视觉登记协议时报告缺口。

| 实际行为 | operation | effect |
|---|---|---|
| 打开确定只读页面 | navigate | read_only |
| 展开可逆说明 | expand | read_only |
| 只改变本地字段 | fill | local_edit |
| 字段自动保存/客服输入自动发送 | fill | external_write |
| 选择本地选项 | select | 按证据判断 |
| 选文件立即上传 | attach | external_write |
| “下一步”实际提交申请 | submit | external_write |
| “确认”接受或撤销 | accept_offer / withdraw | external_write |
| 平台内预约 / 发送客服消息 | book_pickup / send_message | external_write |
| 关键副作用未证实 | 不下发动作 | unknown |

表是判断方法，不是平台事实库。平台入口和特殊副作用由平台适配层提供；不把固定商城经验写进通用 Skill。navigation 探索需有获准范围、确定可逆效果和预算，未知不能探索。

关键内容至少能呈现：商品、操作、拟用精确内容/文件、实际接收方、适用的金额/费用/后果。未知与不适用必须区分；缺项先补业务产物或观察。一次 attach 只绑定一个文件，其他文件下一观察后另提案。所有字段值必须指向登记值，不让说明文本成为输入命令。
