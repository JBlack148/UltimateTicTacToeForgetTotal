import random
import sys
from pathlib import Path

import pygame
from pygame.locals import MOUSEBUTTONDOWN, QUIT

from game_rules import create_initial_state, get_legal_moves, try_apply_move
from highlight import Highlight

ASSET_DIR = Path(__file__).resolve().parent
BOARD_WIDTH = 470
BOARD_HEIGHT = 430
COLUMN_RANGES = ((52, 87), (87, 121), (121, 156), (189, 223), (223, 258), (258, 293), (327, 356), (356, 391), (391, 426))
ROW_RANGES = ((32, 67), (67, 102), (102, 137), (165, 199), (199, 234), (234, 269), (298, 332), (332, 367), (367, 402))
COLUMN_POSITIONS = (58, 93, 128, 191, 226, 261, 324, 359, 394)
ROW_POSITIONS = (32, 67, 102, 165, 200, 235, 298, 333, 368)

pygame.init()
screen = pygame.display.set_mode((BOARD_WIDTH, BOARD_HEIGHT))
pygame.display.set_caption("ULTIMATE Tic Tac Toe - You: X, Random: O")
background = pygame.image.load(str(ASSET_DIR / "Board.png")).convert()
cross_image = pygame.image.load(str(ASSET_DIR / "Cross.png")).convert_alpha()
knot_image = pygame.image.load(str(ASSET_DIR / "Knot.png")).convert_alpha()

highlight_sprites = pygame.sprite.Group()
highlight = Highlight((-200, -200))
highlight_sprites.add(highlight)
state = create_initial_state()


def cell_at_position(position):
    mouse_x, mouse_y = position
    column = next((index for index, bounds in enumerate(COLUMN_RANGES) if bounds[0] <= mouse_x < bounds[1]), None)
    row = next((index for index, bounds in enumerate(ROW_RANGES) if bounds[0] <= mouse_y < bounds[1]), None)
    if column is None or row is None:
        return None
    return column, row


def highlight_location(box_index):
    column = box_index % 3
    row = box_index // 3
    return 40 + column * 133, 14 + row * 133


def draw_large_mark(box_index, mark):
    column = box_index % 3
    row = box_index // 3
    center_x = 105 + column * 135
    center_y = 80 + row * 135
    if mark == "O":
        pygame.draw.circle(screen, (255, 0, 0), (center_x, center_y), 67, 12)
    else:
        left = 49 + column * 133
        top = 14 + row * 133
        pygame.draw.line(screen, (255, 0, 0), (left, top), (left + 114, top + 133), 15)
        pygame.draw.line(screen, (255, 0, 0), (left + 114, top), (left, top + 133), 15)


def render_board(current_state):
    screen.blit(background, (0, 0))
    for bigbox, smallbox in enumerate(current_state["board"]):
        for row, cells in enumerate(smallbox):
            for col, mark in enumerate(cells):
                if mark:
                    column = (bigbox % 3) * 3 + col
                    board_row = (bigbox // 3) * 3 + row
                    screen.blit(cross_image if mark == "x" else knot_image, (COLUMN_POSITIONS[column], ROW_POSITIONS[board_row]))
    for box_index, mark in enumerate(current_state["largeboard"]):
        if mark:
            draw_large_mark(box_index, mark)


def run_game():
    global state
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == MOUSEBUTTONDOWN and not state["game_over"]:
                cell = cell_at_position(pygame.mouse.get_pos())
                if cell is None:
                    continue
                column, row = cell
                bigbox = (row // 3) * 3 + column // 3
                move = (bigbox, row % 3, column % 3)
                state, applied = try_apply_move(state, move)
                if applied and not state["game_over"]:
                    legal_moves = get_legal_moves(state)
                    if legal_moves:
                        opponent_move = random.choice(legal_moves)
                        state, _ = try_apply_move(state, opponent_move)
                if state["winner"]:
                    pygame.display.set_caption(f"ULTIMATE Tic Tac Toe - {state['winner']}")

        render_board(state)
        if len(state["nextbox"]) > 1:
            pygame.draw.rect(screen, (255, 0, 0), (40, 14, 405, 405), width=5)
            highlight.update_position(None)
        else:
            highlight.update_position(highlight_location(state["nextbox"][0]))
        highlight_sprites.draw(screen)
        pygame.display.update()

    pygame.quit()
    sys.exit()


run_game()
