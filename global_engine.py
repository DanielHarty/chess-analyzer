# global_engine.py

"""
Global Stockfish engine singleton for the chess analyzer application.

This module provides a single shared Stockfish engine instance that can be used
across the entire application, avoiding the overhead of creating multiple engine
instances per session.
"""

from __future__ import annotations

import os
import asyncio
from typing import Optional, Tuple

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
            self.transport: asyncio.SubprocessTransport | None = None
            # Can be either SimpleEngine or UciProtocol
            self.engine: chess.engine.SimpleEngine | chess.engine.UciProtocol | None = None
            self.time_limit = time_limit
            # Defer engine start to first usage (async)

    @classmethod
    def get_instance(cls) -> Optional['GlobalStockfishEngine']:
        """Get the global engine instance, or None if not initialized."""
        return cls._instance

    async def _ensure_engine(self) -> None:
        """Ensure the engine is started and available."""
        if self.engine is not None:
            # For SimpleEngine, check if it's still alive by trying to ping
            if isinstance(self.engine, chess.engine.SimpleEngine):
                try:
                    self.engine.ping()
                    return
                except:
                    # Engine is dead, need to restart
                    self.engine = None
            elif self.transport is not None and not self.transport.is_closing():
                return

        try:
            if not os.path.exists(self._engine_path):
                print(f"Engine file not found at {self._engine_path}")
                return

            # Use SimpleEngine.popen_uci which is synchronous and works on Windows
            # regardless of event loop type. Run it in an executor to avoid blocking.
            # This is the recommended approach for Windows compatibility.
            loop = asyncio.get_event_loop()
            self.engine = await loop.run_in_executor(
                None,
                lambda: chess.engine.SimpleEngine.popen_uci(str(self._engine_path))
            )
            self.transport = None  # SimpleEngine manages its own transport internally
        except Exception as e:
            print(f"[GlobalStockfishEngine] Failed to start engine: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.engine = None
            self.transport = None

    async def evaluate_cp(self, board: chess.Board) -> Optional[int]:
        """
        Return evaluation in centipawns from White's perspective.
        Positive = White better, negative = Black better.
        Returns None if engine is unavailable.
        """
        try:
            await self._ensure_engine()
            if self.engine is None:
                return None

            # Handle both SimpleEngine (synchronous) and UciProtocol (async)
            if isinstance(self.engine, chess.engine.SimpleEngine):
                # SimpleEngine uses synchronous analyse
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(
                    None,
                    lambda: self.engine.analyse(board, chess.engine.Limit(time=self.time_limit))
                )
            else:
                # Use async analyse for UciProtocol
                info = await self.engine.analyse(board, chess.engine.Limit(time=self.time_limit))
            
            score = info["score"].white()

            if score.is_mate():
                # Treat mate scores as large CP values (clamped later for UI)
                mate_in = score.mate()  # positive = mate for white, negative = mate for black
                # Use 10_000 cp for "mate is coming"
                return 10_000 if mate_in and mate_in > 0 else -10_000

            val = score.score(mate_score=10_000)
            return val
        except Exception as e:
            print(f"[GlobalStockfishEngine] Evaluation error: {e}")
            # Reset engine on error
            await self.close()
            return None

    async def close(self) -> None:
        """Close the engine if it exists."""
        if self.engine is not None:
            try:
                # Handle both SimpleEngine (synchronous) and UciProtocol (async)
                if isinstance(self.engine, chess.engine.SimpleEngine):
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.engine.quit)
                else:
                    await self.engine.quit()
            except Exception:
                pass
            self.engine = None
        if self.transport is not None:
            try:
                if not self.transport.is_closing():
                    self.transport.close()
            except Exception:
                pass
            self.transport = None

    @classmethod
    async def shutdown(cls) -> None:
        """Shutdown the global engine instance."""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None


# Convenience functions for easy access
def get_global_engine() -> Optional[GlobalStockfishEngine]:
    """Get the global Stockfish engine instance."""
    return GlobalStockfishEngine.get_instance()


async def evaluate_position(board: chess.Board) -> Optional[int]:
    """Evaluate a chess position using the global engine."""
    engine = get_global_engine()
    if engine:
        return await engine.evaluate_cp(board)
    return None


async def shutdown_global_engine() -> None:
    """Shutdown the global engine (call on application exit)."""
    await GlobalStockfishEngine.shutdown()
