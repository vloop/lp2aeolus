#!/usr/bin/python3
# -*- coding: utf-8 -*-
# MPER 20171012

import sys
import getopt
import logging
import time

from subprocess import Popen

from rtmidi.midiutil import open_midiport, open_midioutput, list_available_ports
from rtmidi.midiconstants import (NOTE_OFF, NOTE_ON, CONTROL_CHANGE, PROGRAM_CHANGE,
    NRPN_MSB, NRPN_LSB, DATA_ENTRY_MSB, DATA_ENTRY_LSB, END_OF_EXCLUSIVE, SYSTEM_EXCLUSIVE)

from rtmidi import (API_LINUX_ALSA, MidiIn, MidiOut, get_compiled_api)

import aconnect

AEOLUS_CC = 98
AEOLUS_CC2 = AEOLUS_CC + 1
MAX_STOPS = 18
MAX_GROUPS = 4
LP_BLACK = 0
LP_WHITE = 3
LP_BLUE = 45
LP_LTBLUE = 36
LP_RED = 6
LP_LTRED = 52
LP_GREEN = 16
LP_LTGREEN = 64
LP_YELLOW = 12
LP_BROWN = 105
keyuptypecolor = [LP_BLUE, LP_BLACK, LP_BROWN, LP_LTGREEN]
keydowntypecolor = [LP_LTBLUE, LP_WHITE, LP_YELLOW, LP_GREEN]


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
        self.keydowncolor = [LP_WHITE] * 128
        self.keyupcolor = [LP_BLACK] * 128
        self.mode_in = None
        self.type_in = None
        self.group_in = None

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
                                self.out_port.send_message([NOTE_ON + self.midi_channel_out, note, self.keyupcolor[note]])
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
                                # Rien à faire (désactivation du groupe)
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
                                color = self.keydowncolor[note] if self.keydown[note] else self.keyupcolor[note]
                                self.out_port.send_message([NOTE_ON + self.midi_channel_out, note, color])
            elif message[1] == AEOLUS_CC2:
                # Ce nouveau CC provient d'Aeolus et définit le type
                # d'élément du GUI, et donc sa couleur
                # print("Aeolus type:", message[2])
                if (message[2] & 0x40):
                    # Message type/groupe d'Aeolus
                    self.type_in = (message[2] >> 4) & 0x03
                    self.group_in = message[2] & 0x07
                    print("Aeolus: type", self.type_in, "groupe", self.group_in)
                else:
                    # Numéro de registre d'Aeolus
                    if self.type_in is None:
                        logging.error("Type non défini")
                    else:
                        self.stop_number_in = message[2] & 0x1F
                        if self.stop_number_in < MAX_STOPS and self.group_in < MAX_GROUPS:
                            note = self.aeolus_cc_to_note(self.group_in, self.stop_number_in)
                            print("Aeolus: type", self.type_in, "groupe", self.group_in, "registre", self.stop_number_in, note)
                            self.keyupcolor[note] = keyuptypecolor[self.type_in]
                            self.keydowncolor[note] = keydowntypecolor[self.type_in]
                            print("Couleurs:", self.keydowncolor[note], self.keyupcolor[note])
                            color = self.keydowncolor[note] if self.keydown[note] else self.keyupcolor[note]
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
                color = self.keydowncolor[note] if self.keydown[note] else self.keyupcolor[note]
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


def get_midi_port_num_in(s):
    p_num = 0
    for p in MidiIn(API_LINUX_ALSA).get_ports():
        if p.startswith(s):
            return(p_num)
        p_num += 1
    return(None)


def get_midi_port_num_out(s):
    p_num = 0
    for p in MidiOut(API_LINUX_ALSA).get_ports():
        if p.startswith(s):
            return(p_num)
        p_num += 1
    return(None)


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

    # Cherche le launchpad si les ports ne sont pas donnés via -i et -o
    s = 'Launchpad MK2'
    if input_port is None:
        input_port = get_midi_port_num_in(s)
        if input_port is not None:
            print('Trouvé', s, 'en entrée:', input_port)
    if output_port is None:
        output_port = get_midi_port_num_out(s)
        if output_port is not None:
            print('Trouvé', s, 'en sortie:', output_port)

    app = MidiMapper(port_num_in=input_port, port_num_out=output_port, midi_channel_in=channel, midi_channel_out=channel, midi_channel_out2=channel)

    # Tente de se connecter avec Aeolus dans les deux sens
    connected = True
    # aeolus:Out KO avec Aeolus 0.9.5f ??
    # fonctionne avec 129:1 et avec aeolus:1
    # pb de gestion du nom/du numéro à l'ouverture du port dans Aeolus?
    # pq les deux ports aeolus ont-ils le même numéro (132:0 et 132:1)
    if (aconnect.aconnect(b"aeolus:1", b"RtMidiIn Client") == 1):
        logging.error("Echec de connection depuis Aeolus")
        connected = False
    if (aconnect.aconnect(b"to_aeolus", b"aeolus:In") == 1):
        logging.error("Echec de connection vers Aeolus")
        connected = False
    if not connected:
        print("Démarrage de Aeolus...")
        Popen("aeolus")
        time.sleep(1)
        connected = True
        if (aconnect.aconnect(b"aeolus:1", b"RtMidiIn Client") == 1):
            logging.error("Echec de connection depuis Aeolus")
            connected = False
        if (aconnect.aconnect(b"to_aeolus", b"aeolus:In") == 1):
            logging.error("Echec de connection vers Aeolus")
            connected = False
    if not connected:
        list_midi_ports()

    # Demande à Aeolus sa configuration via la note spéciale 23
    print("Envoi de", [NOTE_ON + app.midi_channel_out, 23, 127])
    app.midiout2.send_message([NOTE_ON + app.midi_channel_out, 23, 127])

    print('En attente de message MIDI')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nInterrompu par l\'utilisateur')
    print('Fini')


if __name__ == '__main__':
    main()
