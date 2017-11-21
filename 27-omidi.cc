// ----------------------------------------------------------------------------
//
//  Copyright (C) 2003-2013 Fons Adriaensen <fons@linuxaudio.org>
//    
//  This program is free software; you can redistribute it and/or modify
//  it under the terms of the GNU General Public License as published by
//  the Free Software Foundation; either version 3 of the License, or
//  (at your option) any later version.
//
//  This program is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//  GNU General Public License for more details.
//
//  You should have received a copy of the GNU General Public License
//  along with this program.  If not, see <http://www.gnu.org/licenses/>.
//
// ----------------------------------------------------------------------------
// Added MPER 20171110


#include "omidi.h"



Omidi::Omidi (Lfq_u8 *qfb, const char *appname) :
    A_thread ("Omidi"),
//    _qnote (qnote),
    _qfb (qfb),
//    _midimap (midimap),
    _appname (appname)
{
}


Omidi::~Omidi (void)
{
}


void Omidi::terminate (void)
{
/*
    snd_seq_event_t E;

    if (_handle)
    {   
	snd_seq_ev_clear (&E);
	snd_seq_ev_set_direct (&E);
	E.type = SND_SEQ_EVENT_USR0;
	E.source.port = _opport;
	E.dest.client = _client;
	E.dest.port   = _ipport;
	snd_seq_event_output_direct (_handle, &E);
    }
*/
}


void Omidi::thr_main (void)
{
    open_midi ();
    proc_queue ();
    close_midi ();
    send_event (EV_EXIT, 1);
}


void Omidi::open_midi (void)
{
    snd_seq_client_info_t *C;
//    M_midi_info *M;

    if (snd_seq_open (&_handle, "hw", SND_SEQ_OPEN_DUPLEX, 0) < 0)
    {
        fprintf(stderr, "Error opening secondary ALSA sequencer.\n");
        exit(1);
    }

    snd_seq_client_info_alloca (&C);
    snd_seq_get_client_info (_handle, C);
    _client = snd_seq_client_info_get_client (C);
    snd_seq_client_info_set_name (C, "aeolus2");
    snd_seq_set_client_info (_handle, C);
/*
    if ((_ipport = snd_seq_create_simple_port (_handle, "In",
        SND_SEQ_PORT_CAP_WRITE | SND_SEQ_PORT_CAP_SUBS_WRITE,
        SND_SEQ_PORT_TYPE_APPLICATION)) < 0)
    {
        fprintf(stderr, "Error creating sequencer input port.\n");
        exit(1);
    }
*/
    if ((_opport = snd_seq_create_simple_port (_handle, "Out",
         SND_SEQ_PORT_CAP_READ | SND_SEQ_PORT_CAP_SUBS_READ,
         SND_SEQ_PORT_TYPE_APPLICATION)) < 0)
    {
        fprintf(stderr, "Error creating sequencer secondary output port.\n");
        exit(1);
    }
/*
    M = new M_midi_info ();
    M->_client = _client;
    M->_ipport = _ipport;    int              c, d, f, m, n, p, t, v;

    memcpy (M->_chbits, _midimap, 16 * sizeof (uint16_t));
    send_event (TO_MODEL, M);
*/
}


void Omidi::close_midi (void)
{
    if (_handle) snd_seq_close (_handle);
}

void Omidi::proc_queue (void) 
{
    int p, t, v, e;
    snd_seq_event_t ev; // MPER
    fprintf(stderr, "Waiting for feedback queue\n");
    while (true)
    {
        fprintf(stderr, "Waiting for event\n");
        // usleep(2000);
        e = get_event();
        fprintf(stderr, "Got event %u\n", e);

        while (_qfb->read_avail () >= 3)
	{
	    t = _qfb->read (0);
	    p = _qfb->read (1);
	    v = _qfb->read (2);
	    _qfb->read_commit (3);
            fprintf(stderr, "Received from feedback queue %X %X %X\n", t, p, v);
	    if ((t & 0xF0) == 0xB0)
	    {
		snd_seq_ev_clear(&ev);
		snd_seq_ev_set_direct(&ev);
		snd_seq_ev_set_subs(&ev);
		// snd_seq_ev_set_note(&ev, 0, 64, 127, 1);
		snd_seq_ev_set_controller (&ev, t & 0x0F, p, v);
		snd_seq_ev_set_source(&ev, _opport);
		// snd_seq_ev_set_dest(&ev, synth_addr.client, synth_addr.port);
		snd_seq_event_output_direct(_handle, &ev);
		fprintf(stderr, "Sent to port %u\n", _opport);
	    }
	    else
	    {
                fprintf(stderr, "Unexpected status byte %X\n", t);
	    }
	}
    }
}

