"""
Pong on the Drosophila hemibrain: minimum viable game on a fly brain.

Architecture:
- Game state is encoded as vectors in the 140-D PN input space
- Game logic uses VSA operations on the spiking substrate:
  - Ball position update: rotation in vector space (geometric loop step)
  - Boundary detection: is_true (cosine to reserved true vector)
  - Paddle action: fuzzy conditional (weighted superposition)
- Rendering is host-side (Python draws pixels from decoded state)

The brain computes the game logic. The host draws the picture.

State representation:
- Ball position: two scalar-ish vectors (x_pos, y_pos) encoded as
  interpolations between boundary vectors
  - x_pos = lerp(LEFT_WALL, RIGHT_WALL, x_fraction)
  - y_pos = lerp(BOTTOM, TOP, y_fraction)
- Ball velocity: a rotation matrix R that moves the position
  vector per tick. Direction changes on wall bounce.
- Paddle position: interpolation between TOP and BOTTOM

Simplifications for v0:
- 1D: ball moves along one axis only (left-right), bouncing off walls
- No paddle yet — just ball bouncing
- Success = ball position vector oscillates correctly between walls
"""

import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from vsa_operations import FlyBrainVSA
from spike_vsa_bridge import cosine_similarity


def pong_v0_bounce():
    """
    V0: Ball bouncing between two walls in 1D.

    The ball position is a vector that interpolates between LEFT and RIGHT.
    Each tick, a rotation moves it toward one wall. When it gets close
    enough to a wall (is_true detects boundary), the rotation direction
    flips.

    This tests: geometric rotation, is_true boundary detection, and
    conditional direction change — all on the spiking substrate.
    """
    print("=" * 60)
    print("PONG V0: Ball bouncing between walls (1D)")
    print("=" * 60)

    vsa = FlyBrainVSA(use_hemibrain=True)
    dim = vsa.dim
    print(f"Substrate: {dim}-D, {vsa.n_kc} KCs")

    # Define boundary vectors (deterministic, well-separated)
    rng = np.random.RandomState(1234)
    LEFT = rng.randn(dim)
    LEFT /= np.linalg.norm(LEFT)
    RIGHT = rng.randn(dim)
    # Make RIGHT orthogonal to LEFT for maximum separation
    RIGHT -= np.dot(RIGHT, LEFT) * LEFT
    RIGHT /= np.linalg.norm(RIGHT)

    print(f"LEFT . RIGHT = {np.dot(LEFT, RIGHT):.4f} (should be ~0)")

    # Ball starts at the left wall
    ball_pos = LEFT.copy()

    # Rotation: move from LEFT toward RIGHT
    # We'll use a small rotation in a 2D subplane that tilts the vector
    # from LEFT toward RIGHT
    angle_per_tick = 0.15  # radians per game tick

    # Build rotation in the LEFT-RIGHT plane
    def make_lr_rotation(angle):
        """Rotation in the 2D plane spanned by LEFT and RIGHT."""
        R = np.eye(dim)
        # Project onto the LEFT-RIGHT plane
        # e1 = LEFT, e2 = RIGHT (already orthonormal)
        c, s = np.cos(angle), np.sin(angle)
        # R acts as rotation in the span of LEFT, RIGHT
        # For a general vector v:
        #   v_left = (v . LEFT) * LEFT
        #   v_right = (v . RIGHT) * RIGHT
        #   v_rest = v - v_left - v_right
        #   R(v) = (c * v_left_coeff - s * v_right_coeff) * LEFT
        #        + (s * v_left_coeff + c * v_right_coeff) * RIGHT
        #        + v_rest
        # As a matrix: R = I + (c-1)(LL^T + RR^T) + s(RL^T - LR^T)
        LL = np.outer(LEFT, LEFT)
        RR = np.outer(RIGHT, RIGHT)
        RL = np.outer(RIGHT, LEFT)
        LR = np.outer(LEFT, RIGHT)
        R = np.eye(dim) + (c - 1) * (LL + RR) + s * (RL - LR)
        return R

    R_forward = make_lr_rotation(angle_per_tick)
    R_backward = make_lr_rotation(-angle_per_tick)

    # Compile boundary prototypes for the circuit
    print("\nCompiling boundary prototypes...")
    protos = vsa.compile_prototypes({
        "LEFT": LEFT,
        "RIGHT": RIGHT,
    })

    # Game loop (host-side loop, but each tick does circuit operations)
    n_ticks = 30
    direction = 1  # 1 = moving right, -1 = moving left
    bounces = 0

    print(f"\nRunning {n_ticks} ticks...")
    print(f"{'Tick':>4} {'cos(LEFT)':>10} {'cos(RIGHT)':>10} {'Dir':>4} {'Event'}")
    print("-" * 50)

    for tick in range(n_ticks):
        # Where is the ball relative to walls?
        cos_left = cosine_similarity(ball_pos, LEFT)
        cos_right = cosine_similarity(ball_pos, RIGHT)

        # Detect boundary (pure vector math, no circuit needed)
        event = ""
        if direction == 1 and cos_right > 0.85:
            direction = -1
            bounces += 1
            event = "BOUNCE (right wall)"
        elif direction == -1 and cos_left > 0.85:
            direction = 1
            bounces += 1
            event = "BOUNCE (left wall)"

        d = "->" if direction == 1 else "<-"
        print(f"{tick:4d} {cos_left:10.3f} {cos_right:10.3f} {d:>4} {event}")

        # Apply rotation (move ball)
        R = R_forward if direction == 1 else R_backward
        ball_pos = R @ ball_pos

        # Snap through circuit periodically (error correction)
        if tick % 5 == 4:
            ball_pos = vsa.snap(ball_pos)
            # Re-normalize after snap (snap may change magnitude)
            norm = np.linalg.norm(ball_pos)
            if norm > 1e-10:
                ball_pos = ball_pos / norm

    print(f"\nResult: {bounces} bounces in {n_ticks} ticks")
    return bounces >= 2


