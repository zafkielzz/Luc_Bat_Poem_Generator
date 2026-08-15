import unittest

from engine.tet4_agent import Tet4Agent


class Tet4AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = Tet4Agent()

    def test_brainstorm_returns_a_user_choice_set_and_sources(self):
        brief = self.agent.brainstorm("Chúc ông bà bình an, con cháu sum vầy")
        self.assertGreaterEqual(len(brief.suggested_keywords), 4)
        self.assertLessEqual(len(brief.suggested_keywords), 6)
        self.assertTrue(brief.source_refs)
        self.assertTrue(all(ref["material_id"] for ref in brief.source_refs))

    def test_selection_enforces_the_tet4_two_or_three_keyword_contract(self):
        metadata = self.agent.select_keywords("Chúc nhà luôn vui", ["mai vàng", "sum vầy"])
        self.assertEqual(metadata["từ khoá"], ["mai vàng", "sum vầy"])
        with self.assertRaisesRegex(ValueError, "2 hoặc 3"):
            self.agent.select_keywords("Chúc nhà luôn vui", ["mai vàng"])

    def test_plan_message_uses_selected_keywords_and_no_thinking_instruction(self):
        brief = self.agent.brainstorm("Chúc bạn một năm thuận lợi")
        metadata = self.agent.select_keywords(brief.wish_intent, ["nắng xuân", "tin vui"])
        messages = self.agent.build_plan_messages(brief, metadata)
        self.assertIn("nắng xuân, tin vui", messages[1]["content"])
        self.assertIn("không dùng <think>", messages[0]["content"])
        self.assertIn("đúng 4 object", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
