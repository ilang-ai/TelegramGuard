# corpus/ — Telegram 群 spam 语料库（I-Lang 格式）

这里保存 antispam.bot（@iLangGuardbot）在真实 Telegram 群里**自动收敛**出来的 spam 硬库，供反 spam 研究、
学术数据使用，以及让 AI 直接读取学习。文件是 I-Lang v5.0 格式（`::ILANG::v5.0::RULES`，`[TYPE:spam_library]`）。

## 怎么来的

1. bot 对群消息做 AI 判定（现在是 DeepSeek `deepseek-flash`）。
2. 每判出一条 spam，文本先归一化（全角转半角、去零宽字符、同形字还原、转小写、空白折叠），
   以 SHA-1 为主键落库；重复出现只加计数，不加行。联系方式（t.me 链接、@ 用户名、微信号、QQ、手机号）单独抽出。
3. bot 自己用这个库做**容灾硬判**：AI 不可用时，联系方式命中 / 文本命中 / 字符三元组 Jaccard ≥ 0.85 即判 spam。
4. 每周日 03:00（北京时间）自动清理：90 天没再出现且只见过一次的条目删除。
5. **本目录不是自动更新的**：每次 bot 迭代发版时，维护者手动跑一次导出并随版本提交。

## 文件里有什么

- `::FACT{source}`：生成规则说明。
- `::RULE{hard_judge}`：bot 容灾时怎么用这个库。
- `::FACT{contacts}`：spam 里出现 ≥ 2 次的联系方式。每行 `token ¦ count=次数 ¦ last=最近出现（UTC 日期）`。
- `::FACT{patterns}`：出现 ≥ 2 次的归一化 spam 文本（截断到 300 字）。每行 `文本 ¦ count ¦ first ¦ last`。

只收出现 ≥ 2 次的条目；只见过一次的不进文件，以免把 AI 的偶然误判发出去。

## 隐私

- 只含被判为 spam 的消息，**不含任何正常消息**，不含发送者 ID、群 ID。
- 联系方式是广告里公开刊登的联系方式，不是用户资料。
- 文本经过归一化，不是原始消息逐字节副本。

## 自己重新生成

```bash
venv/bin/python tools/export_corpus.py
```

读取 `data/bot.db`，写 `corpus/spamlib-antispam-bot-vYYYY.MM.DD.ilang.md`，目录里只留最新一份，旧版本看 git 历史。

## 用它

- 做自己的反 spam 兜底：按 `::RULE{hard_judge}` 三条规则实现即可，零外部依赖。
- 喂给 AI：整个文件就是给模型读的，I-Lang 的 FACT / RULE 块可直接当上下文。
- 研究：时间字段是 UTC 日期；`count` 是独立出现次数（同一条文本在不同群、不同时间各算一次）。

许可随仓库。