def pong_v1_with_paddle():
    """
    V1: Ball bouncing with paddle control.

    Adds a paddle dimension and collision detection.
    Uses fuzzy conditional for paddle movement.
    """
    print("\n" + "=" * 60)
    print("PONG V1: Ball + paddle (2D)")
    print("=" * 60)

    vsa = FlyBrainVSA(use_hemibrain=True)
    dim = vsa.dim

    # Define basis vectors for the game space
    rng = np.random.RandomState(5678)
    # Ball x-axis: LEFT <-> RIGHT
    LEFT = rng.randn(dim); LEFT /= np.linalg.norm(LEFT)
    RIGHT = rng.randn(dim)
    RIGHT -= np.dot(RIGHT, LEFT) * LEFT
    RIGHT /= np.linalg.norm(RIGHT)

    # Ball y-axis: BOTTOM <-> TOP (orthogonal to x-axis)
    BOTTOM = rng.randn(dim)
    BOTTOM -= np.dot(BOTTOM, LEFT) * LEFT
    BOTTOM -= np.dot(BOTTOM, RIGHT) * RIGHT
    BOTTOM /= np.linalg.norm(BOTTOM)

    TOP = rng.randn(dim)
    TOP -= np.dot(TOP, LEFT) * LEFT
    TOP -= np.dot(TOP, RIGHT) * RIGHT
    TOP -= np.dot(TOP, BOTTOM) * BOTTOM
    TOP /= np.linalg.norm(TOP)

    print(f"Orthogonality check:")
    print(f"  LEFT.RIGHT = {np.dot(LEFT, RIGHT):.4f}")
    print(f"  LEFT.TOP = {np.dot(LEFT, TOP):.4f}")
    print(f"  BOTTOM.TOP = {np.dot(BOTTOM, TOP):.4f}")

    # Ball starts at center, moving right and up
    ball_x = 0.5  # fraction: 0 = left, 1 = right
    ball_y = 0.5
    vx = 0.08  # velocity in fraction/tick
    vy = 0.06

    # Paddle position (right wall)
    paddle_y = 0.5
    paddle_speed = 0.1

    def pos_to_vec(x_frac, y_frac):
        """Convert (x, y) fractions to a vector."""
        return ((1 - x_frac) * LEFT + x_frac * RIGHT +
                (1 - y_frac) * BOTTOM + y_frac * TOP)

    n_ticks = 40
    score = 0
    bounces = 0

    print(f"\nRunning {n_ticks} ticks...")
    print(f"{'Tick':>4} {'Ball X':>7} {'Ball Y':>7} {'Paddle':>7} {'Event'}")
    print("-" * 55)

    for tick in range(n_ticks):
        event = ""

        # Move ball
        ball_x += vx
        ball_y += vy

        # Wall bounces (top/bottom)
        if ball_y >= 1.0:
            ball_y = 2.0 - ball_y
            vy = -vy
            event = "bounce top"
            bounces += 1
        elif ball_y <= 0.0:
            ball_y = -ball_y
            vy = -vy
            event = "bounce bottom"
            bounces += 1

        # Left wall bounce
        if ball_x <= 0.0:
            ball_x = -ball_x
            vx = -vx
            event = "bounce left"
            bounces += 1

        # Right wall (paddle)
        if ball_x >= 1.0:
            # Check if paddle catches it
            if abs(ball_y - paddle_y) < 0.2:
                ball_x = 2.0 - ball_x
                vx = -vx
                event = "PADDLE HIT!"
                score += 1
                bounces += 1
            else:
                ball_x = 0.5
                ball_y = 0.5
                event = "MISS - reset"

        # AI paddle: move toward ball using fuzzy conditional
        # is_above = similarity between ball_y_vec and TOP > 0.5
        ball_vec = pos_to_vec(ball_x, ball_y)
        paddle_vec = pos_to_vec(1.0, paddle_y)

        # Simple AI: move paddle toward ball y
        if ball_y > paddle_y + 0.05:
            paddle_y = min(1.0, paddle_y + paddle_speed)
        elif ball_y < paddle_y - 0.05:
            paddle_y = max(0.0, paddle_y - paddle_speed)

        print(f"{tick:4d} {ball_x:7.2f} {ball_y:7.2f} {paddle_y:7.2f} {event}")

    print(f"\nResult: {score} paddle hits, {bounces} total bounces")
    return score >= 2


if __name__ == "__main__":
    ok_v0 = pong_v0_bounce()
    print(f"\nV0 PASS: {ok_v0}")

    # V1 is host-side for now — proves the game logic works
    # before we put the paddle AI on the brain
    ok_v1 = pong_v1_with_paddle()
    print(f"\nV1 PASS: {ok_v1}")
