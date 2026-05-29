import unittest
from unittest.mock import Mock, patch

from doomsday.vision.ui_graph import build_default_doomsday_ui_graph, evaluate_ui_graph, learn_ui_knowledge


class UIGraphTests(unittest.TestCase):
    def test_default_graph_exposes_boot_popup_and_playable_nodes(self):
        graph = build_default_doomsday_ui_graph()

        node_ids = {node.node_id for node in graph.nodes}
        self.assertIn("game_runtime_root", node_ids)
        self.assertIn("exterior_region_view", node_ids)
        self.assertIn("shelter_interior_view", node_ids)
        self.assertIn("top_left_compact_status_panel", node_ids)
        self.assertIn("top_right_extended_status_panel", node_ids)
        self.assertIn("bottom_left_shelter_switch_button", node_ids)
        self.assertIn("shelter_left_side_controls_panel", node_ids)
        self.assertIn("shelter_bottom_right_sections_panel", node_ids)
        self.assertIn("shelter_right_edge_alerts_panel", node_ids)
        self.assertIn("boot_overlay_layer", node_ids)
        self.assertIn("initial_blocking_popup_close_symbol", node_ids)
        self.assertIn("playable_interface_without_boot_popup", node_ids)
        self.assertEqual(graph.get_node("initial_blocking_popup_close_symbol").recovery_action, "click_popup_exit_close_symbol")
        self.assertEqual(graph.get_node("initial_blocking_popup_close_symbol").parent_node_id, "boot_overlay_layer")
        self.assertEqual(graph.get_node("shelter_left_side_controls_panel").parent_node_id, "shelter_interior_view")
        self.assertEqual(graph.get_node("top_right_extended_status_panel").layout_role, "top_right_extended")

    def test_default_graph_exposes_region_shelter_navigation_semantics(self):
        graph = build_default_doomsday_ui_graph()

        edges = {(edge.from_node_id, edge.to_node_id, edge.trigger, edge.action_name) for edge in graph.edges}
        self.assertIn(
            ("bottom_left_shelter_switch_button", "shelter_interior_view", "enter_shelter", "open_shelter_view"),
            edges,
        )
        self.assertIn(
            ("bottom_left_shelter_switch_button", "exterior_region_view", "exit_shelter", "open_region_view"),
            edges,
        )

    def test_evaluate_ui_graph_marks_popup_node_active_when_symbol_is_found(self):
        found_result = Mock(condition_satisfied=True, found=True, score=0.91)
        absent_result = Mock(condition_satisfied=False, found=True, score=0.91)

        with patch(
            "doomsday.vision.ui_graph.search_game_window_elements",
            side_effect=[found_result, absent_result],
        ):
            evaluation = evaluate_ui_graph(build_default_doomsday_ui_graph(), (0, 0, 1920, 1080))

        self.assertIn("initial_blocking_popup_close_symbol", evaluation.active_node_ids)
        popup_node = evaluation.get_node_result("initial_blocking_popup_close_symbol")
        self.assertTrue(popup_node.active)
        self.assertGreaterEqual(popup_node.confidence, 0.91)

    def test_evaluate_ui_graph_marks_playable_node_active_when_popup_symbol_is_absent(self):
        present_result = Mock(condition_satisfied=False, found=False, score=None)
        absent_result = Mock(condition_satisfied=True, found=False, score=None)

        with patch(
            "doomsday.vision.ui_graph.search_game_window_elements",
            side_effect=[present_result, absent_result],
        ):
            evaluation = evaluate_ui_graph(build_default_doomsday_ui_graph(), (0, 0, 1920, 1080))

        self.assertIn("playable_interface_without_boot_popup", evaluation.active_node_ids)
        playable_node = evaluation.get_node_result("playable_interface_without_boot_popup")
        self.assertTrue(playable_node.active)
        self.assertEqual(playable_node.confidence, 1.0)

    def test_learn_ui_knowledge_reconstructs_relationships_and_seen_counts(self):
        graph = build_default_doomsday_ui_graph()
        fake_evaluation = Mock(
            graph_id=graph.graph_id,
            active_node_ids=("game_runtime_root", "boot_overlay_layer", "initial_blocking_popup_close_symbol"),
        )
        fake_evaluation.get_node_result = lambda node_id: {
            "game_runtime_root": Mock(active=True, confidence=1.0),
            "boot_overlay_layer": Mock(active=True, confidence=1.0),
            "initial_blocking_popup_close_symbol": Mock(active=True, confidence=0.92),
            "playable_interface_without_boot_popup": Mock(active=False, confidence=0.0),
        }.get(node_id)

        knowledge = learn_ui_knowledge(graph, fake_evaluation)
        popup_record = knowledge.get_node_record("initial_blocking_popup_close_symbol")
        overlay_record = knowledge.get_node_record("boot_overlay_layer")

        self.assertEqual(knowledge.active_node_ids, fake_evaluation.active_node_ids)
        self.assertEqual(popup_record.seen_count, 1)
        self.assertGreaterEqual(popup_record.avg_confidence, 0.92)
        self.assertEqual(popup_record.parent_node_id, "boot_overlay_layer")
        self.assertIn("initial_blocking_popup_close_symbol", overlay_record.related_node_ids)

    def test_learn_ui_knowledge_accumulates_confidence_over_time(self):
        graph = build_default_doomsday_ui_graph()
        eval1 = Mock(graph_id=graph.graph_id, active_node_ids=("initial_blocking_popup_close_symbol",))
        eval1.get_node_result = lambda node_id: {
            "initial_blocking_popup_close_symbol": Mock(active=True, confidence=0.90),
        }.get(node_id, Mock(active=False, confidence=0.0))
        eval2 = Mock(graph_id=graph.graph_id, active_node_ids=("initial_blocking_popup_close_symbol",))
        eval2.get_node_result = lambda node_id: {
            "initial_blocking_popup_close_symbol": Mock(active=True, confidence=0.80),
        }.get(node_id, Mock(active=False, confidence=0.0))

        knowledge1 = learn_ui_knowledge(graph, eval1)
        knowledge2 = learn_ui_knowledge(graph, eval2, previous=knowledge1)
        popup_record = knowledge2.get_node_record("initial_blocking_popup_close_symbol")

        self.assertEqual(popup_record.seen_count, 2)
        self.assertAlmostEqual(popup_record.avg_confidence, 0.85, places=2)


if __name__ == "__main__":
    unittest.main()
