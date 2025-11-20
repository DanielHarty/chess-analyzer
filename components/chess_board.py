"""
Chess Board Component
A visual chess board component with JavaScript integration.
"""

from nicegui import ui
from pathlib import Path
import json


class ChessBoard:
    """A chess board component with canvas rendering and JavaScript integration."""

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

    def __init__(self):
        """Initialize the chess board component."""
        self.game_title_label = None
        self.board_html = None
        self.board_js_init = None

        # Load JavaScript and CSS
        self._load_assets()

    def _load_assets(self):
        """Load JavaScript and CSS assets."""
        root = Path(__file__).resolve().parent.parent
        js_path = root / 'chess_board.js'
        css_path = root / 'chess_board.css'

        if js_path.exists():
            self.board_js_init = js_path.read_text(encoding='utf-8')
        else:
            self.board_js_init = ""

        if css_path.exists():
            self.board_css_init = css_path.read_text(encoding='utf-8')
        else:
            self.board_css_init = ""

    def create_ui(self, parent_container=None):
        """Create the chess board UI elements.

        Args:
            parent_container: Optional parent container. If None, creates its own column.
        """
        container = parent_container or ui.column().classes('items-center bg-gray-800 rounded-lg p-4')

        with container:
            # Game title above board
            self.game_title_label = ui.label('No game loaded').classes('text-lg font-bold text-center text-white mb-2')

            # Chess board container
            with ui.element('div').classes('flex items-center justify-center'):
                self.board_html = ui.html(self.BOARD_HTML, sanitize=False).classes('block')

            # Initialize JavaScript
            if self.board_js_init:
                ui.run_javascript(self.board_js_init)

            # Add keyboard navigation
            self.setup_keyboard_navigation()

        return container

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

    def update_game_title(self, current_game=None):
        """Update the game title display.

        Args:
            current_game: The current chess game object
        """
        if self.game_title_label is None:
            return

        if current_game:
            white = current_game.headers.get('White', 'Unknown')
            black = current_game.headers.get('Black', 'Unknown')
            self.game_title_label.text = f"{white} vs {black}"
        else:
            self.game_title_label.text = "No game loaded"

    def send_position_to_js(self, position_dict):
        """Send the current board position to the browser.

        Args:
            position_dict: Dictionary representing the board position
        """
        position_json = json.dumps(position_dict)

        # Guard against chessAnim not being defined yet
        ui.run_javascript(
            f'if (window.chessAnim && window.chessAnim.setPosition) '
            f'{{ window.chessAnim.setPosition({position_json}); }}'
        )

    def animate_transition(self, start_pos, end_pos, result):
        """Send animation command with full state context.

        Args:
            start_pos: Starting position dictionary
            end_pos: Ending position dictionary
            result: Move result information
        """
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

    @property
    def css_init(self):
        """Get the CSS initialization code."""
        return self.board_css_init
