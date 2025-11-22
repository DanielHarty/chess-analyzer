"""
Header Bar Component
A component for the application header with title, upload, and progress indicators.
"""

from nicegui import ui


class HeaderBar:
    """A header bar component for the chess analyzer application."""

    def __init__(self, on_upload=None, on_load_sample=None, on_load_chesscom=None):
        """Initialize the header bar component.

        Args:
            on_upload: Callback function called when a file is uploaded (takes event as argument)
            on_load_sample: Callback function called when the load sample button is clicked
            on_load_chesscom: Callback function called when the chess.com button is clicked
        """
        self.upload_element = None
        self.eval_progress_label = None
        self.on_upload = on_upload or (lambda e: None)
        self.on_load_sample = on_load_sample or (lambda: None)
        self.on_load_chesscom = on_load_chesscom or (lambda: None)

    def create_ui(self, parent_container=None):
        """Create the header bar UI elements.

        Args:
            parent_container: Optional parent container. If None, creates its own row.
        """
        container = parent_container or ui.row().classes('w-full px-4 py-3 border-b border-gray-700 items-center gap-4 flex-shrink-0')

        with container:
            ui.label('Chess Analyzer v0.1').classes('text-2xl font-bold')

            # Hidden upload component
            self.upload_element = ui.upload(
                on_upload=self.on_upload,
                label="",
                auto_upload=True
            ).props('accept=.pgn').classes('hidden')

            # Sample game button
            ui.button(
                'Load Sample',
                icon='play_arrow',
                on_click=self.on_load_sample
            ).classes('')

            # Chess.com button
            ui.button(
                'Chess.com',
                icon='language',
                on_click=self.on_load_chesscom
            ).classes('')

            # Visible upload button
            ui.button(
                'Upload PGN',
                icon='add',
                on_click=self.trigger_upload
            ).classes('ml-auto')

            # Progress indicator
            self.eval_progress_label = ui.label('Analyzing positions: 0%').classes('text-sm text-gray-400 ml-4')
            self.eval_progress_label.visible = False

        return container

    def trigger_upload(self):
        """Trigger the file upload dialog."""
        if self.upload_element:
            self.upload_element.run_method('pickFiles')

    def update_progress(self, current: int, total: int):
        """Update the progress indicator.

        Args:
            current: Current progress count
            total: Total count
        """
        if self.eval_progress_label is None:
            return

        percent = int((current / total) * 100)
        self.eval_progress_label.text = f"Analyzing positions: {percent}%"

    def show_progress(self):
        """Show the progress indicator."""
        if self.eval_progress_label:
            self.eval_progress_label.visible = True
            self.eval_progress_label.text = "Analyzing positions: 0%"

    def hide_progress(self):
        """Hide the progress indicator."""
        if self.eval_progress_label:
            self.eval_progress_label.visible = False

