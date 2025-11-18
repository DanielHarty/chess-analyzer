# global_engine.py

"""
Global Stockfish engine singleton for the chess analyzer application.

This module provides a single shared Stockfish engine instance that can be used
across the entire application, avoiding the overhead of creating multiple engine
instances per session.
"""

from __future__ import annotations

import os
from typing import Optional

import chess
import chess.engine

# Default paths - will be overridden by main.py with platform-specific binaries
DEFAULT_STOCKFISH_PATH = os.environ.get('STOCKFISH_PATH', 'stockfish')

class GlobalStockfishEngine:
    """Singleton wrapper around a UCI Stockfish binary for evaluation.

    This class ensures only one Stockfish engine instance exists throughout
    the application lifecycle.
    """

    _instance: Optional['GlobalStockfishEngine'] = None
    _engine_path: str = DEFAULT_STOCKFISH_PATH
    _time_limit: float = 0.05  # Reduced for faster batch evaluation

    def __new__(cls, path: str = DEFAULT_STOCKFISH_PATH, time_limit: float = 0.05) -> 'GlobalStockfishEngine':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._engine_path = path
            cls._time_limit = time_limit
        return cls._instance

    def __init__(self, path: str = DEFAULT_STOCKFISH_PATH, time_limit: float = 0.05):
        """Initialize the global engine (only called once due to singleton pattern)."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.engine: Optional[chess.engine.SimpleEngine] = None
            self.time_limit = time_limit
            self._ensure_engine()

    @classmethod
    def get_instance(cls) -> Optional['GlobalStockfishEngine']:
        """Get the global engine instance, or None if not initialized."""
        return cls._instance

    def _ensure_engine(self) -> None:
        """Ensure the engine is started and available."""
        if self.engine is None:
            try:
                self.engine = chess.engine.SimpleEngine.popen_uci(self._engine_path)
            except Exception as e:
                print(f"[GlobalStockfishEngine] Failed to start engine: {e}")
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
            print(f"[GlobalStockfishEngine] Evaluation error: {e}")
            return None

    def close(self) -> None:
        """Close the engine if it exists."""
        if self.engine is not None:
            try:
                self.engine.quit()
            except Exception:
                pass
            self.engine = None

    @classmethod
    def shutdown(cls) -> None:
        """Shutdown the global engine instance."""
        if cls._instance is not None:
            cls._instance.close()
            cls._instance = None


# Convenience functions for easy access
def get_global_engine() -> Optional[GlobalStockfishEngine]:
    """Get the global Stockfish engine instance."""
    return GlobalStockfishEngine.get_instance()


def evaluate_position(board: chess.Board) -> Optional[int]:
    """Evaluate a chess position using the global engine."""
    engine = get_global_engine()
    if engine:
        return engine.evaluate_cp(board)
    return None


def shutdown_global_engine() -> None:
    """Shutdown the global engine (call on application exit)."""
    GlobalStockfishEngine.shutdown()
