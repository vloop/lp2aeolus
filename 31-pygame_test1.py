#!/usr/bin/env python3
import pygame.midi
import time


def play1(note):
    player.note_on(note, 127)
    time.sleep(1)
    player.note_off(note, 127)

pygame.midi.init()

print (pygame.midi.get_default_output_id())
print (pygame.midi.get_device_info(0))

player = pygame.midi.Output(0)
player.set_instrument(0)

play1(65)

del player
pygame.midi.quit()
