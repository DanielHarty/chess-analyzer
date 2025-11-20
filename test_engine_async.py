
import sys
import os
from pathlib import Path
import chess
import chess.engine
import asyncio
from global_engine import GlobalStockfishEngine, evaluate_position

# Setup path
ROOT = Path(os.getcwd())
ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'windows' / 'stockfish-windows-x86-64-avx2.exe'

print(f"Testing GlobalStockfishEngine at: {ENGINE_PATH}")

# Initialize singleton
GlobalStockfishEngine(str(ENGINE_PATH))

async def test_async_eval():
    print("Starting async eval test")
    board = chess.Board()
    
    try:
        # Simulate what game_model.py does
        score = await asyncio.to_thread(evaluate_position, board)
        print(f"Evaluation result: {score}")
    except Exception as e:
        print(f"Async evaluation failed: {e}")

    GlobalStockfishEngine.shutdown()

if __name__ == "__main__":
    asyncio.run(test_async_eval())
