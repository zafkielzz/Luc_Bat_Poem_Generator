from engine.tet4_naturalness import build_critic_messages, parse_critic, repair_feedback


def test_critic_schema_and_repair_feedback():
    raw = '{"decision":"reject","issues":["cụm bàn thài không tự nhiên"],"repair_instruction":"dùng từ thông dụng"}'
    critic = parse_critic(raw)
    assert critic is not None
    feedback = repair_feedback("bàn thài ông ơ", critic)
    assert "bàn thài" in feedback and "Không lặp lại" in feedback
    assert parse_critic('{"decision":"maybe"}') is None


def test_critic_prompt_is_evaluation_only():
    messages = build_critic_messages("ông bà sum vầy", {"ý chúc": "chúc ông bà", "từ khoá": ["sum vầy"]})
    assert "không sáng tác lại" in messages[0]["content"]
    assert "ông bà sum vầy" in messages[1]["content"]


def test_parse_critic_recovers_clear_reject_from_unescaped_quote():
    raw = ('{"decision":"reject", "issues":["cụm \"bữa thơi\" gượng"], '
           '"repair_instruction":"dùng cụm tự nhiên"}')
    result = parse_critic(raw)
    assert result is not None
    assert result["decision"] == "reject"
    assert "bữa thơi" in result["issues"][0]
