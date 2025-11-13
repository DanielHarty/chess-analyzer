import unittest
import sys
from pathlib import Path

# Add parent directory to path so we can import game_model
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game_model import GameModel

class TestGameModel(unittest.TestCase):
    def test_kasparov_topalov_game(self):
        """Test loading and stepping through the Kasparov-Topalov 1999 game."""
        # Load the PGN file
        pgn_path = ROOT / 'kasparov_topalov_1999.pgn'
        pgn_text = pgn_path.read_text(encoding='utf-8')

        # Create game model and load PGN
        model = GameModel()
        model.load_pgn_text(pgn_text)

        # Verify initial state
        self.assertEqual(model.current_ply, 0)
        total_moves = len(model.moves)
        self.assertGreater(total_moves, 0)  # Should have moves loaded

        # Step through all moves to the end
        move_count = 0
        while True:
            result = model.step_forward()
            if result is None:
                break
            move_count += 1

        # Assert final state
        self.assertEqual(model.current_ply, total_moves)
        self.assertEqual(move_count, total_moves)
        # Consistency check: current_ply should equal the total number of moves
        self.assertEqual(model.current_ply, len(model.moves))

        # Assert final FEN to verify we reached a valid end position
        # The game ends with Kasparov winning
        final_fen = model.board.fen() if model.board else None
        self.assertIsNotNone(final_fen)

        # Validate FEN structure: should have exactly 6 space-separated parts
        parts = final_fen.split()
        self.assertEqual(len(parts), 6, f"FEN should have 6 parts, got {len(parts)}")

        # Basic validation of FEN components
        board_part, side_to_move, castling, en_passant, halfmove_clock, fullmove_number = parts
        self.assertIn(side_to_move, ('w', 'b'), f"Side to move should be 'w' or 'b', got '{side_to_move}'")
        self.assertRegex(board_part, r'^[prnbqkPRNBQK1-8/]+$', "Board part should only contain valid piece symbols, digits, and slashes")

        # Validate fullmove number is a positive integer
        fullmove_num = int(fullmove_number)
        self.assertGreater(fullmove_num, 0, f"Fullmove number should be > 0, got {fullmove_num}")

    def test_navigation_edge_cases(self):
        """Test edge cases for navigation methods."""
        # Load the PGN file
        pgn_path = ROOT / 'kasparov_topalov_1999.pgn'
        pgn_text = pgn_path.read_text(encoding='utf-8')

        # Create game model and load PGN
        model = GameModel()
        model.load_pgn_text(pgn_text)

        # Test go_to_ply with out-of-bounds values
        model.go_to_ply(0)  # Should clamp to start
        self.assertEqual(model.current_ply, 0)

        model.go_to_ply(9999)  # Should clamp to end
        self.assertEqual(model.current_ply, len(model.moves))

        # Go back to ply 0 to test step_back from start
        model.go_to_ply(0)
        self.assertEqual(model.current_ply, 0)

        # Test step_back from ply 0 (should do nothing)
        result = model.step_back()
        self.assertIsNone(result)  # Should return None
        self.assertEqual(model.current_ply, 0)  # Should not change

if __name__ == '__main__':
    unittest.main()
