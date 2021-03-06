#!/usr/bin/env python3

import machine
import machine.machine
import machine.parser

import sender
import sender.emulatorsender

import sys

class Controller(object):
    def __init__(self, sender):
        self.sender = sender
        self.machine = machine.machine.Machine(self.sender)
        self.parser = machine.parser.GLineParser()
        self.machine.paused += self.continue_on_pause
        self.machine.finished += self.done

    def continue_on_pause(self, reason):
        print(reason)
        self.machine.WorkContinue()

    def done(self):
        print("Done")

    def load(self, lines):
        frames = []
        for line in lines:
            frame = self.parser.parse(line)
            frames.append(frame)
        self.machine.Load(frames)

    def run(self):
        self.machine.WorkStart()

file = sys.argv[1]

ctl = Controller(sender.emulatorsender.EmulatorSender())

f = open(file)
lines = f.readlines()
f.close()

ctl.load(lines)

ctl.run()
