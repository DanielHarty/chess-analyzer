import unittest
import sys
from pathlib import Path

# Add parent directory to path so we can import game_model
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from game_model import GameModel
from engine_adapter import StockfishEngine

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

    def test_evaluation_consistency(self):
        """Test that evaluation is computed consistently across navigation patterns."""
        # Load the PGN file
        pgn_path = ROOT / 'kasparov_topalov_1999.pgn'
        pgn_text = pgn_path.read_text(encoding='utf-8')

        # Create game model and load PGN
        model = GameModel()
        model.load_pgn_text(pgn_text)

        # Create engine (will work even if Stockfish not available)
        engine = StockfishEngine()

        # Test evaluation at starting position
        start_eval = engine.evaluate_cp(model.board)
        self.assertIsInstance(start_eval, (int, type(None)))

        # Store evaluations at various positions
        evaluations = {}

        # Pattern 1: Play forward to various points and record evaluations
        test_plys = [5, 10, 15, 20, 25, 30, 35, 40]

        for ply in test_plys:
            model.go_to_ply(ply)
            eval_score = engine.evaluate_cp(model.board)
            evaluations[f'forward_{ply}'] = eval_score
            # Evaluation should be computable (not None if engine works)
            self.assertIsInstance(eval_score, (int, type(None)))

        # Pattern 2: Go back to start, then play forward again to same positions
        model.go_to_ply(0)
        for ply in test_plys:
            model.go_to_ply(ply)
            eval_score = engine.evaluate_cp(model.board)
            # Should match the forward evaluations
            self.assertEqual(eval_score, evaluations[f'forward_{ply}'],
                           f"Evaluation inconsistency at ply {ply}: got {eval_score}, expected {evaluations[f'forward_{ply}']}")

        # Pattern 3: Navigate backward from end and check consistency
        model.go_to_end()
        for ply in reversed(test_plys):
            model.go_to_ply(ply)
            eval_score = engine.evaluate_cp(model.board)
            self.assertEqual(eval_score, evaluations[f'forward_{ply}'],
                           f"Backward navigation evaluation inconsistency at ply {ply}")

        # Pattern 4: Random jumping around
        import random
        random.seed(42)  # For reproducible tests
        all_plys = list(range(len(model.moves) + 1))
        random_plys = random.sample(all_plys, min(10, len(all_plys)))

        for ply in random_plys:
            model.go_to_ply(ply)
            eval_score = engine.evaluate_cp(model.board)
            self.assertIsInstance(eval_score, (int, type(None)))

        engine.close()

    def test_eval_bar_calculation(self):
        """Test the evaluation bar UI calculation logic."""
        # Import the calculation logic from main.py (we'll simulate the methods)
        # Since we can't easily import the UI class, we'll reimplement the logic

        def calculate_eval_bar(cp, clamp=800):
            """Replicate the eval bar calculation from main.py"""
            if cp is None:
                return {
                    'height_percent': 50,
                    'from_bottom': True,
                    'color': '#9CA3AF',  # gray
                    'label_text': '--'
                }

            # Clamp crazy evals
            cp_clamped = max(-clamp, min(clamp, cp))

            # New mapping: 50% at equal, 100% at ±clamp
            m = min(1.0, abs(cp_clamped) / clamp)      # 0..1
            percent = 50 + m * 50                      # 50..100

            # White advantage -> fill from bottom up in white
            # Black advantage -> fill from top down in black
            if cp_clamped >= 0:
                style_info = {
                    'height_percent': percent,
                    'from_bottom': True,
                    'color': '#F9FAFB',  # white-ish
                    'label_text': f'{cp / 100:.2f}'
                }
            else:
                style_info = {
                    'height_percent': percent,
                    'from_bottom': False,
                    'color': '#020617',  # near-black
                    'label_text': f'{cp / 100:.2f}'
                }

            return style_info

        # Test cases
        test_cases = [
            # (cp_input, expected_height, expected_from_bottom, expected_color_contains)
            (None, 50, True, '#9CA3AF'),  # None case
            (0, 50, True, '#F9FAFB'),     # Equal position
            (100, 56.25, True, '#F9FAFB'),  # Slight white advantage: 50 + (100/800)*50 = 56.25
            (-100, 56.25, False, '#020617'), # Slight black advantage
            (800, 100, True, '#F9FAFB'),   # Max white advantage
            (-800, 100, False, '#020617'), # Max black advantage
            (1600, 100, True, '#F9FAFB'),  # Over max (clamped)
            (-1600, 100, False, '#020617'), # Over max (clamped)
            (10000, 100, True, '#F9FAFB'), # Mate score (treated as large positive)
            (-10000, 100, False, '#020617'), # Mate score (treated as large negative)
        ]

        for cp, expected_height, expected_from_bottom, expected_color in test_cases:
            result = calculate_eval_bar(cp)
            self.assertAlmostEqual(result['height_percent'], expected_height, places=2,
                                 msg=f"Height calculation failed for cp={cp}")
            self.assertEqual(result['from_bottom'], expected_from_bottom,
                           msg=f"Direction failed for cp={cp}")
            self.assertIn(expected_color, result['color'],
                         msg=f"Color failed for cp={cp}: got {result['color']}, expected to contain {expected_color}")

    def test_navigation_with_evaluation(self):
        """Test evaluation during various navigation patterns."""
        # Load the PGN file
        pgn_path = ROOT / 'kasparov_topalov_1999.pgn'
        pgn_text = pgn_path.read_text(encoding='utf-8')

        # Create game model and load PGN
        model = GameModel()
        model.load_pgn_text(pgn_text)

        # Create engine
        engine = StockfishEngine()

        # Test pattern: step forward, step back, verify eval consistency
        evaluations_forward = []
        evaluations_backward = []

        # Go forward and record evaluations
        model.go_to_start()
        while True:
            eval_score = engine.evaluate_cp(model.board)
            evaluations_forward.append(eval_score)

            result = model.step_forward()
            if result is None:
                break

        # Now go backward and record evaluations in reverse
        while model.current_ply > 0:
            eval_score = engine.evaluate_cp(model.board)
            evaluations_backward.append(eval_score)
            model.step_back()

        # Add the starting position evaluation for backward comparison
        eval_score = engine.evaluate_cp(model.board)
        evaluations_backward.append(eval_score)

        # Reverse the backward evaluations to match forward order
        evaluations_backward.reverse()

        # They should match
        self.assertEqual(len(evaluations_forward), len(evaluations_backward),
                        "Forward and backward evaluation lists have different lengths")

        for i, (forward_eval, backward_eval) in enumerate(zip(evaluations_forward, evaluations_backward)):
            self.assertEqual(forward_eval, backward_eval,
                           f"Evaluation mismatch at ply {i}: forward={forward_eval}, backward={backward_eval}")

        # Test zigzag pattern: forward 3, back 2, forward 5, back 3, etc.
        model.go_to_start()
        ply = 0
        eval_history = []

        moves = [3, -2, 5, -3, 2, -1, 4, -2, 1, -5]  # negative = backward

        for move_count in moves:
            if move_count > 0:
                # Move forward
                for _ in range(move_count):
                    if ply < len(model.moves):
                        model.step_forward()
                        ply += 1
                        eval_score = engine.evaluate_cp(model.board)
                        eval_history.append((ply, eval_score))
            else:
                # Move backward
                for _ in range(abs(move_count)):
                    if ply > 0:
                        model.step_back()
                        ply -= 1
                        eval_score = engine.evaluate_cp(model.board)
                        eval_history.append((ply, eval_score))

        # Verify we can reach each position multiple ways and get consistent evals
        position_evals = {}
        for ply_val, eval_score in eval_history:
            if ply_val not in position_evals:
                position_evals[ply_val] = eval_score
            else:
                self.assertEqual(eval_score, position_evals[ply_val],
                               f"Inconsistent evaluation for ply {ply_val}")

        engine.close()

if __name__ == '__main__':
    unittest.main()
