"""
Chess Game Analyzer
A NiceGUI application for uploading and analyzing chess games in PGN format.
"""

import io
from nicegui import ui
import chess
import chess.pgn
import os


class ChessAnalyzer:
    """Main application class for chess game analysis.

    Future architecture note: Consider splitting into separate classes:
    - GameModel: Handle game state, moves, SAN conversion, and board logic
    - ChessAnalyzer: Focus on UI interaction and display logic
    This would enable better testing and modularity for features like engine evaluation.
    """

    # Chess piece Unicode symbols
    CHESS_PIECES = {
        'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',  # White pieces
        'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'   # Black pieces
    }

    # Initial chess board setup (FEN notation: rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR)
    # White pieces at bottom (home side), black pieces at top (far side)
    INITIAL_BOARD = [
        ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],  # rank 8 - black pieces at top
        ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],  # rank 7 - black pieces
        [' ', ' ', ' ', ' ', ' ', ' ', ' ', ' '],   # rank 6
        [' ', ' ', ' ', ' ', ' ', ' ', ' ', ' '],   # rank 5
        [' ', ' ', ' ', ' ', ' ', ' ', ' ', ' '],   # rank 4
        [' ', ' ', ' ', ' ', ' ', ' ', ' ', ' '],   # rank 3
        ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],  # rank 2 - white pieces
        ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']   # rank 1 - white pieces at bottom
    ]

    def __init__(self):
        """Initialize the chess analyzer."""
        self.current_game = None
        self.moves_container = None
        self.controls_container = None
        self.board_container = None
        self.current_ply = 0
        self.board = None  # chess.Board object for current position
        self.moves = []  # Cache mainline moves to avoid recomputation
        self.san_moves = []  # Cache SAN notation for moves
        self.last_move_squares = set()  # Track squares for last move highlighting
        self.game_title_label = None  # Label to display game title above board
        self.move_row_elements = {}  # Store references to move row elements for scrolling

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

    def board_to_2d_array(self, board):
        """Convert chess.Board to 2D array for display.
        
        Args:
            board: chess.Board object
            
        Returns:
            2D list representing the board (rank 8 to rank 1)
        """
        board_array = []
        for rank in range(7, -1, -1):  # 7 to 0 (rank 8 to rank 1)
            row = []
            for file in range(8):  # a to h
                square = chess.square(file, rank)
                piece = board.piece_at(square)
                if piece:
                    # Convert to our notation (uppercase=white, lowercase=black)
                    symbol = piece.symbol()
                    row.append(symbol)
                else:
                    row.append(' ')
            board_array.append(row)
        return board_array

    def create_chess_board_html(self, large=False, board_state=None, highlight_squares=None):
        """Generate HTML for the chess board display.

        Args:
            large: If True, creates a larger board that scales with viewport
            board_state: 2D array representing board state (if None, uses INITIAL_BOARD)
            highlight_squares: Set of square names (e.g., {'e2', 'e4'}) to highlight
        """
        if board_state is None:
            board_state = self.INITIAL_BOARD
            
        # Set sizes based on large parameter
        if large:
            cell_size = 64  # pixels
            font_size = 48  # pixels
            label_size = 24  # pixels
        else:
            cell_size = 32  # pixels
            font_size = 24  # pixels
            label_size = 14  # pixels

        # Common cell style to ensure perfect squares
        cell_style = f"width: {cell_size}px; height: {cell_size}px; min-width: {cell_size}px; max-width: {cell_size}px; min-height: {cell_size}px; max-height: {cell_size}px; text-align: center; font-weight: bold; line-height: {cell_size}px; box-sizing: border-box;"

        table_html = f'''
            <table style="border-collapse: collapse; border: 2px solid #374151; display: inline-table; table-layout: fixed;">
                <tr style="height: {cell_size}px;">
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;"></td>
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;">a</td>
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;">b</td>
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;">c</td>
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;">d</td>
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;">e</td>
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;">f</td>
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;">g</td>
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;">h</td>
                </tr>'''

        # Add board rows
        for rank in range(8, 0, -1):  # 8 to 1
            # Force exact row height
            table_html += f'''
                <tr style="height: {cell_size}px;">
                    <td style="{cell_style} color: #6B7280; font-size: {label_size}px; vertical-align: middle;">{rank}</td>'''

            for file in range(8):
                piece = board_state[8-rank][file]
                square_name = chr(ord('a') + file) + str(rank)
                is_light = (rank + file) % 2 == 0
                is_highlighted = highlight_squares and square_name in highlight_squares

                if is_highlighted:
                    bg_color = '#10B981' if is_light else '#059669'  # emerald-500 : emerald-600
                else:
                    bg_color = '#FEF3C7' if is_light else '#92400E'  # amber-100 : amber-800

                # Set piece color based on piece type, not square color
                if piece.isupper():  # White pieces
                    text_color = '#FFFFFF'  # White
                elif piece.islower():  # Black pieces
                    text_color = '#000000'  # Black
                else:
                    text_color = '#000000'  # Empty squares

                piece_symbol = self.CHESS_PIECES.get(piece, '') if piece != ' ' else ''
                # Add drop shadow for better visibility
                shadow_style = 'text-shadow: 1px 1px 2px rgba(0,0,0,0.7);' if piece != ' ' else ''
                table_html += f'''
                    <td style="{cell_style} background-color: {bg_color}; color: {text_color}; font-size: {font_size}px; cursor: pointer; vertical-align: middle; {shadow_style}" onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">{piece_symbol}</td>'''

            table_html += '''
                </tr>'''

        table_html += '''
            </table>'''

        return table_html

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

            # Display results
            print(f"✓ Successfully processed: {filename}")
            print(f"Game headers: {dict(self.current_game.headers)}")
            print(f"Number of moves: {len(self.moves)}")

            # Update the UI with moves and board
            self.display_moves()
            self.update_board_display()

            ui.notify(f"Successfully uploaded and parsed: {filename}", type="positive")

        except Exception as e:
            print(f"✗ Upload error: {e}")
            ui.notify(f"Upload failed: {e}", type="negative")

    def display_moves(self):
        """Display the moves in the right panel."""
        print(f"display_moves called, moves_container: {self.moves_container}")
        if self.moves_container is None:
            print("moves_container is None!")
            return

        # Clear existing content
        self.moves_container.clear()
        print("Cleared moves_container")
        self.move_row_elements.clear()  # Clear stored row references

        if self.current_game is None:
            print("No current game")
            with self.moves_container:
                ui.label('No game loaded').classes('text-gray-400 text-center py-8')
            return

        # Get SAN moves
        san_moves = self.get_san_moves()
        print(f"Found {len(san_moves)} moves")

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
                    ui.button('⏮️', on_click=self.go_to_first_move).classes('px-4 py-2')
                    ui.button('◀', on_click=self.go_to_previous_move).classes('px-4 py-2')
                    ui.button('▶', on_click=self.go_to_next_move).classes('px-4 py-2')
                    ui.button('⏭️', on_click=self.go_to_last_move).classes('px-4 py-2')
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
    
    def update_board_display(self):
        """Update the board display with current position."""
        if self.board_container is None or self.board is None:
            return
        
        # Convert board to 2D array
        board_array = self.board_to_2d_array(self.board)
        
        # Generate new HTML
        board_html = self.create_chess_board_html(large=True, board_state=board_array, highlight_squares=self.last_move_squares)
        
        # Update display
        self.board_container.clear()
        with self.board_container:
            ui.html(board_html, sanitize=False)

    def go_to_first_move(self):
        """Go to the first move."""
        self.current_ply = 0
        self.update_board_to_ply(self.current_ply)
        self.update_board_display()
        self.display_moves()

    def go_to_previous_move(self):
        """Go to the previous move."""
        if self.current_ply > 0:
            self.current_ply -= 1
            self.update_board_to_ply(self.current_ply)
            self.update_board_display()
            self.display_moves()

    def go_to_next_move(self):
        """Go to the next move."""
        if self.current_game:
            if self.current_ply < len(self.moves):
                self.current_ply += 1
                self.update_board_to_ply(self.current_ply)
                self.update_board_display()
                self.display_moves()

    def go_to_last_move(self):
        """Go to the last move."""
        if self.current_game:
            self.current_ply = len(self.moves)
            self.update_board_to_ply(self.current_ply)
            self.update_board_display()
            self.display_moves()

    def jump_to_ply(self, ply):
        """Jump to a specific ply by clicking on a move."""
        self.current_ply = ply
        self.update_board_to_ply(self.current_ply)
        self.update_board_display()
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

            # Display results
            print(f"✓ Successfully loaded sample game")
            print(f"Game headers: {dict(self.current_game.headers)}")
            print(f"Number of moves: {len(self.moves)}")

            # Update the UI with moves and board
            self.display_moves()
            self.update_board_display()

            ui.notify(f"Successfully loaded sample game: Kasparov vs Topalov", type="positive")

        except Exception as e:
            print(f"✗ Sample game load error: {e}")
            ui.notify(f"Failed to load sample game: {e}", type="negative")

    def create_ui(self):
        """Create and setup the user interface."""
        # Add modern scrollbar styling
        ui.add_css('''
            .modern-scrollbar {
                scrollbar-width: thin;
                scrollbar-color: #4B5563 #1F2937;
            }
            .modern-scrollbar::-webkit-scrollbar {
                width: 8px;
            }
            .modern-scrollbar::-webkit-scrollbar-track {
                background: #1F2937;
                border-radius: 4px;
            }
            .modern-scrollbar::-webkit-scrollbar-thumb {
                background: #4B5563;
                border-radius: 4px;
                border: 1px solid #1F2937;
            }
            .modern-scrollbar::-webkit-scrollbar-thumb:hover {
                background: #6B7280;
            }
            .modern-scrollbar::-webkit-scrollbar-thumb:active {
                background: #9CA3AF;
            }
        ''')

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
            with ui.row().classes('flex-1 gap-4 px-4 py-2 overflow-hidden min-h-0'):
                # Left side: Chess board
                with ui.column().classes('flex-1 items-center justify-center bg-gray-800 rounded-lg p-2 overflow-hidden'):
                    # Game title above board
                    self.game_title_label = ui.label('No game loaded').classes('text-lg font-bold text-center text-white mb-2')

                    self.board_container = ui.column().classes('flex items-center justify-center')
                    with self.board_container:
                        board_html = self.create_chess_board_html(large=True, highlight_squares=set())
                        ui.html(board_html, sanitize=False)

                # Right side: Moves panel
                with ui.column().classes('w-68 bg-gray-800 rounded-lg overflow-hidden flex flex-col'):
                    # Header
                    ui.label('Moves').classes('text-lg font-bold p-4 border-b border-gray-700')

                    # Moves list
                    self.moves_container = ui.column().classes('flex-1 w-full overflow-y-auto pl-4 pr-0 py-2 gap-2 max-h-96 modern-scrollbar')
                    with self.moves_container:
                        ui.label('No game loaded').classes('text-gray-400 text-center py-8')

                    # Game controls at bottom
                    self.controls_container = ui.column().classes('w-full border-t border-gray-700 p-4')
                    with self.controls_container:
                        ui.label('Upload a PGN file to start analyzing').classes('text-gray-400 text-center')


@ui.page('/')
def home():
    """Create the main application page."""
    analyzer = ChessAnalyzer()
    analyzer.create_ui()

if __name__ in {"__main__", "__mp_main__"}:
    port = int(os.environ.get('PORT', 8080))
    ui.run(host="0.0.0.0", port=port)