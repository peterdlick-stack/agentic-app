"""Check fixture consistency and export one isolated fake queue. No host/model calls."""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
from pathlib import Path

from build_fixtures import read_seed

ROOT = Path(__file__).resolve().parent
CONTEXT = {"slot", "weather", "motion", "place", "act", "intent.vocal", "intent.lang", "intent.mood", "intent.text"}
SONG = {"song.energy", "song.mood", "song.vocal", "song.lang", "history.like"}
EV = CONTEXT | SONG
ACTS = {"study", "work", "commute", "walk", "workout", "relax", "sleep"}
ALL_CODES = {"E_JSON", "E_STATUS", "E_COUNT", "E_DUP", "E_RANGE", "E_NOT_ELIG", "E_CAT",
             "E_HARD_VOCAL", "E_HARD_LANG", "E_REF_ENUM", "E_REF_ABSENT", "E_REF_MISMATCH",
             "E_REF_KIND", "E_WHY", "E_INSUFF"}


def load(name):
    # object_pairs_hook rejects duplicate keys too; ordinary json.loads silently keeps the last.
    def unique(pairs):
        out = {}
        for key, value in pairs:
            assert key not in out, f"duplicate JSON key {key!r} in {name}"
            out[key] = value
        return out
    return json.loads((ROOT / name).read_text(encoding="utf-8"), object_pairs_hook=unique)


def oracle(value, case, catalog):
    """Independent specification oracle, not a claim about the Splash implementation."""
    found = []

    def fail(code, pick=0, ref=""):
        entry = (code, pick, ref)
        if entry not in found:
            found.append(entry)

    setup = case["setup"]
    if setup["catalog_mutation"]:
        fail("E_CAT")
        return set(found)
    required = {"status", "understood", "activity", "activity_why", "picks"}
    if not isinstance(value, dict) or not required <= value.keys():
        fail("E_JSON")
        return set(found)
    if value["status"] not in {"ok", "insufficient_candidates"}:
        fail("E_STATUS")
        return set(found)
    if value["status"] == "insufficient_candidates":
        if len(case["eligible_indices"]) >= 6:
            fail("E_INSUFF")
        return set(found)
    if not isinstance(value["picks"], list):
        fail("E_JSON")
        return set(found)
    if len(value["picks"]) != 6:
        fail("E_COUNT")
    songs = catalog + setup["library_append"]
    seen = set()
    it = setup["it"]
    for pos, pick in enumerate(value["picks"], 1):
        if not isinstance(pick, dict) or not {"i", "why", "ev"} <= pick.keys():
            fail("E_JSON", pos)
            continue
        index = pick["i"]
        if type(index) is not int or index < 0 or index >= len(songs):
            fail("E_RANGE", pos)
            continue
        if index in seen:
            fail("E_DUP", pos)
        seen.add(index)
        song = songs[index]
        if index not in case["eligible_indices"]:
            fail("E_NOT_ELIG", pos)
        if it["instr"] == 1 and song.get("vo") is True:
            fail("E_HARD_VOCAL", pos)
        if it["lang"] and song.get("lg") is not None and song["lg"] != it["lang"]:
            fail("E_HARD_LANG", pos)
        why = pick["why"]
        if not isinstance(why, str) or not why.strip() or len(why) > 30:
            fail("E_WHY", pos)
        refs = pick["ev"]
        if not isinstance(refs, list):
            fail("E_JSON", pos)
            continue
        # These fixtures all use 2--4 references. The task did not freeze a code for a count violation.
        assert 2 <= len(refs) <= 4, f"undocumented reference-count mutation in {case['id']}"
        if not (set(refs) & CONTEXT) or not (set(refs) & SONG):
            fail("E_REF_KIND", pos)
        for ref in refs:
            if ref not in EV:
                fail("E_REF_ENUM", pos, ref)
                continue
            available, matches = True, True
            if ref in {"slot", "weather", "motion", "place", "act"}:
                available = setup["avail"][ref]
            elif ref == "intent.text":
                available = bool(setup["raw"].strip())
            elif ref == "intent.vocal":
                available = it["instr"] != 0
                matches = song.get("vo") is (it["instr"] == -1)
            elif ref == "intent.lang":
                available, matches = bool(it["lang"]), song.get("lg") == it["lang"]
            elif ref == "intent.mood":
                available, matches = bool(it["mood"]), song.get("md") == it["mood"]
            elif ref.startswith("song."):
                field = {"song.energy": "en", "song.mood": "md", "song.vocal": "vo", "song.lang": "lg"}[ref]
                available = song.get(field) is not None
            elif ref == "history.like":
                matches = setup["likes"][index] > 0
            if not available:
                fail("E_REF_ABSENT", pos, ref)
            elif not matches:
                fail("E_REF_MISMATCH", pos, ref)
    return set(found)


