"""情境 DJ 偏好学习参考实现（PREF 轮）。应用里的 OctoScript 必须与本文件逐值一致。
用法：python3 -I ref_pref.py <main.splash> --out expected.json
只用标准库。数值约定：浮点按 IEEE double；比较容差 1e-9。"""
import json, math, re, sys

P = 1000003                     # 哈希模数（质数）
ETA, R_MAX, BETA_MAX = 0.5, 2.0, 3.0
TOPK, REC_N = 12, 6
MOODS = ["欢快", "怀旧", "平静", "振奋", "伤感", "专注", "温暖"]
FEAT = ["能量", "人声", "节奏"] + MOODS + ["中文", "英文"]          # 12 维，顺序冻结
ACTS = {"study": (1.5, 1.5, "专注"), "work": (2.5, 0.8, "专注"), "commute": (3.4, 0.0, "欢快"),
        "walk": (3.0, 0.0, "温暖"), "workout": (4.7, 0.0, "振奋"), "relax": (2.0, 0.3, "温暖"),
        "sleep": (1.0, 1.5, "平静")}

def load_seed(path):
    src = open(path, encoding="utf-8").read()
    body = src[src.index("let SEED = ["):]
    body = body[:body.index("\n]")]
    out = []
    for m in re.finditer(r'\{t: "(.*?)" a: "(.*?)" en: (\d) vo: (\w+) md: "(.*?)" lg: "(\w+)"(?: pc: (-?\d))?\}', body):
        t, a, en, vo, md, lg, pc = m.groups()
        out.append({"t": t, "a": a, "en": int(en), "vo": vo == "true", "md": md, "lg": lg,
                    "pc": None if pc is None else int(pc)})
    return out

def key_of(s): return s["t"] + "|" + s["a"]

# ---- 1. 并列定序哈希 ----
def tie_hash(seed, key):
    h = 0
    for ch in str(seed) + "|" + key:
        h = (h * 31 + ord(ch)) % P          # ord = Unicode 码点（BMP 内即 UTF-16 码元）
    for _ in range(2):
        h = (h * h + 12345) % P
    return h

# ---- 2. 特征（缺失填 0）----
def features(s, bpm=None):
    # 第 3 维：节奏密度三档 pc（快 1 / 中 0 / 慢 -1，缺失 0），2026-10-12 替代 BPM。
    # bpm 参数只为保持各函数签名不变（ref_explore.py 照旧传入），不再使用。
    en, vo, md, lg, pc = s.get("en"), s.get("vo"), s.get("md"), s.get("lg"), s.get("pc")
    x = [0.0 if en is None else (en - 3) / 2,
         0.0 if vo is None else (1.0 if vo else -1.0),
         0.0 if pc is None else float(pc)]
    x += [1.0 if md == m else 0.0 for m in MOODS]
    x += [1.0 if lg == "zh" else 0.0, 1.0 if lg == "en" else 0.0]
    return x

def dot(a, b): return sum(p * q for p, q in zip(a, b))

# ---- 3. 学习：按歌单中心化的投影逻辑回归，按 n 升序重放 ----
def replay(votes, songs_by_key, bpm):
    """votes: [{n, r, k, a, y, L:[6 个歌曲键]}]，每个 (r,k) 只保留最后一票（调用方保证）。
    返回 {活动: {"v": [12], "beta": float, "n": 票数}}。未知歌曲键的票跳过并计数。"""
    st = {}
    skipped = 0
    for vt in sorted(votes, key=lambda z: z["n"]):
        s = songs_by_key.get(vt["k"])
        Ls = [songs_by_key[k] for k in vt["L"] if k in songs_by_key]
        if s is None or not Ls or vt["a"] not in ACTS:
            skipped += 1
            continue
        c = st.setdefault(vt["a"], {"v": [0.0] * len(FEAT), "beta": 0.0, "n": 0})
        xs = [features(q, bpm) for q in Ls]
        mu = [sum(col) / len(xs) for col in zip(*xs)]
        xt = [p - q for p, q in zip(features(s, bpm), mu)]
        z = dot(c["v"], xt) + c["beta"]
        p = 1.0 / (1.0 + math.exp(-z))
        g = ETA * (vt["y"] - p)
        c["v"] = [w + g * xi for w, xi in zip(c["v"], xt)]
        c["beta"] = max(-BETA_MAX, min(BETA_MAX, c["beta"] + g))
        nv = math.sqrt(dot(c["v"], c["v"]))
        if nv > R_MAX:
            c["v"] = [w * R_MAX / nv for w in c["v"]]
        c["n"] += 1
    return st, skipped

# ---- 4. 规则分 b（移植 score_song，关抖动；天气固定为不可用）----
def rule_score(s, act, it, fb):
    tg, ins, amd = ACTS[act] if act in ACTS else (2.8, None, None)
    tg += it.get("energy", 0.0)
    sc = 0.0
    if s.get("en") is not None: sc -= abs(s["en"] - tg) * 1.2
    else: sc -= 0.9
    if s.get("vo") is not None:
        if not s["vo"]:
            if it.get("instr") == 1: sc += 2.0
            if ins is not None: sc += ins
            if it.get("instr") == -1: sc -= 2.5
        else:
            if it.get("instr") == 1: sc -= 3.0
            if it.get("instr") == -1: sc += 1.0
    if s.get("md") is not None:
        if it.get("mood") and s["md"] == it["mood"]: sc += 1.6
        if amd is not None and s["md"] == amd: sc += 0.6
    if it.get("lang") and s.get("lg") is not None:
        sc += 1.0 if s["lg"] == it["lang"] else -1.5
    f = fb.get(key_of(s), {})
    ca, g = f.get(act, 0), f.get("g", 0)
    if act in ACTS:
        if ca > 0: sc += 1.4 * ca
        if ca < 0: sc -= 4.0
    if g > 0: sc += 0.6 * g
    if g < 0: sc -= 1.5
    if it.get("fresh") and key_of(s) in it.get("recent", []): sc -= 6.0
    return sc

