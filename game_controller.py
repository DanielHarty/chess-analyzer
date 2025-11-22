import asyncio
from nicegui import ui
import chess
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
        self.games = [model]  # List of all game variations
        self.current_game_index = 0  # Index of currently active game

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

    def load_chesscom_game(self, pgn_content):
        """Load a game from chess.com PGN content.

        Args:
            pgn_content: PGN string content from chess.com
        """
        try:
            self._load_game_and_refresh_ui(pgn_content)
        except Exception as e:
            print(f"✗ Chess.com game load error: {e}")
            ui.notify(f"Failed to load Chess.com game: {e}", type="negative")

    def _load_game_and_refresh_ui(self, content):
        """Load PGN content into model and refresh all UI components."""
        self.model.load_pgn_text(content)

        # Reset variations when loading a new game
        self.games = [self.model]
        self.current_game_index = 0

        # Update View
        self.view.update_game_title()
        self.view.display_moves()
        self.view.send_full_position_to_js()
        self.view.recompute_eval()
        self.view.update_eval_chart()
        self._update_variations_ui()

        # Start background evaluation
        self.start_evaluation_with_progress()

    def go_to_first_move(self):
        """Go to the starting position (total board reset)."""
        self.model.go_to_start()
        self.view.send_full_position_to_js()
        self.view.display_moves()
        self.view.recompute_eval()
        self.view.update_eval_chart()
        self._update_variations_ui()

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
        self._update_variations_ui()

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
        self._update_variations_ui()

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

    def _update_variations_ui(self):
        """Update the variations tabs in the UI."""
        variation_names = []
        for i, game_model in enumerate(self.games):
            if i == 0:
                variation_names.append("Main")
            else:
                variation_names.append(f"Var {i}")

        self.view.moves_list.set_variations(variation_names, self.current_game_index)

    def handle_move(self, from_square, to_square):
        """Handle a piece move attempt on the board.

        Args:
            from_square: Algebraic square the piece is moving from (e.g., "e2")
            to_square: Algebraic square the piece is moving to (e.g., "e4")
        """
        if not self.model.board:
            return

        try:
            # Convert algebraic squares to chess squares
            from_sq = chess.parse_square(from_square)
            to_sq = chess.parse_square(to_square)
            print(f"Parsed squares: {from_square}={from_sq}, {to_square}={to_sq}")

            # Create the move object
            move = chess.Move(from_sq, to_sq)

            # Check if it's a promotion (pawn reaching 8th rank)
            piece = self.model.board.piece_at(from_sq)
            if piece and piece.piece_type == chess.PAWN:
                # Determine if promotion is needed
                if (piece.color == chess.WHITE and chess.square_rank(to_sq) == 7) or \
                   (piece.color == chess.BLACK and chess.square_rank(to_sq) == 0):
                    # Default to queen promotion
                    move = chess.Move(from_sq, to_sq, chess.QUEEN)

            # Validate the move
            if not self.model.board.is_legal(move):
                # Try other promotion pieces if it was a pawn promotion attempt
                if piece and piece.piece_type == chess.PAWN:
                    for promotion_piece in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
                        alt_move = chess.Move(from_sq, to_sq, promotion_piece)
                        if alt_move in self.model.board.legal_moves:
                            move = alt_move
                            break

                if not self.model.board.is_legal(move):
                    print(f"Illegal move: {from_square} to {to_square}")
                    # Snap the piece back to its original position
                    self.view.chess_board.snap_piece_back()
                    return

            # Check if we're at the end of the current game or if this move matches the next expected move
            current_ply = self.model.current_ply
            num_moves = len(self.model.moves)

            if current_ply >= num_moves:
                # We're at the end of the current line/variation - extend it
                self._extend_current_variation(move)
            else:
                # Check if the move matches the expected next move
                expected_move = self.model.moves[current_ply]
                if move == expected_move:
                    # This is following the current line - just advance
                    self.go_to_next_move()
                else:
                    # This is a deviation - create a new variation
                    self._create_variation(move)

        except Exception as e:
            print(f"Error handling move: {e}")
            self.view.chess_board.snap_piece_back()

    def _extend_current_variation(self, move):
        """Extend the current variation with a new move."""
        try:
            # Add the move to the current model's moves
            self.model.moves.append(move)

            # Apply the move to the board
            self.model.board.push(move)

            # Update the current ply
            self.model.current_ply += 1

            # Clear cached SAN moves so they will be recomputed
            self.model.san_moves = []

            # Update last move squares
            if self.model.moves:
                last_move = self.model.moves[-1]
                self.model.last_move_squares = {
                    chess.square_name(last_move.from_square),
                    chess.square_name(last_move.to_square),
                }

            # Extend evaluations list with None placeholder for the new position
            self.model.evaluations.append(None)

            # Mark evaluation as incomplete so it will be re-run
            self.model._eval_complete = False

            # Recreate the PGN game tree with the extended moves
            if self.model.current_game:
                game = chess.pgn.Game()
                game.setup(chess.Board(self.model._initial_fen))
                node = game
                for mv in self.model.moves:
                    node = node.add_variation(mv)
                self.model.current_game = game

            # Refresh UI
            self.view.display_moves()
            self.view.send_full_position_to_js()
            self.view.recompute_eval()
            self.view.update_eval_chart()

            # Start background evaluation for the variation
            self.start_evaluation_with_progress()

        except Exception as e:
            print(f"Error extending variation: {e}")

    def _create_variation(self, move):
        """Create a new variation with the given move."""
        try:
            # Create the variation
            variation_model = self.model.create_variation(self.model.current_ply, move)

            # Add to games list
            self.games.append(variation_model)

            # Switch to the new variation
            variation_index = len(self.games) - 1
            self.switch_variation(variation_index)

        except Exception as e:
            print(f"Error creating variation: {e}")

    def switch_variation(self, index):
        """Switch to a different game variation.

        Args:
            index: Index of the variation to switch to
        """
        if 0 <= index < len(self.games):
            self.current_game_index = index
            self.model = self.games[index]

            # Refresh all UI components
            self.view.update_game_title()
            self.view.display_moves()
            self.view.send_full_position_to_js()
            self.view.recompute_eval()
            self.view.update_eval_chart()
            self._update_variations_ui()
        else:
            print(f"Invalid index {index}, games has {len(self.games)} items")

            # Start background evaluation for the new variation if needed
            if not self.model._eval_complete:
                self.start_evaluation_with_progress()