def normalized(errors):
    return {(e["code"], e["pick"], e["ref"]) for e in errors}


def check_case(case, queue, catalog):
    setup, ex = case["setup"], case["expect"]
    start, count = case["queue_offset"], case["queue_count"]
    replies = queue[start:start + count]
    assert [r["name"] for r in replies] == case["response_names"]
    songs = catalog + setup["library_append"]
    assert len(songs) == case["catalog_size"] == len(setup["likes"])
    it = setup["it"]
    eligible = [i for i, s in enumerate(songs)
                if (it["instr"] != 1 or s.get("vo") is not True)
                and (not it["lang"] or s.get("lg") is None or s["lg"] == it["lang"])]
    assert eligible == case["eligible_indices"] == ex["playlist_indices_subset_of"]
    assert ex["playlist_count"] == min(6, len(eligible))
    assert count <= 2 and count == ex["model_calls"]
    assert ex["attempts_logged"] == max(1, count)
    local = dt.datetime.fromtimestamp(setup["now_unix"], tz=dt.timezone(dt.timedelta(hours=8)))
    assert local.isoformat() == setup["local_time"], (case["id"], local.isoformat(), setup["local_time"])
    assert setup["sim"] is True
    # Frozen parse_intent facts relevant to the scenarios. No fixture bypasses these inputs.
    assert it["instr"] == (1 if "不要人声" in setup["raw"] else 0)
    assert it["lang"] == ("en" if "英文" in setup["raw"] else "")
    assert it["mood"] == ("欢快" if "开心" in setup["raw"] else "")
    errors = [set(), set()]
    actual_net = ""
    if len(eligible) < 6:
        actual_res = "local_insuff"
        assert count == 0
    elif not setup["has_model"]:
        actual_res = "local_nomodel"
        assert count == 0
    else:
        assert replies
        actual_res = None
        for attempt, reply in enumerate(replies):
            assert set(reply) == {"name", "delay_s", "is_ok", "error", "data"}
            assert reply["delay_s"] >= 0 and type(reply["is_ok"]) is bool
            if reply["delay_s"] > 90:
                actual_res = "local_timeout"
                assert ex["late_callback_discarded"] and attempt + 1 == count
                break
            if not reply["is_ok"]:
                actual_res = "local_net" if attempt == 0 else "local_fail"
                actual_net = reply["error"][:40]
                assert attempt + 1 == count
                break
            errors[attempt] = oracle(reply["data"]["output"], case, catalog)
            if not errors[attempt]:
                actual_res = "ai" if attempt == 0 else "ai_retry"
                assert attempt + 1 == count
                break
            if attempt == 1 or reply["delay_s"] > 60 or any(e[0] == "E_CAT" for e in errors[attempt]):
                actual_res = "local_fail"
                assert attempt + 1 == count
                break
            assert count == 2, "locatable first-attempt contract error must have a retry"
    assert actual_res == ex["res"], (case["id"], actual_res, ex["res"])
    if "net" in ex:
        assert actual_net == ex["net"], (case["id"], actual_net, ex["net"])
    assert errors[0] == normalized(ex["e1"]), (case["id"], errors[0], ex["e1"])
    assert errors[1] == normalized(ex["e2"]), (case["id"], errors[1], ex["e2"])
    if actual_res in {"ai", "ai_retry"}:
        picks = replies[-1]["data"]["output"]["picks"]
        indices = [p["i"] for p in picks]
        assert indices == ex["playlist_indices_exact"]
        assert len(set(indices)) == 6 and set(indices) <= set(eligible)


