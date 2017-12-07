#!/usr/bin/python3
# -*- coding: utf-8 -*-
# MPER 20171012

import sys
import getopt
import logging
import time

from rtmidi.midiutil import open_midiport, open_midioutput, list_available_ports
from rtmidi.midiconstants import (NOTE_OFF, NOTE_ON, CONTROL_CHANGE, PROGRAM_CHANGE,
    NRPN_MSB, NRPN_LSB, DATA_ENTRY_MSB, DATA_ENTRY_LSB, END_OF_EXCLUSIVE, SYSTEM_EXCLUSIVE)

from rtmidi import (API_LINUX_ALSA, MidiIn, MidiOut, get_compiled_api)

AEOLUS_CC = 98
MAX_STOPS = 18
MAX_GROUPS = 4
LP_BLACK = 0
LP_BLUE = 0x2D


class MidiInputHandler(object):
    """Process incoming MIDI messages"""
    def __init__(self, in_port, midi_channel_in, out_port, midi_channel_out, out_port2, midi_channel_out2):
        self.in_port = in_port
        self.midi_channel_in = int(midi_channel_in)
        self.out_port = out_port
        self.midi_channel_out = int(midi_channel_out)
        self.out_port2 = out_port2
        self.midi_channel_out2 = int(midi_channel_out2)
        self._wallclock = time.time()
        self.in_callback = False
        self.keydown = [False] * 128

    def aeolus_cc_to_note(self, group_in, stop_number):
        y = 1 + 2 * (3 - group_in) + 1 - (stop_number // 9)
        x = 1 + (stop_number % 9)
        return(10 * y + x)

    def __call__(self, event, data=None):
        if self.in_callback:
            logging.error('MIDI overflow')
            return
        message, deltatime = event
        self._wallclock += deltatime
        print("@%0.6f %r" % (self._wallclock, message))
        self.in_callback = True
        if message[0] == CONTROL_CHANGE + int(self.midi_channel_in):
            # Les numéros de contrôleur utilisés par les boutons ronds
            # de la ligne supérieure ne changent pas quel que soit le
            # mode, c'est toujours de 68h à 6Fh
            if 0x68 <= message[1] <= 0x6F:
                print('Launchpad: Bouton du dessus', message[1] - 0x68, 'valeur', message[2])
            elif message[1] == AEOLUS_CC:
                # Ce CC provient d'Aeolus
                if (message[2] & 0x40):
                    # Message mode/groupe d'Aeolus
                    self.mode_in = (message[2] >> 4) & 0x03
                    self.group_in = message[2] & 0x07
                    print("Aeolus: Mode", self.mode_in, "group", self.group_in)
                    if self.mode_in == 0:
                        # Remise à zéro du groupe
                        self.mode_in = None
                        print("Désactivation du groupe", self.group_in)
                        for stop_number in range(MAX_STOPS):
                            note = self.aeolus_cc_to_note(self.group_in, stop_number)
                            if self.keydown[note]:
                                self.keydown[note] = False
                                self.out_port.send_message([NOTE_ON + self.midi_channel_out, note, LP_BLACK])
                else:
                    # Message de numéro de registre d'Aeolus
                    if self.mode_in is None:
                        logging.error("Mode non défini")
                    else:
                        stop_number_in = message[2] & 0x1F
                        # Calcul de la note à partir du groupe, du mode et du registre
                        # Ne pas tenir compte des touches absentes launchpad:
                        # On ignore le message si le registre dépasse MAX_STOPS
                        # ou si le groupe dépasse MAX_GROUPS
                        if stop_number_in < MAX_STOPS and self.group_in < MAX_GROUPS:
                            note = self.aeolus_cc_to_note(self.group_in, stop_number_in)
                            print("Aeolus: mode", self.mode_in, "groupe", self.group_in, "registre", stop_number_in, note)
                            if self.mode_in == 0:
                                # Rien à faire, désactivation du groupe.
                                v = None
                            elif self.mode_in == 1:
                                # Activation d'un registre
                                v = False
                            elif self.mode_in == 2:
                                # Désactivation d'un registre
                                v = True
                            else:  # self.mode_in == 3
                                # Inversion de l'état d'un registre
                                v = not self.keydown[note]
                            if v is not None and v != self.keydown[note]:
                                self.keydown[note] = v
                                color = LP_BLUE if v else LP_BLACK
                                self.out_port.send_message([NOTE_ON + self.midi_channel_out, note, color])
            else:
                logging.warning("Contrôleur MIDI inattendu: %s %s %s", message[0], message[1], message[2])
        elif message[0] == NOTE_ON + int(self.midi_channel_in):
            # Le launchpad est exploité en mode session
            # Ce mode convient bien pour utiliser le launchpad comme une
            # grille: ajouter un correspond à un déplacement d'une
            # colonne vers la droite, ajouter 10 correspond à une ligne
            # vers le haut
            note = message[1]
            y, x = divmod(note, 10)
            print('Launchpad: Bouton colonne', x, 'ligne', y, 'valeur', message[2])
            if message[2] == 0x7F:
                # Appui sur le pad, changement d'état
                self.keydown[note] = not self.keydown[note]
                color = 0x2D if self.keydown[note] else 0
                print("Envoi vers le launchpad:", NOTE_ON + self.midi_channel_out, note, color)
                self.out_port.send_message([NOTE_ON + self.midi_channel_out, note, color])
                # Envoi vers Aeolus sur le deuxième port de sortie
                mode = 2 if self.keydown[note] else 1  # action 2 pour on, 1 pour off
                group = (8 - y) // 2  # 2 lignes par groupe à partir du haut
                stop_number = x - 1 + (((8 - y) & 1) * 9)
                print('Envoi vers Aeolus: mode', mode, 'groupe', group, 'registre', stop_number)
                self.out_port2.send_message([CONTROL_CHANGE + self.midi_channel_out2, 98, 0x40 + (mode << 4) + group])
                self.out_port2.send_message([CONTROL_CHANGE + self.midi_channel_out2, 98, stop_number])
            else:
                # Relachement du pad, aucun changement
                pass
        else:
            logging.warning("Message MIDI inattendu: %s %s %s", message[0], message[1], message[2])
        self.in_callback = False
        return


class MidiMapper:
    """Show incoming MIDI messages from launchpad"""
    def __init__(self, port_num_in, port_num_out, midi_channel_in=0, midi_channel_out=0, midi_channel_out2=0):
        self.port_num_in = port_num_in
        self.port_num_out = port_num_out
        self.midi_channel_in = midi_channel_in
        self.midi_channel_out = midi_channel_out
        self.midi_channel_out2 = midi_channel_out2
        # Nous aurons besoin de la sortie depuis l'intérieur du callback
        # Il faut donc l'initialiser en premier
        try:
            self.midiout, self.port_name_out = open_midiport(port_num_out, 'output', interactive=False)
            logging.info("%s ouvert en sortie", self.port_name_out)
        except Exception as e:
            logging.error("Echec d'ouverture en sortie %s", e)
            sys.exit(1)
        # Passe le launchpad en mode session
        self.midiout.send_message([0xF0, 0x00, 0x20, 0x29, 0x02, 0x18, 0x22, 0x00, 0xF7])

        # Creation du deuxième port de sortie en tant que port virtuel
        try:
            self.midiout2 = open_midioutput(None, client_name='to_aeolus', use_virtual=True)[0]
        except Exception as e:
            logging.error("Echec d'ouverture de la deuxième sortie %s", e)
            sys.exit(1)

        # Initialisation de l'entrée MIDI
        try:
            self.midiin, self.port_name_in = open_midiport(port_num_in, 'input', interactive=False)
            logging.info("%s ouvert en entrée", self.port_name_in)
            self.midiin.ignore_types(sysex=True, timing=True, active_sense=True)
            self.midiin.set_callback(MidiInputHandler(
                self.midiin, self.midi_channel_in,
                self.midiout, self.midi_channel_out,
                self.midiout2, self.midi_channel_out2))
        except Exception as e:
            logging.error("Echec d'ouverture en entrée %s", e)
            sys.exit(1)


def list_midi_ports():
    """ Imprime une liste des ports MIDI Alsa"""
    if API_LINUX_ALSA in get_compiled_api():
        print('Input:')
        for p in MidiIn(API_LINUX_ALSA).get_ports():
            print(p)
        print('Output:')
        for p in MidiOut(API_LINUX_ALSA).get_ports():
            print(p)
    else:
        print('Ce programme nécessite Alsa')


def main(argv=None):

    def usage():
        print(sys.argv[0], "-h -l -i port -o port -c channel -v")

    if argv is None:
        argv = sys.argv
    try:
        opts, args = getopt.getopt(sys.argv[1:],
            "hli:o:c:v",
            ["help", "list", "input=", "output=", "channel=", "verbose"])
    except getopt.GetoptError as err:
        # Affiche l'aide et sort
        print(str(err))  # Imprimera quelque chose comme "option -a not recognized"
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
            assert False, "option non reconnue"
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
