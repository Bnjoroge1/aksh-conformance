#!/usr/bin/env python3
"""Capture all concurrency scenarios from the aksh-conformance repo on GitHub using the registered runner."""
import subprocess, json, time, sys
from pathlib import Path

REPO = "Bnjoroge1/aksh-conformance"
OUT = Path("results/github-official")
OUT.mkdir(parents=True, exist_ok=True)

SCENARIOS = [
    # (scenario_id, workflow_file, triggers)
    # trigger: list of (label, delay_before_submit)
    ("01", "concurrency-01-bare-string.yml", [("01-bare-A", 0), ("01-bare-B", 1)]),
    ("02", "concurrency-02-cancel-in-progress.yml", [("02-cancel-A", 0), ("02-cancel-B", 2)]),
    ("03", "concurrency-03-fifo-pending.yml", [("03-fifo-A", 0), ("03-fifo-B", 0.5)]),
    ("04", "concurrency-04-cancel-expr-true.yml", [("04-cancel-expr-A", 0), ("04-cancel-expr-B", 2)]),
    ("05", "concurrency-05-cancel-expr-false.yml", [("05-expr-false-A", 0), ("05-expr-false-B", 0.5)]),
    ("06", "concurrency-06-queue-max.yml", [("06-queue-max-A", 0), ("06-queue-max-B", 0.5), ("06-queue-max-C", 0.5)]),
    ("07a", "concurrency-07a-case-Prod.yml", [("07a-case-Prod", 0)]),
    ("07b", "concurrency-07b-case-prod.yml", [("07b-case-prod", 0)]),
    ("08", "concurrency-08-job-level.yml", [("08-job-level", 0)]),
    ("09", "concurrency-09-multi-job-hold.yml", [("09-multi-job", 0)]),
    ("10", "concurrency-10-empty-group.yml", [("10-empty", 0)]),
    ("11", "concurrency-11-expr-group-ref.yml", [("11-expr-group", 0)]),
    ("12", "concurrency-12-matrix-same-group.yml", [("12-matrix", 0)]),
    ("13", "concurrency-13-jobset-caller-only.yml", [("13-jobset-caller", 0)]),
    ("14", "concurrency-14-jobset-embedded-only.yml", [("14-jobset-embedded", 0)]),
    ("15", "concurrency-15-jobset-different-key.yml", [("15-jobset-diffkey", 0)]),
]

def run_gh(args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()

def get_run_ids(wf):
    out = run_gh(["gh", "run", "list", "--repo", REPO, "--workflow", wf, "--limit", "50", "--json", "databaseId"])
    return {str(r["databaseId"]) for r in json.loads(out)}

def wait_for_completion(run_id, timeout_secs=300):
    for _ in range(timeout_secs // 3):
        time.sleep(3)
        out = run_gh(["gh", "run", "view", "--repo", REPO, run_id, "--json", "status,conclusion"])
        r = json.loads(out)
        if r["status"] == "completed":
            return r["conclusion"]
    return "timeout"

all_results = {}

for scenario_id, wf, triggers in SCENARIOS:
    print(f"\n=== {scenario_id}: {wf} ===")
    known = get_run_ids(wf)
    
    for label, delay in triggers:
        if delay > 0:
            time.sleep(delay)
        run_gh(["gh", "workflow", "run", "--repo", REPO, wf, "--ref", "main"])
    
    # Find new runs
    new_runs = []
    for _ in range(30):
        time.sleep(2)
        current = get_run_ids(wf)
        new = current - known
        if len(new) >= len(triggers):
            new_runs = sorted(new, key=int)
            break
    
    if len(new_runs) < len(triggers):
        print(f"  WARNING: only found {len(new_runs)}/{len(triggers)} new runs")
    
    for (label, _), rid in zip(triggers, new_runs):
        print(f"  {label} ({rid}): waiting...")
        conclusion = wait_for_completion(rid)
        print(f"  {label}: {conclusion}")
        all_results[label] = conclusion
        
        rdir = OUT / label
        rdir.mkdir(parents=True, exist_ok=True)
        full = run_gh(["gh", "run", "view", "--repo", REPO, rid, "--json", "status,conclusion,jobs,createdAt,updatedAt,url"])
        (rdir / "summary.json").write_text(full)
        log = run_gh(["gh", "run", "view", "--repo", REPO, rid, "--log"])
        (rdir / "run.log").write_text(log)
        (rdir / "github-run-id.txt").write_text(rid)

print("\n=== ALL RESULTS ===")
print(json.dumps(all_results, indent=2))
(OUT / "all-results.json").write_text(json.dumps(all_results, indent=2))
print(f"\nResults saved to {OUT}")
