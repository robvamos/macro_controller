"""Sezione espandibile/ comprimibile per interfacce Tkinter."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class CollapsibleSection:
    def __init__(self, parent, *, title: str, expanded: bool = True):
        self.container = ttk.Frame(parent)
        self._expanded = expanded

        header = ttk.Frame(self.container)
        header.pack(fill="x")

        self.toggle_button = ttk.Button(header, text="", width=3, command=self.toggle)
        self.toggle_button.pack(side="left", padx=(0, 6))
        self.title_label = ttk.Label(header, text=title)
        self.title_label.pack(side="left", anchor="w")

        self.body = ttk.Frame(self.container)
        if expanded:
            self.body.pack(fill="both", expand=True, pady=(6, 0))

        self._refresh_button_label()

    def _refresh_button_label(self):
        self.toggle_button.config(text="−" if self._expanded else "+")

    def pack(self, **kwargs):
        self.container.pack(**kwargs)

    def toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.body.pack(fill="both", expand=True, pady=(6, 0))
        else:
            self.body.pack_forget()
        self._refresh_button_label()

    def set_expanded(self, expanded: bool):
        if self._expanded != expanded:
            self.toggle()
