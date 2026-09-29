import pygame

class Highlight(pygame.sprite.Sprite):
    def __init__(self, coords):
        super().__init__()
        self.image = pygame.Surface((133, 133), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=coords)
        self.coords = coords
        self.last_position = None
        self.draw_outline()

    def draw_outline(self):
        self.image.fill((0, 0, 0, 0))
        pygame.draw.rect(self.image, (255, 0, 0), (0, 0, 133, 133), 5)

    def clear(self, screen, background):
        if self.last_position is not None:
            screen.blit(background, self.last_position, (self.last_position[0], self.last_position[1], 133, 133))
        self.last_position = self.rect.topleft

    def update_position(self, coords):
        if coords is None:
            self.rect.topleft = (-200, -200)
        else:
            self.rect.topleft = coords
            self.draw_outline()