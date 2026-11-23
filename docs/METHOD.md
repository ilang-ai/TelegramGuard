# Convergence-only learning for group anti-spam

**A zero-cost, self-converging hard library distilled from a language-model judge, with deterministic fallback and an open corpus in iLang form.**

Zhu, Long Quan (iLang Inc.) — ORCID 0009-0004-4540-8082
Software: TelegramGuard, concept DOI [10.5281/zenodo.22865154](https://doi.org/10.5281/zenodo.22865154)

> 中文摘要。群反 spam 的判定由一个大模型当裁判完成，但裁判是要钱、会断的。本文描述一种**只做收敛**的自学习方法：裁判每判出一条 spam，归一化后的文本以哈希为主键落库，重复只加计数；联系方式单独抽出。库不参与平时判定，只在裁判不可用时做**确定性容灾硬判**（联系方式命中、文本命中、字符三元组相似度），且只认出现两次以上的条目，使裁判的偶然误判不会被硬化。库每周自动清理并导出为 I-Lang 文件公开发布，供研究、复现和让 AI 直接学习。另附两条进群时的确定性规则：昵称本身就是广告的账号拒绝入群；新成员第一句是「签到」类填充的按机器人处理。本版给出设计与性质；量化结果随后续版本的语料库发布。

## 1. Problem

A moderation bot for public Telegram groups has to judge every message. In production TelegramGuard judges on the order of ten thousand messages a day across several hundred groups, using a hosted language model as the judge. Two properties of that judge shape the design:

1. **It costs money per call**, and a second, stronger model as fallback would cost an order of magnitude more.
2. **It is an external dependency.** Keys expire, balances run out, providers go down. In one 29-day incident the judge failed silently on every call and the bot fell back to a small hand-written keyword list without anyone noticing.

The question is therefore not "how to make the judge better" but **"what should the system learn from the judge while it is available, so that it keeps working at zero cost when it is not, and so that the learned knowledge is itself a publishable artefact."** Framed in the literature: the language model is a *weak labelling function* in the sense of Snorkel [Ratner 2017] and an *LLM-as-a-judge* [Zheng 2023]; what we distil from it is not a student network [Hinton 2015] but a counted, human-readable rule library.

## 2. Method

### 2.1 Convergence-only learning

Let the judge be an oracle `J(m) ∈ {spam, ok}` over messages `m`. The system never trains anything — no Bayesian filter in the classic sense [Androutsopoulos 2000], no fitted weights. It only **converges** the oracle's positive verdicts into a library `L`:

```
on J(m) = spam:
    n  := normalize(m)                 # full-width→half-width, zero-width removal,
                                       # homoglyph folding, lowercase, whitespace collapse
    h  := sha1(n)
    L[h].count += 1 ; L[h].last_seen := now     (insert with count = 1 if absent)
    for t in contacts(n):                       # t.me links, @handles, WeChat / QQ ids, phone numbers
        C[t].count += 1 ; C[t].last_seen := now
```

Normalization folds full-width characters, strips zero-width code points and maps visually confusable characters (Latin/Cyrillic/CJK look-alikes) to a canonical form, in the spirit of Unicode's confusable-character tables [UTS 39]; spam relies on exactly these substitutions to evade keyword filters.

Three choices make this trivially correct and cheap:

- **Idempotent by construction.** The hash is the primary key, so duplicates cannot exist; "deduplication" is not a job that can fail.
- **Positive-only.** Normal messages are never stored. The library contains nothing that a group member wrote in good faith.
- **Monotone with decay.** Entries only ever gain weight while they recur. A weekly job removes entries that were seen once and not again for 90 days, so the library tracks the current spam population instead of growing forever — a deliberately simple answer to concept drift [Gama 2014]: forget what stopped recurring, keep what keeps coming back.

### 2.2 Deterministic fallback (disaster-recovery judgement)

When the oracle is unavailable — call fails, or returns something unparseable — the message is judged locally, with no network call:

```
hard(m):
    n := normalize(m)
    if any contact token in n is in C with count ≥ 2       → spam
    if sha1(n) in L with count ≥ 2                          → spam
    if max_{e ∈ L, count ≥ 2} J3(n, e) ≥ 0.85               → spam
    else                                                    → defer to the keyword lexicon
```

`J3` is the Jaccard index [Jaccard 1912] of character trigram sets (whitespace removed) — the resemblance measure of Broder's shingling [Broder 1997] applied at character level, which is language-agnostic and handles Chinese without tokenisation. Length pre-filtering (±50 %) keeps the scan linear and cheap; the library is cached in memory and refreshed every ten minutes.

**The `count ≥ 2` gate is the false-positive guard.** A language-model judge is occasionally wrong. A single wrong verdict enters the library with count 1 and is inert; it only becomes an active rule if the same normalized text (or the same contact token) is independently judged spam again. This is the crudest possible form of requiring agreement between independent noisy labels — the problem Dawid and Skene modelled with observer error rates [Dawid 1979] — chosen because it needs no model of the judge's reliability. In practice spam is repeated verbatim or near-verbatim across groups, while a mistaken verdict on a genuine message is not.

The library is **only** used in fallback. While the oracle is healthy the judgement path is unchanged, so the system's day-to-day precision is the oracle's precision; the library adds resilience, not noise.

### 2.3 Deterministic rules at the door

Two rules act before any model is consulted, because the signal is unambiguous and the cost of a model call is wasted on it:

- **Name-is-spam.** If a joining account's display name or username contains a contact channel (t.me link, another @handle, WeChat/QQ/phone pattern), a URL, a contact token already in `C`, or scores above the lexicon's hard threshold, the join is rejected and the name itself is fed to `learn`. The account's own @username is excluded. Real people's names, including emoji-decorated ones, do not match these patterns.
- **First-message probe.** A newly joined member (tracked from the `chat_member` update, 48 h window) whose first message is check-in filler — 签到 / 打卡 / 测试 / test / ping / 在吗 …, or ≤ 6 characters of pure digits, punctuation or emoji — is removed. Spam automation uses such messages to test whether a group is moderated; genuine newcomers do not open with them. The same patterns applied to *all* members would be far too aggressive (a wider probe pattern measured against real Chinese group chat matched 59 % of ordinary short messages), which is why this rule is scoped strictly to a member's first message.

### 2.4 The corpus as an artefact

The weekly maintenance job exports the active part of the library (`count ≥ 2`) as an **iLang** document [iLang spec]. Publishing a counted, deduplicated short-text spam collection follows the precedent of the SMS spam corpus [Almeida 2011], which made comparable results possible for that medium:

```
::ILANG::v5.0::RULES
[TYPE:spam_library] ...
::FACT{source|conf:confirmed}      how the library was produced
::RULE{hard_judge|conf:confirmed}  the three fallback rules, stated for a reader or a model
::FACT{contacts|conf:confirmed}    token ¦ count ¦ last-seen
::FACT{patterns|conf:confirmed}    normalized text ¦ count ¦ first ¦ last
```

The export is written for two readers at once: a human or a classifier that wants a current, deduplicated, counted list of Chinese-language Telegram spam, and a language model that can be handed the file as context and will know both the data and the rule for using it. Snapshots are published in `corpus/` with each release of this repository and archived with the release's DOI, so a citation pins an exact version of the data.

## 3. Properties

| Property | Why it holds |
|---|---|
| Zero marginal cost | `learn` is one UPSERT per positive verdict; `hard` is in-memory. No model calls on the fallback path. |
| No training, no drift | Nothing is fitted. The library *is* the oracle's verdict history, counted. |
| Bounded false positives in fallback | An entry needs two independent positive verdicts before it can act. |
| Self-pruning | Weekly removal of stale singletons; `VACUUM` keeps the store small. |
| Reproducible | The corpus file plus the three rules in §2.2 reproduce the fallback judge exactly. |
| Transparent | Every active rule is a line in a published text file, in a form a model can read. |

## 4. What this version does and does not claim

This document describes the design as deployed on 2026-11-23. It does **not** yet report measurements: the library starts empty at deployment and fills from production traffic, and the fallback path is exercised only during oracle outages. Later releases will publish, alongside the corpus snapshot, the quantities that matter for this method:

- library size and active-entry count over time, and the fraction of oracle-positive messages that were already in the library (a direct measure of how repetitive the spam population is);
- during oracle outages, the hard-judge hit rate and the share of hits by rule (contact / exact / similar);
- join-time rejections by rule, with a manual precision check on a sample.

Numbers are reported when they exist; the absence of a number means it has not been measured.

## 5. Relation to prior work

Content-based spam filtering with naive Bayes classifiers was established for e-mail by Sahami et al. (1998) and evaluated systematically by Androutsopoulos et al. [Androutsopoulos 2000]; the SMS spam corpus [Almeida 2011] carried the same methodology to short messages, the closest medium to group chat. Current open-source Telegram anti-spam bots such as *tg-spam* combine a Bayes classifier over sample sets, stop-words, similarity checks and metadata heuristics, with optional language-model checks. Using a large model as the labeller is the weak-supervision setting of Snorkel [Ratner 2017] and the LLM-as-a-judge setting of Zheng et al. [Zheng 2023]; compressing a strong model's behaviour into a cheap artefact is the aim of knowledge distillation [Hinton 2015]. The method here differs in what is learned and from whom: nothing is fitted, the only source of labels is the production language-model judge, the learned object is a counted, deduplicated library that is published as text, and the library is deliberately confined to the fallback path so that it can never lower the precision of the primary judge.

## 6. Reproducing

- `modules/spamlib.py` — `learn`, `hard_judge`, `weekly_maintain`, `export_ilang`.
- `modules/namecheck.py` — the name-is-spam rule; `modules/probe.py` — probe patterns, join tracking and the first-message rule.
- `tools/export_corpus.py` — regenerate `corpus/` from a running instance's database.
- `corpus/README.md` — field definitions and privacy boundary of the published data.

## References

- [Jaccard 1912] P. Jaccard. The distribution of the flora in the alpine zone. *New Phytologist* 11(2):37–50, 1912. doi:[10.1111/j.1469-8137.1912.tb05611.x](https://doi.org/10.1111/j.1469-8137.1912.tb05611.x)
- [Broder 1997] A. Z. Broder. On the resemblance and containment of documents. *Proceedings, Compression and Complexity of SEQUENCES 1997*, IEEE. doi:[10.1109/SEQUEN.1997.666900](https://doi.org/10.1109/SEQUEN.1997.666900)
- [Dawid 1979] A. P. Dawid, A. M. Skene. Maximum likelihood estimation of observer error-rates using the EM algorithm. *Applied Statistics* 28(1):20–28, 1979. doi:[10.2307/2346806](https://doi.org/10.2307/2346806)
- [Androutsopoulos 2000] I. Androutsopoulos, J. Koutsias, K. V. Chandrinos, G. Paliouras, C. D. Spyropoulos. An evaluation of naive Bayesian anti-spam filtering. Workshop on Machine Learning in the New Information Age, ECML 2000. doi:[10.48550/arXiv.cs/0006013](https://doi.org/10.48550/arXiv.cs/0006013)
- [Almeida 2011] T. A. Almeida, J. M. Gómez Hidalgo, A. Yamakami. Contributions to the study of SMS spam filtering: new collection and results. *DocEng '11*, ACM. doi:[10.1145/2034691.2034742](https://doi.org/10.1145/2034691.2034742)
- [Gama 2014] J. Gama, I. Žliobaitė, A. Bifet, M. Pechenizkiy, A. Bouchachia. A survey on concept drift adaptation. *ACM Computing Surveys* 46(4), 2014. doi:[10.1145/2523813](https://doi.org/10.1145/2523813)
- [Hinton 2015] G. Hinton, O. Vinyals, J. Dean. Distilling the knowledge in a neural network. arXiv:1503.02531, 2015. doi:[10.48550/arXiv.1503.02531](https://doi.org/10.48550/arXiv.1503.02531)
- [Ratner 2017] A. Ratner, S. H. Bach, H. Ehrenberg, J. Fries, S. Wu, C. Ré. Snorkel: rapid training data creation with weak supervision. *Proceedings of the VLDB Endowment* 11(3):269–282, 2017. doi:[10.14778/3157794.3157797](https://doi.org/10.14778/3157794.3157797)
- [Zheng 2023] L. Zheng, W.-L. Chiang, Y. Sheng, S. Zhuang, Z. Wu, Y. Zhuang, Z. Lin, Z. Li, D. Li, E. P. Xing, H. Zhang, J. E. Gonzalez, I. Stoica. Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. arXiv:2306.05685, 2023 (NeurIPS 2023 Datasets and Benchmarks). doi:[10.48550/arXiv.2306.05685](https://doi.org/10.48550/arXiv.2306.05685)
- [UTS 39] Unicode Consortium. Unicode Technical Standard #39: Unicode Security Mechanisms. https://www.unicode.org/reports/tr39/
- [iLang spec] L. Q. Zhu. iLang Protocol Specification. Zenodo. doi:[10.5281/zenodo.21821452](https://doi.org/10.5281/zenodo.21821452)
- Sahami, M., Dumais, S., Heckerman, D., Horvitz, E. A Bayesian approach to filtering junk e-mail. AAAI-98 Workshop on Learning for Text Categorization, 1998 (no DOI).
- umputun. tg-spam: anti-spam bot for Telegram and general-purpose anti-spam library. https://github.com/umputun/tg-spam (MIT).
