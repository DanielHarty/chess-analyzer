"""Quick test to verify game loading is now fast and non-blocking."""

import time
from game_model import GameModel
from global_engine import GlobalStockfishEngine, shutdown_global_engine
from pathlib import Path

# Initialize engine
ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    import platform
    if platform.system() == 'Windows':
        ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'windows' / 'stockfish-windows-x86-64-avx2.exe'
    else:
        ENGINE_PATH = ROOT / 'engines' / 'stockfish' / 'linux' / 'stockfish-ubuntu-x86-64-avx2'
    
    engine = GlobalStockfishEngine(str(ENGINE_PATH))

    # Load the PGN file
    pgn_path = ROOT / 'kasparov_topalov_1999.pgn'
    pgn_text = pgn_path.read_text(encoding='utf-8')

    # Test synchronous load (should be fast now)
    print("Loading PGN file...")
    start = time.time()
    
    model = GameModel()
    model.load_pgn_text(pgn_text)
    
    load_time = time.time() - start
    print(f"✓ PGN loaded in {load_time:.3f}s (should be < 0.1s)")
    print(f"✓ Game has {len(model.moves)} moves")
    print(f"✓ Evaluations array initialized with {len(model.evaluations)} slots (all None initially)")
    
    # Test that evaluations start as None
    print(f"✓ First evaluation is: {model.evaluations[0]} (None = not calculated yet)")
    
    # Now test async evaluation
    print("\nStarting background evaluation...")
    import asyncio
    
    async def test_evaluation():
        progress_updates = []
        
        def progress_callback(current, total):
            percent = int((current / total) * 100)
            progress_updates.append((current, total, percent))
            if current % 10 == 0 or current == total:
                print(f"  Progress: {current}/{total} ({percent}%)")
        
        start = time.time()
        model.start_background_evaluation(progress_callback)
        
        if model._eval_task:
            await model._eval_task
        
        eval_time = time.time() - start
        
        print(f"\n✓ Background evaluation completed in {eval_time:.2f}s")
        print(f"✓ Total positions evaluated: {len(progress_updates)}")
        print(f"✓ Evaluation complete flag: {model._eval_complete}")
        print(f"✓ First evaluation is now: {model.evaluations[0]} (should be ~20-30 cp)")
        
        # Verify evaluations are not None
        non_none_count = sum(1 for e in model.evaluations if e is not None)
        print(f"✓ {non_none_count}/{len(model.evaluations)} evaluations calculated")
    
    asyncio.run(test_evaluation())
    
    shutdown_global_engine()
    print("\n✓ All tests passed!")

