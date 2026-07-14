import copy
import unittest

from doomsday.vision.hero_inspection_workflow import load_hero_inspection_workflow
from doomsday.vision.semantic_workflow import can_automate_transition, validate_semantic_workflow


class SemanticWorkflowTests(unittest.TestCase):
    def test_default_hero_workflow_has_valid_references_and_is_not_automatable(self):
        workflow = load_hero_inspection_workflow()

        validate_semantic_workflow(workflow)
        self.assertEqual(workflow["workflow_id"], "hero-inspection-v1")
        self.assertFalse(can_automate_transition(workflow, "select_hero"))
        self.assertTrue(all(not item["automation_allowed"] for item in workflow["transitions"]))

    def test_validated_transition_still_requires_confirmed_before_and_after_frames(self):
        workflow = copy.deepcopy(load_hero_inspection_workflow())
        transition = next(item for item in workflow["transitions"] if item["transition_id"] == "select_hero")
        transition["maturity"] = "validated"
        transition["automation_allowed"] = True
        transition["evidence"] = [
            {"kind": "before_frame", "quality": {"valid": True}, "human_confirmed": True},
            {"kind": "after_frame", "quality": {"valid": True}, "human_confirmed": True},
        ]

        self.assertTrue(can_automate_transition(workflow, "select_hero"))

    def test_automation_before_validation_is_rejected(self):
        workflow = copy.deepcopy(load_hero_inspection_workflow())
        workflow["transitions"][0]["automation_allowed"] = True

        with self.assertRaisesRegex(ValueError, "before validation"):
            validate_semantic_workflow(workflow)


if __name__ == "__main__":
    unittest.main()
