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
from game_controller import GameController
from components.eval_bar import EvalBar
from components.eval_chart import EvalChart
from components.chess_board import ChessBoard
from components.moves_list import MovesList
from components.header_bar import HeaderBar
from components.game_controls import GameControls
from components.chesscom_dialog import ChesscomDialog
import platform
import asyncio

ROOT = Path(__file__).resolve().parent
if platform.system() == 'Windows':
    ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'windows' / 'stockfish-windows-x86-64-avx2.exe'
else:
    # Linux/macOS
    ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'linux' / 'stockfish-ubuntu-x86-64-avx2'

# Use ProactorEventLoop on Windows - required for subprocess support
# SimpleEngine.popen_uci() works with ProactorEventLoop when run in executor
if platform.system() == 'Windows':
    try:
        policy = asyncio.WindowsProactorEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)
    except AttributeError:
        # WindowsProactorEventLoopPolicy not available on older Python versions
        # Fall back to default policy
        pass

BOARD_CSS_INIT = (Path(__file__).parent / 'chess_board.css').read_text(encoding='utf-8')

class ChessAnalyzerUI:
    """Main GUI application class for chess game analysis.

    This class handles all user interface concerns including:
    - NiceGUI widget management and updates
    - JavaScript communication with the chess board
    - User interaction handling (clicks, uploads, navigation)

    Game logic is delegated to the GameModel class.
    Flow control is delegated to the GameController class.
    """

    def __init__(self):
        """Initialize the chess analyzer."""
        self.model = GameModel()
        self.controller = GameController(self.model, self)

        # UI Components
        self.chesscom_dialog = ChesscomDialog(
            on_game_selected=self.controller.load_chesscom_game
        )
        self.header_bar = HeaderBar(
            on_upload=self.controller.handle_upload,
            on_load_sample=self.controller.load_sample_game,
            on_load_chesscom=self.show_chesscom_dialog
        )
        self.chess_board = ChessBoard()
        # Set up the callback for piece selection
        self.chess_board.set_on_piece_selected(self.handle_piece_selected)
        # Set up the callback for piece moves
        self.chess_board.set_on_move(self.controller.handle_move)
        # Initialize current turn (white starts by default)
        self.chess_board.update_current_turn(True)
        
        self.eval_bar = EvalBar()
        self.eval_chart = EvalChart()
        self.moves_list = MovesList(
            on_jump_to_ply=self.controller.jump_to_ply,
            on_tab_change=self.controller.switch_variation
        )
        self.game_controls = GameControls(
            on_first=self.controller.go_to_first_move,
            on_previous=self.controller.go_to_previous_move,
            on_next=self.controller.go_to_next_move,
            on_last=self.controller.go_to_last_move
        )

    def handle_piece_selected(self, square):
        """Handle piece selection on the board."""
        model = self.controller.model
        if model.board:
            # Update legal moves using the current board state
            self.chess_board.update_legal_moves_from_board(model.board)

    def display_moves(self):
        """Display the moves in the right panel."""
        model = self.controller.model
        move_rows = model.get_move_rows() if model.current_game else None
        self.moves_list.display_moves(move_rows, model.current_ply)
        self.game_controls.update_controls(model.current_game is not None)

    def animate_transition(self, start_pos, end_pos, result):
        """Send animation command with full state context."""
        model = self.controller.model
        self.chess_board.animate_transition(start_pos, end_pos, result)
        # Update current turn after move
        self.chess_board.update_current_turn(model.board.turn)
        # Clear selection and don't show legal moves for navigation moves
        self.chess_board.clear_selection()

    def trigger_upload(self):
        """Trigger the file upload dialog."""
        self.header_bar.trigger_upload()

    def show_chesscom_dialog(self):
        """Show the chess.com game loader dialog."""
        self.chesscom_dialog.show()

    def update_game_title(self):
        """Update the game title display above the chess board."""
        model = self.controller.model
        self.chess_board.update_game_title(model.current_game)

    def create_ui(self):
        """Create and setup the user interface."""
        # Add modern scrollbar styling
        ui.add_css(BOARD_CSS_INIT)

        with ui.column().classes('fixed inset-0 w-screen h-screen bg-gray-900 text-white overflow-hidden'):
            # Header
            self.header_bar.create_ui()

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
                    self.game_controls.create_ui()

    def send_full_position_to_js(self):
        """Send the current board position to the browser (no animation)."""
        # Get the current model from the controller
        model = self.controller.model
        if model.board is None:
            return

        pos_dict = model.get_position_dict()
        self.chess_board.send_position_to_js(pos_dict)
        # Update current turn
        self.chess_board.update_current_turn(model.board.turn)

    # ---------- Plotly evaluation chart ----------

    def update_eval_chart(self):
        """Update the plotly evaluation chart."""
        model = self.controller.model
        blunders = model.get_blunders()
        self.eval_chart.update_eval_chart(
            current_game=model.current_game,
            evaluations=model.evaluations,
            current_ply=model.current_ply,
            blunders=blunders
        )

    # ---------- Stockfish evaluation + bar update ----------

    def recompute_eval(self):
        """Update the eval bar using precalculated evaluations."""
        model = self.controller.model
        if model.board is None:
            self.eval_bar.update_eval_bar(None)
            return

        cp = model.get_current_evaluation()
        self.eval_bar.update_eval_bar(cp)


@ui.page('/')
def home():
    """Create the main application page."""
    # Initialize the global Stockfish engine
    GlobalStockfishEngine(str(ENGINE_PATH))

    analyzer = ChessAnalyzerUI()
    analyzer.create_ui()
    # app.on_shutdown(shutdown_global_engine)

if __name__ in {"__main__", "__mp_main__"}:
    async def shutdown_handler():
        """Handle application shutdown gracefully."""
        try:
            await shutdown_global_engine()
        except asyncio.CancelledError:
            # Ignore cancellation errors during shutdown
            pass
        except Exception as e:
            print(f"Error during shutdown: {e}")
    
    app.on_shutdown(shutdown_handler)
    port = int(os.environ.get('PORT', 8080))
    ui.run(host="0.0.0.0", port=port, reload=True)
    print("Application shutdown complete!")
