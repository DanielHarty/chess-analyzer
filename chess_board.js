(function () {
    const root = document.getElementById('chess_board_root');
    const canvas = document.getElementById('chess_board_canvas');

    if (!root || !canvas) {
        console.warn('Chess board root/canvas not found');
        return;
    }

    const ctx = canvas.getContext('2d');

    function squareToXY(square) {
        const file = square.charCodeAt(0) - 'a'.charCodeAt(0); // 0..7
        const rank = parseInt(square[1], 10) - 1;              // 0..7
        const size = canvas.width / 8;
        const x = file * size;
        const y = (7 - rank) * size; // rank 1 at bottom
        return { x, y, size };
    }

    function drawBoard() {
        if (!canvas.width) return;

        const size = canvas.width / 8;

        for (let r = 0; r < 8; r++) {
            for (let f = 0; f < 8; f++) {
                const light = (r + f) % 2 === 0;
                ctx.fillStyle = light ? '#FEF3C7' : '#92400E';
                ctx.fillRect(f * size, r * size, size, size);
            }
        }

        // Add coordinate labels only on bottom row and left column
        ctx.font = (size * 0.2) + 'px system-ui';
        ctx.textAlign = 'right';

        // Bottom row: file letters (a-h) in bottom-right corner
        ctx.textBaseline = 'bottom';
        for (let f = 0; f < 8; f++) {
            const file = String.fromCharCode(97 + f); // a-h
            const light = (7 + f) % 2 === 0;
            ctx.fillStyle = light ? '#000000' : '#FFFFFF';
            ctx.fillText(file, f * size + size - 3, 7 * size + size - 3);
        }

        // Left column: rank numbers (8-1) in top-left corner
        ctx.textBaseline = 'top';
        ctx.textAlign = 'left';
        for (let r = 0; r < 8; r++) {
            const rank = (8 - r).toString(); // 8-1
            const light = (r + 0) % 2 === 0;
            ctx.fillStyle = light ? '#000000' : '#FFFFFF';
            ctx.fillText(rank, 0 * size + 3, r * size + 3);
        }
    }

    function pieceToUnicode(symbol) {
        const map = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
        };
        return map[symbol] || '?';
    }

    let position = {}; // { "e2": "P", ... }

    function draw() {
        if (!canvas.width) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawBoard();

        const size = canvas.width / 8;
        ctx.font = (size * 0.7) + 'px system-ui';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        for (const square in position) {
            if (!Object.prototype.hasOwnProperty.call(position, square)) continue;

            const piece = position[square];
            const glyph = pieceToUnicode(piece);
            const { x, y, size: s } = squareToXY(square);
            const cx = x + s / 2;
            const cy = y + s / 2;
            const isWhite = (piece === piece.toUpperCase());

            // Outline + shadow settings
            ctx.lineWidth = size * 0.08;
            ctx.shadowBlur = size * 0.15;

            if (isWhite) {
                // White pieces: dark outline + strong shadow
                ctx.fillStyle = '#FFFFFF';
                ctx.strokeStyle = 'rgba(0, 0, 0, 0.9)';
                ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
            } else {
                // Black pieces: no outline + shadow
                ctx.fillStyle = '#000000';
                ctx.strokeStyle = 'transparent';
                ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
            }

            ctx.strokeText(glyph, cx, cy);
            ctx.fillText(glyph, cx, cy);
        }

        ctx.shadowBlur = 0;
        ctx.shadowColor = 'transparent';
    }

    function resize() {
        const rect = root.getBoundingClientRect();
        const size = Math.min(rect.width, rect.height);
        canvas.width = size;
        canvas.height = size;
        draw();
    }

    window.addEventListener('resize', resize);
    window.chessAnim = window.chessAnim || {};
    window.chessAnim.setPosition = function (pos) {
        position = pos || {};
        draw();
    };

    resize();
})();
