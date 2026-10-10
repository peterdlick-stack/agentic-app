#!/usr/bin/env python3
"""Make clearly synthetic analyzer inputs from T's labels and hand-set scores.

This is a Python analyzer smoke test, not an application/storage acceptance.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import analyze


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def from_label(label, eid, prior_labels):
    order = label["top"] + [name for name in analyze.ACTIVITIES if name not in label["top"]]
    top = (.4, .6, .9)[(eid - 1) % 3]
    # Explicit artificial predictions. These are NOT a replay of rank_acts.
    q = [[name, round(top if index == 0 else (1 - top) / 6, 3)] for index, name in enumerate(order)]
    prior = [[name, .143] for name in order]
    majority = max(prior_labels, key=prior_labels.get) if prior_labels else ""
    y = label["chosen"]
    return {"e": "act", "id": eid, "at": label["at"], "sim": True, "dv": 1,
            "pv": "synthetic-analyzer-demo", "b": "|".join(label[key] for key in ("day", "slot", "place_kind", "motion")),
            "lvl": "full", "n": sum(prior_labels.values()), "q": q, "pr": prior, "rule": order[0], "maj": majority,
            "tier": "low" if top < .5 else "mid", "eh": top >= .8, "low": "q1" if top < .5 else "",
            "how": label["how"], "y": y, "dup": False, "hit": order[0] == y, "rhit": order[0] == y,
            "mhit": majority == y, "br": analyze.full_brier(q, y), "bp": analyze.full_brier(prior, y)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-seed", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    analyze.require(not args.output.exists(), "choose a new synthetic output directory")
    labels = analyze.read_json(args.labels_seed)
    analyze.require(isinstance(labels, list) and len(labels) == 60 and all(row.get("sim") is True for row in labels),
                    "expected T's 60 explicitly synthetic labels")
    rows, counts = [], Counter()
    for eid, label in enumerate(labels, 1):
        rows.append(from_label(label, eid, counts))
        counts[label["chosen"]] += 1
    for row in rows:
        analyze.validate_event(row, "synthetic labels demo")
    groups, _, _, _ = analyze.replay(rows)
    for index in range(2):
        save(args.output / "seed" / "device" / f"decisions-{index}.json", rows[index * 50:(index + 1) * 50])
    save(args.output / "seed" / "device" / "dstats.json", {"v": 1, "seq": 61, "shard": 1, "shard_n": 10, **groups})

    # Ring fixture has an independent, hand-counted cumulative dstats oracle:
    # 900 identical simulated confirmations, n=lab=hit=rhit=mid=eh=eh_lab=eh_hit=900.
    prototype = rows[2].copy()
    prototype.update(rule=prototype["y"], maj=prototype["y"])
    q = [[prototype["y"], .9]] + [[name, .017] for name in analyze.ACTIVITIES if name != prototype["y"]]
    prototype.update(q=q, pr=[[name, .143] for name, _ in q], hit=True, rhit=True, mhit=True,
                     tier="mid", eh=True, low="", how="tap", b="synthetic-ring")
    prototype["br"] = .011734  # (.9 - 1)^2 + 6 * .017^2
    prototype["bp"] = .857143  # (.143 - 1)^2 + 6 * .143^2
    ring = [{**prototype, "id": eid, "at": 1791504000 + eid} for eid in range(1, 901)]
    for index in range(18):
        shard = ring[index * 50:(index + 1) * 50]
        save(args.output / "ring" / "archive" / f"decisions-{index}.json", shard)
        if index >= 2:
            save(args.output / "ring" / "device" / f"decisions-{index % 16}.json", shard)
    expected = {"real": analyze.empty_group(), "sim": analyze.empty_group()}
    for field in ("n", "lab", "hit", "rhit", "mhit", "mid", "eh", "eh_lab", "eh_hit"):
        expected["sim"]["act"][field] = 900
    expected["sim"]["act"]["br"] = .011734 * 900
    expected["sim"]["act"]["bp"] = .857143 * 900
    save(args.output / "ring" / "device" / "dstats.json", {"v": 1, "seq": 901, "shard": 18, "shard_n": 0, **expected})
    (args.output / "SYNTHETIC.md").write_text(
        "全部为合成数据。seed 使用 T 的 60 个合成标签，q/pr 为人为设定；不代表真实预测。\n"
        "ring 使用 900 个固定合成事件，归档保留全部，device 模拟 16×50 覆盖后保留 101..900。\n"
        "ring dstats 为独立手算 oracle；该物理文件布局只是读取夹具，不证明 D 的写入游标或重启行为。\n",
        encoding="utf-8")
    print(f"Synthetic inputs: {args.output}")


if __name__ == "__main__":
    main()
