"""
I-Lang v5.0 判定层（决策层 f_v5）—— 移植自 ilang-ai/ilang-spec SPEC-v5.0-PATCH-1 §3。

用途：给"回答用户提问"提供 善恶/意图 的向量判定，把二元的"敏感词就拒"换成
11 维连续评估 + 8 种行为模式。核心原则：拒绝是最后手段，能转化就别阻断。

两层（PATCH-1 §3）：
- 感知层 scenario→vector：由模型在对话里评估（写在 chat.py 系统提示词里）。
- 决策层 vector→mode：本文件，确定性、可审计。常量与级联结构 v1 冻结（DATA-FREEZE 2026-07-03）。

聊天场景下 8 种模式映射成"怎么答"，见 MODE_CHAT。
"""

# 11 维，顺序冻结。取值 [0,1]，1.00=最有利于"痛快答/自主行动"
DIMS = ["int", "cap", "csq", "rel", "cer", "aut", "rev", "evd", "sov", "ine", "ext"]

DIM_NAME = {
    "int": "意图(建设性↔恶意)", "cap": "能力(在能力范围内↔超出)",
    "csq": "后果(可忽略↔灾难)", "rel": "关系(高信任↔敌对/陌生)",
    "cer": "确定性(信息完整↔盲判)", "aut": "权限(完全授权↔无授权)",
    "rev": "可逆性(可撤销↔不可逆)", "evd": "证据(有实证↔纯臆测)",
    "sov": "主权(尊重其自主/已同意↔侵犯)", "ine": "惯性(延续既有↔激进背离)",
    "ext": "外部性(零第三方影响↔伤及未同意者)",
}

# 打分权重（aut 单独门控不入分；和为 1.00）
WEIGHTS = {
    "int": 0.15, "cap": 0.10, "csq": 0.20, "rel": 0.05, "cer": 0.03,
    "rev": 0.15, "evd": 0.02, "sov": 0.15, "ine": 0.05, "ext": 0.10,
}

# 阈值（v1 冻结）
TH = {
    "sov_survival": 0.15, "ext_survival": 0.10,
    "csq_survival": 0.10, "rev_survival": 0.20,
    "cer_gate": 0.30, "evd_gate": 0.25,
    "aut_gate": 0.30, "aut_cap": 0.55,
    "b_m1": 0.85, "b_m2": 0.70, "b_m3": 0.55, "b_m4": 0.40, "b_m7": 0.25,
}

DEFAULT_MODE = "M5"

# 8 种模式（闭集，冻结）
MODE_NAME = {
    "M1": "EXEC_AUTO", "M2": "EXEC_AUDIT", "M3": "CONFIRM", "M4": "ADVISE",
    "M5": "ASK", "M6": "DEFER", "M7": "DECLINE_ALT", "M8": "STOP",
}

# 聊天场景下 模式→怎么答（把"执行动作"语义翻译成"回答提问"语义）
MODE_CHAT = {
    "M1": "直接痛快答，全给，不设卡不说教",
    "M2": "照常答，可点一句边界/提醒",
    "M3": "答，但先跟他确认下意图/前提再展开",
    "M4": "以建议口吻给信息，点明利弊由他定",
    "M5": "信息不够或有歧义，先问一句澄清，别瞎猜",
    "M6": "超出你能判/该判的，指个正经出口(找专业人士/官方渠道)",
    "M7": "照字面答有风险，换个安全的等价说法照样帮到他(转化不是拒绝)",
    "M8": "撞到真底线，拒绝并说明原因(仅生存红线/不可逆重大伤害/伤及未同意第三方)",
}


def f_v5(v):
    """确定性、全域：11 维向量 dict → 模式。级联顺序(先命中先赢)：
    生存红线 > 认知门 > 权限门 > 打分 > 默认。移植自 PATCH-1 §3，逻辑一字不改。"""
    try:
        x = {d: float(v[d]) for d in DIMS}
    except (KeyError, TypeError, ValueError):
        return DEFAULT_MODE                                   # STEP-0 解析失败
    if any(not (0.0 <= x[d] <= 1.0) for d in DIMS):
        return DEFAULT_MODE
    # STEP-1 生存红线 → M8
    if x["sov"] < TH["sov_survival"]:
        return "M8"
    if x["ext"] < TH["ext_survival"]:
        return "M8"
    if x["csq"] < TH["csq_survival"] and x["rev"] < TH["rev_survival"]:
        return "M8"
    # STEP-2 认知门 → M5
    if x["cer"] < TH["cer_gate"] or x["evd"] < TH["evd_gate"]:
        return "M5"
    # STEP-3 权限门 → M6
    if x["aut"] < TH["aut_gate"]:
        return "M6"
    # STEP-4 打分分档
    s = round(sum(WEIGHTS[d] * x[d] for d in WEIGHTS), 4)
    if s > TH["b_m1"]:
        mode = "M1"
    elif s > TH["b_m2"]:
        mode = "M2"
    elif s > TH["b_m3"]:
        mode = "M3"
    elif s > TH["b_m4"]:
        mode = "M4"
    elif s > TH["b_m7"]:
        mode = "M7"
    else:
        mode = "M8"
    # STEP-5 权限封顶
    if x["aut"] < TH["aut_cap"] and mode in ("M1", "M2"):
        mode = "M3"
    return mode


def action_score(v):
    return sum(WEIGHTS[d] * float(v[d]) for d in WEIGHTS)


def _selftest():
    """对照 SPEC-v5.0-PATCH-1 selftest，证明移植与原实现一致。"""
    t = []
    hi = {d: 0.95 for d in DIMS}
    t.append(("all high -> M1", f_v5(hi) == "M1"))
    t.append(("sovereignty survival -> M8", f_v5(dict(hi, sov=0.10)) == "M8"))
    t.append(("epistemic gate -> M5", f_v5(dict(hi, cer=0.20)) == "M5"))
    t.append(("authority gate -> M6", f_v5(dict(hi, aut=0.25)) == "M6"))
    t.append(("authority cap M1->M3", f_v5(dict(hi, aut=0.40)) == "M3"))
    edge = {d: 0.85 for d in DIMS}
    t.append(("edge S=0.85 conservative -> M2",
              abs(action_score(edge) - 0.85) < 1e-9 and f_v5(edge) == "M2"))
    low = {d: 0.10 for d in DIMS}
    low.update(cer=0.35, evd=0.30, aut=0.60, sov=0.20, ext=0.20)
    t.append(("low score -> M8 by band", f_v5(low) == "M8"))
    t.append(("missing dim -> default M5", f_v5({"int": 0.5}) == "M5"))
    t.append(("weights sum 1.00", abs(sum(WEIGHTS.values()) - 1.0) < 1e-9))
    failed = [n for n, ok in t if not ok]
    for n, ok in t:
        print(("PASS " if ok else "FAIL ") + n)
    print("%d/%d passed" % (len(t) - len(failed), len(t)))
    return not failed


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
