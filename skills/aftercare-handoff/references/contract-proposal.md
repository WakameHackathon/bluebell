# 最小契约修订提案（未实施）

本文件是待议提案，不修改中央 Schema，也不表示运行时支持。现有 v1 足以承载草稿正文、引用数组及一个可空渠道引用，但无法满足用户要求的逐条来源、材料关联、版本绑定和生命周期核验。最小建议在 v1 后续兼容版本中为 `HandoffDraft` 增加可选且受约束的对象：

- `draft_revision` 或 `content_digest`：稳定绑定规范化正文、渠道引用和附件引用；任何关键变化产生新版本。
- `timeline_facts[]`：每条 `text`、`source_kind`（user_reported/platform_observed/execution_receipt/inference/unknown）、`evidence_refs[]`、`certainty`、可空 `occurred_at`。
- `attachments[]`：`file_ref`、`related_question_ids[]`、`necessity`（required/helpful）、`source_bundle_ref`、`content_revision`；允许数组为空。
- `official_channel`：可空 `channel_ref`、`channel_kind`（platform_support/seller/unknown）、`verified_from_ref`、`verified_at`、`expires_on_page_change`。不能将 seller 标为平台客服。
- 生命周期事件由宿主专用记录保存：draft_prepared、user_reviewed、send_authorized、dispatch_started、sent/unknown、support_received、support_accepted、resolved；每个事件带草稿摘要、收件人/附件绑定摘要、来源和时间。发送授权凭证本体仍不作为 Skill 自报字段。

消费者影响：严格拒绝未知扩展字段的现有 v1 验证器需按新契约版本升级；旧消费者只可继续读取原字段，不得将缺失扩展解释为已核验。新消费者应以数组形式处理时间线/附件并允许空附件；宿主需要数据库迁移、附件版本快照、渠道过期规则、版本哈希规范及原子授权消费/重复发送阻断。OperationLedger 目前只能记通用操作事件，需定义消息发送与客服回复证据如何关联，或增加独立 handoff lifecycle artifact。

正样例：`timeline_facts` 一条 `platform_observed` 记录引用当前 `obs_x`；`attachments: []`；`official_channel` 引用当前支持页并标出观察时刻；修改正文后 `draft_revision` 改变、旧 `user_reviewed` 不再适用。

反样例：将推断“商家故意拖延”标为用户事实；将商家私聊 URL 标成 `platform_support`；只用显示文件名作为附件版本；把用户核对事件视作发送授权；发送结果超时后再次消费旧授权。上述均应由宿主拒绝。
