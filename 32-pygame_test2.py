#!/usr/bin/env python3
# de http://pastebin.com/UggZ2fiT
import pygame
import pygame.locals as pgl
import pygame.midi

midiport_i = 1
midiport_o = 0

pygame.init()
pygame.fastevent.init()
event_get = pygame.fastevent.get
event_post = pygame.fastevent.post

pygame.midi.init()
i = pygame.midi.Input(midiport_i)
# fenêtre pour recevoir événements, ex. pour pouvoir quitter
window = pygame.display.set_mode((468, 60))
print (pygame.__file__)
print (pygame.midi.get_device_info(midiport_i))

mt = None
going = True
while going:
    events = event_get()
    for e in events:
        if e.type in [pgl.QUIT]:
            going = False
        if e.type in [pgl.KEYDOWN]:
            going = False
        if e.type in [pygame.midi.MIDIIN]:
            print (e, mt)

    if i.poll():
        print ("polled")
        midi_events = i.read(10)
        mt = pygame.midi.time()
        # convert them into pygame events.
        midi_evs = pygame.midi.midis2events(midi_events, i.device_id)
        for m_e in midi_evs:
            event_post(m_e)

del i
pygame.midi.quit()
