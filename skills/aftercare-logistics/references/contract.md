# v1 接口、现状与校验边界

包版本1.0.0，中央contract_version=1.0.0。logistics.schema.json由权威定义递归提取，provenance.json记录实际来源及SHA-256；不手改中央Schema/catalog。examples保存body；传输信封仍为{message_type:request|result,body:...}。

请求字段：contract_version、skill_id、skill_version、call_id、task_id、expected_task_revision、mode、task_snapshot、inputs。inputs严格为order:OrderSelectionRef、remedy:RemedyPlanRef、outcome:OutcomeReportRef、platform_view:PlatformViewRef、user_decision:UserDecisionRef|null；引用均artifact_id/kind/revision，宿主解引用。不能偷偷添加ledger、addresses或host。

结果字段：contract_version、skill_id、call_id、task_id、based_on_task_revision、status、data、questions、issues、user_message。data恰为stage/address_ref/time_slot_ref/fee/fee_known/tracking_ref/user_todos/next_steps。本包始终给对象；中央非completed也允许null，本包更窄。completed不能带questions/issues；needs_user必须问题；needs_observation/blocked/failed必须issues。Issue.code只能取已有枚举；默认retryable=false，查证不是重发许可。

宿主须核验身份、任务版本、模式、暂停、权限、平台/账户/商品/售后归属、引用存在及不可变版本、来源、时间、页面版本、用户事件、选择凭证、当前状态及完整操作史。OutcomeReport.stage_complete不等于可寄件；effect_result只在关联原动作后才有意义。当前PlatformView缺标准物流事实键和来源时序绑定，不能根据任意Fact文本自动放行。

实际已读成果：order/remedy/interact/verify/recover/resume均有中央v1包；order商品选择凭证、remedy方案凭证不能仅凭非空信任；remedy明确正式准备门禁未接通。interact接受goal_step、platform_view、source_artifacts，可结构上接LogisticsPlan。verify只接受platform_view、receipt、ledger；原动作通过proposal_id找不可变提案，不能加expected_result字段。resume先用当前verify结果，不重放历史确认。interact执行桩为测试替身；其独立浏览器装置不等于生产运行时。catalog仍design_not_implementation/implemented=false，不据此否认包文件存在，也不据包存在宣称运行时注册。

v1没有两地址、预约记录、包裹、物流证据、未知动作显式输入。TaskSnapshot.pending_execution_refs/related_artifact_refs只能索引真实获准记录，不是任意扩展槽。单凭快照无pending不能证明完整台账无在途。默认停止正式预约和运单准备；读懂证据、解释状态、收集选择仍可进行。缺工程机制用blocked/contract_error，缺页面用needs_observation，不反复让用户确认。

scripts/check_plan.py提供check(request,result,context)，依赖jsonschema>=4,<5。context是严格定义的离线诊断上下文（context.schema.json），不是wire扩展或已实施宿主协议；完整样例在交付examples。registry保存实际中央正文，objects保存合成受控地址/时间/运单/选择/证据元数据，facts是宿主独立核验的语义见证。本代码不解析网页、不认证上下文真伪，绝不能从待验结果反向填见证。所有外部执行恒为false；无错误仅表示已实现检查通过。CLI仅读取显式指定三个JSON，输出诊断，无网络或外部写入。

宿主待实现：可信引用仓库和受保护核对界面；完整台账/发送前持久化；商品+售后+包裹的未知动作阻断（不能仅按proposal或变更内容去重）；内容绑定确认；任务比较更新与互斥；暂停/模式/session epoch失效；当前适配器和时区/期限验证；候选契约协商及消费者迁移；执行后重新观察和核对。此包不能替代这些服务。
