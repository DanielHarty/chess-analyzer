"""
Chess Game Analyzer
A NiceGUI application for uploading and analyzing chess games in PGN format.
"""

import io
from nicegui import ui
import chess
import chess.pgn
import os
import json
from pathlib import Path

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
    """Main application class for chess game analysis.

    Future architecture note: Consider splitting into separate classes:
    - GameModel: Handle game state, moves, SAN conversion, and board logic
    - ChessAnalyzer: Focus on UI interaction and display logic
    This would enable better testing and modularity for features like engine evaluation.
    """



    def __init__(self):
        """Initialize the chess analyzer."""
        self.current_game = None
        self.moves_container = None
        self.controls_container = None
        self.current_ply = 0
        self.board = None  # chess.Board object for current position
        self.moves = []  # Cache mainline moves to avoid recomputation
        self.san_moves = []  # Cache SAN notation for moves
        self.last_move_squares = set()  # Track squares for last move highlighting
        self.game_title_label = None  # Label to display game title above board
        self.move_row_elements = {}  # Store references to move row elements for scrolling
        self.upload_element = None  # Upload component for PGN files

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

    def parse_pgn_game(self, pgn_content):
        """Parse PGN content into a chess game object."""
        pgn_stream = io.StringIO(pgn_content)
        game = chess.pgn.read_game(pgn_stream)
        return game

    def get_san_moves(self):
        """Generate SAN notation moves from cached moves."""
        if not self.current_game or not self.moves:
            return []

        # Use cached SAN moves if available
        if self.san_moves:
            return self.san_moves

        # Generate SAN moves from temporary board
        board = self.current_game.board()
        san_moves = []
        for move in self.moves:
            san = board.san(move)
            san_moves.append(san)
            board.push(move)

        self.san_moves = san_moves  # Cache result
        return san_moves


    async def handle_upload(self, event):
        """Handle PGN file upload and parsing."""
        try:
            # Extract file content
            filename, content = await self.process_pgn_file(event.file)

            # Parse the chess game
            self.current_game = self.parse_pgn_game(content)
            self.current_ply = 0  # Reset to starting position
            self.board = self.current_game.board()  # Initialize board at starting position
            self.moves = list(self.current_game.mainline_moves())  # Cache moves to avoid recomputation
            self.san_moves = []  # Clear SAN cache for new game
            self.last_move_squares = set()  # Clear last move highlighting
            self.move_row_elements.clear()  # Clear move row references

            # Update game title
            self.update_game_title()

            # Update the UI with moves and board
            self.display_moves()
            self.send_full_position_to_js()

        except Exception as e:
            print(f"✗ Upload error: {e}")
            ui.notify(f"Upload failed: {e}", type="negative")

    def display_moves(self):
        """Display the moves in the right panel."""
        if self.moves_container is None:
            return

        # Clear existing content
        self.moves_container.clear()
        self.move_row_elements.clear()  # Clear stored row references

        if self.current_game is None:
            with self.moves_container:
                ui.label('No game loaded').classes('text-gray-400 text-center py-8')
            return

        # Get SAN moves
        san_moves = self.get_san_moves()

        with self.moves_container:
            for i in range(0, len(san_moves), 2):
                move_number = (i // 2) + 1
                white_move = san_moves[i]
                black_move = san_moves[i + 1] if i + 1 < len(san_moves) else ''
                white_ply = i
                black_ply = i + 1

                # Create move row and store reference for scrolling
                move_row = ui.row().classes('w-full justify-between py-1')
                self.move_row_elements[move_number] = move_row

                with move_row:
                    ui.label(f"{move_number}.").classes('text-gray-300 w-8')

                    # White move highlighting
                    is_active_white = (white_ply + 1 == self.current_ply)
                    white_classes = 'text-white flex-1 text-center cursor-pointer px-2 py-1 rounded'
                    if is_active_white:
                        white_classes += ' bg-blue-700'
                    else:
                        white_classes += ' hover:bg-gray-700'
                    ui.label(white_move).classes(white_classes).on('click', self.make_jump_handler(white_ply + 1))

                    # Black move highlighting
                    is_active_black = (black_ply + 1 == self.current_ply)
                    black_classes = 'text-white flex-1 text-center cursor-pointer px-2 py-1 rounded'
                    if is_active_black:
                        black_classes += ' bg-blue-700'
                    else:
                        black_classes += ' hover:bg-gray-700'
                    black_label = ui.label(black_move).classes(black_classes)
                    if black_ply < len(san_moves):
                        black_label.on('click', self.make_jump_handler(black_ply + 1))

        # Auto-scroll to current move if we're not at the starting position
        if self.current_ply > 0:
            # Calculate which row contains the current move
            # Each row has 2 moves (white and black), so row number = ((ply - 1) // 2) + 1
            current_row_number = ((self.current_ply - 1) // 2) + 1
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

        if self.current_game:
            # Show navigation buttons
            with self.controls_container:
                with ui.row().classes('w-full justify-center gap-4'):
                    ui.button('◀◀', on_click=self.go_to_first_move).classes('px-4 py-2')
                    ui.button('◀', on_click=self.go_to_previous_move).classes('px-4 py-2')
                    ui.button('▶', on_click=self.go_to_next_move).classes('px-4 py-2')
                    ui.button('▶▶', on_click=self.go_to_last_move).classes('px-4 py-2')
        else:
            # Show upload message
            with self.controls_container:
                ui.label('Upload a PGN file to start analyzing').classes('text-gray-400 text-center')

    def update_board_to_ply(self, ply):
        """Update the board to a specific ply.

        Args:
            ply: The ply index to display (0 = starting position)
        """
        if not self.current_game:
            return

        # Reset board to starting position
        self.board = self.current_game.board()

        # Apply moves up to the current ply
        limit = min(ply, len(self.moves))
        for i in range(limit):
            self.board.push(self.moves[i])

        # Set last move highlighting
        if ply > 0 and ply <= len(self.moves):
            last_move = self.moves[ply - 1]
            self.last_move_squares = {
                chess.square_name(last_move.from_square),
                chess.square_name(last_move.to_square),
            }
        else:
            self.last_move_squares = set()
    

    def go_to_first_move(self):
        """Go to the starting position (total board reset)."""
        self.current_ply = 0
        self.update_board_to_ply(self.current_ply)
        self.send_full_position_to_js()
        self.display_moves()

    def go_to_previous_move(self):
        """Go to the previous move."""
        if self.current_ply > 0:
            self.current_ply -= 1
            self.update_board_to_ply(self.current_ply)
            self.send_full_position_to_js()
            self.display_moves()

    def go_to_next_move(self):
        """Go to the next move."""
        if self.current_game:
            if self.current_ply < len(self.moves):
                # Get the move before applying it
                move = self.moves[self.current_ply]
                piece = self.board.piece_at(move.from_square)

                # Determine whether animation is safe for this move
                should_animate = True
                if (
                    piece is None
                    or self.board.is_castling(move)
                    or self.board.is_en_passant(move)
                    or move.promotion is not None
                ):
                    should_animate = False

                # Apply the move to the board
                self.board.push(move)
                self.current_ply += 1

                from_name = chess.square_name(move.from_square)
                to_name = chess.square_name(move.to_square)

                if should_animate and piece is not None:
                    symbol = piece.symbol()
                    self.animate_single_move(from_name, to_name, symbol)
                else:
                    self.send_full_position_to_js()

                # Update last move highlighting
                self.last_move_squares = {from_name, to_name}

                self.display_moves()

    def go_to_last_move(self):
        """Go to the last move."""
        if self.current_game:
            self.current_ply = len(self.moves)
            self.update_board_to_ply(self.current_ply)
            self.send_full_position_to_js()
            self.display_moves()

    def jump_to_ply(self, ply):
        """Jump to a specific ply by clicking on a move."""
        self.current_ply = ply
        self.update_board_to_ply(self.current_ply)
        self.send_full_position_to_js()
        self.display_moves()

    def trigger_upload(self):
        """Trigger the file upload dialog."""
        if self.upload_element:
            self.upload_element.run_method('pickFiles')

    def update_game_title(self):
        """Update the game title display above the chess board."""
        if self.game_title_label is None:
            return

        if self.current_game:
            white = self.current_game.headers.get('White', 'Unknown')
            black = self.current_game.headers.get('Black', 'Unknown')
            self.game_title_label.text = f"{white} vs {black}"
        else:
            self.game_title_label.text = "No game loaded"

    def load_sample_game(self):
        """Load the sample Kasparov vs Topalov game."""
        try:
            with open('kasparov_topalov_1999.pgn', 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse the chess game
            self.current_game = self.parse_pgn_game(content)
            self.current_ply = 0  # Reset to starting position
            self.board = self.current_game.board()  # Initialize board at starting position
            self.moves = list(self.current_game.mainline_moves())  # Cache moves to avoid recomputation
            self.san_moves = []  # Clear SAN cache for new game
            self.last_move_squares = set()  # Clear last move highlighting
            self.move_row_elements.clear()  # Clear move row references

            # Update game title
            self.update_game_title()

            # Update the UI with moves and board
            self.display_moves()
            self.send_full_position_to_js()

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

            # Main content area
            with ui.row().classes('gap-4 px-4 py-2 items-start flex-1 overflow-hidden'):
                # Left side: Chess board
                with ui.column().classes('items-center bg-gray-800 rounded-lg p-4'):
                    # Game title above board
                    self.game_title_label = ui.label('No game loaded').classes('text-lg font-bold text-center text-white mb-2')

                    # simple container – no flex-1 / h-full
                    with ui.element('div').classes('flex items-center justify-center'):
                        self.board_html = ui.html(BOARD_HTML, sanitize=False).classes('block')

                    ui.run_javascript(BOARD_JS_INIT)

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
        if self.board is None:
            return

        pos_dict = {
            chess.square_name(square): piece.symbol()
            for square, piece in self.board.piece_map().items()
        }
        position_json = json.dumps(pos_dict)

        # Guard against chessAnim not being defined yet
        ui.run_javascript(
            f'if (window.chessAnim && window.chessAnim.setPosition) '
            f'{{ window.chessAnim.setPosition({position_json}); }}'
        )

    def animate_single_move(self, from_square: str, to_square: str, symbol: str):
        """Animate a single piece movement from one square to another."""
        js = (
            "if (window.chessAnim && window.chessAnim.animateMove) {"
            f"  window.chessAnim.animateMove({{"
            f"    from: '{from_square}',"
            f"    to: '{to_square}',"
            f"    piece: '{symbol}',"
            f"    durationMs: 200"
            f"  }});"
            "}"
        )
        ui.run_javascript(js)


@ui.page('/')
def home():
    """Create the main application page."""
    analyzer = ChessAnalyzer()
    analyzer.create_ui()

if __name__ in {"__main__", "__mp_main__"}:
    port = int(os.environ.get('PORT', 8080))
    ui.run(host="0.0.0.0", port=port)