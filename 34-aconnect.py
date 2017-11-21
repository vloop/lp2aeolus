#!/usr/bin/python3
# -*- coding: utf-8 -*-
# MPER 20171101
# See http://linuxfr.org/users/illwieckz/journaux/pyalsacap-python-pointeurs-et-cartes-sons
# See alsa source seq.h, seqmid.h, control.h, aconnect.c
import logging

from ctypes import *

# from seq.h
SND_SEQ_OPEN_OUTPUT = 1  # define SND_SEQ_OPEN_OUTPUT    1    /**< open for output (write) */
SND_SEQ_OPEN_INPUT = 2  # define SND_SEQ_OPEN_INPUT    2    /**< open for input (read) */
SND_SEQ_OPEN_DUPLEX = SND_SEQ_OPEN_OUTPUT | SND_SEQ_OPEN_INPUT  # define SND_SEQ_OPEN_DUPLEX    (SND_SEQ_OPEN_OUTPUT|SND_SEQ_OPEN_INPUT)    /**< open for both input and output (read/write) */


def aconnect(from_port, to_port):
    libasound = cdll.LoadLibrary("libasound.so.2")

    seq = c_void_p()  # snd_seq_t *seq;
    queue = c_int(0)
    convert_time = c_int(0)
    convert_real = c_int(0)
    exclusive = c_int(0)
    # list_perm = c_int(0)  # int list_perm = 0;
    client = c_int()  # int client;
    list_subs = c_int(0)  # int list_subs = 0;
    subs = c_void_p()  # snd_seq_port_subscribe_t *subs;
    # snd_seq_addr_t sender, dest;
    sender = c_void_p()
    dest = c_void_p()

    # int snd_seq_open(snd_seq_t **handle, const char *name, int streams, int mode);
    # if (snd_seq_open(&seq, "default", SND_SEQ_OPEN_DUPLEX, 0) < 0) {
    if (libasound.snd_seq_open(byref(seq), b"default", SND_SEQ_OPEN_DUPLEX, 0) < 0):
        logging.error("can't open sequencer\n")
        return(1)
    # print(seq, seq.value)  # Looks ok

    # int snd_seq_client_id(snd_seq_t *handle);
    # if ((client = snd_seq_client_id(seq)) < 0) {
    client = libasound.snd_seq_client_id(seq)
    if (client < 0):
        libasound.snd_seq_close(seq)
        logging.error("can't get client id")
        return(1)

    # set client info
    # if (snd_seq_set_client_name(seq, "ALSA Connector") < 0) {
    if (libasound.snd_seq_set_client_name(seq, b"ALSA Connector") < 0):
        libasound.snd_seq_close(seq)
        logging.error("can't set client info")
        return(1)

    # set subscription
    # Example use of original aconnect:
    # aconnect 14:0 16:32
    # in seqmid.h:
    # int snd_seq_parse_address(snd_seq_t *seq, snd_seq_addr_t *addr, const char *str);
    # if (snd_seq_parse_address(seq, &sender, argv[optind]) < 0) {
    # if (libasound.snd_seq_parse_address(seq, byref(sender), b"14:0") < 0):  # ok
    if (libasound.snd_seq_parse_address(seq, byref(sender), from_port) < 0):
        libasound.snd_seq_close(seq)
        logging.error("invalid sender address %s", from_port)
        return(1)
    # if (snd_seq_subscribe_port(seq, subs) < 0) {

    # if (snd_seq_parse_address(seq, &dest, argv[optind + 1]) < 0) {
    # if (libasound.snd_seq_parse_address(seq, byref(dest), b"16:32") < 0):
    if (libasound.snd_seq_parse_address(seq, byref(dest), to_port) < 0):
        # Also ok with aeolus:In
        libasound.snd_seq_close(seq)
        logging.error("invalid destination address %s", to_port)
        return(1)

    # define snd_seq_port_subscribe_alloca(ptr) \
    #    __snd_alloca(ptr, snd_seq_port_subscribe)
    # int snd_seq_port_subscribe_malloc(snd_seq_port_subscribe_t **ptr);
    # define __snd_alloca(ptr,type) do { *ptr = (type##_t *) alloca(type##_sizeof()); memset(*ptr, 0, type##_sizeof()); } while (0)
    # size_t snd_seq_port_subscribe_sizeof(void);
    # print(libasound.snd_seq_port_subscribe_sizeof()) # --> 80
    # What if it was not an exact multiple of 8?
    subs = (c_void_p * int(libasound.snd_seq_port_subscribe_sizeof() / sizeof(c_void_p)))()
    # snd_seq_port_subscribe_alloca(&subs);

    libasound.snd_seq_port_subscribe_set_sender(subs, byref(sender))
    libasound.snd_seq_port_subscribe_set_dest(subs, byref(dest))
    libasound.snd_seq_port_subscribe_set_queue(subs, queue)
    libasound.snd_seq_port_subscribe_set_exclusive(subs, exclusive)
    libasound.snd_seq_port_subscribe_set_time_update(subs, convert_time)
    libasound.snd_seq_port_subscribe_set_time_real(subs, convert_real)

    # if (snd_seq_get_port_subscription(seq, subs) == 0) {
    if (libasound.snd_seq_get_port_subscription(seq, subs) == 0):
        libasound.snd_seq_close(seq)
        logging.error("Connection from %s to %s is already subscribed", from_port, to_port)
        return(1)

    # if (snd_seq_subscribe_port(seq, subs) < 0) {
    if (libasound.snd_seq_subscribe_port(seq, subs) < 0):
        libasound.snd_seq_close(seq)
        logging.error("Connection from %s to %s failed", from_port, to_port)
        return (1)

    return(0)


if __name__ == '__main__':
    print(aconnect(b"VMPK Output", b"aeolus"))