def verify():
    catalog, queue, manifest, labels = [load(name) for name in ("catalog.json", "fake_model.json", "cases.json", "labels_seed.json")]
    assert read_seed() == catalog, "current SEED differs from fixture catalog"
    canonical = json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == manifest["catalog_sha256_canonical"]
    cases = manifest["cases"]
    assert len({c["id"] for c in cases}) == len(cases)
    assert len({r["name"] for r in queue}) == len(queue)
    assert [n for c in cases for n in c["response_names"]] == [r["name"] for r in queue]
    assert sum(c["queue_count"] for c in cases) == len(queue)
    covered = set()
    for case in cases:
        check_case(case, queue, catalog)
        covered |= {e["code"] for a in ("e1", "e2") for e in case["expect"][a]}
    assert covered == ALL_CODES, ("error coverage", ALL_CODES - covered)
    assert len(labels) == 60 and all(row["sim"] is True for row in labels)
    assert labels == sorted(labels, key=lambda row: row["at"])
    assert len({row["at"] for row in labels}) == 60
    assert {row["chosen"] for row in labels} == ACTS
    assert {row["day"] for row in labels} == {"weekday", "weekend"}
    assert {row["slot"] for row in labels} == {"深夜", "早晨", "上午", "中午", "下午", "傍晚", "晚上"}
    assert {row["motion"] for row in labels} == {"unknown", "still", "walk", "run_bike", "vehicle"}
    for row in labels:
        when = dt.datetime.fromtimestamp(row["at"], dt.timezone(dt.timedelta(hours=8)))
        assert row["day"] == ("weekend" if when.weekday() >= 5 else "weekday")
        hour = when.hour
        slot = "深夜" if hour < 5 or hour >= 23 else "早晨" if hour < 9 else "上午" if hour < 12 else "中午" if hour < 14 else "下午" if hour < 17 else "傍晚" if hour < 19 else "晚上"
        assert row["slot"] == slot
        assert len(row["top"]) == 3 and len(set(row["top"])) == 3 and set(row["top"]) <= ACTS
    buckets = Counter((x["day"], x["slot"], x["place_kind"], x["motion"]) for x in labels)
    assert buckets[("weekday", "上午", "school", "still")] == 20
    assert buckets[("weekday", "下午", "work", "still")] == 20
    print(f"PASS: {len(cases)} cases / {len(queue)} replies / {len(covered)} error codes / {len(labels)} synthetic labels / {len(catalog)} seed songs")
    print("Scope: fixture-only specification consistency; Splash/UI/timers/model not executed")
    return cases, queue, catalog


def export(case_id, cases, queue, catalog):
    matches = [c for c in cases if c["id"] == case_id]
    if not matches:
        raise SystemExit("Unknown case id; see CASES.md")
    case = matches[0]
    dest = ROOT / "generated" / case_id
    dest.mkdir(parents=True, exist_ok=True)
    setup = case["setup"]
    songs = catalog + setup["library_append"]
    feedback = []
    for i, like in enumerate(setup["likes"]):
        if like:
            fb = {"g": like, **{act: 0 for act in sorted(ACTS)}}
            feedback.append({"k": songs[i]["t"] + "|" + songs[i]["a"], "fb": fb})
    start, count = case["queue_offset"], case["queue_count"]
    files = {"dev_fake_model.json": queue[start:start + count], "library.json": setup["library_append"],
             "feedback.json": feedback, "setup.json": case}
    # The output stays inside fixtures; the caller separately installs it in an isolated test profile.
    for name, value in files.items():
        path = dest / name
        data = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") != data:
            raise SystemExit(f"Refusing to overwrite changed export: {path}")
        path.write_text(data, encoding="utf-8")
    print(f"Exported {case_id}: {dest} ({count} callbacks)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-case", metavar="ID", help="export one case beneath fixtures/generated/ID")
    args = parser.parse_args()
    cases, queue, catalog = verify()
    if args.export_case:
        export(args.export_case, cases, queue, catalog)


if __name__ == "__main__":
    main()
