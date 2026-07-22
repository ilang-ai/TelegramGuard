<div align="center">

# 🛡️ antispam.bot

**守护你电报群的 AI —— 自动清垃圾广告,还能真正回答问题。**

开源(MIT)、零配置、可自托管 —— 项目代号 **TelegramGuard**。

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Powered by I-Lang](https://img.shields.io/badge/powered%20by-I--Lang%20Spec-blueviolet)](https://ilang.ai)
[![AI: OpenAI-compatible](https://img.shields.io/badge/AI-OpenAI--compatible-06D6A0)](#自己部署)

🌐 [English](README.md) · [中文](README_CN.md) · [Русский](README_RU.md) · [Español](README_ES.md) · [العربية](README_AR.md) · [فارسی](README_FA.md)

</div>

---

## 加进群就能用(零配置)

把官方机器人拉进群 —— 不用安装、不用服务器、不花钱。

### → [@iLangGuardBot](https://t.me/iLangGuardBot)

1. 在电报搜 `@iLangGuardBot`
2. 加到你的群里
3. 给管理员权限 —— **删消息** + **封人**
4. 完事。垃圾自动清理;随时 @ 它提问。

也可以直接私聊它,什么都能问。

---

## 它能做什么

**🚫 反垃圾** — 识别广告、诈骗、加密货币与赌博 spam。看穿 Unicode 变体、全角/零宽字符、emoji 混淆和黑话。零成本预过滤在消息碰到 AI 之前就干掉明显垃圾,刷屏更是完全不花 AI 调用就拦下。

**👁️ 看图** — 识别图片和视频缩略图,拦截图片广告和二维码诈骗。聊天时读的是照片背后的故事,不是干巴巴描述像素。

**💬 聊天** — 在群里 @ 它或私聊。自动检测语言,用你的语言回复。什么都能问,给你清晰实用的回答 —— 敏感话题客观陈述,真正有害的事守住边界。

---

## 自己部署

用任意 **OpenAI 兼容**的 AI 服务 —— [硅基流动](https://cloud.siliconflow.cn)(默认)、OpenAI、DeepSeek 或本地模型。你需要两样:

- **Bot Token** — [@BotFather](https://t.me/BotFather) → `/newbot`
- **AI API Key** — 你的服务商(默认对接硅基流动)

### 方式一:VPS 一键安装

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

自动下载、装依赖、填两个 key、创建 systemd 服务并启动。管理命令:

```bash
systemctl status telegramguard     # 看状态
systemctl restart telegramguard    # 重启
journalctl -u telegramguard -f     # 看日志
```

### 方式二:HuggingFace Space(免费,不用服务器)

1. Fork 这个仓库
2. 创建 [HuggingFace Space](https://huggingface.co/new-space) → Docker SDK → Blank
3. GitHub 仓库 → Settings → Secrets → 加 `HF_TOKEN`(你的 HF write token)
4. HF Space → Settings → Secrets → 加 `BOT_TOKEN` + `AI_API_KEY`
5. HF Space → Settings → 开启**持久化存储**,让 `/data`(SQLite 库)可写 —— 或加个 `DB_PATH` secret 指向可写路径
6. 推代码到 GitHub,自动部署到 Space

### 方式三:手动

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
cp .env.example .env         # 填 BOT_TOKEN + AI_API_KEY
set -a; source .env; set +a  # 把 .env 加载进环境变量
python bot.py
```

创建机器人后,给 [@BotFather](https://t.me/BotFather) 发 `/setjoingroups → Enable` 和 `/setprivacy → Disable`(让它能看到群消息)。

### 配置项

全部通过环境变量设置 —— 见 [`.env.example`](.env.example):

| 变量 | 默认值 | 作用 |
|------|--------|------|
| `BOT_TOKEN` | *(必填)* | 电报机器人 token |
| `AI_API_KEY` | *(必填)* | OpenAI 兼容的 API key |
| `AI_BASE_URL` | `https://api.siliconflow.cn/v1` | 服务端点 |
| `AI_MODEL` | `deepseek-ai/DeepSeek-V4-Flash` | 文本模型 |
| `AI_VISION_MODELS` | `Qwen/Qwen3-VL-30B…` | 识图模型容错链(逗号分隔) |
| `AI_AUDIO_MODEL` | `Qwen/Qwen3-Omni-30B-A3B-Instruct` | 语音模型 |
| `AI_IMAGE_MAX_WIDTH` | `600` | 识图前压缩宽度 |
| `LEXICON_HARD_THRESHOLD` | `6` | 黑话预过滤严格度(越高越严) |

---

## 自定义 AI 人格

机器人的大脑是几个 `.ilang` 文件 —— [I-Lang Prompt Spec](https://ilang.ai),每个 `::GENE` 定义一个行为。

```
prompts_demo/
├── persona.ilang     怎么思考 + 怎么说话
├── antispam.ilang    什么算垃圾
└── vision.ilang      怎么看图
```

```
::GENE_IMMUTABLE{S002, T:RUTHLESS_RED_TEAM, A:FLATTER⇒FAIL, G:ALL, Θ:ALWAYS}
# 给它看方案, 它不夸你, 直接找致命漏洞。

::GENE_MUTABLE{P002, T:CONCISE, G:ALL, Θ:ALWAYS}
# 2-3 句话。先给答案, 后补细节, 零废话。

::IMMUNE{SPAM, DETECT_THEN_NUKE}
# 广告 / 诈骗 / 刷屏 → 删除 + 记过, 看穿规避手法。
```

改基因 = 改机器人。想自定义:复制 `prompts_demo/` 到 `prompts/`(优先加载)再编辑。

**[学习 I-Lang Prompt Spec →](https://ilang.ai)**

---

## 项目结构

```
TelegramGuard/
├── bot.py                 入口 —— 处理器(群 · 私聊 · 事件)
├── config.py              环境变量配置
├── install.sh             一键 VPS 安装脚本
├── Dockerfile             容器构建
├── modules/
│   ├── ai_provider.py     OpenAI兼容 AI 层(文本 · 识图 · 语音)
│   ├── chat.py            提示词编排(加载 .ilang)
│   ├── prefilter.py       零成本垃圾预过滤 + 三路分诊
│   ├── lexicon.py         黑话/规避归一化 + 打分
│   ├── ilang_judge.py     I-Lang 判定函数
│   ├── admin.py           群管理
│   ├── db.py              SQLite 共享连接 + 异步锁
│   └── database.py        数据表
└── prompts_demo/          AI 人格定义(.ilang 文件)
```

---

<div align="center">

基于 **[I-Lang Prompt Spec](https://ilang.ai)** 构建 —— 用基因代码定义 AI 行为。

[![Spec](https://img.shields.io/badge/spec-ilang--ai/ilang--spec-black?logo=github)](https://github.com/ilang-ai/ilang-spec)
[![Web](https://img.shields.io/badge/web-ilang.ai-blue)](https://ilang.ai)
[![HF](https://img.shields.io/badge/HF-i--Lang-yellow?logo=huggingface)](https://huggingface.co/i-Lang)

MIT · © [iLang Inc.](https://eastsoft.com) · [antispam.bot](https://antispam.bot) · [ilang.ai](https://ilang.ai)

</div>
