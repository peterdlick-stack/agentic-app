"""A/B/C trial preparation and observations. No synthetic human benefit claims."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sqlite3

from .feedback import FeedbackStore, _json, _id
from .recommend import load_catalog, recommend

TRIAL_VERSION = "abc-local-v1"


class ExperimentTrial:
    def __init__(self, state_dir, catalog, trial_id="trial-1", request="", limit=4):
        _id(trial_id)
        if type(limit) is not int or not 1 <= limit <= 24:
            raise ValueError("invalid_trial_limit")
        self.root = Path(state_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog = json.loads(_json(catalog))
        self.stores = {}
        self.db = sqlite3.connect(str(self.root / "trial.sqlite3"))
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS protocol (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations (event_id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS rounds (round_id TEXT PRIMARY KEY, body TEXT NOT NULL);
        """)
        index = int(hashlib.sha256(trial_id.encode()).hexdigest()[:8], 16) % 6
        manifest = {"version": TRIAL_VERSION, "trial_id": trial_id,
                    "catalog": [{"id": t["id"], "content_id": t["content_id"], "features": t["features"]} for t in catalog],
                    "order": list(itertools.permutations("ABC"))[index], "request": request, "limit": limit,
                    "comparison": "descriptive counts and denominators only; do not attribute time/activity differences to algorithm",
                    "metrics": ["accepted", "like", "dislike", "defer", "missing_feedback", "corrections", "disturbance_0_to_4"],
                    "initial_preferences": "empty and isolated by condition; A/B never learn", "evidence": "NO_USER_BENEFIT_EVIDENCE"}
        body = _json(manifest)
        existing = self.db.execute("SELECT body FROM protocol WHERE id=1").fetchone()
        if not existing and any((self.root / condition).exists() for condition in "ABC"):
            self.db.close()
            raise ValueError("new_trial_requires_empty_condition_directories")
        if existing and existing["body"] != body:
            self.db.close()
            raise ValueError("frozen_trial_inputs_changed_use_new_directory")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO protocol VALUES (1,?)", (body,))
        self.protocol = json.loads(body)
        for condition in "ABC":
            self.stores[condition] = FeedbackStore(self.root / condition)

    def create_round(self, round_id, context):
        """Freeze one context/request for all conditions. Reopening is idempotent."""
        _id(round_id)
        frozen_context = json.loads(_json(context))
        existing = self.db.execute("SELECT body FROM rounds WHERE round_id=?", (round_id,)).fetchone()
        if existing:
            result = json.loads(existing["body"])
            if result["context"] != frozen_context:
                raise ValueError("frozen_round_context_changed")
            return result
        snapshots = {}
        for condition in self.protocol["order"]:
            effective = dict(frozen_context) if condition != "A" else {"activity": "unknown", "source_kind": "manual", "freshness": "unverifiable", "allowed_for_current": False}
            # Historical times are retained; only the isolated experiment opts into replay.
            if effective.get("historical") is True:
                effective["experiment_mode"] = True
            result = recommend(self.catalog, effective, self.stores[condition].preferences(condition),
                               self.protocol["request"], self.protocol["limit"])
            snapshots[condition] = self.stores[condition].create_snapshot(result, condition)
        result = {"round_id": round_id, "context": frozen_context,
                  "order": self.protocol["order"], "snapshots": snapshots}
        with self.db:
            self.db.execute("INSERT INTO rounds VALUES (?,?)", (round_id, _json(result)))
        return result

    def record_observation(self, event_id, condition, snapshot_id, track_id,
                           accepted=None, disturbance=None, skipped=None):
        """User reports only; None remains missing, skipping is not dislike."""
        _id(event_id)
        if condition not in self.stores:
            raise ValueError("invalid_condition")
        if accepted is not None and type(accepted) is not bool or skipped is not None and type(skipped) is not bool:
            raise ValueError("accepted_and_skipped_must_be_bool_or_null")
        if disturbance is not None and (type(disturbance) is not int or not 0 <= disturbance <= 4):
            raise ValueError("disturbance_must_be_0_to_4_or_null")
        snapshot = self.stores[condition].get_snapshot(snapshot_id)
        if not any(t["id"] == track_id for t in snapshot["tracks"]):
            raise ValueError("track_not_in_snapshot")
        observation = {"condition": condition, "snapshot_id": snapshot_id, "track_id": track_id,
                       "accepted": accepted, "disturbance": disturbance, "skipped": skipped}
        body = _json(observation)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            existing = self.db.execute("SELECT body FROM observations WHERE event_id=?", (event_id,)).fetchone()
            if existing and existing["body"] != body:
                raise ValueError("conflicting_observation_id")
            if not existing:
                for row in self.db.execute("SELECT body FROM observations"):
                    previous = json.loads(row["body"])
                    if (previous["condition"], previous["snapshot_id"], previous["track_id"]) == (condition, snapshot_id, track_id):
                        raise ValueError("snapshot_track_observation_already_recorded")
                self.db.execute("INSERT INTO observations VALUES (?,?)", (event_id, body))
        return {"saved": True, "duplicate": existing is not None}

    def report(self):
        output = {"protocol": self.protocol, "conditions": {}, "benefit_status": "NO_USER_BENEFIT_EVIDENCE",
                  "interpretation": "recorded descriptive observations only; no causal effect or recognition validity established"}
        rounds = [json.loads(r["body"]) for r in self.db.execute("SELECT body FROM rounds ORDER BY round_id")]
        observations = [json.loads(r["body"]) for r in self.db.execute("SELECT body FROM observations ORDER BY event_id")]
        for condition, store in self.stores.items():
            events = store.list_events()
            shown = {(r["snapshots"][condition]["snapshot_id"], t["id"]) for r in rounds for t in r["snapshots"][condition]["tracks"]}
            feedback = {(e["snapshot_id"], e["track_id"]) for e in events}
            rows = [x for x in observations if x["condition"] == condition]
            output["conditions"][condition] = {
                "recommended_tracks": len(shown), "like": sum(e["value"] == "like" for e in events),
                "dislike": sum(e["value"] == "dislike" for e in events), "defer": sum(e["value"] == "defer" for e in events),
                "missing_feedback": len(shown - feedback), "accepted": sum(x["accepted"] is True for x in rows),
                "acceptance_observations": sum(x["accepted"] is not None for x in rows),
                "missing_acceptance": len(shown) - sum(x["accepted"] is not None for x in rows),
                "disturbance_values": [x["disturbance"] for x in rows if x["disturbance"] is not None],
                "missing_disturbance": len(shown) - sum(x["disturbance"] is not None for x in rows),
                "skips": sum(x["skipped"] is True for x in rows), "corrections": len(store.list_corrections()),
                "learning_events": store.preferences(condition)["event_count"]}
        return output

    def close(self):
        for store in self.stores.values():
            store.close()
        self.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", required=True)
    parser.add_argument("--state-dir", required=True, help="new isolated trial directory, never user preference directory")
    parser.add_argument("--trial-id", default="trial-1")
    parser.add_argument("--request", default="")
    parser.add_argument("--limit", type=int, default=4)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("report")
    init = commands.add_parser("round")
    init.add_argument("--round-id", required=True)
    init.add_argument("--context-json", required=True, help="path to exact context envelope JSON")
    for action in ("feedback", "observe"):
        sub = commands.add_parser(action)
        sub.add_argument("--condition", choices=list("ABC"), required=True)
        sub.add_argument("--event-id", required=True)
        sub.add_argument("--snapshot-id", required=True)
        sub.add_argument("--track-id", required=True)
        if action == "feedback":
            sub.add_argument("--value", choices=("like", "dislike", "defer"), required=True)
        else:
            sub.add_argument("--accepted", choices=("yes", "no", "missing"), default="missing")
            sub.add_argument("--disturbance", type=int)
            sub.add_argument("--skipped", choices=("yes", "no", "missing"), default="missing")
    args = parser.parse_args()
    trial = ExperimentTrial(args.state_dir, load_catalog(args.catalog_root), args.trial_id, args.request, args.limit)
    try:
        if args.command == "round":
            result = trial.create_round(args.round_id, json.loads(Path(args.context_json).read_text(encoding="utf-8")))
        elif args.command == "feedback":
            result = trial.stores[args.condition].record(args.event_id, args.snapshot_id, args.track_id, args.value)
        elif args.command == "observe":
            values = {"yes": True, "no": False, "missing": None}
            result = trial.record_observation(args.event_id, args.condition, args.snapshot_id, args.track_id,
                                              values[args.accepted], args.disturbance, values[args.skipped])
        else:
            result = trial.report()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        trial.close()


if __name__ == "__main__":
    main()
