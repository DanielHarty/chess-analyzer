"""
Chess.com Game Loader Dialog Component
A component for loading games from chess.com by username.
"""

import asyncio
import httpx
from nicegui import ui
from datetime import datetime


class ChesscomDialog:
    """A dialog component for loading games from chess.com."""

    def __init__(self, on_game_selected=None):
        """Initialize the chess.com dialog component.

        Args:
            on_game_selected: Callback function called when a game is selected (takes PGN string as argument)
        """
        self.dialog = None
        self.username_input = None
        self.games_container = None
        self.loading_spinner = None
        self.error_label = None
        self.games_list = []
        self.on_game_selected = on_game_selected or (lambda pgn: None)

    def show(self):
        """Show the chess.com dialog."""
        if self.dialog:
            self.dialog.open()
        else:
            self._create_dialog()
            self.dialog.open()

    def _create_dialog(self):
        """Create the dialog UI elements."""
        self.dialog = ui.dialog().props('persistent')
        
        with self.dialog, ui.card().classes('w-[800px] max-h-[90vh]'):
            # Header
            with ui.row().classes('w-full items-center justify-between mb-4'):
                ui.label('Load Game from Chess.com').classes('text-xl font-bold')
                ui.button(icon='close', on_click=self.dialog.close).props('flat round dense')

            # Username input section
            with ui.row().classes('w-full gap-2 mb-4'):
                self.username_input = ui.input(
                    label='Chess.com Username',
                    placeholder='Enter username...'
                ).classes('flex-grow').on('keydown.enter', self._fetch_games)
                
                ui.button(
                    'Load Games',
                    icon='search',
                    on_click=self._fetch_games
                ).props('color=primary')

            # Error message area
            self.error_label = ui.label('').classes('text-red-500 mb-2')
            self.error_label.visible = False

            # Loading spinner
            self.loading_spinner = ui.spinner(size='lg').classes('mx-auto')
            self.loading_spinner.visible = False

            # Games list container
            with ui.scroll_area().classes('w-full h-96 border border-gray-700 rounded p-2'):
                self.games_container = ui.column().classes('w-full gap-2')
                with self.games_container:
                    ui.label('Enter a username to load recent games').classes('text-gray-400 text-center p-8')

    async def _fetch_games(self):
        """Fetch recent games from chess.com."""
        username = self.username_input.value.strip()
        if not username:
            self._show_error('Please enter a username')
            return

        self._show_loading()
        self._hide_error()

        try:
            # Fetch the archives list to get the most recent month
            async with httpx.AsyncClient(timeout=30.0) as client:
                archives_url = f'https://api.chess.com/pub/player/{username}/games/archives'
                response = await client.get(archives_url)
                
                if response.status_code == 404:
                    self._show_error(f'User "{username}" not found on Chess.com')
                    self._hide_loading()
                    return
                
                response.raise_for_status()
                archives = response.json()
                
                if not archives.get('archives'):
                    self._show_error('No games found for this user')
                    self._hide_loading()
                    return

                # Get the most recent archive
                latest_archive = archives['archives'][-1]
                
                # Fetch games from the latest archive
                games_response = await client.get(latest_archive)
                games_response.raise_for_status()
                games_data = games_response.json()

                # Process and display games
                self._display_games(games_data.get('games', []), username)
                
        except httpx.HTTPError as e:
            self._show_error(f'Network error: {str(e)}')
        except Exception as e:
            self._show_error(f'Error: {str(e)}')
        finally:
            self._hide_loading()

    def _display_games(self, games, username):
        """Display the fetched games in the dialog.

        Args:
            games: List of game data from chess.com API
            username: The username whose games we're displaying
        """
        self.games_container.clear()
        
        if not games:
            with self.games_container:
                ui.label('No games found').classes('text-gray-400 text-center p-8')
            return

        # Filter for games with PGN data and sort by most recent
        valid_games = [g for g in games if 'pgn' in g]
        valid_games.reverse()  # Most recent first

        self.games_list = valid_games

        with self.games_container:
            ui.label(f'Found {len(valid_games)} recent games').classes('text-sm text-gray-400 mb-2')
            
            for i, game in enumerate(valid_games[:50]):  # Limit to 50 most recent
                self._create_game_card(i, game, username)

    def _create_game_card(self, index, game, username):
        """Create a card for a single game.

        Args:
            index: Index of the game in the list
            game: Game data from chess.com API
            username: The username whose games we're displaying
        """
        white = game.get('white', {}).get('username', 'Unknown')
        black = game.get('black', {}).get('username', 'Unknown')
        white_result = game.get('white', {}).get('result', '')
        black_result = game.get('black', {}).get('result', '')
        time_control = game.get('time_control', 'Unknown')
        time_class = game.get('time_class', '')
        
        # Parse date
        end_time = game.get('end_time', 0)
        date_str = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M') if end_time else 'Unknown'
        
        # Determine result display
        result_display = self._format_result(white_result, black_result, white, black, username)
        
        with ui.card().classes('w-full p-3 cursor-pointer hover:bg-gray-700 transition-colors').on('click', lambda i=index: self._select_game(i)):
            with ui.row().classes('w-full items-center justify-between'):
                # Game info
                with ui.column().classes('gap-1 flex-grow'):
                    with ui.row().classes('items-center gap-2'):
                        ui.label(f'{white} vs {black}').classes('font-semibold')
                        ui.badge(result_display, color='primary' if 'won' in result_display.lower() else 'grey').classes('text-xs')
                    
                    with ui.row().classes('gap-4 text-sm text-gray-400'):
                        ui.label(f'📅 {date_str}')
                        ui.label(f'⏱️ {time_class.title()} ({time_control})')
                
                # Arrow icon
                ui.icon('chevron_right').classes('text-gray-400')

    def _format_result(self, white_result, black_result, white, black, username):
        """Format the game result for display.

        Args:
            white_result: Result for white player
            black_result: Result for black player
            white: White player username
            black: Black player username
            username: The username whose games we're displaying

        Returns:
            Formatted result string
        """
        username_lower = username.lower()
        
        if white.lower() == username_lower:
            if white_result == 'win':
                return 'Won'
            elif white_result == 'lose':
                return 'Lost'
            elif 'draw' in white_result or 'agreed' in white_result or 'stalemate' in white_result:
                return 'Draw'
            else:
                return white_result.title()
        elif black.lower() == username_lower:
            if black_result == 'win':
                return 'Won'
            elif black_result == 'lose':
                return 'Lost'
            elif 'draw' in black_result or 'agreed' in black_result or 'stalemate' in black_result:
                return 'Draw'
            else:
                return black_result.title()
        else:
            # Neither player is the searched username (shouldn't happen)
            if white_result == 'win':
                return '1-0'
            elif black_result == 'win':
                return '0-1'
            else:
                return '½-½'

    def _select_game(self, index):
        """Handle game selection.

        Args:
            index: Index of the selected game
        """
        if 0 <= index < len(self.games_list):
            game = self.games_list[index]
            pgn = game.get('pgn', '')
            
            if pgn:
                # Close the dialog
                self.dialog.close()
                
                # Call the callback with the PGN
                self.on_game_selected(pgn)
                
                ui.notify('Game loaded successfully!', type='positive')
            else:
                ui.notify('No PGN data available for this game', type='negative')

    def _show_loading(self):
        """Show the loading spinner."""
        if self.loading_spinner:
            self.loading_spinner.visible = True

    def _hide_loading(self):
        """Hide the loading spinner."""
        if self.loading_spinner:
            self.loading_spinner.visible = False

    def _show_error(self, message):
        """Show an error message.

        Args:
            message: The error message to display
        """
        if self.error_label:
            self.error_label.text = message
            self.error_label.visible = True

    def _hide_error(self):
        """Hide the error message."""
        if self.error_label:
            self.error_label.visible = False

