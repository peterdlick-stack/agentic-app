"""情境 DJ 探索位参考实现（EXPLORE 轮，6+1 的第 7 首）。应用里的 OctoScript 必须与本文件逐值一致。
用法：python3 -I tools/explore/ref_explore.py <main.splash> --out expected.json [--selftest]
只用标准库。排名、特征、评价表一律复用 tools/pref/ref_pref.py，本文件不改它们的任何数值。
（10-12：第 3 维特征改为 SEED 里的节奏三档 pc，原 --bpm 参数已去掉。）

算法（Beta-Thompson）：
  候选 = PREF 前 TOPK 名里、不在这次 6 首里、且该歌手在 6 首里不足 2 首的歌
  对每首候选：c1 = 这个活动下 ♥ 行数，c0 = ✕ 行数（取自 pref_votes 评价表，每个 (推荐, 歌) 只算最后一票）
             总数超过 X_CAP 时按比例缩到 X_CAP；a = 1 + c1，b = 1 + c0
             θ ~ Beta(a, b)：生成 a+b-1 个确定性均匀数，升序排列后取第 a 个（整数参数 Beta 的顺序统计量）
  取 θ 最大的一首；并列按 PREF 名次升序。
"""
import importlib.util, json, math, os, sys

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("ref_pref", os.path.join(_here, "..", "pref", "ref_pref.py"))
RP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RP)

P = RP.P                 # 1000003，与 PREF 哈希同一个模数
LCG_A, LCG_C = 48271, 11 # 均匀数递推：h = (h*48271 + 11) mod P；中间值 < 5e10，双精度精确
X_CAP = 40               # 每首歌参与抽样的票数上限（控制指令数）
X_TAG = "x"              # 探索专用种子前缀，和并列定序哈希错开


def x_seed(seed):
    """探索种子字符串："x" + str(int)。应用端拼接时数字部分必须与 Python str(int) 一致（"x1"，不是 "x1.0"）。"""
    return X_TAG + str(seed)


def uniforms(seed, key, n):
    """n 个 (0,1) 内的确定性均匀数。h0 = PREF 哈希(x_seed, key)，之后按 LCG 递推，每步先递推再取值。"""
    h = RP.tie_hash(x_seed(seed), key)
    out = []
    for _ in range(n):
        h = (h * LCG_A + LCG_C) % P
        out.append((h + 0.5) / P)
    return out


def cap_counts(c1, c0):
    """总票数超过 X_CAP 时按比例缩放。舍入一律 floor(x + 0.5)，不用 Python round（银行家舍入）。"""
    t = c1 + c0
    if t <= X_CAP:
        return c1, c0
    k1 = math.floor(X_CAP * c1 / t + 0.5)
    return k1, X_CAP - k1


def beta_draw(seed, key, a, b):
    """整数参数 Beta(a, b) 的一次抽样：a+b-1 个均匀数升序后的第 a 个。"""
    us = sorted(uniforms(seed, key, a + b - 1))
    return us[a - 1]


def counts(votes, act, key):
    """评价表里 (活动 act, 歌 key) 的 ♥ 行数与 ✕ 行数。votes 行形状同 PREF：{n r k a y L}（可带 x）。"""
    c1 = c0 = 0
    for row in votes:
        if row["a"] == act and row["k"] == key:
            if row["y"] == 1:
                c1 += 1
            else:
                c0 += 1
    return c1, c0


def why_text(c1, c0):
    if c1 + c0 == 0:
        return "试一首：这个场景下你还没评过它"
    return "试一首：这个场景下 ♥" + str(c1) + " ✕" + str(c0) + "，再给它一次机会"


def explore_pick(rows, pick_keys, act, votes, seed, on=True):
    """rows = PREF rank() 的输出（已按名次排好）；pick_keys = 这次 6 首的歌曲键。
    返回 None（不出探索位），或 {k, rank, c1, c0, a, b, theta, xt, why}。"""
    if not on or act not in RP.ACTS:
        return None
    picked = set(pick_keys)
    per = {}
    for k in pick_keys:
        art = k.split("|", 1)[1]
        per[art] = per.get(art, 0) + 1
    best = None
    for r in rows[:RP.TOPK]:
        k = r["k"]
        if k in picked or per.get(k.split("|", 1)[1], 0) >= 2:
            continue
        c1, c0 = counts(votes, act, k)
        u1, u0 = cap_counts(c1, c0)
        a, b = 1 + u1, 1 + u0
        th = beta_draw(seed, k, a, b)
        if best is None or th > best["theta"]:     # 严格大于：并列时保留名次更靠前的
            best = {"k": k, "rank": r["rank"], "c1": c1, "c0": c0, "a": a, "b": b, "theta": th,
                    "xt": math.floor(th * 1000000), "why": why_text(c1, c0)}
    return best


def selftest(keys):
    """统计自检（不进期望值）：抽样均值应接近 a/(a+b)，探索位在无票时应大致均匀。"""
    print("selftest: mean of Beta draws over seeds 1..3000 (expect ~ a/(a+b))")
    for a, b in [(1, 1), (2, 1), (1, 3), (5, 5), (8, 2), (1, 9)]:
        xs = [beta_draw(s, keys[s % len(keys)], a, b) for s in range(1, 3001)]
        m = sum(xs) / len(xs)
        print(f"  Beta({a},{b}) mean {m:.4f} vs {a/(a+b):.4f}  |diff| {abs(m - a/(a+b)):.4f}")
    xs = [beta_draw(s, keys[0], 1, 1) for s in range(1, 3001)]
    bins = [0] * 10
    for x in xs:
        bins[min(9, int(x * 10))] += 1
    print("  Beta(1,1) decile counts (expect ~300 each):", bins)