# ---- 5. 排名：s = b + v·x（仅有效活动），(s 降序, 哈希升序, 曲库序号升序) ----
def rank(songs, act, it, fb, model, bpm, seed, elig=None, learn=True):
    v = model.get(act, {}).get("v") if (learn and act in ACTS) else None
    rows = []
    for i, s in enumerate(songs):
        if elig is not None and not elig[i]: continue
        b = rule_score(s, act, it, fb)
        lt = dot(v, features(s, bpm)) if v else 0.0
        rows.append({"i": i, "k": key_of(s), "b": b, "learn": lt, "s": b + lt, "h": tie_hash(seed, key_of(s))})
    rows.sort(key=lambda r: (-r["s"], r["h"], r["i"]))
    for n, r in enumerate(rows, 1): r["rank"] = n
    return rows

def local_six(rows):
    """回退：按排名取 6 首，同一歌手最多 2 首。"""
    out, per = [], {}
    for r in rows:
        a = r["k"].split("|", 1)[1]
        if per.get(a, 0) >= 2: continue
        out.append(r); per[a] = per.get(a, 0) + 1
        if len(out) == REC_N: break
    return out

# ---- 6. 评价表：同一 (r,k) 只留最后一票；y=None 表示撤销 ----
def apply_vote(table, ev, counter):
    """ev: {r, k, a, y(1/0/None), L}。返回新表（按 n 升序）。改票/撤销 → 调用方须全表重放。"""
    t = [row for row in table if not (row["r"] == ev["r"] and row["k"] == ev["k"])]
    if ev["y"] is not None:
        t.append({"n": counter, "r": ev["r"], "k": ev["k"], "a": ev["a"], "y": ev["y"], "L": list(ev["L"])})
    return t

if __name__ == "__main__":
    args = sys.argv[1:]
    songs = load_seed(args[0]); byk = {key_of(s): s for s in songs}
    bpm = {}   # 已不用（节奏写在 SEED 的 pc 字段）
    out = {"constants": {"P": P, "ETA": ETA, "R_MAX": R_MAX, "BETA_MAX": BETA_MAX, "TOPK": TOPK, "FEAT": FEAT},
           "hash": {str(seed): {key_of(s): tie_hash(seed, key_of(s)) for s in songs} for seed in (1, 17, 123456)},
           "features": {key_of(s): features(s, bpm) for s in songs}}
    # 夹具 A：演示（通勤，推荐 1 的回退 6 首，✕ 其中两首英文）
    rows = rank(songs, "commute", {}, {}, {}, bpm, 1); L = [r["k"] for r in local_six(rows)]
    en = [k for k in L if byk[k]["lg"] == "en"][:2]
    tab, n = [], 0
    for k in en:
        n += 1; tab = apply_vote(tab, {"r": 1, "k": k, "a": "commute", "y": 0, "L": L}, n)
    mA, _ = replay(tab, byk, bpm)
    fb = {k: {"commute": -1, "g": -1} for k in en}
    out["fixture_A"] = {"rec1_L": L, "votes": tab, "model": mA,
        "rec2_seed": 1001,
        "commute_top12_no_learn": [r["k"] for r in rank(songs, "commute", {}, fb, mA, bpm, 1001, learn=False)[:TOPK]],
        "commute_top12_learn": [r["k"] for r in rank(songs, "commute", {}, fb, mA, bpm, 1001)[:TOPK]],
        "workout_top12_learn_equals_no_learn": True}
    # 夹具 B：♥ → 改 ✕ → 另一首 ♥ → 撤销第一首 → 学习场景一票
    LB = [r["k"] for r in local_six(rank(songs, "commute", {}, {}, {}, bpm, 17))]
    LS = [r["k"] for r in local_six(rank(songs, "study", {}, {}, {}, bpm, 18))]
    evs = [{"r": 17, "k": LB[0], "a": "commute", "y": 1, "L": LB},
           {"r": 17, "k": LB[0], "a": "commute", "y": 0, "L": LB},
           {"r": 17, "k": LB[1], "a": "commute", "y": 1, "L": LB},
           {"r": 17, "k": LB[2], "a": "commute", "y": 0, "L": LB},
           {"r": 17, "k": LB[0], "a": "commute", "y": None, "L": LB},
           {"r": 18, "k": LS[0], "a": "study", "y": 0, "L": LS}]
    tab = []
    for n, e in enumerate(evs, 1): tab = apply_vote(tab, e, n)
    mB, _ = replay(tab, byk, bpm)
    out["fixture_B"] = {"events": evs, "final_table": tab, "model": mB}
    json.dump(out, open(args[args.index("--out") + 1], "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print("ok", len(songs), "songs; A model", {a: [round(w, 4) for w in c["v"]] for a, c in mA.items()})
    print("B model", {a: [round(w, 4) for w in c["v"]] for a, c in mB.items()})
    print("A top12 diff:", set(out["fixture_A"]["commute_top12_no_learn"]) ^ set(out["fixture_A"]["commute_top12_learn"]))
