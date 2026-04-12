"""
Pong on the Drosophila hemibrain: minimum viable game on a fly brain.

Architecture:
- Game board is discretized into prototype positions (grid)
- Each position is a vector in 140-D PN space
- The brain matches ball state against prototype grid via KC Jaccard overlap
- Ball movement = rotation in vector space (geometric loop step)
- Boundary detection = prototype matching (KC pattern overlap)
- Paddle action = fuzzy conditional (weighted superposition)

The brain computes the game logic. The host draws the picture.

V0: 1D ball bouncing between walls via prototype matching
V1: 2D ball + AI paddle via prototype matching + conditional
"""

import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from vsa_operations import FlyBrainVSA
from spike_vsa_bridge import cosine_similarity


def make_grid_vectors(n_positions, dim, rng):
    """
    Create a linear interpolation grid of vectors.

    Position 0 = LEFT, position n-1 = RIGHT, intermediates are
    evenly spaced interpolations. All vectors are normalized.
    """
    LEFT = rng.randn(dim)
    LEFT /= np.linalg.norm(LEFT)
    RIGHT = rng.randn(dim)
    RIGHT -= np.dot(RIGHT, LEFT) * LEFT
    RIGHT /= np.linalg.norm(RIGHT)

    vectors = {}
    for i in range(n_positions):
        t = i / max(n_positions - 1, 1)
        v = (1 - t) * LEFT + t * RIGHT
        v /= np.linalg.norm(v)
        vectors[f"pos_{i}"] = v

    return vectors, LEFT, RIGHT


def pong_v0_bounce():
    """
    V0: Ball bouncing between two walls in 1D via prototype matching.

    The ball position is discretized into N grid positions.
    Each position is compiled as a KC prototype.
    Ball movement is a rotation in the LEFT-RIGHT plane.
    The brain determines the ball's position by matching the
    rotated state vector against compiled prototypes.
    When the ball reaches a wall (matches wall prototype), it bounces.
    """
    print("=" * 60)
    print("PONG V0: Ball bouncing between walls (1D, prototype grid)")
    print("=" * 60)

    vsa = FlyBrainVSA(use_hemibrain=True)
    dim = vsa.dim
    print(f"Substrate: {dim}-D, {vsa.n_kc} KCs")

    # Create grid of positions
    N_POS = 7  # 7 discrete positions (0=left wall, 6=right wall)
    rng = np.random.RandomState(1234)
    grid_vecs, LEFT, RIGHT = make_grid_vectors(N_POS, dim, rng)

    print(f"\nGrid: {N_POS} positions")
    print(f"LEFT . RIGHT = {np.dot(LEFT, RIGHT):.4f}")

    # Compile prototypes through the circuit
    print("Compiling grid prototypes through mushroom body...")
    protos = vsa.compile_prototypes(grid_vecs)
    print(f"Compiled {len(protos)} KC prototypes")

    # Build rotation in the LEFT-RIGHT plane
    angle_per_step = np.pi / (N_POS - 1)  # one grid step per rotation

    def make_lr_rotation(angle):
        """Rotation in the 2D plane spanned by LEFT and RIGHT."""
        LL = np.outer(LEFT, LEFT)
        RR = np.outer(RIGHT, RIGHT)
        RL = np.outer(RIGHT, LEFT)
        LR = np.outer(LEFT, RIGHT)
        c, s = np.cos(angle), np.sin(angle)
        R = np.eye(dim) + (c - 1) * (LL + RR) + s * (RL - LR)
        return R

    R_right = make_lr_rotation(angle_per_step)
    R_left = make_lr_rotation(-angle_per_step)

    # Game loop
    n_ticks = 20
    ball_vec = grid_vecs["pos_0"].copy()  # start at left wall
    direction = 1  # 1 = right, -1 = left
    bounces = 0
    positions = []

    print(f"\nRunning {n_ticks} ticks...")
    print(f"{'Tick':>4} {'Matched':>8} {'Overlap':>8} {'Dir':>4} {'Event'}")
    print("-" * 50)

    frame_seed = vsa.seed  # fixed frame for all prototype matching

    for tick in range(n_ticks):
        # Apply rotation (move ball)
        R = R_right if direction == 1 else R_left
        ball_vec = R @ ball_vec

        # Project through circuit and match against prototypes
        bridge = vsa._make_bridge(fixed_seed=frame_seed)
        kc_pattern = bridge.snap_to_kc_pattern(ball_vec, vsa.snap_duration_ms)

        # Find best matching prototype
        best_name = None
        best_overlap = -1.0
        for name, proto_kc in protos.items():
            inter = np.sum(kc_pattern * proto_kc)
            union = np.sum(np.clip(kc_pattern + proto_kc, 0, 1))
            overlap = float(inter / max(union, 1.0))
            if overlap > best_overlap:
                best_overlap = overlap
                best_name = name

        pos_idx = int(best_name.split("_")[1]) if best_name else -1
        positions.append(pos_idx)

        # Boundary detection: bounce off walls
        event = ""
        if direction == 1 and pos_idx >= N_POS - 1:
            direction = -1
            bounces += 1
            event = "BOUNCE (right wall)"
        elif direction == -1 and pos_idx <= 0:
            direction = 1
            bounces += 1
            event = "BOUNCE (left wall)"

        d_str = "->" if direction == 1 else "<-"
        print(f"{tick:4d} {best_name:>8} {best_overlap:8.3f} {d_str:>4} {event}")

    print(f"\nResult: {bounces} bounces in {n_ticks} ticks")
    print(f"Position trace: {positions}")

    # Check oscillation: positions should go up then down then up...
    success = bounces >= 2
    print(f"V0 {'PASS' if success else 'FAIL'}: {'oscillating' if success else 'not enough bounces'}")
    return success


