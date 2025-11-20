import asyncio
from nicegui import ui
from pgn_utils import extract_pgn_content
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class GameController:
    """
    Handles game flow, user input, and orchestration between the GameModel and the View.
    """

    def __init__(self, model, view):
        self.model = model
        self.view = view

    async def handle_upload(self, event):
        """Handle PGN file upload and parsing."""
        try:
            filename, content = await extract_pgn_content(event.file)
            self._load_game_and_refresh_ui(content)
        except Exception as e:
            print(f"✗ Upload error: {e}")
            ui.notify(f"Upload failed: {e}", type="negative")

    def load_sample_game(self):
        """Load the sample Kasparov vs Topalov game."""
        try:
            pgn_path = ROOT / 'kasparov_topalov_1999.pgn'
            if not pgn_path.exists():
                 # Fallback or error if file not found, though usually it should be there
                 ui.notify("Sample game file not found.", type="negative")
                 return

            with open(pgn_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self._load_game_and_refresh_ui(content)
        except Exception as e:
            print(f"✗ Sample game load error: {e}")
            ui.notify(f"Failed to load sample game: {e}", type="negative")

    def _load_game_and_refresh_ui(self, content):
        """Load PGN content into model and refresh all UI components."""
        self.model.load_pgn_text(content)

        # Update View
        self.view.update_game_title()
        self.view.display_moves()
        self.view.send_full_position_to_js()
        self.view.recompute_eval()
        self.view.update_eval_chart()

        # Start background evaluation
        self.start_evaluation_with_progress()

    def go_to_first_move(self):
        """Go to the starting position (total board reset)."""
        self.model.go_to_start()
        self.view.send_full_position_to_js()
        self.view.display_moves()
        self.view.recompute_eval()
        self.view.update_eval_chart()

    def go_to_previous_move(self):
        """Go to the previous move."""
        if self.model.current_game is None:
            return

        start_pos = self.model.get_position_dict()
        result = self.model.step_back()
        if result is None:
            return
        end_pos = self.model.get_position_dict()

        self.view.animate_transition(start_pos, end_pos, result)
        self.view.display_moves()
        self.view.recompute_eval()
        self.view.update_eval_chart()

    def go_to_next_move(self):
        """Go to the next move."""
        if self.model.current_game is None:
            return

        start_pos = self.model.get_position_dict()
        result = self.model.step_forward()
        if result is None:
            return
        end_pos = self.model.get_position_dict()

        self.view.animate_transition(start_pos, end_pos, result)
        self.view.display_moves()
        self.view.recompute_eval()
        self.view.update_eval_chart()

    def go_to_last_move(self):
        """Go to the last move."""
        self.model.go_to_end()
        self.view.send_full_position_to_js()
        self.view.display_moves()
        self.view.recompute_eval()
        self.view.update_eval_chart()

    def jump_to_ply(self, ply):
        """Jump to a specific ply by clicking on a move."""
        self.model.go_to_ply(ply)
        self.view.send_full_position_to_js()
        self.view.display_moves()
        self.view.recompute_eval()
        self.view.update_eval_chart()

    def start_evaluation_with_progress(self):
        """Start background evaluation and show progress."""
        self.view.header_bar.show_progress()
        
        def progress_callback(current: int, total: int):
            """Update progress indicator."""
            self.view.header_bar.update_progress(current, total)
            
            # Update eval bar for current position if we're viewing it
            if current - 1 == self.model.current_ply:
                self.view.recompute_eval()
            
            # Update the plotly chart every few evaluations for performance
            if current % 5 == 0 or current == total:
                self.view.update_eval_chart()
            
            # Hide progress when complete
            if current == total:
                self.view.header_bar.hide_progress()
                self.view.recompute_eval()  # Final update
                self.view.update_eval_chart()  # Final chart update
        
        self.model.start_background_evaluation(progress_callback)