def main():
    args = sys.argv[1:]
    songs = RP.load_seed(args[0])
    byk = {RP.key_of(s): s for s in songs}
    bpm = {}   # 已不用：节奏写在 SEED 的 pc 字段，ref_pref 的签名仍带这个参数
    keys = [RP.key_of(s) for s in songs]
    out = {"constants": {"P": P, "LCG_A": LCG_A, "LCG_C": LCG_C, "X_CAP": X_CAP, "X_TAG": X_TAG, "TOPK": RP.TOPK}}

    # ---- X1 均匀数与 Beta 抽样（逐值核对用）----
    out["x1_uniforms"] = {str(seed): {k: uniforms(seed, k, 3) for k in keys[:5]} for seed in (1, 17)}
    out["x1_theta_11"] = {str(seed): {k: beta_draw(seed, k, 1, 1) for k in keys} for seed in (1, 17)}
    pairs = [(2, 1), (1, 3), (4, 4), (6, 2), (1, 41), (41, 1), (21, 21)]
    out["x1_theta_ab"] = [{"seed": 123456, "k": keys[i % len(keys)], "a": a, "b": b,
                           "theta": beta_draw(123456, keys[i % len(keys)], a, b)} for i, (a, b) in enumerate(pairs)]
    out["x1_cap"] = [[c1, c0, *cap_counts(c1, c0)] for c1, c0 in [(0, 0), (40, 0), (25, 15), (30, 30), (45, 5), (1, 99), (3, 38)]]

    # ---- X2 演示场景：接 PREF fixture_A（通勤，✕ 两首英文后第二次推荐，种子 1001）----
    rows = RP.rank(songs, "commute", {}, {}, {}, bpm, 1)
    L1 = [r["k"] for r in RP.local_six(rows)]
    en = [k for k in L1 if byk[k]["lg"] == "en"][:2]
    tab, n = [], 0
    for k in en:
        n += 1
        tab = RP.apply_vote(tab, {"r": 1, "k": k, "a": "commute", "y": 0, "L": L1}, n)
    mA, _ = RP.replay(tab, byk, bpm)
    fb = {k: {"commute": -1, "g": -1} for k in en}
    rows2 = RP.rank(songs, "commute", {}, fb, mA, bpm, 1001)
    six2 = [r["k"] for r in RP.local_six(rows2)]
    xA = explore_pick(rows2, six2, "commute", tab, 1001)
    out["x2_demo"] = {"seed": 1001, "top12": [r["k"] for r in rows2[:RP.TOPK]], "six": six2,
                      "candidates": [k for k in [r["k"] for r in rows2[:RP.TOPK]] if k not in six2],
                      "pick": xA}

    # ---- X3 票数改变抽样：给 X2 的探索歌连续 ✕ 3 次（三张不同歌单），另一候选 ♥ 2 次，再按种子 1002 抽 ----
    cands = out["x2_demo"]["candidates"]
    tab3, n3 = list(tab), n
    other = [k for k in cands if k != xA["k"]][0]
    for j in range(3):
        n3 += 1
        tab3 = RP.apply_vote(tab3, {"r": 10 + j, "k": xA["k"], "a": "commute", "y": 0, "L": six2}, n3)
    for j in range(2):
        n3 += 1
        tab3 = RP.apply_vote(tab3, {"r": 20 + j, "k": other, "a": "commute", "y": 1, "L": six2}, n3)
    # 只看探索层：排名与 6 首沿用 X2（隔离 PREF 学习的影响），评价表换成 tab3
    detail = []
    for k in cands:
        c1, c0 = counts(tab3, "commute", k)
        u1, u0 = cap_counts(c1, c0)
        detail.append({"k": k, "c1": c1, "c0": c0, "theta": beta_draw(1002, k, 1 + u1, 1 + u0)})
    out["x3_counts"] = {"seed": 1002, "votes": tab3, "explored": xA["k"], "liked": other,
                        "detail": detail, "pick": explore_pick(rows2, six2, "commute", tab3, 1002)}
    # 长期频率（不是逐值核对项，只给人看）：种子 2000..2999 里各候选被选中的次数
    freq = {}
    for s in range(2000, 3000):
        p = explore_pick(rows2, six2, "commute", tab3, s)
        freq[p["k"]] = freq.get(p["k"], 0) + 1
    out["x3_counts"]["freq_1000_seeds"] = dict(sorted(freq.items(), key=lambda kv: -kv[1]))

    # ---- X4 不出探索位的情况 ----
    out["x4_none"] = {"no_activity": explore_pick(rows2, six2, "", tab, 1001),
                      "unknown_activity": explore_pick(rows2, six2, "party", tab, 1001),
                      "flag_off": explore_pick(rows2, six2, "commute", tab, 1001, on=False),
                      "no_candidates": explore_pick(rows2[:6], [r["k"] for r in rows2[:6]], "commute", tab, 1001)}

    json.dump(out, open(args[args.index("--out") + 1], "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print("ok", len(songs), "songs")
    print("X2 demo pick:", xA["k"], "rank", xA["rank"], "theta", round(xA["theta"], 4))
    print("X3 pick:", out["x3_counts"]["pick"]["k"], "| explored", xA["k"], "liked", other)
    print("X3 freq over 1000 seeds:", out["x3_counts"]["freq_1000_seeds"])
    if "--selftest" in args:
        selftest(keys)


if __name__ == "__main__":
    main()
