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
import platform

ROOT = Path(__file__).resolve().parent
if platform.system() == 'Windows':
    ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'windows' / 'stockfish-windows-x86-64-avx2.exe'
else:
    # Linux/macOS
    ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'linux' / 'stockfish-ubuntu-x86-64-avx2'

# Canvas-based board: JS helper with setPosition({ square: "P", ... })
BOARD_HTML = """
<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center;">
  <div id="chess_board_root"
       style="
         position:relative;
         width: min(70vh, 70vw);
         height: min(70vh, 70vw);
       ">
    <canvas id="chess_board_canvas" style="width:100%; height:100%;"></canvas>
  </div>
</div>
"""

BOARD_JS_INIT = (Path(__file__).parent / 'chess_board.js').read_text(encoding='utf-8')
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
        self.moves_container = None
        self.controls_container = None
        self.game_title_label = None  # Label to display game title above board
        self.move_row_elements = {}  # Store references to move row elements for scrolling
        self.upload_element = None  # Upload component for PGN files

        # Stockfish + eval bar UI references (using global engine)
        self.eval_bar_fill = None
        self.eval_label = None

    def make_jump_handler(self, ply):
        """Create a click handler that jumps to the specified ply."""
        return lambda e: self.jump_to_ply(ply)

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
            self.move_row_elements.clear()  # Clear move row references

            # Update game title
            self.update_game_title()

            # Update the UI with moves and board
            self.display_moves()
            self.send_full_position_to_js()
            self.recompute_eval()  # NEW

        except Exception as e:
            print(f"✗ Upload error: {e}")
            ui.notify(f"Upload failed: {e}", type="negative")

    def display_moves(self):
        """Display the moves in the right panel."""
        if self.moves_container is None:
            return

        self.moves_container.clear()
        self.move_row_elements.clear()

        if self.model.current_game is None:
            with self.moves_container:
                ui.label('No game loaded').classes('text-gray-400 text-center py-8')
            self.update_controls()
            return

        rows = self.model.get_move_rows()
        current_ply = self.model.current_ply

        with self.moves_container:
            for row_index, (move_number, white_move, black_move) in enumerate(rows):
                white_ply = row_index * 2
                black_ply = white_ply + 1

                move_row = ui.row().classes('w-full justify-between py-1')
                self.move_row_elements[move_number] = move_row

                with move_row:
                    ui.label(f"{move_number}.").classes('text-gray-300 w-8')

                    # white
                    is_active_white = (white_ply + 1 == current_ply)
                    white_classes = 'text-white flex-1 text-center cursor-pointer px-2 py-1 rounded'
                    white_classes += ' bg-blue-700' if is_active_white else ' hover:bg-gray-700'
                    ui.label(white_move).classes(white_classes).on(
                        'click', self.make_jump_handler(white_ply + 1)
                    )

                    # black
                    is_active_black = (black_ply + 1 == current_ply)
                    black_classes = 'text-white flex-1 text-center cursor-pointer px-2 py-1 rounded'
                    black_classes += ' bg-blue-700' if is_active_black else ' hover:bg-gray-700'
                    black_label = ui.label(black_move).classes(black_classes)
                    if black_move:
                        black_label.on('click', self.make_jump_handler(black_ply + 1))

        # Auto-scroll to current move if we're not at the starting position
        if self.model.current_ply > 0:
            # Calculate which row contains the current move
            # Each row has 2 moves (white and black), so row number = ((ply - 1) // 2) + 1
            current_row_number = ((self.model.current_ply - 1) // 2) + 1
            if current_row_number in self.move_row_elements:
                # Use run_method to scroll the row into view
                self.move_row_elements[current_row_number].run_method('scrollIntoView', {'behavior': 'smooth', 'block': 'start'})

        # Update controls visibility
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
        self.recompute_eval()  # NEW

    def animate_transition(self, start_pos, end_pos, result):
        """Send animation command with full state context."""
        move_type = 'simple'
        details = {}

        if result.get("is_castling"):
            move_type = 'castling'
            # Determine castling details from the move
            king_from = result["from"]
            king_to = result["to"]
            piece = result["piece"]
            is_white = piece.symbol().isupper()
            
            if is_white:
                king_symbol = 'K'
                rook_symbol = 'R'
                if king_to == 'g1': # Kingside
                    rook_from, rook_to = 'h1', 'f1'
                else: # Queenside
                    rook_from, rook_to = 'a1', 'd1'
            else:
                king_symbol = 'k'
                rook_symbol = 'r'
                if king_to == 'g8': # Kingside
                    rook_from, rook_to = 'h8', 'f8'
                else: # Queenside
                    rook_from, rook_to = 'a8', 'd8'
            
            details = {
                'kingFrom': king_from, 'kingTo': king_to,
                'rookFrom': rook_from, 'rookTo': rook_to,
                'kingSymbol': king_symbol, 'rookSymbol': rook_symbol
            }

        elif result.get("is_en_passant") and result["piece"]:
            # En passant: pawn moves diagonally, captures adjacent pawn
            move_type = 'en_passant'

            # Calculate captured square: same rank as from, same file as to
            from_square = result["from"]  # e.g., "f5"
            to_square = result["to"]      # e.g., "e6"

            # Convert to coordinates
            from_file = ord(from_square[0]) - ord('a')
            from_rank = int(from_square[1]) - 1
            to_file = ord(to_square[0]) - ord('a')

            # Captured pawn is at (to_file, from_rank)
            captured_file = chr(ord('a') + to_file)
            captured_rank = str(from_rank + 1)
            captured_square = captured_file + captured_rank

            details = {
                'pawnFrom': from_square,
                'pawnTo': to_square,
                'pawnSymbol': result["piece"].symbol(),
                'capturedSquare': captured_square
            }
        elif result["piece"]:
            # Simple move (including promotions)
            details = {
                'from': result["from"],
                'to': result["to"],
                'symbol': result["piece"].symbol()
            }

        js_args = json.dumps({
            'startPos': start_pos,
            'endPos': end_pos,
            'type': move_type,
            'details': details
        })
        
        ui.run_javascript(f'if(window.chessAnim && window.chessAnim.animateMoveWithState) window.chessAnim.animateMoveWithState({js_args});')

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
        self.recompute_eval()  # NEW

    def go_to_last_move(self):
        """Go to the last move."""
        self.model.go_to_end()
        self.send_full_position_to_js()
        self.display_moves()
        self.recompute_eval()  # NEW

    def jump_to_ply(self, ply):
        """Jump to a specific ply by clicking on a move."""
        self.model.go_to_ply(ply)
        self.send_full_position_to_js()
        self.display_moves()
        self.recompute_eval()  # NEW

    def trigger_upload(self):
        """Trigger the file upload dialog."""
        if self.upload_element:
            self.upload_element.run_method('pickFiles')

    def update_game_title(self):
        """Update the game title display above the chess board."""
        if self.game_title_label is None:
            return

        if self.model.current_game:
            white = self.model.current_game.headers.get('White', 'Unknown')
            black = self.model.current_game.headers.get('Black', 'Unknown')
            self.game_title_label.text = f"{white} vs {black}"
        else:
            self.game_title_label.text = "No game loaded"

    def load_sample_game(self):
        """Load the sample Kasparov vs Topalov game."""
        try:
            with open('kasparov_topalov_1999.pgn', 'r', encoding='utf-8') as f:
                content = f.read()

            self.model.load_pgn_text(content)
            self.move_row_elements.clear()  # Clear move row references

            # Update game title
            self.update_game_title()

            # Update the UI with moves and board
            self.display_moves()
            self.send_full_position_to_js()
            self.recompute_eval()  # NEW

        except Exception as e:
            print(f"✗ Sample game load error: {e}")
            ui.notify(f"Failed to load sample game: {e}", type="negative")

    def load_en_passant_test(self):
        """Load a test game that includes en passant moves."""
        try:
            # Create a simple PGN with en passant
            test_pgn = """[Event "En Passant Test"]
[Site "Test"]
[Date "2024.01.01"]
[White "Test"]
[Black "Test"]
[Result "*"]

1. e4 d5 2. exd5 e5 3. dxe6
"""

            self.model.load_pgn_text(test_pgn)
            self.move_row_elements.clear()  # Clear move row references

            # Update game title
            self.update_game_title()

            # Update the UI with moves and board
            self.display_moves()
            self.send_full_position_to_js()
            self.recompute_eval()  # NEW

        except Exception as e:
            print(f"✗ En passant test load error: {e}")
            ui.notify(f"Failed to load en passant test: {e}", type="negative")

    def load_promotion_test(self):
        """Load a test game that includes pawn promotion moves."""
        try:
            # Create a simple PGN with pawn promotion
            test_pgn = """[Event "Promotion Test"]
[Site "Test"]
[Date "2024.01.01"]
[White "Test"]
[Black "Test"]
[Result "*"]

1. e4 d5 2. exd5 e6 3. dxe6 fxe6 4. e7 f5 5. e8=Q
"""

            self.model.load_pgn_text(test_pgn)
            self.move_row_elements.clear()  # Clear move row references

            # Update game title
            self.update_game_title()

            # Update the UI with moves and board
            self.display_moves()
            self.send_full_position_to_js()
            self.recompute_eval()  # NEW

        except Exception as e:
            print(f"✗ Promotion test load error: {e}")
            ui.notify(f"Failed to load promotion test: {e}", type="negative")

    def setup_keyboard_navigation(self):
        """Set up keyboard event listeners for arrow key navigation."""
        js_code = """
        document.addEventListener('keydown', function(event) {
            // Only handle arrow keys if no input/textarea is focused
            if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
                return;
            }

            if (event.key === 'ArrowLeft') {
                event.preventDefault();
                // Find and click the previous button
                const prevBtn = document.querySelector('.chess-prev-btn');
                if (prevBtn) prevBtn.click();
            } else if (event.key === 'ArrowRight') {
                event.preventDefault();
                // Find and click the next button
                const nextBtn = document.querySelector('.chess-next-btn');
                if (nextBtn) nextBtn.click();
            }
        });
        """
        ui.run_javascript(js_code)

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

                # Test en passant button
                ui.button('Test En Passant', icon='science', on_click=self.load_en_passant_test).classes('')

                # Test promotion button
                ui.button('Test Promotion', icon='upgrade', on_click=self.load_promotion_test).classes('')

                # Visible upload button
                ui.button('Upload PGN', icon='add', on_click=self.trigger_upload).classes('ml-auto')

            # Main content area
            with ui.row().classes('gap-4 px-4 py-2 items-start flex-1 overflow-hidden'):
                # Left side: Eval bar
                with ui.column().classes('items-center justify-center w-16 flex-shrink-0'):
                    ui.label('Eval').classes('text-xs text-gray-400 mb-1')

                    with ui.element('div').classes('eval-bar-container'):
                        self.eval_bar_fill = ui.element('div').classes('eval-bar-fill')

                    self.eval_label = ui.label('0.00').classes('eval-bar-label text-center w-full')

                # Center: Chess board
                with ui.column().classes('items-center bg-gray-800 rounded-lg p-4'):
                    # Game title above board
                    self.game_title_label = ui.label('No game loaded').classes('text-lg font-bold text-center text-white mb-2')

                    # simple container – no flex-1 / h-full
                    with ui.element('div').classes('flex items-center justify-center'):
                        self.board_html = ui.html(BOARD_HTML, sanitize=False).classes('block')

                    ui.run_javascript(BOARD_JS_INIT)

                    # Add keyboard navigation
                    self.setup_keyboard_navigation()

                # Right side: Moves panel
                with ui.column().classes('w-72 bg-gray-800 rounded-lg overflow-hidden flex flex-col h-full'):
                    # Header
                    ui.label('Moves').classes('text-lg font-bold p-4 border-b border-gray-700 flex-shrink-0')

                    # Moves list
                    self.moves_container = ui.column().classes('flex-1 w-full overflow-y-auto pl-4 pr-0 py-2 gap-2 modern-scrollbar min-h-0')
                    with self.moves_container:
                        ui.label('No game loaded').classes('text-gray-400 text-center py-8')

                    # Game controls at bottom
                    self.controls_container = ui.column().classes('w-full border-t border-gray-700 p-4 flex-shrink-0')
                    with self.controls_container:
                        ui.label('Upload a PGN file to start analyzing').classes('text-gray-400 text-center')

    def send_full_position_to_js(self):
        """Send the current board position to the browser (no animation)."""
        if self.model.board is None:
            return

        pos_dict = self.model.get_position_dict()
        position_json = json.dumps(pos_dict)

        # Guard against chessAnim not being defined yet
        ui.run_javascript(
            f'if (window.chessAnim && window.chessAnim.setPosition) '
            f'{{ window.chessAnim.setPosition({position_json}); }}'
        )

    # ---------- Stockfish evaluation + bar update ----------

    def recompute_eval(self):
        """Re-run Stockfish on the current position and update the bar."""
        if self.model.board is None:
            self.update_eval_bar(None)
            return

        from global_engine import evaluate_position
        cp = evaluate_position(self.model.board)
        self.update_eval_bar(cp)

    def update_eval_bar(self, cp: int | None):
        """Update the eval bar and numeric label from a centipawn score."""
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


@ui.page('/')
def home():
    """Create the main application page."""
    # Initialize the global Stockfish engine
    GlobalStockfishEngine(str(ENGINE_PATH))

    analyzer = ChessAnalyzer()
    analyzer.create_ui()
    app.on_shutdown(shutdown_global_engine)

if __name__ in {"__main__", "__mp_main__"}:
    port = int(os.environ.get('PORT', 8080))
    ui.run(host="0.0.0.0", port=port)