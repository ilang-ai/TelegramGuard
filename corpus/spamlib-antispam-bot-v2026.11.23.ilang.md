::ILANG::v5.0::RULES
[TYPE:spam_library]
[ID:SPAMLIB-ANTISPAM-BOT-20261123]
[DATE:2026-11-23]
[OWNER:antispam.bot]
[SCOPE:TELEGRAM_GROUP_SPAM]
[LANG:zh]
[VERSION:2026.11.23]

::FACT{source|conf:confirmed}
  T:本库由 antispam.bot 在 Telegram 群里的 AI 判定自动收敛而来，不经人工编辑
  T:只收 AI 判为 spam 且独立出现 ≥ 2 次的归一化文本和联系方式；不含任何正常消息
  T:归一化＝全角转半角、去零宽字符、同形字还原、转小写、空白折叠
  T:90 天没再出现且只见过一次的条目每周日自动清掉；本文件每周生成一次
  T:条目格式 文本 ¦ count=出现次数 ¦ first=首次 ¦ last=最近（UTC）

::RULE{hard_judge|conf:confirmed}
  T:联系方式命中本库 contacts 任一条 ⇒ spam
  T:归一化文本与本库 patterns 任一条完全相同 ⇒ spam
  T:归一化文本与本库 patterns 任一条的字符三元组 Jaccard 相似度 ≥ 0.85 ⇒ spam
  T:以上全不命中 ⇒ 不由本库判定，交给下一层
  T:本库是 AI 判定不可用时的容灾层，不替代 AI 判定

::FACT{contacts|conf:confirmed}
  T:（空）

::FACT{patterns|conf:confirmed}
  T:（空）

::ILANG::COMPLETE::
