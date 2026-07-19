from check_outcomes import get_final_result
import fixtures

# this is the finished match we already inspected earlier
fixture_id = 18187298
result = get_final_result(fixture_id)

label = fixtures.describe_fixture(fixture_id)

# Matches the "Fixture: / Outcome:" convention used in broadcast_signal,
# so this is the same readable format judges see in the Telegram bot.
print(f"Fixture: {label}\nOutcome: {result}")