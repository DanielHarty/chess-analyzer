"""
Evaluation Chart Component
A plotly-based component for displaying chess position evaluation over time.
"""

import plotly.graph_objects as go
from nicegui import ui


class EvalChart:
    """A plotly evaluation chart component for chess game analysis."""

    def __init__(self):
        """Initialize the evaluation chart component."""
        self.eval_chart = None

    def create_ui(self, parent_container=None):
        """Create the evaluation chart UI elements.

        Args:
            parent_container: Optional parent container. If None, creates its own column.
        """
        container = parent_container or ui.column().classes('w-full p-3 border-b border-gray-700 flex-shrink-0')

        with container:
            initial_fig = self.create_eval_chart_figure()
            self.eval_chart = ui.plotly(initial_fig).classes('w-full')

        return container

    def create_eval_chart_figure(self, current_game=None, evaluations=None, current_ply=0):
        """Create a plotly figure for the evaluation chart.

        Args:
            current_game: The current chess game (used to check if game exists)
            evaluations: List of evaluation scores
            current_ply: Current position in the game

        Returns:
            Plotly figure object
        """
        if not current_game:
            # Empty chart when no game is loaded
            fig = go.Figure()
            fig.update_layout(
                title="Evaluation",
                xaxis_title="Move",
                yaxis_title="Pawns",
                template="plotly_dark",
                height=220,
                margin=dict(l=35, r=10, t=35, b=35),
                plot_bgcolor='rgba(31, 41, 55, 1)',
                paper_bgcolor='rgba(31, 41, 55, 1)',
                font=dict(size=10),
            )
            return fig

        # Get evaluations and convert to pawns (divide by 100)
        evals = evaluations or []
        move_numbers = list(range(len(evals)))

        # Convert centipawns to pawns, handling None values
        eval_pawns = []
        valid_moves = []
        for i, ev in enumerate(evals):
            if ev is not None:
                # Clamp extreme values for better visualization
                clamped = max(-30, min(30, ev / 100))
                eval_pawns.append(clamped)
                valid_moves.append(i)

        # Create the line trace
        fig = go.Figure()

        if eval_pawns:
            fig.add_trace(go.Scatter(
                x=valid_moves,
                y=eval_pawns,
                mode='lines',
                name='Evaluation',
                line=dict(color='#60A5FA', width=2),
                hovertemplate='Move %{x}<br>Eval: %{y:.2f}<extra></extra>'
            ))

            # Add a marker for the current position
            if current_ply < len(evals) and evals[current_ply] is not None:
                current_eval = max(-30, min(30, evals[current_ply] / 100))
                fig.add_trace(go.Scatter(
                    x=[current_ply],
                    y=[current_eval],
                    mode='markers',
                    name='Current Position',
                    marker=dict(size=10, color='#F59E0B', symbol='circle'),
                    hovertemplate='Current<br>Move %{x}<br>Eval: %{y:.2f}<extra></extra>'
                ))

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

        fig.update_layout(
            title="Evaluation",
            xaxis_title="Move",
            yaxis_title="Pawns",
            template="plotly_dark",
            height=220,
            margin=dict(l=35, r=10, t=35, b=35),
            plot_bgcolor='rgba(31, 41, 55, 1)',
            paper_bgcolor='rgba(31, 41, 55, 1)',
            hovermode='x unified',
            showlegend=False,
            font=dict(size=10),
            xaxis=dict(
                gridcolor='rgba(75, 85, 99, 0.3)',
                dtick=5 if len(evals) > 30 else 2,
            ),
            yaxis=dict(
                gridcolor='rgba(75, 85, 99, 0.3)',
                range=[-10, 10] if max(abs(min(eval_pawns, default=0)), abs(max(eval_pawns, default=0))) <= 10 else None
            ),
        )

        return fig

    def update_eval_chart(self, current_game=None, evaluations=None, current_ply=0):
        """Update the plotly evaluation chart.

        Args:
            current_game: The current chess game (used to check if game exists)
            evaluations: List of evaluation scores
            current_ply: Current position in the game
        """
        if self.eval_chart is None:
            return

        fig = self.create_eval_chart_figure(current_game, evaluations, current_ply)
        self.eval_chart.update_figure(fig)
