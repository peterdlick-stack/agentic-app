#!/usr/bin/env python3
"""Read-only decision-log analysis. Only the output directory is written."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import statistics
import sys

ACT_FIELDS = "n hit rhit mhit lab br bp skip dup undo low mid high eh eh_lab eh_hit".split()
REC_FIELDS = "n ai ai_retry nomodel net fail insuff timeout first_ret first_bad retry retry_ok".split()
ERRORS = "E_JSON E_STATUS E_COUNT E_DUP E_RANGE E_NOT_ELIG E_CAT E_HARD_VOCAL E_HARD_LANG E_REF_ENUM E_REF_ABSENT E_REF_MISMATCH E_REF_KIND E_WHY E_INSUFF".split()
TIERS = ("H", "M", "L")
ACTIVITIES = ("study", "work", "commute", "walk", "workout", "relax", "sleep")
ACT_TIERS = ("low", "mid", "high")
RESULTS = ("ai", "ai_retry", "local_nomodel", "local_net", "local_fail", "local_insuff", "local_timeout")
TAIPEI = timezone(timedelta(hours=8), "Asia/Taipei")


class InputError(ValueError):
    pass


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InputError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                          object_pairs_hook=unique_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(InputError(f"nonfinite JSON: {value}")))
    except (OSError, ValueError) as exc:
        raise InputError(str(exc)) from exc


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def require(condition, message):
    if not condition:
        raise InputError(message)


def validate_event(ev, origin):
    require(isinstance(ev, dict), f"{origin}: event must be an object")
    eid = ev.get("id")
    require(type(eid) is int and eid >= 1, f"{origin}: id must be positive integer")
    prefix = f"{origin}: event {eid}"
    require(type(ev.get("sim")) is bool, f"{prefix}: missing/invalid sim")
    require(ev.get("dv") == 1, f"{prefix}: unsupported dv")
    require(finite(ev.get("at")), f"{prefix}: missing/invalid at")
    kind = ev.get("e")
    require(kind in ("act", "act_undo", "rec", "rate", "click"), f"{prefix}: unknown event type")
    if kind == "act":
        require(type(ev.get("dup")) is bool and type(ev.get("eh")) is bool, f"{prefix}: dup/eh must be boolean")
        require(ev.get("tier") in ACT_TIERS and isinstance(ev.get("y"), str), f"{prefix}: invalid tier/y")
        require(isinstance(ev.get("rule"), str) and isinstance(ev.get("maj"), str), f"{prefix}: missing rule/maj")
        for key in ("q", "pr"):
            vector = ev.get(key)
            require(isinstance(vector, list) and len(vector) in (3, 7), f"{prefix}: {key} must contain 7 entries (or 3 after truncation)")
            names = []
            for pair in vector:
                require(isinstance(pair, list) and len(pair) == 2 and pair[0] in ACTIVITIES
                        and finite(pair[1]) and 0 <= pair[1] <= 1, f"{prefix}: invalid {key} entry")
                names.append(pair[0])
            require(len(set(names)) == len(names), f"{prefix}: duplicate activities in {key}")
            if len(vector) == 7:
                require(abs(sum(pair[1] for pair in vector) - 1) <= .003501, f"{prefix}: {key} does not sum to 1 within 3-decimal rounding")
        require([pair[0] for pair in ev["q"]] == [pair[0] for pair in ev["pr"]], f"{prefix}: q/pr activity order differs")
        require(ev["y"] in (*ACTIVITIES, "") and ev["rule"] in (*ACTIVITIES, "") and ev["maj"] in (*ACTIVITIES, ""), f"{prefix}: unknown activity label")
        require(all(ev["q"][i][1] >= ev["q"][i + 1][1] for i in range(len(ev["q"]) - 1)), f"{prefix}: q not sorted")
        for key in ("hit", "rhit", "mhit"):
            require(type(ev.get(key)) is bool if ev["y"] else ev.get(key) is None, f"{prefix}: invalid {key}")
        for key in ("br", "bp"):
            require((finite(ev.get(key)) and 0 <= ev[key] <= 2) if ev["y"] else ev.get(key) is None,
                    f"{prefix}: invalid {key}")
    elif kind == "act_undo":
        require(type(ev.get("a")) is int and ev["a"] >= 1, f"{prefix}: invalid undo target")
    elif kind == "rec":
        require(ev.get("res") in RESULTS and type(ev.get("att")) is int and ev["att"] in (1, 2), f"{prefix}: invalid res/att")
        require(ev["res"] != "local_net" or ev["att"] == 1, f"{prefix}: retry network failure must use local_fail, not local_net")
        for key in ("e1", "e2"):
            require(isinstance(ev.get(key), list) and all(code in ERRORS for code in ev[key]), f"{prefix}: invalid {key}")
        require(finite(ev.get("ms1")) and ev["ms1"] >= 0, f"{prefix}: invalid ms1")
        require(ev.get("ms2") is None or (finite(ev["ms2"]) and ev["ms2"] >= 0), f"{prefix}: invalid ms2")
        require(isinstance(ev.get("p"), list), f"{prefix}: invalid p")
        for pick in ev["p"]:
            require(isinstance(pick, list) and len(pick) == 3 and isinstance(pick[0], str)
                    and pick[1] in (*TIERS, "") and type(pick[2]) is int and pick[2] >= 1, f"{prefix}: invalid pick")
        require(len({p[0] for p in ev["p"]}) == len(ev["p"]), f"{prefix}: duplicate exposure key")
    else:
        require(type(ev.get("r")) is int and ev["r"] >= 0 and isinstance(ev.get("k"), str), f"{prefix}: invalid r/k")
        require(ev.get("fb") in (*TIERS, "") and type(ev.get("pos")) is int and ev["pos"] >= 0, f"{prefix}: invalid fb/pos")
        if kind == "rate":
            require(type(ev.get("v")) is int and ev["v"] in (-1, 1), f"{prefix}: invalid vote")


def load_events(device, archives=()):
    files = []
    for source in [Path(device), *map(Path, archives)]:
        require(source.exists(), f"input does not exist: {source}")
        files.extend(sorted(source.glob("decisions-*.json")) if source.is_dir() else [source])
    by_id, origins = {}, {}
    duplicates = 0
    for file in sorted(set(files)):
        rows = read_json(file)
        require(isinstance(rows, list), f"{file}: shard must be a JSON array")
        for ev in rows:
            validate_event(ev, str(file))
            eid = ev["id"]
            if eid in by_id:
                require(by_id[eid] == ev, f"conflicting event id {eid}: {origins[eid]} vs {file}")
                duplicates += 1
            else:
                by_id[eid], origins[eid] = ev, str(file)
    return [by_id[eid] for eid in sorted(by_id)], {"files": [str(p) for p in sorted(set(files))], "identical_duplicates": duplicates}


def empty_group():
    return {"act": dict.fromkeys(ACT_FIELDS, 0), "rec": dict.fromkeys(REC_FIELDS, 0),
            "err": dict.fromkeys(ERRORS, 0), "song": {tier: dict.fromkeys(("exp", "like", "dis", "click"), 0) for tier in TIERS}}


def act_contribution(ev):
    counts = dict.fromkeys(ACT_FIELDS, 0)
    if ev["dup"]:
        counts["dup"] = 1
        return counts
    counts["n"] = 1
    counts[ev["tier"]] = 1
    counts["eh"] = int(ev["eh"])
    if not ev["y"]:
        counts["skip"] = 1
        return counts
    counts["lab"] = 1
    for field in ("hit", "rhit", "mhit", "br", "bp"):
        counts[field] = int(ev[field]) if isinstance(ev[field], bool) else ev[field]
    counts["eh_lab"] = int(ev["eh"])
    counts["eh_hit"] = int(ev["eh"] and ev["hit"])
    return counts


def replay(events):
    """Cumulative replay; reversals persist across shard and process boundaries."""
    groups = {"real": empty_group(), "sim": empty_group()}
    active, seen_acts, undone, votes, warnings = {}, {}, set(), {}, []
    recs = {}
    for ev in events:
        name = "sim" if ev["sim"] else "real"
        group, kind = groups[name], ev["e"]
        if kind == "act":
            seen_acts[ev["id"]] = ev
            active[ev["id"]] = ev
            for key, value in act_contribution(ev).items():
                group["act"][key] += value
        elif kind == "act_undo":
            target = seen_acts.get(ev["a"])
            if target is None:
                warnings.append(f"act_undo {ev['id']}: missing earlier act {ev['a']}")
                group["act"]["undo"] += 1
            elif ev["a"] in undone:
                warnings.append(f"act_undo {ev['id']}: target {ev['a']} already undone; not subtracted twice")
            else:
                target_group = groups["sim" if target["sim"] else "real"]["act"]
                for key, value in act_contribution(target).items():
                    target_group[key] -= value
                target_group["undo"] += 1
                active.pop(ev["a"])
                undone.add(ev["a"])
        elif kind == "rec":
            recs[ev["id"]] = ev
            counts = group["rec"]
            counts["n"] += 1
            result = ev["res"]
            # net means first-attempt network failure, not retry network failure.
            if result != "local_net" or ev["att"] == 1:
                counts[result.removeprefix("local_")] += 1
            counts["first_ret"] += int(bool(ev["e1"]) or result in ("ai", "ai_retry") or ev["att"] == 2)
            counts["first_bad"] += int(bool(ev["e1"]))
            counts["retry"] += int(ev["att"] == 2)
            counts["retry_ok"] += int(result == "ai_retry")
            for code in ev["e1"] + ev["e2"]:
                group["err"][code] += 1
            for _, tier, _ in ev["p"]:
                if tier:
                    group["song"][tier]["exp"] += 1
        elif kind == "rate" and ev["fb"]:
            key = (ev["r"], ev["k"])
            old = votes.get(key)
            if old:
                old_group = groups["sim" if old["sim"] else "real"]
                old_group["song"][old["fb"]]["like" if old["v"] == 1 else "dis"] -= 1
            group["song"][ev["fb"]]["like" if ev["v"] == 1 else "dis"] += 1
            votes[key] = ev
        elif kind == "click" and ev["fb"]:
            group["song"][ev["fb"]]["click"] += 1
    for ev in events:
        if ev["e"] == "act" and ev["y"]:
            for field, predicted in (("hit", ev["q"][0][0]), ("rhit", ev["rule"]), ("mhit", ev["maj"])):
                if ev[field] != (predicted == ev["y"]):
                    warnings.append(f"act {ev['id']}: logged {field} contradicts frozen prediction")
            # Seven independently rounded values can change the summed Brier by
            # at most about .007002; do not reject normal 3-decimal quantization.
            for vector, scalar in (("q", "br"), ("pr", "bp")):
                calculated = full_brier(ev[vector], ev["y"])
                if calculated is not None and abs(calculated - ev[scalar]) > .00701:
                    warnings.append(f"act {ev['id']}: logged {scalar} differs from full {vector} beyond rounding tolerance")
        if ev["e"] in ("rate", "click") and ev["fb"]:
            rec = recs.get(ev["r"])
            pick = next((p for p in rec["p"] if p[0] == ev["k"]), None) if rec else None
            if not pick or rec["id"] >= ev["id"]:
                warnings.append(f"{ev['e']} {ev['id']}: missing earlier exposure {ev['r']} / {ev['k']}")
            elif pick[1] != ev["fb"] or pick[2] != ev["pos"] or rec["sim"] != ev["sim"]:
                warnings.append(f"{ev['e']} {ev['id']}: exposure tier/position/sim differs")
    return groups, list(active.values()), votes, warnings


def wilson(hits, count):
    if count == 0:
        return None
    require(0 <= hits <= count, "Wilson needs 0 <= hits <= count")
    z = 1.95996398454
    p = hits / count
    divisor = 1 + z * z / count
    center = (p + z * z / (2 * count)) / divisor
    half = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / divisor
    return [max(0.0, center - half), min(1.0, center + half)]


def ratio(numerator, denominator, interval=False):
    value = {"numerator": numerator, "denominator": denominator,
             "value": numerator / denominator if denominator else None}
    if interval:
        value["wilson95"] = wilson(numerator, denominator)
    return value


def full_brier(vector, y):
    if len(vector) != 7 or y not in {name for name, _ in vector}:
        return None
    return sum((value - int(name == y)) ** 2 for name, value in vector)


def describe(events, active, groups, include_sim=False):
    selected = [ev for ev in events if include_sim or not ev["sim"]]
    acts = [ev for ev in active if not ev["dup"] and (include_sim or not ev["sim"])]
    labels = [ev for ev in acts if ev["y"]]
    hits = {"q": lambda ev: ev["q"][0][0] == ev["y"],
            "rule": lambda ev: ev["rule"] == ev["y"], "majority": lambda ev: ev["maj"] == ev["y"]}
    accuracy = {key: ratio(sum(test(ev) for ev in labels), len(labels), True) for key, test in hits.items()}
    bins = []
    for low, high, name in ((0, .5, "[0,0.5)"), (.5, .8, "[0.5,0.8)"), (.8, 1, "[0.8,1]")):
        rows = [ev for ev in labels if low <= ev["q"][0][1] and (ev["q"][0][1] < high or high == 1)]
        bins.append({"bin": name, "n": len(rows), "mean_support": statistics.mean(ev["q"][0][1] for ev in rows) if rows else None,
                     "hit_rate": ratio(sum(hits["q"](ev) for ev in rows), len(rows), True)})
    tiers = {}
    for tier in ACT_TIERS:
        rows = [ev for ev in acts if ev["tier"] == tier]
        labelled = [ev for ev in rows if ev["y"]]
        tiers[tier] = {"coverage": ratio(len(rows), len(acts)), "label_coverage": ratio(len(labelled), len(rows)),
                       "error_rate": ratio(sum(not hits["q"](ev) for ev in labelled), len(labelled), True),
                       "unlabelled": len(rows) - len(labelled)}
    eligible = [ev for ev in labels if ev["eh"]]
    brier = {}
    for vector, field in (("q", "br"), ("pr", "bp")):
        values = [full_brier(ev[vector], ev["y"]) for ev in labels]
        complete = [value for value in values if value is not None]
        brier[vector] = {"mean_from_full_vectors": statistics.mean(complete) if complete else None,
                         "full_vector_n": len(complete), "truncated_or_missing_label_n": len(labels) - len(complete),
                         "mean_logged_scalar": statistics.mean(ev[field] for ev in labels) if labels else None,
                         "logged_scalar_n": len(labels)}
    recs = [ev for ev in selected if ev["e"] == "rec"]
    first_ret = sum(bool(ev["e1"]) or ev["res"] in ("ai", "ai_retry") or ev["att"] == 2 for ev in recs)
    first_bad = sum(bool(ev["e1"]) for ev in recs)
    first_net = sum(ev["res"] == "local_net" and ev["att"] == 1 for ev in recs)
    started = sum(ev["res"] not in ("local_nomodel", "local_insuff") for ev in recs)
    retry = sum(ev["att"] == 2 for ev in recs)
    fallback = sum(ev["res"] in ("local_fail", "local_net", "local_timeout", "local_insuff") for ev in recs)
    timings = {}
    for key in ("ms1", "ms2"):
        values = [ev[key] for ev in recs if ev[key] is not None and ev["res"] not in ("local_nomodel", "local_insuff")
                  and (key != "ms2" or ev["att"] == 2)]
        timings[key] = {"n": len(values), "median": statistics.median(values) if values else None,
                        "max": max(values) if values else None}
    songs = {}
    for tier in TIERS:
        counts = {key: groups["real"]["song"][tier][key] + (groups["sim"]["song"][tier][key] if include_sim else 0)
                  for key in ("exp", "like", "dis", "click")}
        counts["unrated"] = counts["exp"] - counts["like"] - counts["dis"]
        counts["positive_rate"] = ratio(counts["like"], counts["like"] + counts["dis"])
        counts["feedback_coverage"] = ratio(counts["like"] + counts["dis"], counts["exp"])
        songs[tier] = counts
    return {"include_sim": include_sim, "event_n": len(selected), "activity_n": len(acts), "label_n": len(labels),
            "accuracy": accuracy, "brier": brier, "reliability": bins, "tiers": tiers,
            "eligible_high": ratio(sum(hits["q"](ev) for ev in eligible), len(eligible), True),
            "recommendation": {"n": len(recs), "first_bad_rate": ratio(first_bad, first_ret),
                               "first_network_failure_rate": ratio(first_net, started),
                               "debug_network_failure_rate": ratio(first_net, len(recs)),
                               "retry_repair_rate": ratio(sum(ev["res"] == "ai_retry" for ev in recs), retry),
                               "final_fallback_rate": ratio(fallback, len(recs)),
                               "nomodel": sum(ev["res"] == "local_nomodel" for ev in recs),
                               "res": dict(Counter(ev["res"] for ev in recs)),
                               "errors": dict(Counter(code for ev in recs for code in ev["e1"] + ev["e2"])),
                               "timing_ms": timings, "pending": None}, "songs": songs}


def missing_ranges(ids, seq):
    ranges, previous = [], 0
    for eid in sorted(eid for eid in ids if 0 < eid < seq):
        if eid > previous + 1:
            ranges.append([previous + 1, eid - 1])
        previous = eid
    if previous + 1 < seq:
        ranges.append([previous + 1, seq - 1])
    return ranges


def flatten(obj, prefix=""):
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            result.update(flatten(value, f"{prefix}.{key}" if prefix else key))
        return result
    return {prefix: obj}


def check_dstats(events, groups, dstats, replay_warnings):
    require(isinstance(dstats, dict) and type(dstats.get("seq")) is int and dstats["seq"] >= 1, "dstats.seq must be next positive integer")
    missing = missing_ranges([ev["id"] for ev in events], dstats["seq"])
    extra = [ev["id"] for ev in events if ev["id"] >= dstats["seq"]]
    expected = flatten(groups)
    actual = flatten({name: dstats.get(name) for name in ("real", "sim")})
    differences = []
    for field in sorted(expected.keys() | actual.keys()):
        left, right = expected.get(field), actual.get(field)
        equal = (finite(left) and finite(right) and math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-8))
        if not equal:
            differences.append({"field": field, "events": left, "dstats": right})
    metadata = []
    if type(dstats.get("v")) is not int or dstats["v"] != 1:
        metadata.append("dstats.v is not 1")
    for field in sorted(dstats.keys() - {"v", "seq", "shard", "shard_n", "real", "sim"}):
        metadata.append(f"unexpected dstats field: {field}")
    for field in ("shard", "shard_n"):
        if type(dstats.get(field)) is not int or dstats[field] < 0:
            metadata.append(f"dstats.{field} must be a nonnegative integer")
    # Logical shard size is 50, or 25 if P has required the documented reduction.
    # Reconstructing physical shard state from merged archives is not possible.
    status = "HISTORY_INCOMPLETE" if missing else "FAIL" if extra or differences or replay_warnings or metadata else "PASS"
    return {"status": status, "missing_id_ranges": missing, "events_at_or_after_seq": extra,
            "differences": differences, "replay_warnings": replay_warnings, "metadata_errors": metadata,
            "metadata_scope": "seq continuity checked; v/shard/shard_n types checked. Physical shard cursor is not independently reconstructed."}


def pretty_rate(value):
    text = f"{value['numerator']}/{value['denominator']}"
    text += f" = {100 * value['value']:.1f}%" if value["value"] is not None else " = N/A"
    if value.get("wilson95") is not None:
        low, high = value["wilson95"]
        text += f"（95% Wilson {100 * low:.1f}%–{100 * high:.1f}%）"
    return text


def render_report(metrics, provenance, check, warnings):
    lines = [f"样本量 n={metrics['label_n']}；这些数字描述的是这台设备上这段时间的记录，不是校准过的概率，也不能推广到其他用户。", "",
             "# 决策日志离线分析", "", f"包含模拟数据：{'是' if metrics['include_sim'] else '否'}。n 为排除重复和撤销后的已标注活动数。",
             f"读取 {len(provenance['files'])} 个文件；合并相同 id 的相同事件 {provenance['identical_duplicates']} 次。核验始终分别复算 real 和 sim，不受展示开关影响。", "",
             "## 活动", "", "| 预测 | 命中/有效标签 |", "|---|---|"]
    for key, label in (("q", "支持度第一名"), ("rule", "规则"), ("majority", "多数类")):
        lines.append(f"| {label} | {pretty_rate(metrics['accuracy'][key])} |")
    lines.extend(["", "Brier 使用多类求和，不除以类别数。完整的 7 维日志向量独立复算；截为 3 项的向量无法重建完整 Brier，单列其冻结标量口径。", ""])
    for key, values in metrics["brier"].items():
        mean = values["mean_from_full_vectors"]
        logged = values["mean_logged_scalar"]
        mean_text = f"{mean:.6g}" if mean is not None else "N/A"
        logged_text = f"{logged:.6g}" if logged is not None else "N/A"
        lines.append(f"- {key}：完整向量均值 {mean_text}（n={values['full_vector_n']}）；日志标量均值 {logged_text}（n={values['logged_scalar_n']}）；向量不完整 {values['truncated_or_missing_label_n']}。")
    lines.extend(["", "| 展示档 | 覆盖率（该档/全部有效活动） | 标签覆盖率 | 错误率（错误/该档已标注） | 未确认 |", "|---|---|---|---|---|"])
    for tier, counts in metrics["tiers"].items():
        lines.append(f"| {tier} | {pretty_rate(counts['coverage'])} | {pretty_rate(counts['label_coverage'])} | {pretty_rate(counts['error_rate'])} | {counts['unlabelled']} |")
    eh = metrics["eligible_high"]
    lower = eh["wilson95"][0] if eh["wilson95"] else None
    lower_text = f"{lower:.4f}" if lower is not None else "N/A"
    lines.extend(["", f"eh 子集：{pretty_rate(eh)}；Wilson 下界 {lower_text}。至少 30 条且下界 ≥0.80 只是产品检查条件，本脚本不改变高档开关。", "",
                  "可靠性图使用 [0,0.5)、[0.5,0.8)、[0.8,1] 三箱，点横坐标为箱内平均支持度。区间仅作近似独立、同一策略下的描述性参考。", "", "![可靠性图](reliability.png)", ""])
    for bucket in metrics["reliability"]:
        lines.append(f"- {bucket['bin']}：n={bucket['n']}，{pretty_rate(bucket['hit_rate']) if bucket['n'] else '无数据'}。")
    rec = metrics["recommendation"]
    lines.extend(["", "## 选歌", "", "| 比例 | 分母定义 | 结果 |", "|---|---|---|"])
    for key, label, denominator in (("first_bad_rate", "首轮不合格", "首轮返回文本（包括无法解析的文本）"),
                                     ("first_network_failure_rate", "首轮网络失败", "已发起模型调用的已结束决定；排除 nomodel/insuff"),
                                     ("retry_repair_rate", "重试修复", "att=2 的已结束决定，重试网络失败算未修复"),
                                     ("final_fallback_rate", "最终退回本地", "全部已结束选歌；分子 fail/net/timeout/insuff，nomodel 单列"),
                                     ("debug_network_failure_rate", "调试页网络比例", "全部已结束选歌 n（区别于上方研究口径）")):
        lines.append(f"| {label} | {denominator} | {pretty_rate(rec[key])} |")
    lines.extend(["", f"无模型 {rec['nomodel']}；pending=UNKNOWN（只有结束事件，不能重建在途请求）。", "",
                  f"res 分布：`{json.dumps(rec['res'], ensure_ascii=False)}`。", "",
                  f"错误码分布：`{json.dumps(rec['errors'], ensure_ascii=False)}`（e1/e2 每次出现均计数）。", "",
                  f"耗时（毫秒）：`{json.dumps(rec['timing_ms'], ensure_ascii=False)}`。排除未调用模型的决定；ms2 仅 att=2。", "",
                  "## 歌曲", "", "| 档 | 曝光 | ♥ | ✕ | 未评 | 去听 | 正评价率 ♥/(♥+✕) | 反馈覆盖率 |", "|---|---|---|---|---|---|---|---|"])
    for tier, song in metrics["songs"].items():
        lines.append(f"| {tier} | {song['exp']} | {song['like']} | {song['dis']} | {song['unrated']} | {song['click']} | {pretty_rate(song['positive_rate'])} | {pretty_rate(song['feedback_coverage'])} |")
    lines.extend(["", "改票按 (rec id, 歌曲键) 的最后一票；跨分片保留旧票。去听为点击事件次数，重复去听会重复计数。未评不代表不喜欢。历史不完整时，未评可能为负，必须补快照后解释。", "", "## 汇总核验", ""])
    if check:
        lines.append(f"状态：**{check['status']}**。" + ("历史不完整；不能声明零差异。" if check["missing_id_ranges"] else ""))
        lines.append(f"缺失 id 区间：`{check['missing_id_ranges']}`；不早于 seq 的事件：`{check['events_at_or_after_seq']}`。")
        lines.append("逐字段差异见 `metrics.json` 的 dstats_check.differences；以下列出全部差异。")
        lines.extend(f"- {row['field']}: events={row['events']!r}; dstats={row['dstats']!r}" for row in check["differences"])
        lines.extend(f"- 元数据：{warning}" for warning in check["metadata_errors"])
        lines.append(check["metadata_scope"])
    else:
        lines.append("未指定 --check-dstats，未核验累计汇总。即使图表可生成，也不代表历史完整。")
    if warnings:
        lines.extend(["", "## 证据限制", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def plot_reliability(bins, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    fonts = {font.name for font in font_manager.fontManager.ttflist}
    chosen = next((name for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS") if name in fonts), None)
    if chosen:
        plt.rcParams["font.sans-serif"] = [chosen]
    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
    ax.plot([0, 1], [0, 1], "--", color="0.75", label="Reference y=x (not calibration proof)")
    for i, bucket in enumerate(bins):
        if bucket["n"]:
            rate = bucket["hit_rate"]
            low, high = rate["wilson95"]
            ax.errorbar(bucket["mean_support"], rate["value"], yerr=[[max(0, rate["value"] - low)], [max(0, high - rate["value"])]], fmt="o", capsize=5)
            ax.annotate(f"{bucket['bin']} n={bucket['n']}", (bucket["mean_support"], rate["value"]), xytext=(4, 8), textcoords="offset points", fontsize=9)
        else:
            empty = "无数据" if chosen else "No data / n=0"
            ax.text(.02, .95 - i * .055, f"{bucket['bin']}: {empty}", transform=ax.transAxes, fontsize=9)
    ax.set(xlim=(-.02, 1.02), ylim=(-.02, 1.08), xlabel="Mean top-1 support (uncalibrated)", ylabel="Observed hit rate (95% Wilson)", title="Descriptive reliability by support bin")
    ax.legend(loc="lower right", fontsize=8)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", type=Path, help="accounts/device directory; read only")
    parser.add_argument("--archive", action="append", default=[], type=Path, help="earlier snapshot directory or shard JSON; repeatable")
    parser.add_argument("--include-sim", action="store_true", help="include synthetic/simulation events in displayed metrics")
    parser.add_argument("--check-dstats", action="store_true", help="check full cumulative history against device/dstats.json")
    default = Path("F:/context-dj-work/research/confidence/analysis") / datetime.now(TAIPEI).date().isoformat()
    parser.add_argument("--output", type=Path, default=default, help="new output directory (default: Asia/Taipei date)")
    args = parser.parse_args(argv)
    try:
        require(args.device.is_dir(), f"not an accounts/device directory: {args.device}")
        events, provenance = load_events(args.device, args.archive)
        groups, active, _, warnings = replay(events)
        metrics = describe(events, active, groups, args.include_sim)
        check = check_dstats(events, groups, read_json(args.device / "dstats.json"), warnings) if args.check_dstats else None
        for name in ("REPORT.md", "metrics.json", "reliability.png"):
            require(not (args.output / name).exists(), f"refusing to overwrite {args.output / name}; choose a fresh --output")
        args.output.mkdir(parents=True, exist_ok=True)
        output = {"metrics": metrics, "provenance": provenance, "cumulative_replay": groups, "warnings": warnings, "dstats_check": check}
        (args.output / "metrics.json").write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        (args.output / "REPORT.md").write_text(render_report(metrics, provenance, check, warnings), encoding="utf-8")
        try:
            plot_reliability(metrics["reliability"], args.output / "reliability.png")
        except ImportError as exc:
            print(f"Report and metrics written; reliability chart unavailable: {exc}", file=sys.stderr)
            return 2
        print(f"Report: {args.output / 'REPORT.md'}")
        if check:
            print(f"dstats: {check['status']}; differences={len(check['differences'])}; missing ranges={check['missing_id_ranges']}")
            return 0 if check["status"] == "PASS" else 3
        return 0
    except InputError as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
