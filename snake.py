#!/usr/bin/env python3

import argparse
import curses
import random
import time
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple
from collections import deque


Direction = Tuple[int, int]  # (dy, dx)


@dataclass(frozen=True)
class Point:
    row: int
    col: int


DIRECTIONS: dict[str, Direction] = {
    "UP": (-1, 0),
    "DOWN": (1, 0),
    "LEFT": (0, -1),
    "RIGHT": (0, 1),
}

OPPOSITE: dict[str, str] = {
    "UP": "DOWN",
    "DOWN": "UP",
    "LEFT": "RIGHT",
    "RIGHT": "LEFT",
}

CLOCKWISE_ORDER: List[str] = ["UP", "RIGHT", "DOWN", "LEFT"]


class SnakeGame:
    def __init__(
        self,
        stdscr: "curses._CursesWindow",
        width: Optional[int] = None,
        height: Optional[int] = None,
        speed_fps: int = 10,
        demo_steps: int = 0,
    ) -> None:
        self.stdscr = stdscr
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.keypad(True)

        # Compute playfield size inside a border
        max_y, max_x = stdscr.getmaxyx()
        # Ensure minimum sizes
        max_y = max(max_y, 20)
        max_x = max(max_x, 40)

        self.height = max(5, min(height if height else max_y, max_y))
        self.width = max(10, min(width if width else max_x, max_x))

        # Interior play area (without the border) from (1,1) to (height-2,width-2)
        self.play_rows = self.height - 2
        self.play_cols = self.width - 2

        # Timing
        self.speed_fps = max(1, min(30, speed_fps))
        self.frame_delay = 1.0 / float(self.speed_fps)

        # Game state
        self.score = 0
        self.snake: Deque[Point] = deque()
        self.direction: str = "RIGHT"
        self.pending_direction: Optional[str] = None
        self.food: Optional[Point] = None
        self.game_over = False
        self.paused = False

        # Demo/Autopilot
        self.demo_steps = max(0, demo_steps)

        self._initialize_snake()
        self._spawn_food()

    def _initialize_snake(self) -> None:
        center_row = self.play_rows // 2
        start_col = self.play_cols // 2 - 1
        # Place snake at center moving RIGHT
        self.snake.clear()
        self.snake.append(Point(center_row, start_col))
        self.snake.append(Point(center_row, start_col + 1))
        self.snake.append(Point(center_row, start_col + 2))
        self.direction = "RIGHT"
        self.pending_direction = None
        self.score = 0

    def _spawn_food(self) -> None:
        occupied = set(self.snake)
        free_cells = [
            Point(r, c)
            for r in range(self.play_rows)
            for c in range(self.play_cols)
            if Point(r, c) not in occupied
        ]
        if not free_cells:
            self.food = None
            return
        self.food = random.choice(free_cells)

    def _draw_border(self) -> None:
        # Draw frame border
        self.stdscr.clear()
        # Create a centered playfield if terminal is larger than desired width/height
        max_y, max_x = self.stdscr.getmaxyx()
        top = max(0, (max_y - self.height) // 2)
        left = max(0, (max_x - self.width) // 2)

        # Draw border rectangle
        for x in range(left, min(left + self.width, max_x)):
            if top >= 0 and top < max_y:
                self.stdscr.addch(top, x, ord('#'))
            if top + self.height - 1 >= 0 and top + self.height - 1 < max_y:
                self.stdscr.addch(top + self.height - 1, x, ord('#'))
        for y in range(top, min(top + self.height, max_y)):
            if left >= 0 and left < max_x:
                self.stdscr.addch(y, left, ord('#'))
            if left + self.width - 1 >= 0 and left + self.width - 1 < max_x:
                self.stdscr.addch(y, left + self.width - 1, ord('#'))

        # Store offsets for rendering interior
        self.offset_row = top + 1
        self.offset_col = left + 1

    def _render(self) -> None:
        self._draw_border()

        # Draw food
        if self.food is not None:
            y = self.offset_row + self.food.row
            x = self.offset_col + self.food.col
            try:
                self.stdscr.addch(y, x, ord('*'))
            except curses.error:
                pass

        # Draw snake
        for idx, segment in enumerate(self.snake):
            ch = 'O' if idx == len(self.snake) - 1 else 'o'
            y = self.offset_row + segment.row
            x = self.offset_col + segment.col
            try:
                self.stdscr.addch(y, x, ord(ch))
            except curses.error:
                pass

        # Draw score and status
        status = f" Score: {self.score}  Speed: {self.speed_fps} fps  Length: {len(self.snake)} "
        if self.paused:
            status += " [PAUSED] "
        self._draw_status(status)

        self.stdscr.refresh()

    def _draw_status(self, text: str) -> None:
        max_y, max_x = self.stdscr.getmaxyx()
        y = min(self.offset_row - 1, max_y - 1)
        if y < 0:
            return
        x = max(0, (max_x - len(text)) // 2)
        try:
            self.stdscr.addstr(y, x, text[: max_x - x])
        except curses.error:
            pass

    def _handle_input(self) -> None:
        try:
            key = self.stdscr.getch()
        except curses.error:
            key = -1

        if key == -1:
            return

        if key in (ord('q'), 27):  # q or Esc
            self.game_over = True
            return
        if key in (ord('p'), ord('P')):
            self.paused = not self.paused
            return

        if key in (curses.KEY_UP, ord('w'), ord('W')):
            self._queue_direction("UP")
        elif key in (curses.KEY_DOWN, ord('s'), ord('S')):
            self._queue_direction("DOWN")
        elif key in (curses.KEY_LEFT, ord('a'), ord('A')):
            self._queue_direction("LEFT")
        elif key in (curses.KEY_RIGHT, ord('d'), ord('D')):
            self._queue_direction("RIGHT")

    def _queue_direction(self, new_direction: str) -> None:
        if new_direction == OPPOSITE[self.direction]:
            return
        self.pending_direction = new_direction

    def _next_head(self, direction: Optional[str] = None) -> Point:
        if direction is None:
            direction = self.direction
        dy, dx = DIRECTIONS[direction]
        head = self.snake[-1]
        return Point(head.row + dy, head.col + dx)

    def _is_collision(self, point: Point) -> bool:
        # Walls
        if point.row < 0 or point.row >= self.play_rows:
            return True
        if point.col < 0 or point.col >= self.play_cols:
            return True
        # Self
        if point in self.snake:
            return True
        return False

    def _autopilot_direction(self) -> str:
        # Simple safe-ish autopilot: prefer continuing forward; if blocked, try clockwise order
        preferred: List[str] = []
        preferred.append(self.direction)
        # rotate clockwise order so current direction is first, then clockwise
        idx = CLOCKWISE_ORDER.index(self.direction)
        for i in range(1, 4):
            preferred.append(CLOCKWISE_ORDER[(idx + i) % 4])
        for cand in preferred:
            if cand == OPPOSITE[self.direction]:
                continue
            nxt = self._next_head(cand)
            if not self._is_collision(nxt):
                return cand
        return self.direction

    def _tick(self) -> None:
        if self.paused:
            return

        # Apply queued direction if any
        if self.pending_direction and self.pending_direction != OPPOSITE[self.direction]:
            self.direction = self.pending_direction
            self.pending_direction = None

        # In demo mode, steer automatically
        if self.demo_steps > 0:
            self.direction = self._autopilot_direction()

        new_head = self._next_head()

        # Collisions
        if self._is_collision(new_head):
            self.game_over = True
            return

        # Move
        self.snake.append(new_head)

        # Food check
        if self.food is not None and new_head == self.food:
            self.score += 1
            self._spawn_food()
        else:
            # Remove tail if no food consumed
            self.snake.popleft()

    def run(self) -> None:
        last_frame_time = time.perf_counter()
        steps_done = 0

        while not self.game_over:
            now = time.perf_counter()
            dt = now - last_frame_time
            if dt < self.frame_delay:
                # Process some input while waiting to keep UI responsive
                self._handle_input()
                # In demo mode, still need to throttle CPU
                time.sleep(0.001)
                continue

            last_frame_time = now

            # Input and game update
            self._handle_input()
            self._tick()

            # Render
            self._render()

            if self.demo_steps > 0:
                steps_done += 1
                if steps_done >= self.demo_steps:
                    # Graceful stop
                    self.game_over = True

        # Final screen
        self._render()
        over_text = " Game Over! Press any key to exit "
        self._draw_status(over_text)
        self.stdscr.nodelay(False)
        try:
            self.stdscr.getch()
        except curses.error:
            pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Terminal Snake game (curses). Controls: arrows or WASD, P=pause, Q/Esc=quit.",
    )
    parser.add_argument("--width", type=int, default=None, help="Total window width including border")
    parser.add_argument("--height", type=int, default=None, help="Total window height including border")
    parser.add_argument("--speed", type=int, default=10, help="Game speed in frames per second (1-30)")
    parser.add_argument(
        "--demo-steps",
        type=int,
        default=0,
        help="Run an autopilot for N steps then exit (useful for quick checks)",
    )
    return parser.parse_args()


def _curses_main(stdscr: "curses._CursesWindow") -> None:
    args = _parse_args()
    game = SnakeGame(
        stdscr,
        width=args.width,
        height=args.height,
        speed_fps=args.speed,
        demo_steps=args.demo_steps,
    )
    game.run()


def main() -> None:
    curses.wrapper(_curses_main)


if __name__ == "__main__":
    main()