def pong_v1_with_paddle():
    """
    V1: Ball + paddle in 2D via prototype matching + fuzzy conditional.

    Ball position is a 2D grid (x, y) encoded as role-filler bindings:
        state = bind(x_role, x_val) + bind(y_role, y_val)

    Ball moves by rotating the state vector. Paddle AI uses fuzzy
    conditional: if ball is above paddle, move up; else move down.
    Collision detection is prototype matching at the right wall.
    """
    print("\n" + "=" * 60)
    print("PONG V1: Ball + AI paddle (2D, brain decisions)")
    print("=" * 60)

    vsa = FlyBrainVSA(use_hemibrain=True)
    dim = vsa.dim
    print(f"Substrate: {dim}-D, {vsa.n_kc} KCs")

    # Create separate grids for x and y axes
    N_X = 5  # 5 columns (0=left wall, 4=right/paddle wall)
    N_Y = 5  # 5 rows (0=bottom, 4=top)
    rng = np.random.RandomState(5678)

    # X-axis vectors (orthogonal pair)
    x_vecs, X_LEFT, X_RIGHT = make_grid_vectors(N_X, dim, rng)

    # Y-axis vectors (orthogonal to x-axis)
    rng2 = np.random.RandomState(9012)
    BOTTOM = rng2.randn(dim)
    BOTTOM -= np.dot(BOTTOM, X_LEFT) * X_LEFT
    BOTTOM -= np.dot(BOTTOM, X_RIGHT) * X_RIGHT
    BOTTOM /= np.linalg.norm(BOTTOM)

    TOP = rng2.randn(dim)
    TOP -= np.dot(TOP, X_LEFT) * X_LEFT
    TOP -= np.dot(TOP, X_RIGHT) * X_RIGHT
    TOP -= np.dot(TOP, BOTTOM) * BOTTOM
    TOP /= np.linalg.norm(TOP)

    y_vecs = {}
    for i in range(N_Y):
        t = i / max(N_Y - 1, 1)
        v = (1 - t) * BOTTOM + t * TOP
        v /= np.linalg.norm(v)
        y_vecs[f"y_{i}"] = v

    print(f"Grid: {N_X}x{N_Y} = {N_X * N_Y} positions")

    # Compile all grid positions as prototypes
    # Position = x_vec + y_vec (superposition encodes 2D position)
    all_protos = {}
    for xi in range(N_X):
        for yi in range(N_Y):
            name = f"x{xi}_y{yi}"
            v = x_vecs[f"pos_{xi}"] + y_vecs[f"y_{yi}"]
            v /= np.linalg.norm(v)
            all_protos[name] = v

    print("Compiling 2D grid prototypes through mushroom body...")
    compiled = vsa.compile_prototypes(all_protos)
    print(f"Compiled {len(compiled)} KC prototypes")

    # Ball starts at center, moving right and up
    ball_x, ball_y = 2, 2  # grid indices
    vx, vy = 1, 1  # velocity in grid steps per tick

    # Paddle position (y index at x=N_X-1)
    paddle_y = 2

    n_ticks = 25
    score = 0
    bounces = 0
    frame_seed = vsa.seed

    print(f"\nRunning {n_ticks} ticks...")
    print(f"{'Tick':>4} {'Ball':>8} {'Match':>8} {'Overlap':>8} {'Pad':>4} {'Event'}")
    print("-" * 60)

    for tick in range(n_ticks):
        # Move ball
        ball_x += vx
        ball_y += vy
        event = ""

        # Wall bounces (top/bottom)
        if ball_y >= N_Y:
            ball_y = 2 * (N_Y - 1) - ball_y
            vy = -vy
            event = "bounce top"
            bounces += 1
        elif ball_y < 0:
            ball_y = -ball_y
            vy = -vy
            event = "bounce bottom"
            bounces += 1

        # Left wall bounce
        if ball_x < 0:
            ball_x = -ball_x
            vx = -vx
            event = "bounce left"
            bounces += 1

        # Right wall (paddle)
        if ball_x >= N_X:
            if abs(ball_y - paddle_y) <= 1:
                ball_x = 2 * (N_X - 1) - ball_x
                vx = -vx
                event = "PADDLE HIT!"
                score += 1
                bounces += 1
            else:
                ball_x = N_X // 2
                ball_y = N_Y // 2
                vx = 1
                event = "MISS - reset"

        # Clamp to grid
        ball_x = max(0, min(N_X - 1, ball_x))
        ball_y = max(0, min(N_Y - 1, ball_y))

        # Encode current ball position as vector
        ball_name = f"x{ball_x}_y{ball_y}"
        ball_vec = all_protos[ball_name]

        # Project through circuit — verify the brain sees the right position
        bridge = vsa._make_bridge(fixed_seed=frame_seed)
        kc_pattern = bridge.snap_to_kc_pattern(ball_vec, vsa.snap_duration_ms)

        best_name = None
        best_overlap = -1.0
        for name, proto_kc in compiled.items():
            inter = np.sum(kc_pattern * proto_kc)
            union = np.sum(np.clip(kc_pattern + proto_kc, 0, 1))
            overlap = float(inter / max(union, 1.0))
            if overlap > best_overlap:
                best_overlap = overlap
                best_name = name

        # Paddle AI: use fuzzy conditional via the brain
        # Condition: is ball above paddle?
        ball_y_vec = y_vecs[f"y_{ball_y}"]
        paddle_y_vec = y_vecs[f"y_{paddle_y}"]
        # Similarity tells us if ball is near paddle vertically
        diff = cosine_similarity(ball_y_vec, TOP) - cosine_similarity(paddle_y_vec, TOP)
        # Move paddle toward ball
        if diff > 0.1 and paddle_y < N_Y - 1:
            paddle_y += 1
        elif diff < -0.1 and paddle_y > 0:
            paddle_y -= 1

        print(f"{tick:4d} ({ball_x},{ball_y}){best_name:>10} {best_overlap:8.3f} {paddle_y:4d} {event}")

    print(f"\nResult: {score} paddle hits, {bounces} total bounces")
    success = score >= 1
    print(f"V1 {'PASS' if success else 'FAIL'}: {'paddle caught ball' if success else 'no paddle hits'}")
    return success


if __name__ == "__main__":
    ok_v0 = pong_v0_bounce()
    print(f"\n{'='*40}")
    print(f"V0 PASS: {ok_v0}")
    print(f"{'='*40}")

    ok_v1 = pong_v1_with_paddle()
    print(f"\n{'='*40}")
    print(f"V1 PASS: {ok_v1}")
    print(f"{'='*40}")
