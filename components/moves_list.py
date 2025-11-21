"""
Moves List Component
A component for displaying chess moves with navigation and highlighting.
"""

from nicegui import ui


class MovesList:
    """A component for displaying and navigating chess moves."""

    def __init__(self, on_jump_to_ply=None, on_tab_change=None):
        """Initialize the moves list component.

        Args:
            on_jump_to_ply: Callback function called when a move is clicked (takes ply as argument)
            on_tab_change: Callback function called when a tab is clicked (takes tab index as argument)
        """
        self.moves_container = None
        self.tabs_container = None
        self.move_row_elements = {}  # Store references to move row elements for scrolling
        self.on_jump_to_ply = on_jump_to_ply or (lambda ply: None)
        self.on_tab_change = on_tab_change or (lambda index: None)
        self.variations = ["Main"]  # Default to single main variation
        self.current_variation_index = 0

    def create_ui(self, parent_container=None):
        """Create the moves list UI elements.

        Args:
            parent_container: Optional parent container. If None, creates its own column.
        """
        container = parent_container or ui.column().classes('flex-1 w-full overflow-y-auto pl-4 pr-0 py-2 gap-2 modern-scrollbar min-h-0')

        with container:
            # Tabs for variations
            self.tabs_container = ui.row().classes('w-full gap-1 pb-2 flex-shrink-0 overflow-x-auto')

            # Moves container
            self.moves_container = ui.column().classes('flex-1 w-full overflow-y-auto pl-4 pr-0 py-2 gap-2 modern-scrollbar min-h-0')
            with self.moves_container:
                ui.label('No game loaded').classes('text-gray-400 text-center py-8')

        return container

    def make_jump_handler(self, ply):
        """Create a click handler that jumps to the specified ply."""
        return lambda e: self.on_jump_to_ply(ply)

    def make_tab_handler(self, index):
        """Create a click handler that switches to the specified tab."""
        return lambda e: self.on_tab_change(index)

    def set_variations(self, variations, current_index=0):
        """Set the available variations and current active tab.

        Args:
            variations: List of variation names (e.g., ["Main", "Var 1", "Var 2"])
            current_index: Index of the currently active variation
        """
        self.variations = variations
        self.current_variation_index = current_index

        if self.tabs_container is None:
            return

        # Clear existing tabs
        self.tabs_container.clear()

        # Create new tabs
        with self.tabs_container:
            for i, variation_name in enumerate(variations):
                is_active = (i == current_index)
                tab_classes = 'px-3 py-1 text-sm rounded cursor-pointer flex-shrink-0'
                if is_active:
                    tab_classes += ' bg-blue-600 text-white'
                else:
                    tab_classes += ' bg-gray-700 text-gray-300 hover:bg-gray-600'

                ui.button(variation_name, on_click=self.make_tab_handler(i)).classes(tab_classes)

    def display_moves(self, move_rows=None, current_ply=0):
        """Display the moves in the list.

        Args:
            move_rows: List of (move_number, white_move, black_move) tuples
            current_ply: Current position in the game
        """
        if self.moves_container is None:
            return

        self.moves_container.clear()
        self.move_row_elements.clear()

        if move_rows is None or not move_rows:
            with self.moves_container:
                ui.label('No game loaded').classes('text-gray-400 text-center py-8')
            return

        rows = move_rows

        with self.moves_container:
            for row_index, (move_number, white_move, black_move) in enumerate(rows):
                white_ply = row_index * 2
                black_ply = white_ply + 1

                move_row = ui.row().classes('w-full justify-between py-1')
                self.move_row_elements[move_number] = move_row

                with move_row:
                    ui.label(f"{move_number}.").classes('text-gray-300 w-8')

                    # white
                    is_active_white = (white_ply + 1 == current_ply)
                    white_classes = 'text-white flex-1 text-center cursor-pointer px-2 py-1 rounded'
                    white_classes += ' bg-blue-700' if is_active_white else ' hover:bg-gray-700'
                    ui.label(white_move).classes(white_classes).on(
                        'click', self.make_jump_handler(white_ply + 1)
                    )

                    # black
                    is_active_black = (black_ply + 1 == current_ply)
                    black_classes = 'text-white flex-1 text-center cursor-pointer px-2 py-1 rounded'
                    black_classes += ' bg-blue-700' if is_active_black else ' hover:bg-gray-700'
                    black_label = ui.label(black_move).classes(black_classes)
                    if black_move:
                        black_label.on('click', self.make_jump_handler(black_ply + 1))

        # Auto-scroll to current move if we're not at the starting position
        if current_ply > 0:
            # Calculate which row contains the current move
            # Each row has 2 moves (white and black), so row number = ((ply - 1) // 2) + 1
            current_row_number = ((current_ply - 1) // 2) + 1
            if current_row_number in self.move_row_elements:
                # Use run_method to scroll the row into view
                self.move_row_elements[current_row_number].run_method('scrollIntoView', {'behavior': 'smooth', 'block': 'start'})
