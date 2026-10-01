import sys
from pathlib import Path

import pygame
from pygame.locals import *

from highlight import Highlight

ASSET_DIR = Path(__file__).resolve().parent
BOARD_WIDTH = 470
BOARD_HEIGHT = 430

# display
pygame.init()
DISPLAYSURF = pygame.display.set_mode((BOARD_WIDTH, BOARD_HEIGHT))
pygame.display.set_caption('ULTIMATE Tic Tac Toe')
bgrnd = pygame.image.load(str(ASSET_DIR / "Board.png")).convert()
DISPLAYSURF.blit(bgrnd, (0, 0))


def create_initial_state():
    return {
        "count": 0,
        "nextbox": [0, 1, 2, 3, 4, 5, 6, 7, 8],
        "board": [[['', '', ''], ['', '', ''], ['', '', '']],
                  [['', '', ''], ['', '', ''], ['', '', '']],
                  [['', '', ''], ['', '', ''], ['', '', '']],
                  [['', '', ''], ['', '', ''], ['', '', '']],
                  [['', '', ''], ['', '', ''], ['', '', '']],
                  [['', '', ''], ['', '', ''], ['', '', '']],
                  [['', '', ''], ['', '', ''], ['', '', '']],
                  [['', '', ''], ['', '', ''], ['', '', '']],
                  [['', '', ''], ['', '', ''], ['', '', '']]],
        "largeboard": ['', '', '', '', '', '', '', '', ''],
        "piece_history": [{"x": [], "o": []} for _ in range(9)],
        "large_win_history": {"X": [], "O": []},
        "game_over": False,
        "winner": None,
    }


state = create_initial_state()
colforboard = 0
rowforboard = 0


#functions for resources
def knot(coords):
    if coords is not None:
        knot = pygame.image.load(str(ASSET_DIR / "Knot.png")).convert_alpha()
        DISPLAYSURF.blit(knot, coords)


def cross(coords):
    if coords is not None:
        cross = pygame.image.load(str(ASSET_DIR / "Cross.png")).convert_alpha()
        DISPLAYSURF.blit(cross, coords)


highlight_sprites = pygame.sprite.Group()
highlight = Highlight((-200, -200))
highlight_sprites.add(highlight)

#def highlight(bigbox):


#   pygame.sprite.Sprite()
#  if bigbox is not None:
#     pygame.draw.rect(DISPLAYSURF, (255, 0, 0,), (bigbox[0], bigbox[1], 135, 135), width = 5)
def highlightbig():
    pygame.draw.rect(DISPLAYSURF, (
        255,
        0,
        0,
    ), (40, 14, 405, 405), width=5)


def crossbig(bbox):
    if bbox <= 2:
        row = 14
    elif bbox <= 5:
        row = 147
    else:
        row = 280
    if bbox in [0, 3, 6]:
        col = 49
    elif bbox in [1, 4, 7]:
        col = 182
    else:
        col = 315
    pygame.draw.line(DISPLAYSURF, (255, 0, 0), (col, row), (col + 114, row + 133), 15)
    pygame.draw.line(DISPLAYSURF, (255, 0, 0), (col + 114, row), (col, row + 133), 15)


def knotbig(bbox):
    if bbox <= 2:
        row = 80
    elif bbox <= 5:
        row = 215
    else:
        row = 350
    if bbox in [0, 3, 6]:
        col = 105
    elif bbox in [1, 4, 7]:
        col = 240
    else:
        col = 375
    pygame.draw.circle(DISPLAYSURF, (255, 0, 0), (col, row), 67, 12)


#functions for placing stuff
def userclick():
    x, y = pygame.mouse.get_pos()
    if (x < 52):
        col = None
    elif (x < 87):
        col = 0
    elif (x < 121):
        col = 1
    elif (x < 156):
        col = 2
    elif (155 < x < 189):
        col = None
    elif (x < 223):
        col = 3
    elif (x < 258):
        col = 4
    elif (x < 293):
        col = 5
    elif (293 < x < 327):
        col = None
    elif (x < 356):
        col = 6
    elif (x < 391):
        col = 7
    elif (x < 426):
        col = 8
    elif (x < 52):
        col = None
    else:
        col = None
    if (y < 32):
        row = None
    elif (y < 67):
        row = 0
    elif (y < 102):
        row = 1
    elif (y < 137):
        row = 2
    elif (137 < y < 165):
        row = None
    elif (y < 199):
        row = 3
    elif (y < 234):
        row = 4
    elif (y < 269):
        row = 5
    elif (269 < y < 298):
        row = None
    elif (y < 332):
        row = 6
    elif (y < 367):
        row = 7
    elif (y < 402):
        row = 8
    else:
        row = None
    return col, row

