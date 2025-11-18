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

    function pieceToUnicode(symbol) {
        const map = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
        };
        return map[symbol] || '?';
    }

    let position = {}; // { "e2": "P", ... }
    let currentAnimation = null; // State for active animation

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

        // Labels
        ctx.font = (size * 0.2) + 'px system-ui';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'bottom';
        for (let f = 0; f < 8; f++) {
            const file = String.fromCharCode(97 + f);
            const light = (7 + f) % 2 === 0;
            ctx.fillStyle = light ? '#000000' : '#FFFFFF';
            ctx.fillText(file, f * size + size - 3, 7 * size + size - 3);
        }

        ctx.textBaseline = 'top';
        ctx.textAlign = 'left';
        for (let r = 0; r < 8; r++) {
            const rank = (8 - r).toString();
            const light = (r + 0) % 2 === 0;
            ctx.fillStyle = light ? '#000000' : '#FFFFFF';
            ctx.fillText(rank, 0 * size + 3, r * size + 3);
        }
    }

    function drawPiece(piece, x, y, size) {
        const glyph = pieceToUnicode(piece);
        const cx = x + size / 2;
        const cy = y + size / 2;
        const isWhite = (piece === piece.toUpperCase());

        ctx.font = (size * 0.7) + 'px system-ui';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.lineWidth = size * 0.08;
        ctx.shadowBlur = size * 0.15;

        if (isWhite) {
            ctx.fillStyle = '#FFFFFF';
            ctx.strokeStyle = 'rgba(0, 0, 0, 0.9)';
            ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
        } else {
            ctx.fillStyle = '#000000';
            ctx.strokeStyle = 'transparent';
            ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
        }

        ctx.strokeText(glyph, cx, cy);
        ctx.fillText(glyph, cx, cy);
        
        // Reset shadow
        ctx.shadowBlur = 0;
        ctx.shadowColor = 'transparent';
    }

    function draw() {
        if (!canvas.width) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawBoard();

        // Draw static pieces
        for (const square in position) {
            if (!Object.prototype.hasOwnProperty.call(position, square)) continue;

            // If animating, skip pieces that are involved in the animation
            // The animation object will handle drawing them
            if (currentAnimation && currentAnimation.hiddenSquares.has(square)) {
                continue;
            }

            const piece = position[square];
            const { x, y, size } = squareToXY(square);
            drawPiece(piece, x, y, size);
        }

        // Draw animating pieces
        if (currentAnimation) {
            const now = Date.now();
            const progress = Math.min(1, (now - currentAnimation.startTime) / currentAnimation.durationMs);

            currentAnimation.pieces.forEach(animPiece => {
                const fromXY = squareToXY(animPiece.from);
                const toXY = squareToXY(animPiece.to);

                const curX = fromXY.x + (toXY.x - fromXY.x) * progress;
                const curY = fromXY.y + (toXY.y - fromXY.y) * progress;

                drawPiece(animPiece.symbol, curX, curY, fromXY.size);
            });

            if (progress < 1) {
                requestAnimationFrame(draw);
            } else {
                // Animation complete: Snap to final state
                position = currentAnimation.finalPosition;
                currentAnimation = null;
                draw();
            }
        }
    }

    function animateTransition(startPos, endPos, moveType, moveDetails) {
        // Prepare animation data
        const durationMs = 250;
        const hiddenSquares = new Set();
        const piecesToAnimate = [];

        if (moveType === 'simple') {
            // Simple move: One piece moving
            const { from, to, symbol } = moveDetails;
            hiddenSquares.add(from); 
            // Note: We don't hide 'to' in startPos because it might be a capture (we want to see the captured piece until covered? 
            // Actually, usually captures replace instantly or sit under. Let's just hide 'from'.
            // If we want to show capture, we leave the 'to' piece visible until the moving piece arrives. 
            // Simpler: Start state is startPos. We hide the moving piece at 'from'.
            
            piecesToAnimate.push({ symbol, from, to });
        } else if (moveType === 'castling') {
            // Castling: King and Rook moving
            const { kingFrom, kingTo, rookFrom, rookTo, kingSymbol, rookSymbol } = moveDetails;

            hiddenSquares.add(kingFrom);
            hiddenSquares.add(rookFrom);

            piecesToAnimate.push({ symbol: kingSymbol, from: kingFrom, to: kingTo });
            piecesToAnimate.push({ symbol: rookSymbol, from: rookFrom, to: rookTo });
        } else if (moveType === 'en_passant') {
            // En passant: Pawn moves diagonally, captured pawn disappears
            const { pawnFrom, pawnTo, pawnSymbol, capturedSquare } = moveDetails;

            hiddenSquares.add(pawnFrom);
            hiddenSquares.add(capturedSquare); // Hide the captured pawn

            piecesToAnimate.push({ symbol: pawnSymbol, from: pawnFrom, to: pawnTo });
            // The captured pawn will simply disappear (not animated)
        }

        // Set immediate state to startPos (ensure we start from clean slate)
        position = startPos;

        currentAnimation = {
            startTime: Date.now(),
            durationMs,
            finalPosition: endPos,
            hiddenSquares,
            pieces: piecesToAnimate
        };

        draw();
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
        currentAnimation = null;
        position = pos || {};
        draw();
    };

    // Unified animation function
    // args: { startPos: {}, endPos: {}, type: 'simple'|'castling', details: {...} }
    window.chessAnim.animateMoveWithState = function (args) {
        animateTransition(args.startPos, args.endPos, args.type, args.details);
    };

    resize();
})();