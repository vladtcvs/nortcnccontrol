#!/usr/bin/env python3

import time
import sys
import serial
from common import event
import threading
import re

class SerialSender(object):

    class SerialReceiver(threading.Thread):

        def __init__(self, ser, finish_event, ev_completed, ev_started, ev_slots):
            threading.Thread.__init__(self)
            self.ser = ser
            self.finish_event = finish_event
            self.recompleted = re.compile(r"completed N:([0-9]+) Q:([0-9]+).*")
            self.restarted = re.compile(r"started N:([0-9]+) Q:([0-9]+).*")
            self.requeued = re.compile(r"queued N:([0-9]+) Q:([0-9]+).*")
            self.reerror = re.compile(r"error N:([0-9]+).*")
            self.ev_completed = ev_completed
            self.ev_started = ev_started
            self.ev_slots = ev_slots

        def run(self):
            while not self.finish_event.is_set():
                ans = self.ser.readline().decode("utf8")
                print("Received answer: %s" % ans)
                match = self.restarted.match(ans)
                if match != None:
                    print("Start received")
                    Nid = match.group(1)
                    self.ev_started(Nid)
                    Q = int(match.group(2))
                    self.ev_slots(Q)
                    continue

                match = self.recompleted.match(ans)
                if match != None:
                    print("Completed received")
                    Nid = match.group(1)
                    self.ev_completed(Nid)
                    Q = int(match.group(2))
                    self.ev_slots(Q)
                    continue

                match = self.requeued.match(ans)
                if match != None:
                    Q = int(match.group(2))
                    self.ev_slots(Q)
                    continue

                match = self.reerror.match(ans)
                if match != None:
                    Nid = match.group(1)
                    continue

                print("Unknown answer from MCU: %s" % ans)

    queued = event.EventEmitter()
    completed = event.EventEmitter()
    started = event.EventEmitter()
    has_slots = threading.Event()
    
    def __init__(self, port, bdrate):
        self.__id = 0    
        self.__qans = threading.Event()
        self.__slots = event.EventEmitter()
        self.__finish_event = threading.Event()
    
        self.port = port
        self.baudrate = bdrate
        self.__ser = serial.Serial(self.port, self.baudrate,
                                 bytesize=8, parity='N', stopbits=1)
        self.__listener = self.SerialReceiver(self.__ser, self.__finish_event,
                                              self.completed, self.started, self.__slots)
        
        self.__slots += self.__on_slots
        self.__listener.start()
        self.has_slots.set()

    def __on_slots(self, Q):
        if Q == 0:
            self.has_slots.clear()
        else:
            self.has_slots.set()
        self.__qans.set()

    def send_command(self, command):
        self.__qans.clear()
        cmd = ("N%i" % self.__id) + command + "\n"
        print("Sending command %s" % cmd)
        self.queued(self.__id)
        self.__ser.write(bytes(cmd, "UTF-8"))
        self.__ser.flush()
        oid = self.__id
        self.__id += 1
        self.__qans.wait()
        return oid

    def close(self):
        self.__finish_event.set()
        self.__ser.close()