#gives the collumn and row for which larger box has just been played in
def boxcoords(coords):
    if coords[0] != None and coords[1] != None:
        if coords[0] < 3:
            colbox = 0
        elif coords[0] < 6:
            colbox = 1
        else:
            colbox = 2
        if coords[1] < 3:
            rowbox = 0
        elif coords[1] < 6:
            rowbox = 1
        else:
            rowbox = 2
        return colbox, rowbox
    else:
        colbox = None
        rowbox = None
        return colbox, rowbox


def pos_in_box(coords):
    if coords[0] != None and coords[1] != None:
        if coords[0] in [0, 3, 6]:
            col = 0
        elif coords[0] in [1, 4, 7]:
            col = 1
        elif coords[0] in [2, 5, 8]:
            col = 2
        if coords[1] in [0, 3, 6]:
            row = 0
        if coords[1] in [1, 4, 7]:
            row = 1
        if coords[1] in [2, 5, 8]:
            row = 2
        return col, row
    else:
        row = 0
        col = 0
        return col, row


def whatnumberbox(coords):
    if coords[0] != None and coords[1] != None:
        if coords[0] == 0 and coords[1] == 0:
            box = 0
        elif coords[0] == 1 and coords[1] == 0:
            box = 1
        elif coords[0] == 2 and coords[1] == 0:
            box = 2
        elif coords[0] == 0 and coords[1] == 1:
            box = 3
        elif coords[0] == 1 and coords[1] == 1:
            box = 4
        elif coords[0] == 2 and coords[1] == 1:
            box = 5
        elif coords[0] == 0 and coords[1] == 2:
            box = 6
        elif coords[0] == 1 and coords[1] == 2:
            box = 7
        elif coords[0] == 2 and coords[1] == 2:
            box = 8
    else:
        box = None
    return box


def coordstoboard(coords):
    if coords[0] != None and coords[1] != None:
        if coords[0] < 3:
            col = 23 + 35 * (coords[0] + 1)
        elif coords[0] < 6:
            col = 51 + 35 * (coords[0] + 1)
        else:
            col = 79 + 35 * (coords[0] + 1)
        if coords[1] < 3:
            row = -3 + 35 * (coords[1] + 1)
        elif coords[1] < 6:
            row = 25 + 35 * (coords[1] + 1)
        else:
            row = 53 + 35 * (coords[1] + 1)
        return col, row


def highlightlocation(coords):
    if coords is None or coords[0] is None or coords[1] is None:
        return None
    col, row = coords
    if col in (0, 3, 6):
        x = 40
    elif col in (1, 4, 7):
        x = 173
    else:
        x = 306
    if row in (0, 3, 6):
        y = 14
    elif row in (1, 4, 7):
        y = 147
    else:
        y = 280
    return x, y


