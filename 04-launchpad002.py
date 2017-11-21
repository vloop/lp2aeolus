#!/usr/bin/python3
# -*- coding: utf-8 -*-
# MPER 20171012

import sys
import getopt
import logging
import time

from rtmidi.midiutil import open_midiport, list_available_ports
from rtmidi.midiconstants import (NOTE_OFF, NOTE_ON, CONTROL_CHANGE, PROGRAM_CHANGE,
    NRPN_MSB, NRPN_LSB, DATA_ENTRY_MSB, DATA_ENTRY_LSB, END_OF_EXCLUSIVE, SYSTEM_EXCLUSIVE)

from rtmidi import (API_LINUX_ALSA, API_MACOSX_CORE, API_RTMIDI_DUMMY,
    API_UNIX_JACK, API_WINDOWS_MM, MidiIn, MidiOut, get_compiled_api)


class MidiInputHandler(object):

    def __init__(self, in_port, midi_channel_in, out_port, midi_channel_out):
        self.in_port = in_port
        self.midi_channel_in = int(midi_channel_in)
        self.out_port = out_port
        self.midi_channel_out = int(midi_channel_out)
        self._wallclock = time.time()
        self.in_callback = False
        self.keydown = [False] * 128

    def __call__(self, event, data=None):
        if self.in_callback:
            logging.error('MIDI overflow')
            return
        message, deltatime = event
        self._wallclock += deltatime
        print("@%0.6f %r" % (self._wallclock, message))
        self.in_callback = True
        if message[0] == CONTROL_CHANGE + int(self.midi_channel_in):
            # The  controller  self.notes = [False] * 128numbers  for  the  top  row  of  round  buttons
            # do not  change  with  layout  and  is always as 68h to 6Fh
            if 0x68 <= message[1] <= 0x6F:
                print('Bouton du dessus', message[1] - 0x68, 'valeur', message[2])
                self.in_callback = False
                return
            else:
                logging.warning("Contrôleur MIDI inattendu: %s %s %s", message[0], message[1], message[2])
                self.in_callback = False
                return
        elif message[0] == NOTE_ON + int(self.midi_channel_in):
            # Layout  0  is Session layout.
            # This is best for writing software that uses Launchpad MK2
            # as a grid as it is easy to navigate by adding and
            # subtracting - adding 1 moves to the right 1 button,
            # adding 10 moves up one button.
            note = message[1]
            y, x = divmod(note, 10)
            print('Bouton colonne', x, 'ligne', y, 'valeur', message[2])
            if message[2] == 0x7F:
                # pad pressed, change key state
                self.keydown[note] = not self.keydown[note]
                self.out_port.send_message([NOTE_ON + self.midi_channel_out, note, 0x2D if self.keydown[note] else 0])
            else:
                pass  # Pad released, state doesn't change
            self.in_callback = False
            return
        else:
            logging.warning("Message MIDI inattendu: %s %s %s", message[0], message[1], message[2])
            self.in_callback = False
            return


class MidiMapper:
    """Show incoming MIDI messages from launchpad"""
    def __init__(self, port_num_in, port_num_out, midi_channel_in=0, midi_channel_out=0):
        self.port_num_in = port_num_in
        self.port_num_out = port_num_out
        self.midi_channel_in = midi_channel_in
        self.midi_channel_out = midi_channel_out
        self.map_file_name = None
        # Input handler will require output, initialize MIDI output first
        try:
            self.midiout, self.port_name_out = open_midiport(port_num_out, 'output', interactive=False)
            logging.info("%s ouvert en sortie", self.port_name_out)
            # Should switch to session layout (0)
            # Host >> Launchpad MK2:
            # F0h 00h 20h 29h 02h 18h 22h <Layout> F7h
            self.midiout.send_message([0xF0, 0x00, 0x20, 0x29, 0x02, 0x18, 0x22, 0x00, 0xF7])
            # and clear all leds
        except Exception as e:
            logging.error("Echec d'ouverture en sortie %s", e)
            sys.exit(1)
        # Initialize MIDI input
        try:
            self.midiin, self.port_name_in = open_midiport(port_num_in, 'input', interactive=False)
            logging.info("%s ouvert en entrée", self.port_name_in)
            self.midiin.ignore_types(sysex=True, timing=True, active_sense=True)
            self.midiin.set_callback(MidiInputHandler(self.midiin, self.midi_channel_in, self.midiout, self.midi_channel_out))
            # self.midiin.cancel_callback()
        except Exception as e:
            logging.error("Echec d'ouverture en entrée %s", e)
            sys.exit(1)


def list_midi_ports():

    # Example: Launchpad MK2:Launchpad MK2 MIDI 1
    if API_LINUX_ALSA in get_compiled_api():
        print('Input:')
        for p in MidiIn(API_LINUX_ALSA).get_ports():
            print(p)
        print('Output:')
        for p in MidiOut(API_LINUX_ALSA).get_ports():
            print(p)


def main(argv=None):

    def usage():
        print(sys.argv[0], "-h -l -i port -o port -c channel -v")

    if argv is None:
        argv = sys.argv
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hli:o:c:v", ["help", "list", "input=", "output=", "channel=", "verbose"])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err))  # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    input_port = None
    output_port = None
    verbose = False
    channel = 0
    for o, a in opts:
        if o == "-v":
            logging.basicConfig(level=logging.INFO)
            verbose = True
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-l", "--list"):
            list_midi_ports()
            sys.exit()
        elif o in ("-o", "--output"):
            output_port = a
        elif o in ("-i", "--input"):
            input_port = a
        elif o in ("-c", "--channel"):
            channel = a
        else:
            assert False, "unhandled option"
    app = MidiMapper(port_num_in=input_port, port_num_out=output_port, midi_channel_in=channel, midi_channel_out=channel)
    print('En attente de message MIDI')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nInterrompu par l\'utilisateur')
    print('Fini')


if __name__ == '__main__':
    main()
