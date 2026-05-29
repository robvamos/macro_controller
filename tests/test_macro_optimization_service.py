import unittest

from services.macro_optimization_service import (
    accelerate_keyboard_sequences,
    compress_consecutive_mouse_moves,
    compute_macro_duration_seconds,
    compute_macro_event_stats,
    optimize_macro_events,
)


class MacroOptimizationServiceTests(unittest.TestCase):
    def test_compresses_consecutive_mouse_moves_to_one_event(self):
        events = [
            {"time": 100, "type": "mouse", "event": "move", "normalized_x": 0.1, "normalized_y": 0.1},
            {"time": 120, "type": "mouse", "event": "move", "normalized_x": 0.2, "normalized_y": 0.2},
            {"time": 140, "type": "mouse", "event": "move", "normalized_x": 0.3, "normalized_y": 0.4},
            {"time": 180, "type": "mouse", "event": "down", "button": "left", "normalized_x": 0.3, "normalized_y": 0.4},
        ]

        optimized, removed_time_ms = compress_consecutive_mouse_moves(events)

        self.assertEqual(len(optimized), 2)
        self.assertEqual(optimized[0]["time"], 100)
        self.assertEqual(optimized[0]["normalized_x"], 0.3)
        self.assertEqual(optimized[0]["normalized_y"], 0.4)
        self.assertEqual(optimized[1]["time"], 140)
        self.assertEqual(optimized[1]["event"], "down")
        self.assertEqual(removed_time_ms, 40)

    def test_keeps_non_consecutive_moves_separate(self):
        events = [
            {"time": 100, "type": "mouse", "event": "move", "normalized_x": 0.1, "normalized_y": 0.1},
            {"time": 150, "type": "mouse", "event": "down", "button": "left"},
            {"time": 200, "type": "mouse", "event": "move", "normalized_x": 0.5, "normalized_y": 0.6},
        ]

        optimized, removed_time_ms = compress_consecutive_mouse_moves(events)

        self.assertEqual(len(optimized), 3)
        self.assertEqual(optimized[0]["event"], "move")
        self.assertEqual(optimized[1]["event"], "down")
        self.assertEqual(optimized[2]["event"], "move")
        self.assertEqual(removed_time_ms, 0)

    def test_optimize_macro_events_removes_redundant_move_before_click(self):
        events = [
            {"time": 100, "type": "mouse", "event": "move", "normalized_x": 0.1, "normalized_y": 0.1},
            {"time": 130, "type": "mouse", "event": "move", "normalized_x": 0.3, "normalized_y": 0.4},
            {"time": 150, "type": "mouse", "event": "down", "button": "left", "normalized_x": 0.3, "normalized_y": 0.4},
            {"time": 180, "type": "mouse", "event": "up", "button": "left", "normalized_x": 0.3, "normalized_y": 0.4},
        ]

        optimized, report = optimize_macro_events(events)

        self.assertEqual(len(optimized), 3)
        self.assertEqual(report["compressed_move_count"], 1)
        self.assertEqual(report["removed_move_time_ms"], 25)
        self.assertEqual(report["removed_pre_click_moves"], 0)
        self.assertEqual(report["total_removed"], 1)
        self.assertEqual(optimized[0]["time"], 100)
        self.assertEqual(optimized[1]["time"], 125)
        self.assertEqual(optimized[2]["time"], 155)
        self.assertEqual(optimized[0]["event"], "move")
        self.assertEqual(optimized[1]["event"], "down")
        self.assertEqual(optimized[2]["event"], "up")

    def test_keeps_final_move_before_mouse_down_for_ui_settle(self):
        events = [
            {"time": 10, "type": "mouse", "event": "move", "normalized_x": 0.2, "normalized_y": 0.2},
            {"time": 20, "type": "mouse", "event": "move", "normalized_x": 0.4, "normalized_y": 0.4},
            {"time": 60, "type": "mouse", "event": "down", "button": "left", "normalized_x": 0.4, "normalized_y": 0.4},
        ]

        optimized, report = optimize_macro_events(events)

        self.assertEqual([event["event"] for event in optimized], ["move", "down"])
        self.assertEqual(optimized[0]["normalized_x"], 0.4)
        self.assertEqual(optimized[0]["normalized_y"], 0.4)
        self.assertEqual(optimized[1]["time"], 50)
        self.assertEqual(report["removed_pre_click_moves"], 0)

    def test_preserves_minimum_settle_gap_before_next_action(self):
        events = [
            {"time": 100, "type": "mouse", "event": "move", "normalized_x": 0.1, "normalized_y": 0.1},
            {"time": 140, "type": "mouse", "event": "move", "normalized_x": 0.3, "normalized_y": 0.4},
            {"time": 145, "type": "keyboard", "event": "down", "name": "a"},
        ]

        optimized, removed_time_ms = compress_consecutive_mouse_moves(events)

        self.assertEqual(len(optimized), 2)
        self.assertEqual(optimized[0]["time"], 100)
        self.assertEqual(optimized[1]["time"], 125)
        self.assertEqual(removed_time_ms, 20)

    def test_compute_macro_event_stats_counts_categories(self):
        events = [
            {"time": 0, "type": "keyboard", "event": "down"},
            {"time": 20, "type": "mouse", "event": "move"},
            {"time": 25, "type": "mouse", "event": "scroll"},
            {"time": 40, "type": "mouse", "event": "down"},
            {"time": 60, "type": "mouse", "event": "up"},
        ]

        stats = compute_macro_event_stats(events)

        self.assertEqual(stats["total_events"], 5)
        self.assertEqual(stats["duration_ms"], 60)
        self.assertEqual(stats["keyboard_events"], 1)
        self.assertEqual(stats["mouse_moves"], 1)
        self.assertEqual(stats["mouse_clicks"], 2)
        self.assertEqual(stats["scroll_events"], 1)

    def test_compute_macro_duration_seconds_rounds_up_optimized_timeline(self):
        events = [
            {"time": 0, "type": "mouse", "event": "move"},
            {"time": 1250, "type": "mouse", "event": "down"},
        ]

        self.assertEqual(compute_macro_duration_seconds(events), 2)

    def test_compute_macro_duration_seconds_has_minimum_one_second(self):
        self.assertEqual(compute_macro_duration_seconds([]), 1)

    def test_accelerate_keyboard_sequences_reduces_typing_gaps(self):
        events = [
            {"time": 0, "type": "keyboard", "event": "down", "name": "a"},
            {"time": 90, "type": "keyboard", "event": "up", "name": "a"},
            {"time": 220, "type": "keyboard", "event": "down", "name": "b"},
            {"time": 310, "type": "keyboard", "event": "up", "name": "b"},
        ]

        optimized, removed_time_ms, accelerated_events = accelerate_keyboard_sequences(events)

        self.assertEqual([event["time"] for event in optimized], [0, 20, 35, 55])
        self.assertEqual(removed_time_ms, 255)
        self.assertEqual(accelerated_events, 3)

    def test_optimize_macro_events_can_accelerate_keyboard_without_removing_events(self):
        events = [
            {"time": 0, "type": "keyboard", "event": "down", "name": "1"},
            {"time": 100, "type": "keyboard", "event": "up", "name": "1"},
        ]

        optimized, report = optimize_macro_events(events, optimize_keyboard_input=True)

        self.assertEqual(len(optimized), 2)
        self.assertEqual(optimized[1]["time"], 20)
        self.assertEqual(report["removed_keyboard_time_ms"], 80)
        self.assertEqual(report["accelerated_keyboard_events"], 1)


if __name__ == "__main__":
    unittest.main()
