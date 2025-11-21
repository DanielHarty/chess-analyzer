# game_model.py

import io
import chess
import chess.pgn
import asyncio
from typing import Callable
from global_engine import evaluate_position

class GameModel:
    """Pure chess game state & navigation. No GUI, no JS."""

    def __init__(self):
        self.current_game: chess.pgn.Game | None = None
        self.board: chess.Board | None = None
        self.moves: list[chess.Move] = []
        self.san_moves: list[str] = []
        self.current_ply: int = 0
        self.last_move_squares: set[str] = set()
        self.evaluations: list[int | None] = []  # Precalculated evaluations for each ply
        self._eval_task: asyncio.Task | None = None  # Background evaluation task
        self._eval_complete: bool = False  # Flag to track if evaluation is complete
        self._initial_fen: str | None = None

    # ---------- Loading & parsing ----------

    def load_pgn_text(self, pgn_text: str) -> None:
        """Load a single game from PGN text and reset state."""
        pgn_stream = io.StringIO(pgn_text)
        game = chess.pgn.read_game(pgn_stream)

        if game is None:
            raise ValueError("No game found in PGN")

        self.current_game = game
        initial_board = game.board()
        self._initial_fen = initial_board.fen()
        self.board = chess.Board(self._initial_fen)
        self.moves = list(game.mainline_moves())
        self.san_moves = []        # lazy-computed
        self.current_ply = 0
        self.last_move_squares = set()
        self._eval_complete = False

        # Initialize evaluations with None placeholders
        self.evaluations = [None] * (len(self.moves) + 1)

    def start_background_evaluation(self, progress_callback: Callable[[int, int], None] | None = None) -> None:
        """Start background evaluation of all positions in the game.
        
        Args:
            progress_callback: Optional callback function(current, total) called after each evaluation
        """
        if self._eval_task is not None:
            self._eval_task.cancel()
        
        self._eval_task = asyncio.create_task(self._precalculate_evaluations_async(progress_callback))

    async def _precalculate_evaluations_async(self, progress_callback: Callable[[int, int], None] | None = None) -> None:
        """Precalculate evaluations for all positions in the game asynchronously."""
        if not self.current_game:
            self.evaluations = []
            self._eval_complete = True
            return

        try:
            # Start with the initial position
            board = self.current_game.board()
            total = len(self.moves) + 1
            
            # Evaluate starting position (async call)
            eval_score = await evaluate_position(board)
            self.evaluations[0] = eval_score
            
            if progress_callback:
                progress_callback(1, total)

            # Evaluate each position after each move
            for i, move in enumerate(self.moves, start=1):
                board.push(move)
                # Async call directly
                eval_score = await evaluate_position(board)
                self.evaluations[i] = eval_score
                
                if progress_callback:
                    progress_callback(i + 1, total)
                
                # Yield control to allow UI updates (though await evaluate_position already yields)
                await asyncio.sleep(0)
            
            self._eval_complete = True
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in background evaluation: {e}")

    def ensure_san_moves(self) -> list[str]:
        """Return SAN moves, computing and caching if needed."""
        if not self.moves:
            return []

        if self.san_moves:
            return self.san_moves

        # Always start from the initial position, regardless of current_game state
        board = chess.Board(self._initial_fen)
        san_list: list[str] = []

        for mv in self.moves:
            san_list.append(board.san(mv))
            board.push(mv)

        self.san_moves = san_list
        return self.san_moves

    # ---------- Navigation ----------

    def go_to_ply(self, ply: int) -> None:
        """Set board to given ply (0 = starting position)."""
        if not self.current_game or not self.board:
            return

        ply = max(0, min(ply, len(self.moves)))
        if ply == self.current_ply:
            return

        if ply > self.current_ply:
            for i in range(self.current_ply, ply):
                self.board.push(self.moves[i])
        else:
            for _ in range(self.current_ply - ply):
                self.board.pop()

        self.current_ply = ply

        if 0 < ply <= len(self.moves):
            last_move = self.moves[ply - 1]
            self.last_move_squares = {
                chess.square_name(last_move.from_square),
                chess.square_name(last_move.to_square),
            }
        else:
            self.last_move_squares = set()

    def step_forward(self):
        """Advance one ply and return (move, flags) or None if at end."""
        if not self.current_game or self.current_ply >= len(self.moves):
            return None

        move = self.moves[self.current_ply]
        piece = self.board.piece_at(move.from_square) if self.board else None

        # Collect flags for animation decisions
        is_castling = self.board.is_castling(move) if self.board else False
        is_en_passant = self.board.is_en_passant(move) if self.board else False
        is_promotion = move.promotion is not None

        # Apply move
        self.board.push(move)
        self.current_ply += 1
        from_name = chess.square_name(move.from_square)
        to_name = chess.square_name(move.to_square)
        self.last_move_squares = {from_name, to_name}

        return {
            "move": move,
            "piece": piece,
            "from": from_name,
            "to": to_name,
            "is_castling": is_castling,
            "is_en_passant": is_en_passant,
            "is_promotion": is_promotion,
        }

    def step_back(self):
        """Go one ply backward."""
        if not self.current_game or self.current_ply == 0:
            return None

        if not self.board:
            return None

        undone_move = self.board.peek()
        piece = self.board.piece_at(undone_move.to_square)
        is_castling = self.board.is_castling(undone_move)
        is_en_passant = self.board.is_en_passant(undone_move)
        is_promotion = undone_move.promotion is not None

        self.board.pop()
        self.current_ply -= 1

        from_name = chess.square_name(undone_move.from_square)
        to_name = chess.square_name(undone_move.to_square)

        if self.current_ply > 0:
            last_move = self.moves[self.current_ply - 1]
            self.last_move_squares = {
                chess.square_name(last_move.from_square),
                chess.square_name(last_move.to_square),
            }
        else:
            self.last_move_squares = set()

        return {
            "move": undone_move,
            "piece": piece,
            "from": to_name,  # For backward animation, we move from "to" back to "from"
            "to": from_name,  # For backward animation, we move to "from"
            "is_castling": is_castling,
            "is_en_passant": is_en_passant,
            "is_promotion": is_promotion,
            "current_ply": self.current_ply,
            "last_move_squares": self.last_move_squares,
        }

    def go_to_start(self):
        self.go_to_ply(0)

    def go_to_end(self):
        if self.current_game:
            self.go_to_ply(len(self.moves))

    # ---------- Data for the GUI/JS ----------

    def get_position_dict(self) -> dict[str, str]:
        """Return {square_name: piece_symbol} for JS."""
        if not self.board:
            return {}

        return {
            chess.square_name(square): piece.symbol()
            for square, piece in self.board.piece_map().items()
        }

    def get_move_rows(self):
        """Return rows for the moves panel: [(move_no, white_SAN, black_SAN)]."""
        san = self.ensure_san_moves()
        rows = []

        for i in range(0, len(san), 2):
            move_no = (i // 2) + 1
            white = san[i]
            black = san[i + 1] if i + 1 < len(san) else ""
            rows.append((move_no, white, black))

        return rows

    def get_blunders(self, threshold: int = 200) -> list[int]:
        """Return list of ply indices where white blunders occurred.

        A blunder is defined as a white move that causes a significant drop in evaluation.
        Default threshold is 200 centipawns (2 pawns).

        Args:
            threshold: Minimum evaluation drop in centipawns to be considered a blunder.

        Returns:
            List of ply indices (after the blunder move) where white blunders occurred.
        """
        blunders = []

        # Need at least 2 evaluations to compare
        if len(self.evaluations) < 2:
            return blunders

        for i in range(1, len(self.evaluations)):
            prev_eval = self.evaluations[i - 1]
            curr_eval = self.evaluations[i]

            # Skip if either evaluation is None
            if prev_eval is None or curr_eval is None:
                continue

            eval_diff = curr_eval - prev_eval

            # Only check blunders for white moves
            # White moves from even ply (0, 2, 4...) to odd ply (1, 3, 5...)
            if (i - 1) % 2 == 0:  # White moved
                if eval_diff <= -threshold:
                    blunders.append(i)

        return blunders

    def get_current_evaluation(self) -> int | None:
        """Return the precalculated evaluation for the current position."""
        if self.current_ply < len(self.evaluations):
            return self.evaluations[self.current_ply]
        return None

    def create_variation(self, ply: int, new_move: chess.Move) -> 'GameModel':
        """Create a new variation by branching from the given ply with a new move.

        Args:
            ply: The ply to branch from (0 = starting position)
            new_move: The new move to add as the variation

        Returns:
            A new GameModel instance with the variation
        """
        if not self.current_game or not self.board:
            raise ValueError("Cannot create variation: no game loaded")

        if ply < 0 or ply > len(self.moves):
            raise ValueError(f"Ply {ply} is out of range (0-{len(self.moves)})")

        # Create new game model with same initial position
        variation_model = GameModel()
        variation_model._initial_fen = self._initial_fen

        # Copy the moves up to the branching point
        variation_moves = self.moves[:ply]

        # Add the new move
        variation_moves.append(new_move)

        # Reconstruct the game from the variation moves
        game = chess.pgn.Game()
        game.setup(chess.Board(self._initial_fen))

        # Apply all moves to create the new game tree
        node = game
        for move in variation_moves:
            node = node.add_variation(move)

        variation_model.current_game = game
        variation_model.moves = variation_moves
        variation_model.board = chess.Board(self._initial_fen)

        # Replay moves to set up the board state
        for move in variation_moves:
            variation_model.board.push(move)
        variation_model.current_ply = len(variation_moves)
        variation_model.last_move_squares = set()

        # Initialize evaluations (will be computed later)
        variation_model.evaluations = [None] * (len(variation_moves) + 1)

        # Update last move squares if we have moves
        if variation_moves:
            last_move = variation_moves[-1]
            variation_model.last_move_squares = {
                chess.square_name(last_move.from_square),
                chess.square_name(last_move.to_square),
            }

        return variation_model