def render_board_state(current_state):
    DISPLAYSURF.blit(bgrnd, (0, 0))
    for bigbox in range(9):
        for row in range(3):
            for col in range(3):
                value = current_state["board"][bigbox][row][col]
                if value == "o":
                    abs_col = (bigbox % 3) * 3 + col
                    abs_row = (bigbox // 3) * 3 + row
                    knot(coordstoboard((abs_col, abs_row)))
                elif value == "x":
                    abs_col = (bigbox % 3) * 3 + col
                    abs_row = (bigbox // 3) * 3 + row
                    cross(coordstoboard((abs_col, abs_row)))
    for bigbox in range(9):
        if current_state["largeboard"][bigbox] == "O":
            knotbig(bigbox)
        elif current_state["largeboard"][bigbox] == "X":
            crossbig(bigbox)


def get_legal_moves(current_state):
    if current_state["game_over"]:
        return []

    allowed = current_state["nextbox"]
    legal_moves = []
    for bigbox in allowed:
        if current_state["largeboard"][bigbox] != "":
            continue
        for row in range(3):
            for col in range(3):
                if current_state["board"][bigbox][row][col] == "":
                    legal_moves.append((bigbox, row, col))
    if len(legal_moves) == 0:
        for bigbox in range(9):
            if current_state["largeboard"][bigbox] == "":
                for row in range(3):
                    for col in range(3):
                        if current_state["board"][bigbox][row][col] == "":
                            legal_moves.append((bigbox, row, col))
    return legal_moves


def try_apply_move(current_state, bigbox, row, col):
    if current_state["game_over"]:
        return current_state, False
    if (bigbox, row, col) not in get_legal_moves(current_state):
        return current_state, False

    next_state = {
        "count": current_state["count"],
        "nextbox": list(current_state["nextbox"]),
        "board": [
            [[cell for cell in inner_row] for inner_row in box]
            for box in current_state["board"]
        ],
        "largeboard": list(current_state["largeboard"]),
        "piece_history": [{"x": list(history["x"]), "o": list(history["o"])} for history in current_state["piece_history"]],
        "large_win_history": {"X": list(current_state["large_win_history"]["X"]), "O": list(current_state["large_win_history"]["O"])},
        "game_over": current_state["game_over"],
        "winner": current_state["winner"],
    }

    next_state["count"] += 1
    if next_state["count"] % 2 == 0:
        mark = "o"
    else:
        mark = "x"

    place_piece(next_state["board"][bigbox], next_state["piece_history"][bigbox], row, col, mark)
    small_winner = boxwincheck(next_state["board"][bigbox])
    if small_winner:
        record_large_win(bigbox, small_winner, next_state["board"], next_state["largeboard"], next_state["piece_history"], next_state["large_win_history"])

    winner = wincheck(next_state["largeboard"])
    if winner in ("X wins", "O wins"):
        next_state["game_over"] = True
        next_state["winner"] = winner
        pygame.display.set_caption(f"ULTIMATE Tic Tac Toe - {winner}")

    target_box = whatnumberbox((col, row))
    if target_box is not None and next_state["largeboard"][target_box] == "":
        next_state["nextbox"] = [target_box]
    else:
        next_state["nextbox"] = [0, 1, 2, 3, 4, 5, 6, 7, 8]

    return next_state, True


def wincheck(square):
    if square[0] == "X" and square[1] == "X" and square[2] == "X":
        return("X wins")
    elif square[3] == "X" and square[4] == "X" and square[5] == "X":
        return("X wins")
    elif square[6] == "X" and square[7] == "X" and square[8] == "X":
        return("X wins")
    elif square[0] == "X" and square[3] == "X" and square[6] == "X":
        return("X wins")
    elif square[1] == "X" and square[4] == "X" and square[7] == "X":
        return("X wins")
    elif square[2] == "X" and square[5] == "X" and square[8] == "X":
        return("X wins")
    elif square[0] == "X" and square[4] == "X" and square[8] == "X":
        return("X wins")
    elif square[2] == "X" and square[4] == "X" and square[6] == "X":
        return("X wins")
    elif square[0] == "O" and square[1] == "O" and square[2] == "O":
        return("O wins")
    elif square[3] == "O" and square[4] == "O" and square[5] == "O":
        return("O wins")
    elif square[6] == "O" and square[7] == "O" and square[8] == "O":
        return("O wins")
    elif square[0] == "O" and square[3] == "O" and square[6] == "O":
        return("O wins")
    elif square[1] == "O" and square[4] == "O" and square[7] == "O":
        return("O wins")
    elif square[2] == "O" and square[5] == "O" and square[8] == "O":
        return("O wins")
    elif square[0] == "O" and square[4] == "O" and square[8] == "O":
        return("O wins")
    elif square[2] == "O" and square[4] == "O" and square[6] == "O":
        return("O wins")
    else:
        return("the game has not been won yet")
def boxwincheck(smallbox):
    if smallbox[0][0] == "x" and smallbox[0][1] == "x" and smallbox[0][2] == "x":
        return("X")
    elif smallbox[1][0] == "x" and smallbox[1][1] == "x" and smallbox[1][2] == "x":
        return("X")
    elif smallbox[2][0] == "x" and smallbox[2][1] == "x" and smallbox[2][2] == "x":
        return("X")
    elif smallbox[0][0] == "x" and smallbox[1][0] == "x" and smallbox[2][0] == "x":
        return("X")
    elif smallbox[0][1] == "x" and smallbox[1][1] == "x" and smallbox[2][1] == "x":
        return("X")
    elif smallbox[0][2] == "x" and smallbox[1][2] == "x" and smallbox[2][2] == "x":
        return("X")
    elif smallbox[0][0] == "x" and smallbox[1][1] == "x" and smallbox[2][2] == "x":
        return("X")
    elif smallbox[0][2] == "x" and smallbox[1][1] == "x" and smallbox[2][0] == "x":
        return("X")
    elif smallbox[0][0] == "o" and smallbox[0][1] == "o" and smallbox[0][2] == "o":
        return("O")
    elif smallbox[1][0] == "o" and smallbox[1][1] == "o" and smallbox[1][2] == "o":
        return("O")
    elif smallbox[2][0] == "o" and smallbox[2][1] == "o" and smallbox[2][2] == "o":
        return("O")
    elif smallbox[0][0] == "o" and smallbox[1][0] == "o" and smallbox[2][0] == "o":
        return("O")
    elif smallbox[0][1] == "o" and smallbox[1][1] == "o" and smallbox[2][1] == "o":
        return("O")
    elif smallbox[0][2] == "o" and smallbox[1][2] == "o" and smallbox[2][2] == "o":
        return("O")
    elif smallbox[0][0] == "o" and smallbox[1][1] == "o" and smallbox[2][2] == "o":
        return("O")
    elif smallbox[0][2] == "o" and smallbox[1][1] == "o" and smallbox[2][0] == "o":
        return("O")
    else:
        return("")


def place_piece(smallbox, history_by_player, row, col, mark):
    history = history_by_player[mark]
    if len(history) >= 3:
        oldest_row, oldest_col = history.pop(0)
        smallbox[oldest_row][oldest_col] = ""
    smallbox[row][col] = mark
    history.append((row, col))


def record_large_win(bbox, player, board, largeboard, piece_history, win_history):
    history = win_history[player]
    largeboard[bbox] = player
    history.append(bbox)
    if len(history) > 3:
        forgotten_box = history.pop(0)
        largeboard[forgotten_box] = ""
        board[forgotten_box] = [["", "", ""] for _ in range(3)]
        piece_history[forgotten_box] = {"x": [], "o": []}

def correlatedbox(insidebox):
    pass
#check if the box that the most recent piece has been placed in is won by using the coords in box
pygame.display.update()
# each box is 35x35px therefore to move a knot or cross by 1 box in the x axis to the right you add 35 to the X
# each larger box is 133x133px therefore to move the highlight box by 1 larger box to the right you add 133 to the X

#large box = bug fact: centipeeds have 10 legs and millipeeds have 100 despite cent frequently meaning 100 and milli frequently meaning 1000 <- this bug fact is incorrect and a misconception, some millipedes actually have up to 750 pairs of legs
#bug fact: dung beatles can move pieces of dung up to 10 times their own weight
#fun bug fact ants can carry things they want to carry up to 10 times their own weight
#food for thought: what is an arm?

#GAME
while True:
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == MOUSEBUTTONDOWN and not state["game_over"]:
            coords = userclick()
            if coords[1] is not None and coords[0] is not None:
                insidebox = pos_in_box(coords)
                bbox = whatnumberbox(boxcoords(coords))
                boardlocation = coordstoboard(coords)
                if bbox is not None and insidebox is not None and boardlocation is not None:
                    state, applied = try_apply_move(state, bbox, insidebox[1], insidebox[0])
                    if applied:
                        print(state["nextbox"], "nextbox")
                        print(state["board"])

    render_board_state(state)

    if len(state["nextbox"]) == 9:
        highlightbig()
        highlight.update_position(None)
    elif len(state["nextbox"]) == 1:
        highlight_box = state["nextbox"][0]
        highlight_pos = highlightlocation((highlight_box % 3, highlight_box // 3))
        highlight.update_position(highlight_pos)
    else:
        highlight.update_position(None)

    highlight_sprites.draw(DISPLAYSURF)
    pygame.display.update()
