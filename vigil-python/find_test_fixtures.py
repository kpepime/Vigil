from check_outcomes import get_final_result
import fixtures

# reuse the exact same cache/auth the live app uses, instead of a separate
# hand-rolled scan with its own JWT, this way it can't drift out of sync
# with fixtures.py, and it inherits the auto-refreshing token.
fixtures.load_from_db()
fixtures._refresh_once()

with fixtures._lock:
    seen_fixtures = dict(fixtures._fixture_cache)

print(f"\nTotal unique fixtures known: {len(seen_fixtures)}")
print("\nChecking which ones are finished, and how...\n")

for fid in seen_fixtures:
    result = get_final_result(fid)
    if result:
        label = fixtures.describe_fixture(fid)
        outcome_label = fixtures.describe_outcome(fid, result)
        print(f"Fixture {fid} ({label}): FINISHED, result = {outcome_label}")