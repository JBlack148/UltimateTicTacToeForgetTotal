import pygame

# renders a red outline over the current target square for the next move
class Highlight(pygame.sprite.Sprite):
    def __init__(self, coords):
        super().__init__()
        self.image = pygame.Surface((133, 133), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=coords)
        self.coords = coords
        self.last_position = None
        self.draw_outline()

    # draws the red border that marks the highlighted legal target area
    def draw_outline(self):
        self.image.fill((0, 0, 0, 0))
        pygame.draw.rect(self.image, (255, 0, 0), (0, 0, 133, 133), 5)

    # clears the previous highlight by redrawing the board background under it
    def clear(self, screen, background):
        if self.last_position is not None:
            screen.blit(background, self.last_position, (self.last_position[0], self.last_position[1], 133, 133))
        self.last_position = self.rect.topleft

    # moves the highlight to a new square or hides it when no square is valid
    def update_position(self, coords):
        if coords is None:
            self.rect.topleft = (-200, -200)
        else:
            self.rect.topleft = coords
            self.draw_outline()