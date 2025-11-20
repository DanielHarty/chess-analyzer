"""
Game Controls Component
A component for navigation controls (first, previous, next, last move buttons).
"""

from nicegui import ui


class GameControls:
    """A component for game navigation controls."""

    def __init__(self, on_first=None, on_previous=None, on_next=None, on_last=None):
        """Initialize the game controls component.

        Args:
            on_first: Callback function called when first move button is clicked
            on_previous: Callback function called when previous move button is clicked
            on_next: Callback function called when next move button is clicked
            on_last: Callback function called when last move button is clicked
        """
        self.controls_container = None
        self.on_first = on_first or (lambda: None)
        self.on_previous = on_previous or (lambda: None)
        self.on_next = on_next or (lambda: None)
        self.on_last = on_last or (lambda: None)

    def create_ui(self, parent_container=None):
        """Create the game controls UI elements.

        Args:
            parent_container: Optional parent container. If None, creates its own column.
        """
        container = parent_container or ui.column().classes('w-full border-t border-gray-700 p-4 flex-shrink-0')
        self.controls_container = container

        with container:
            ui.label('Upload a PGN file to start analyzing').classes('text-gray-400 text-center')

        return container

    def update_controls(self, has_game: bool):
        """Update the controls visibility based on game state.

        Args:
            has_game: Whether a game is currently loaded
        """
        if self.controls_container is None:
            return

        # Clear existing controls
        self.controls_container.clear()

        if has_game:
            # Show navigation buttons
            with self.controls_container:
                with ui.row().classes('w-full justify-center gap-4'):
                    ui.button(
                        '◀◀',
                        on_click=self.on_first
                    ).classes('px-4 py-2 chess-nav-btn chess-first-btn')
                    ui.button(
                        '◀',
                        on_click=self.on_previous
                    ).classes('px-4 py-2 chess-nav-btn chess-prev-btn')
                    ui.button(
                        '▶',
                        on_click=self.on_next
                    ).classes('px-4 py-2 chess-nav-btn chess-next-btn')
                    ui.button(
                        '▶▶',
                        on_click=self.on_last
                    ).classes('px-4 py-2 chess-nav-btn chess-last-btn')
        else:
            # Show upload message
            with self.controls_container:
                ui.label('Upload a PGN file to start analyzing').classes('text-gray-400 text-center')

