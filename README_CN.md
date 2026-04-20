<div align="center">

# 🛡️ TelegramGuard

**真正回答问题的AI群管机器人**

反垃圾 · 看图识别 · 智能对话 · 知无不答

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Powered by I-Lang](https://img.shields.io/badge/powered%20by-I--Lang%20Spec-blueviolet)](https://ilang.ai)
[![Gemini](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-4285F4)](https://aistudio.google.com)

**[English](README.md)** | **[中文](README_CN.md)**

</div>

---

## 直接使用（零成本零配置）

把官方机器人拉进你的电报群, 立刻开始工作。不需要安装, 不需要服务器, 不花一分钱。

**[@iLangGuardBot](https://t.me/iLangGuardBot)**

1. 打开电报, 搜索 `@iLangGuardBot`
2. 把它加到你的群里
3. 给管理员权限（删消息 + 封人）
4. 完事。反垃圾全自动。

也可以直接私聊机器人, 什么都能问。

---

## 它能做什么

**反垃圾** — AI三步分析, 识别广告、诈骗、加密货币spam、色情、政治宣传。能看穿Unicode变体、emoji混淆、谐音替代等花招。相同消息刷屏3次自动判定, 零AI成本。封人+删除全部近期消息, 并行执行。

**看图** — 识别图片和视频缩略图。拦截图片类垃圾信息。聊天模式下, 分析照片背后真正发生了什么, 不是干巴巴描述物体。

**聊天** — 在群里@它或者私聊。自动检测语言, 用你的语言回复。金融、技术、感情、文化, 什么都聊。先回答, 不说教。

**敏感话题三步法** — 别的机器人直接拒绝, TelegramGuard不一样:

| 步骤 | 做什么 |
|------|--------|
| **风险揭底** | 像老江湖一样告诉你这里面的坑: 骗局、陷阱、后果 |
| **确认意图** | 问你是好奇还是认真的, 不带评判 |
| **给方向** | 给足够的信息让你做聪明的决定 |

---

## 自己部署

### 方式一: VPS一键安装

```bash
curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | sudo bash
```

一行命令搞定: 下载代码、装依赖、填token、创建系统服务、自动启动。

你需要准备两样东西（都免费）:
- **Bot Token** — 打开电报 → 找 [@BotFather](https://t.me/BotFather) → 发 `/newbot`
- **Gemini API Key** — 去 [aistudio.google.com/apikey](https://aistudio.google.com/apikey) 免费申请

装完后管理:
```bash
systemctl status telegramguard     # 看状态
systemctl restart telegramguard    # 重启
journalctl -u telegramguard -f    # 看日志
```

### 方式二: HuggingFace Space（免费, 不需要服务器）

1. Fork 这个仓库
2. 创建 [HuggingFace Space](https://huggingface.co/new-space) → Docker SDK → Blank
3. GitHub仓库 Settings → Secrets → 加 `HF_TOKEN`
4. HF Space Settings → Secrets → 加 `BOT_TOKEN` + `GEMINI_API_KEY`
5. 推代码自动部署

### 方式三: 手动

```bash
git clone https://github.com/ilang-ai/TelegramGuard.git
cd TelegramGuard
pip install -r requirements.txt
export BOT_TOKEN="你的token"
export GEMINI_API_KEY="你的key"
python bot.py
```

---

## 自定义AI人格

机器人的大脑是三个 `.ilang` 文件, 使用 [I-Lang Prompt Spec](https://ilang.ai) 编写:

```
prompts_demo/
├── persona.ilang     思维方式 + 说话方式
├── antispam.ilang    什么算垃圾信息
└── vision.ilang      怎么看图
```

每个文件里的 `::GENE` 定义一个行为:

```
::GENE_IMMUTABLE{S001, T:ANTI_COLLAPSE, A:MORAL_PANIC⇒LETHAL, G:ALL, Θ:ALWAYS}
# 用户问敏感话题时: 不慌, 客观分析

::IMMUNE{RISKY_OR_ILLEGAL, THREE_STEP_RESPONSE}
# 第一步: 揭底风险  第二步: 确认意图  第三步: 给方向
```

改基因 = 改机器人。想自定义: 复制 `prompts_demo/` 到 `prompts/`, 然后编辑。机器人优先加载 `prompts/`。

**[学习 I-Lang Prompt Spec →](https://ilang.ai)**

---

## BotFather 设置

创建机器人后, 给 [@BotFather](https://t.me/BotFather) 发:

```
/setjoingroups  → Enable（允许加群）
/setprivacy     → Disable（让机器人能看到群消息）
```

---

## 项目结构

```
TelegramGuard/
├── bot.py                 核心逻辑
├── config.py              环境变量配置
├── install.sh             一键安装脚本
├── Dockerfile             HF Space部署
├── modules/
│   ├── chat.py            AI引擎（启动时加载.ilang）
│   ├── db.py              SQLite共享连接 + 异步锁
│   ├── database.py        数据表
│   └── admin.py           群管理
└── prompts_demo/          AI人格定义（.ilang文件）
```

---

<div align="center">

基于 **[I-Lang Prompt Spec](https://ilang.ai)** 构建 — 用基因代码定义AI行为

[![Spec](https://img.shields.io/badge/spec-ilang--ai/ilang--spec-black?logo=github)](https://github.com/ilang-ai/ilang-spec)
[![Web](https://img.shields.io/badge/web-ilang.ai-blue)](https://ilang.ai)
[![HF](https://img.shields.io/badge/HF-i--Lang-yellow?logo=huggingface)](https://huggingface.co/i-Lang)

MIT | [Eastsoft Inc.](https://eastsoft.com) | [I-Lang Research](https://research.ilang.ai)

</div>
