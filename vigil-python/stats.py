from collections import Counter
import db
from check_outcomes import get_final_result


def bucket_magnitude(change):
    abs_change = abs(change)
    if abs_change < 3:
        return "2.5-3%"
    elif abs_change < 5:
        return "3-5%"
    elif abs_change < 10:
        return "5-10%"
    elif abs_change < 15:
        return "10-15%"
    else:
        return "15%+"


def compute_summary():
    conn = db.get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM signals")
    total = cur.fetchone()[0]

    cur.execute("SELECT detected_at, fixture_id, outcome, change FROM signals ORDER BY id DESC LIMIT 200")
    recent = [(t, f, o, round(c, 1)) for t, f, o, c in cur.fetchall()]

    cur.execute("SELECT fixture_id, outcome, change FROM signals WHERE change > 0")
    directional = cur.fetchall()

    correct = incorrect = unresolved = 0
    cache = {}
    for fixture_id, outcome, change in directional:
        if fixture_id not in cache:
            cache[fixture_id] = get_final_result(fixture_id)
        result = cache[fixture_id]
        if result is None:
            unresolved += 1
        elif outcome == result:
            correct += 1
        else:
            incorrect += 1

    resolved = correct + incorrect
    accuracy = f"{correct / resolved * 100:.1f}%" if resolved else "n/a"

    cur.execute("SELECT change FROM signals")
    all_changes = [row[0] for row in cur.fetchall()]
    order = ["2.5-3%", "3-5%", "5-10%", "10-15%", "15%+"]
    mag_counts = Counter(bucket_magnitude(c) for c in all_changes)
    magnitude_labels = order
    magnitude_values = [mag_counts.get(bucket, 0) for bucket in order]

    cur.execute("SELECT detected_at FROM signals ORDER BY id ASC")
    timestamps = [row[0] for row in cur.fetchall()]
    bucketed = Counter(ts[11:16] for ts in timestamps)
    sorted_buckets = sorted(bucketed.items())[-20:]
    timeline_labels = [b[0] for b in sorted_buckets]
    timeline_values = [b[1] for b in sorted_buckets]

    return {
        "total": total,
        "recent": recent,
        "resolved": resolved,
        "accuracy": accuracy,
        "correct": correct,
        "incorrect": incorrect,
        "unresolved": unresolved,
        "magnitude_labels": magnitude_labels,
        "magnitude_values": magnitude_values,
        "timeline_labels": timeline_labels,
        "timeline_values": timeline_values,
    }