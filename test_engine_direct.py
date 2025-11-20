
import sys
import os
from pathlib import Path
import chess
import chess.engine
import asyncio

# Setup path
ROOT = Path(os.getcwd())
ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'windows' / 'stockfish-windows-x86-64-avx2.exe'

print(f"Testing engine at: {ENGINE_PATH}")

async def test_engine():
    try:
        transport, engine = await chess.engine.popen_uci(str(ENGINE_PATH))
        print("Engine started successfully")
        
        board = chess.Board()
        info = await engine.analyse(board, chess.engine.Limit(time=0.1))
        print(f"Analysis result: {info}")
        print(f"Score: {info['score'].white().score()}")
        
        await engine.quit()
        print("Engine quit successfully")
    except Exception as e:
        print(f"Engine failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_engine())
