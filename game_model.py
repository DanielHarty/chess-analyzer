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
            
            # Evaluate starting position
            self.evaluations[0] = await asyncio.to_thread(evaluate_position, board)
            if progress_callback:
                progress_callback(1, total)

            # Evaluate each position after each move
            for i, move in enumerate(self.moves, start=1):
                board.push(move)
                eval_score = await asyncio.to_thread(evaluate_position, board)
                self.evaluations[i] = eval_score
                
                if progress_callback:
                    progress_callback(i + 1, total)
                
                # Yield control to allow UI updates
                await asyncio.sleep(0)
            
            self._eval_complete = True
        except asyncio.CancelledError:
            # Task was cancelled, that's fine
            pass

    def ensure_san_moves(self) -> list[str]:
        """Return SAN moves, computing and caching if needed."""
        if not self.current_game or not self.moves:
            return []

        if self.san_moves:
            return self.san_moves

        board = self.current_game.board()
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

    def get_current_evaluation(self) -> int | None:
        """Return the precalculated evaluation for the current position."""
        if self.current_ply < len(self.evaluations):
            return self.evaluations[self.current_ply]
        return None
