import unittest

from services.macro_optimization_service import (
    compress_consecutive_mouse_moves,
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

        optimized = compress_consecutive_mouse_moves(events)

        self.assertEqual(len(optimized), 2)
        self.assertEqual(optimized[0]["time"], 100)
        self.assertEqual(optimized[0]["normalized_x"], 0.3)
        self.assertEqual(optimized[0]["normalized_y"], 0.4)
        self.assertEqual(optimized[1]["event"], "down")

    def test_keeps_non_consecutive_moves_separate(self):
        events = [
            {"time": 100, "type": "mouse", "event": "move", "normalized_x": 0.1, "normalized_y": 0.1},
            {"time": 150, "type": "mouse", "event": "down", "button": "left"},
            {"time": 200, "type": "mouse", "event": "move", "normalized_x": 0.5, "normalized_y": 0.6},
        ]

        optimized = compress_consecutive_mouse_moves(events)

        self.assertEqual(len(optimized), 3)
        self.assertEqual(optimized[0]["event"], "move")
        self.assertEqual(optimized[1]["event"], "down")
        self.assertEqual(optimized[2]["event"], "move")

    def test_optimize_macro_events_removes_redundant_move_before_click(self):
        events = [
            {"time": 100, "type": "mouse", "event": "move", "normalized_x": 0.1, "normalized_y": 0.1},
            {"time": 130, "type": "mouse", "event": "move", "normalized_x": 0.3, "normalized_y": 0.4},
            {"time": 150, "type": "mouse", "event": "down", "button": "left", "normalized_x": 0.3, "normalized_y": 0.4},
            {"time": 180, "type": "mouse", "event": "up", "button": "left", "normalized_x": 0.3, "normalized_y": 0.4},
        ]

        optimized, report = optimize_macro_events(events)

        self.assertEqual(len(optimized), 2)
        self.assertEqual(report["compressed_move_count"], 1)
        self.assertEqual(report["removed_pre_click_moves"], 1)
        self.assertEqual(report["total_removed"], 2)
        self.assertEqual(optimized[0]["event"], "down")
        self.assertEqual(optimized[1]["event"], "up")

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


if __name__ == "__main__":
    unittest.main()
