import unittest
from unittest.mock import Mock, patch

from doomsday.vision.ui_graph import build_default_doomsday_ui_graph, evaluate_ui_graph, learn_ui_knowledge


class UIGraphTests(unittest.TestCase):
    def test_structural_nodes_without_conditions_remain_unknown(self):
        evaluation = evaluate_ui_graph(build_default_doomsday_ui_graph(), (0, 0, 1920, 1080))
        root = evaluation.get_node_result("game_runtime_root")
        self.assertIsNotNone(root)
        self.assertFalse(root.observable)
        self.assertFalse(root.active)
        self.assertNotIn("game_runtime_root", evaluation.active_node_ids)

    def test_default_graph_exposes_boot_popup_and_playable_nodes(self):
        graph = build_default_doomsday_ui_graph()

        node_ids = {node.node_id for node in graph.nodes}
        self.assertIn("game_runtime_root", node_ids)
        self.assertIn("exterior_region_view", node_ids)
        self.assertIn("shelter_interior_view", node_ids)
        self.assertIn("top_left_compact_status_panel", node_ids)
        self.assertIn("top_left_profile_portrait", node_ids)
        self.assertIn("top_left_status_bar", node_ids)
        self.assertIn("top_left_power_indicator", node_ids)
        self.assertIn("top_left_vip_indicator", node_ids)
        self.assertIn("top_left_left_quick_action", node_ids)
        self.assertIn("top_left_right_quick_action", node_ids)
        self.assertIn("top_right_extended_status_panel", node_ids)
        self.assertIn("bottom_left_shelter_switch_button", node_ids)
        self.assertIn("shelter_left_side_controls_panel", node_ids)
        self.assertIn("shelter_bottom_right_sections_panel", node_ids)
        self.assertIn("campaign_section_button", node_ids)
        self.assertIn("backpack_section_button", node_ids)
        self.assertIn("alliance_section_button", node_ids)
        self.assertIn("beast_section_button", node_ids)
        self.assertIn("hero_section_button", node_ids)
        self.assertIn("shelter_right_edge_alerts_panel", node_ids)
        self.assertIn("troop_heal_action_symbol", node_ids)
        self.assertIn("boot_overlay_layer", node_ids)
        self.assertIn("initial_blocking_popup_close_symbol", node_ids)
        self.assertIn("popup_back_return_symbol", node_ids)
        self.assertIn("popup_crossed_circle_symbol", node_ids)
        self.assertIn("empty_space_popup_dismissal_band_4", node_ids)
        self.assertIn("playable_interface_without_boot_popup", node_ids)
        self.assertEqual(graph.get_node("initial_blocking_popup_close_symbol").recovery_action, "click_popup_exit_close_symbol")
        self.assertEqual(graph.get_node("initial_blocking_popup_close_symbol").parent_node_id, "boot_overlay_layer")
        self.assertIn(
            "boot_blocking_popup_close_button",
            graph.get_node("initial_blocking_popup_close_symbol").conditions[0].element_names,
        )
        self.assertIn("basta cliccare", graph.get_node("initial_blocking_popup_close_symbol").notes)
        self.assertEqual(
            graph.get_node("popup_back_return_symbol").recovery_action,
            "click_popup_back_return_symbol_until_gone",
        )
        self.assertIn("2 o 3 volte", graph.get_node("popup_back_return_symbol").notes)
        self.assertEqual(
            graph.get_node("popup_crossed_circle_symbol").recovery_action,
            "click_popup_crossed_circle_symbol_until_gone",
        )
        self.assertIn("cerchio barrato", graph.get_node("popup_crossed_circle_symbol").notes)
        self.assertIn(
            "popup_back_return_symbol",
            graph.get_node("playable_interface_without_boot_popup").conditions[1].element_names,
        )
        self.assertIn(
            "popup_crossed_circle_symbol",
            graph.get_node("playable_interface_without_boot_popup").conditions[2].element_names,
        )
        self.assertEqual(
            graph.get_node("empty_space_popup_dismissal_band_4").recovery_action,
            "click_empty_space_band_4_from_bottom",
        )
        self.assertIn("fascia 4", graph.get_node("empty_space_popup_dismissal_band_4").notes)
        self.assertIn("medio alta", graph.get_node("empty_space_popup_dismissal_band_4").notes)
        self.assertIn("stesso elemento logico", graph.get_node("empty_space_popup_dismissal_band_4").notes)
        self.assertEqual(graph.get_node("shelter_left_side_controls_panel").parent_node_id, "shelter_interior_view")
        self.assertEqual(graph.get_node("top_right_extended_status_panel").layout_role, "top_right_extended")
        self.assertEqual(graph.get_node("top_left_profile_portrait").parent_node_id, "top_left_compact_status_panel")
        self.assertIn("personalizzata", graph.get_node("top_left_profile_portrait").notes)
        self.assertEqual(graph.get_node("top_left_power_indicator").parent_node_id, "top_left_compact_status_panel")
        self.assertIn("numero cambia", graph.get_node("top_left_power_indicator").notes)
        self.assertIn("leggere il numero", graph.get_node("top_left_power_indicator").notes)
        self.assertIn("scritta VIP e da un numero", graph.get_node("top_left_vip_indicator").notes)
        self.assertEqual(graph.get_node("troop_heal_action_symbol").parent_node_id, "shelter_interior_view")
        self.assertIn("riferimento visivo", graph.get_node("troop_heal_action_symbol").notes)
        self.assertEqual(graph.get_node("shelter_bottom_right_sections_panel").parent_node_id, "game_runtime_root")
        self.assertIn("badge rossi", graph.get_node("shelter_bottom_right_sections_panel").notes)
        self.assertEqual(graph.get_node("campaign_section_button").parent_node_id, "shelter_bottom_right_sections_panel")
        self.assertEqual(graph.get_node("hero_section_button").parent_node_id, "shelter_bottom_right_sections_panel")

    def test_default_graph_exposes_region_shelter_navigation_semantics(self):
        graph = build_default_doomsday_ui_graph()
        switch_node = graph.get_node("bottom_left_shelter_switch_button")

        edges = {(edge.from_node_id, edge.to_node_id, edge.trigger, edge.action_name) for edge in graph.edges}
        self.assertIn(
            ("bottom_left_shelter_switch_button", "shelter_interior_view", "enter_shelter", "open_shelter_view"),
            edges,
        )
        self.assertIn(
            ("bottom_left_shelter_switch_button", "exterior_region_view", "exit_shelter", "open_region_view"),
            edges,
        )
        self.assertIn(
            ("exterior_region_view", "shelter_bottom_right_sections_panel", "shared_bottom_right_sections_visible", None),
            edges,
        )
        self.assertIn(
            ("shelter_interior_view", "shelter_bottom_right_sections_panel", "shared_bottom_right_sections_visible", None),
            edges,
        )
        self.assertIn(
            ("shelter_bottom_right_sections_panel", "campaign_section_button", "campaign_slot_visible", "open_campaign_section"),
            edges,
        )
        self.assertIn(
            ("shelter_bottom_right_sections_panel", "hero_section_button", "hero_slot_visible", "open_hero_section"),
            edges,
        )
        self.assertIn(
            ("top_left_compact_status_panel", "top_left_power_indicator", "power_indicator_visible", None),
            edges,
        )
        self.assertIn(
            ("top_left_compact_status_panel", "top_left_vip_indicator", "vip_indicator_visible", None),
            edges,
        )
        self.assertEqual(
            switch_node.conditions[0].element_names,
            ("region_view_switch_globe_icon", "shelter_view_switch_home_icon"),
        )
        self.assertEqual(switch_node.conditions[0].threshold, 0.85)
        self.assertIn("Rifugio", switch_node.notes)

    def test_evaluate_ui_graph_marks_popup_node_active_when_symbol_is_found(self):
        found_result = Mock(condition_satisfied=True, found=True, score=0.91)
        absent_due_to_presence_result = Mock(condition_satisfied=False, found=True, score=0.91)
        absent_ok_result = Mock(condition_satisfied=True, found=False, score=None)
        default_result = Mock(condition_satisfied=False, found=False, score=None)

        def fake_search(_window_rect, *, element_names, expected_presence, **_kwargs):
            names = tuple(element_names)
            if "popup_exit_close_symbol" in names:
                return found_result if expected_presence else absent_due_to_presence_result
            if "popup_back_return_symbol" in names:
                return default_result if expected_presence else absent_ok_result
            if "popup_crossed_circle_symbol" in names:
                return default_result if expected_presence else absent_ok_result
            return default_result

        with patch(
            "doomsday.vision.ui_graph.search_game_window_elements",
            side_effect=fake_search,
        ):
            evaluation = evaluate_ui_graph(build_default_doomsday_ui_graph(), (0, 0, 1920, 1080))

        self.assertIn("initial_blocking_popup_close_symbol", evaluation.active_node_ids)
        popup_node = evaluation.get_node_result("initial_blocking_popup_close_symbol")
        self.assertTrue(popup_node.active)
        self.assertGreaterEqual(popup_node.confidence, 0.91)

    def test_evaluate_ui_graph_marks_playable_node_active_when_popup_symbol_is_absent(self):
        present_result = Mock(condition_satisfied=False, found=False, score=None)
        absent_result = Mock(condition_satisfied=True, found=False, score=None)

        default_result = Mock(condition_satisfied=False, found=False, score=None)

        def fake_search(_window_rect, *, element_names, expected_presence, **_kwargs):
            names = tuple(element_names)
            if "popup_exit_close_symbol" in names:
                return present_result if expected_presence else absent_result
            if "popup_back_return_symbol" in names:
                return present_result if expected_presence else absent_result
            if "popup_crossed_circle_symbol" in names:
                return present_result if expected_presence else absent_result
            return default_result

        with patch(
            "doomsday.vision.ui_graph.search_game_window_elements",
            side_effect=fake_search,
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
