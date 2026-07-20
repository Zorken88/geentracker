"""Panel de output del proceso trackeado."""

from __future__ import annotations

from textual.widgets import RichLog


class ProcessOutput(RichLog):
    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=False, markup=False, wrap=True, **kwargs)
        self.border_title = "Process Output"

    def add_lines(self, lines: list[str]) -> None:
        for line in lines:
            self.write(line)
