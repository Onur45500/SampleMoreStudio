from backend.db import get_db

db = get_db()
print("=== Phase 1 B=512 ===")
for r in sorted(db.leaderboard(phase="phase1_reasoning", budget=512), key=lambda x: -x["accuracy"]):
    print(
        f"{r['strategy']:20} acc={r['accuracy']*100:5.1f}% n={r['n_runs']} "
        f"tokens={r['avg_tokens_spent']:.0f}/{r['avg_target_budget']:.0f}"
    )
print("=== Phase 2 ===")
for r in sorted(db.leaderboard(phase="phase2_agent"), key=lambda x: -x["accuracy"]):
    print(
        f"{r['strategy']:20} acc={r['accuracy']*100:5.1f}% n={r['n_runs']} "
        f"tools={r['avg_tool_calls']:.1f}"
    )
p = db.get_progress()
print("progress", p.get("status"), p.get("completed"), "/", p.get("total"), p.get("current_strategy"), p.get("current_task"))
