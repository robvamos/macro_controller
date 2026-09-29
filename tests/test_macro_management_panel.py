import tkinter as tk
from tkinter import ttk
import unittest

from ui.macro_management_panel import build_macro_management_tab


class MacroManagementPanelTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tk non disponibile: {exc}")

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_command_panel_contains_only_one_stop_button(self):
        notebook = ttk.Notebook(self.root)
        refs = build_macro_management_tab(
            tab_control=notebook,
            theme={
                "font_family": "Segoe UI",
                "font_size_small": 9,
                "border_color": "#333333",
                "text_color": "#ffffff",
            },
            macro_manager_config={
                "loop_interval_sec_default": 1,
                "listbox_height": 8,
            },
            create_new_macro_dialog=lambda: None,
            console_log=lambda *args, **kwargs: None,
            start_playback_thread=lambda: None,
            stop_current_operation=lambda: None,
            edit_selected_macro=lambda: None,
            delete_selected_macro=lambda: None,
            duplicate_selected_macro=lambda: None,
            concat_macros_dialog=lambda: None,
            update_button_states=lambda: None,
            setup_click_context_preview=lambda _parent: None,
            setup_execution_visualizer=lambda _parent: None,
            panel_state={},
            on_panel_state_change=lambda *_args: None,
        )

        stop_buttons = [
            widget
            for widget in self._descendants(refs["macro_tab"])
            if isinstance(widget, ttk.Button) and widget.cget("text") == "■ Stop"
        ]

        self.assertEqual(len(stop_buttons), 1)
        self.assertIs(stop_buttons[0], refs["stop_button"])
        self.assertNotIn("emergency_stop_button", refs)

    def _descendants(self, widget):
        descendants = []
        for child in widget.winfo_children():
            descendants.append(child)
            descendants.extend(self._descendants(child))
        return descendants


if __name__ == "__main__":
    unittest.main()
