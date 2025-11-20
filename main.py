"""
Chess Game Analyzer
A NiceGUI application for uploading and analyzing chess games in PGN format.
"""

from nicegui import ui, app
import os
import json
import chess
from pathlib import Path
from game_model import GameModel
from global_engine import GlobalStockfishEngine, shutdown_global_engine
from components.eval_bar import EvalBar
from components.eval_chart import EvalChart
from components.chess_board import ChessBoard
from components.moves_list import MovesList
import platform
import asyncio

ROOT = Path(__file__).resolve().parent
if platform.system() == 'Windows':
    ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'windows' / 'stockfish-windows-x86-64-avx2.exe'
else:
    # Linux/macOS
    ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'linux' / 'stockfish-ubuntu-x86-64-avx2'

# Force ProactorEventLoop on Windows for subprocess support
if platform.system() == 'Windows':
    policy = asyncio.WindowsProactorEventLoopPolicy()
    asyncio.set_event_loop_policy(policy)

BOARD_CSS_INIT = (Path(__file__).parent / 'chess_board.css').read_text(encoding='utf-8')

class ChessAnalyzer:
    """Main GUI application class for chess game analysis.

    This class handles all user interface concerns including:
    - NiceGUI widget management and updates
    - JavaScript communication with the chess board
    - User interaction handling (clicks, uploads, navigation)

    Game logic is delegated to the GameModel class for better separation of concerns
    and testability.
    """

    def __init__(self):
        """Initialize the chess analyzer."""
        self.model = GameModel()
        self.controls_container = None
        self.upload_element = None  # Upload component for PGN files

        # UI Components
        self.chess_board = ChessBoard()
        self.eval_bar = EvalBar()
        self.eval_chart = EvalChart()
        self.moves_list = MovesList(on_jump_to_ply=self.jump_to_ply)

        # Loading indicator for evaluation progress
        self.eval_progress_label = None


    async def process_pgn_file(self, file_obj):
        """Extract and decode content from an uploaded file object."""
        filename = getattr(file_obj, 'name', 'unknown_file')

        # Try official NiceGUI APIs first
        if hasattr(file_obj, 'read'):
            # File-like object with read method (async in NiceGUI)
            content = (await file_obj.read()).decode('utf-8')
            return filename, content
        elif hasattr(file_obj, 'content'):
            # Direct content attribute (bytes)
            if isinstance(file_obj.content, bytes):
                content = file_obj.content.decode('utf-8')
            else:
                content = str(file_obj.content)
            return filename, content
        elif hasattr(file_obj, '_data'):
            # Fallback to private attribute (current implementation)
            content = file_obj._data.decode('utf-8')
            return filename, content
        else:
            raise ValueError("Unable to extract content from uploaded file")

    async def handle_upload(self, event):
        """Handle PGN file upload and parsing."""
        try:
            filename, content = await self.process_pgn_file(event.file)

            self.model.load_pgn_text(content)


            # Update game title
            self.update_game_title()

            # Update the UI with moves and board
            self.display_moves()
            self.send_full_position_to_js()
            self.recompute_eval()
            self.update_eval_chart()

            # Start background evaluation
            self.start_evaluation_with_progress()

        except Exception as e:
            print(f"✗ Upload error: {e}")
            ui.notify(f"Upload failed: {e}", type="negative")

    def display_moves(self):
        """Display the moves in the right panel."""
        move_rows = self.model.get_move_rows() if self.model.current_game else None
        self.moves_list.display_moves(move_rows, self.model.current_ply)
        self.update_controls()

    def update_controls(self):
        """Update the controls visibility based on game state."""
        if self.controls_container is None:
            return

        # Clear existing controls
        self.controls_container.clear()

        if self.model.current_game:
            # Show navigation buttons
            with self.controls_container:
                with ui.row().classes('w-full justify-center gap-4'):
                    ui.button('◀◀', on_click=self.go_to_first_move).classes('px-4 py-2 chess-nav-btn chess-first-btn')
                    ui.button('◀', on_click=self.go_to_previous_move).classes('px-4 py-2 chess-nav-btn chess-prev-btn')
                    ui.button('▶', on_click=self.go_to_next_move).classes('px-4 py-2 chess-nav-btn chess-next-btn')
                    ui.button('▶▶', on_click=self.go_to_last_move).classes('px-4 py-2 chess-nav-btn chess-last-btn')
        else:
            # Show upload message
            with self.controls_container:
                ui.label('Upload a PGN file to start analyzing').classes('text-gray-400 text-center')


    def go_to_first_move(self):
        """Go to the starting position (total board reset)."""
        self.model.go_to_start()
        self.send_full_position_to_js()
        self.display_moves()
        self.recompute_eval()
        self.update_eval_chart()

    def animate_transition(self, start_pos, end_pos, result):
        """Send animation command with full state context."""
        self.chess_board.animate_transition(start_pos, end_pos, result)

    def go_to_previous_move(self):
        """Go to the previous move."""
        if self.model.current_game is None:
            return

        start_pos = self.model.get_position_dict()
        result = self.model.step_back()
        if result is None:
            return
        end_pos = self.model.get_position_dict()

        self.animate_transition(start_pos, end_pos, result)

        self.display_moves()
        self.recompute_eval()
        self.update_eval_chart()

    def go_to_next_move(self):
        """Go to the next move."""
        if self.model.current_game is None:
            return

        start_pos = self.model.get_position_dict()
        result = self.model.step_forward()
        if result is None:
            return
        end_pos = self.model.get_position_dict()

        self.animate_transition(start_pos, end_pos, result)

        self.display_moves()
        self.recompute_eval()
        self.update_eval_chart()

    def go_to_last_move(self):
        """Go to the last move."""
        self.model.go_to_end()
        self.send_full_position_to_js()
        self.display_moves()
        self.recompute_eval()
        self.update_eval_chart()

    def jump_to_ply(self, ply):
        """Jump to a specific ply by clicking on a move."""
        self.model.go_to_ply(ply)
        self.send_full_position_to_js()
        self.display_moves()
        self.recompute_eval()
        self.update_eval_chart()

    def trigger_upload(self):
        """Trigger the file upload dialog."""
        if self.upload_element:
            self.upload_element.run_method('pickFiles')

    def update_game_title(self):
        """Update the game title display above the chess board."""
        self.chess_board.update_game_title(self.model.current_game)

    def load_sample_game(self):
        """Load the sample Kasparov vs Topalov game."""
        try:
            with open(ROOT / 'kasparov_topalov_1999.pgn', 'r', encoding='utf-8') as f:
                content = f.read()

            self.model.load_pgn_text(content)


            # Update game title
            self.update_game_title()

            # Update the UI with moves and board
            self.display_moves()
            self.send_full_position_to_js()
            self.recompute_eval()
            self.update_eval_chart()

            # Start background evaluation
            self.start_evaluation_with_progress()

        except Exception as e:
            print(f"✗ Sample game load error: {e}")
            ui.notify(f"Failed to load sample game: {e}", type="negative")


    def create_ui(self):
        """Create and setup the user interface."""
        # Add modern scrollbar styling
        ui.add_css(BOARD_CSS_INIT)

        with ui.column().classes('fixed inset-0 w-screen h-screen bg-gray-900 text-white overflow-hidden'):
            # Header
            with ui.row().classes('w-full px-4 py-3 border-b border-gray-700 items-center gap-4 flex-shrink-0'):
                ui.label('Chess Analyzer v0.1').classes('text-2xl font-bold')

                # Hidden upload component
                self.upload_element = ui.upload(on_upload=self.handle_upload, label="", auto_upload=True).props('accept=.pgn').classes('hidden')

                # Sample game button
                ui.button('Load Sample', icon='play_arrow', on_click=self.load_sample_game).classes('')

                # Visible upload button
                ui.button('Upload PGN', icon='add', on_click=self.trigger_upload).classes('ml-auto')
                
                # Progress indicator
                self.eval_progress_label = ui.label('Analyzing positions: 0%').classes('text-sm text-gray-400 ml-4')
                self.eval_progress_label.visible = False

            # Main content area
            with ui.row().classes('gap-4 px-4 py-2 items-start flex-1 overflow-hidden'):
                # Left side: Eval bar
                self.eval_bar.create_ui()

                # Center: Chess board
                self.chess_board.create_ui()

                # Right side: Eval chart and moves panel
                with ui.column().classes('w-96 bg-gray-800 rounded-lg overflow-hidden flex flex-col h-full'):
                    # Evaluation chart at top
                    self.eval_chart.create_ui()
                    
                    # Moves header
                    ui.label('Moves').classes('text-lg font-bold p-4 border-b border-gray-700 flex-shrink-0')

                    # Moves list
                    self.moves_list.create_ui()

                    # Game controls at bottom
                    self.controls_container = ui.column().classes('w-full border-t border-gray-700 p-4 flex-shrink-0')
                    with self.controls_container:
                        ui.label('Upload a PGN file to start analyzing').classes('text-gray-400 text-center')

    def send_full_position_to_js(self):
        """Send the current board position to the browser (no animation)."""
        if self.model.board is None:
            return

        pos_dict = self.model.get_position_dict()
        self.chess_board.send_position_to_js(pos_dict)

    # ---------- Plotly evaluation chart ----------

    def update_eval_chart(self):
        """Update the plotly evaluation chart."""
        self.eval_chart.update_eval_chart(
            current_game=self.model.current_game,
            evaluations=self.model.evaluations,
            current_ply=self.model.current_ply
        )

    # ---------- Stockfish evaluation + bar update ----------

    def start_evaluation_with_progress(self):
        """Start background evaluation and show progress."""
        if self.eval_progress_label:
            self.eval_progress_label.visible = True
            self.eval_progress_label.text = "Analyzing positions: 0%"
        
        def progress_callback(current: int, total: int):
            """Update progress indicator."""
            percent = int((current / total) * 100)
            if self.eval_progress_label:
                self.eval_progress_label.text = f"Analyzing positions: {percent}%"
            
            # if current == 1:
                # print("DEBUG: First evaluation complete")
                # ui.notify("First evaluation complete")
            
            # Debug logging
            # print(f"Eval {current}/{total}: {self.model.evaluations[current-1]}")
            
            # Update eval bar for current position if we're viewing it
            if current - 1 == self.model.current_ply:
                self.recompute_eval()
            
            # Update the plotly chart every few evaluations for performance
            if current % 5 == 0 or current == total:
                self.update_eval_chart()
            
            # Hide progress when complete
            if current == total and self.eval_progress_label:
                self.eval_progress_label.visible = False
                self.recompute_eval()  # Final update
                self.update_eval_chart()  # Final chart update
        
        self.model.start_background_evaluation(progress_callback)

    def recompute_eval(self):
        """Update the eval bar using precalculated evaluations."""
        if self.model.board is None:
            self.eval_bar.update_eval_bar(None)
            return

        cp = self.model.get_current_evaluation()
        self.eval_bar.update_eval_bar(cp)


@ui.page('/')
def home():
    """Create the main application page."""
    # Initialize the global Stockfish engine
    GlobalStockfishEngine(str(ENGINE_PATH))

    analyzer = ChessAnalyzer()
    analyzer.create_ui()
    # app.on_shutdown(shutdown_global_engine)

if __name__ in {"__main__", "__mp_main__"}:
    app.on_shutdown(shutdown_global_engine)
    port = int(os.environ.get('PORT', 8080))
    ui.run(host="0.0.0.0", port=port, reload=False)
