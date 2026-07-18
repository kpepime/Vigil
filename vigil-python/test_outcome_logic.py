from check_outcomes import get_final_result

# this is the finished match we already inspected earlier
fixture_id = 18202783
result = get_final_result(fixture_id)
print(f"Fixture {fixture_id} final result: {result}")