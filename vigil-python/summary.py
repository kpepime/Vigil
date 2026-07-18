import sqlite3
from check_outcomes import get_final_result

conn = sqlite3.connect("signals.db")
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM signals")
total_signals = cur.fetchone()[0]

cur.execute("SELECT DISTINCT fixture_id FROM signals")
fixture_ids = [row[0] for row in cur.fetchall()]

cur.execute("""
    SELECT id, fixture_id, outcome, old_pct, new_pct, change
    FROM signals
    WHERE change > 0
""")
directional_signals = cur.fetchall()

correct = 0
incorrect = 0
unresolved = 0
result_cache = {}

for row_id, fixture_id, outcome, old_pct, new_pct, change in directional_signals:
    if fixture_id not in result_cache:
        result_cache[fixture_id] = get_final_result(fixture_id)
    result = result_cache[fixture_id]

    if result is None:
        unresolved += 1
    elif outcome == result:
        correct += 1
    else:
        incorrect += 1

resolved = correct + incorrect

print("=" * 50)
print("SHARP MOVEMENT DETECTOR SUMMARY")
print("=" * 50)
print(f"Fixtures monitored: {len(fixture_ids)}")
print(f"Total signals logged: {total_signals}")
print(f"Directional signals: {len(directional_signals)}")
print(f"Resolved (match finished): {resolved}")
print(f"Correct: {correct}")
print(f"Incorrect: {incorrect}")
print(f"Unresolved (still live): {unresolved}")
if resolved > 0:
    print(f"Accuracy on resolved signals: {correct / resolved * 100:.1f}%")
else:
    print("Accuracy: no resolved matches yet")
print("=" * 50)