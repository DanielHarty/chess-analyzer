# engine_adapter.py

from __future__ import annotations

import os
from typing import Optional

import chess
import chess.engine

# Default paths - will be overridden by main.py with platform-specific binaries
DEFAULT_STOCKFISH_PATH = os.environ.get('STOCKFISH_PATH', 'stockfish')

class StockfishEngine:
    """Thin wrapper around a UCI Stockfish binary for evaluation only."""

    def __init__(self, path: str = DEFAULT_STOCKFISH_PATH, time_limit: float = 0.2):
        """
        Args:
            path: Path or command name for the Stockfish binary.
            time_limit: Per-position analysis time in seconds.
        """
        self.path = path
        self.time_limit = time_limit
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self._ensure_engine()

    def _ensure_engine(self) -> None:
        if self.engine is None:
            try:
                self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
            except Exception as e:
                print(f"[StockfishEngine] Failed to start engine: {e}")
                self.engine = None

    def evaluate_cp(self, board: chess.Board) -> Optional[int]:
        """
        Return evaluation in centipawns from White's perspective.
        Positive = White better, negative = Black better.
        Returns None if engine is unavailable.
        """
        try:
            self._ensure_engine()
            if self.engine is None:
                return None

            info = self.engine.analyse(board, chess.engine.Limit(time=self.time_limit))
            score = info["score"].white()

            if score.is_mate():
                # Treat mate scores as large CP values (clamped later for UI)
                mate_in = score.mate()  # positive = mate for white, negative = mate for black
                # Use 10_000 cp for "mate is coming"
                return 10_000 if mate_in and mate_in > 0 else -10_000

            return score.score(mate_score=10_000)
        except Exception as e:
            print(f"[StockfishEngine] Evaluation error: {e}")
            return None

    def close(self) -> None:
        if self.engine is not None:
            try:
                self.engine.quit()
            except Exception:
                pass
            self.engine = None