#!/usr/bin/python3
# -*- coding: utf-8 -*-
# MPER 20171101
# See https://jackclient-python.readthedocs.io/en/0.4.2/index.html#usage

import jack
client = jack.Client("MyGreatClient")
client.activate()
# This will show jack audio and midi, but not alsa midi
for p in client.get_ports():
    print(p.name)
    
try:    
    client.connect("aeolus:out.L", "system:playback_1")
    client.connect("aeolus:out.R", "system:playback_2")
except Exception as e:
    print("Caramba! Encore raté!", e)
