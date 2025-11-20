"""
Evaluation Bar Component
A visual component for displaying chess position evaluation scores.
"""

from nicegui import ui


class EvalBar:
    """A vertical evaluation bar component for chess position analysis."""

    def __init__(self):
        """Initialize the evaluation bar component."""
        self.eval_bar_fill = None
        self.eval_label = None

    def create_ui(self, parent_container=None):
        """Create the evaluation bar UI elements.

        Args:
            parent_container: Optional parent container. If None, creates its own column.
        """
        container = parent_container or ui.column().classes('items-center justify-center w-16 flex-shrink-0')

        with container:
            ui.label('Eval').classes('text-xs text-gray-400 mb-1')

            with ui.element('div').classes('eval-bar-container'):
                self.eval_bar_fill = ui.element('div').classes('eval-bar-fill')

            self.eval_label = ui.label('0.00').classes('eval-bar-label text-center w-full')

        return container

    def update_eval_bar(self, cp: int | None):
        """Update the eval bar and numeric label from a centipawn score.

        Args:
            cp: Centipawn evaluation score, or None if unknown
        """
        if self.eval_bar_fill is None or self.eval_label is None:
            return

        if cp is None:
            # Unknown / engine failed
            self.eval_bar_fill.style(
                'height: 50%; bottom: 0; top: auto; background-color: #9CA3AF;'
            )
            self.eval_label.text = '--'
            return

        # Clamp crazy evals so the bar doesn't just slam to the top all the time
        clamp = 800  # 8 pawns, roughly
        cp_clamped = max(-clamp, min(clamp, cp))

        # New mapping: 50% at equal, 100% at ±clamp
        m = min(1.0, abs(cp_clamped) / clamp)      # 0..1
        percent = 50 + m * 50                      # 50..100

        # Always fill from bottom up in white
        # White advantage: larger white bar from bottom
        # Black advantage: smaller white bar from bottom
        if cp_clamped >= 0:
            height_percent = percent
        else:
            height_percent = 100 - percent

        style = (
            f'height: {height_percent}%; '
            f'bottom: 0; top: auto; '
            f'background-color: #F9FAFB;'
        )

        self.eval_bar_fill.style(style)

        # Show eval as something like "+0.34" (white perspective)
        self.eval_label.text = f'{cp / 100:.2f}'
