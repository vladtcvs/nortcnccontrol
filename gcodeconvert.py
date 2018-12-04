#!/usr/bin/env python3

import euclid3
import sys
import getopt
import abc
import threading
import queue

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from ui import guithread
from ui.guithread import InterfaceThread

from converter import machine
from converter.machine import Machine
from converter.parser import GLineParser
from converter.machinethread import MachineThread

from sender import serialsender

def usage():
    pass

class Controller(object):

    class UI2Machine(threading.Thread):
        def __init__(self, controller):
            threading.Thread.__init__(self)
            self.controller = controller

        def run(self):
            while not self.controller.finish_event.is_set():
                try:
                    uievent = self.controller.uievents.get(timeout=0.5)
                    if uievent == InterfaceThread.UIEvent.Finish:
                        self.controller.finish_event.set()

                    elif uievent == InterfaceThread.UIEvent.Continue:
                        self.controller.continue_event.set()

                    elif uievent == InterfaceThread.UIEvent.Start:
                        self.controller.continue_event.clear()
                        if self.controller.machine_thread != None:
                            self.controller.machine_thread.dispose()
                        self.controller.load_file(self.controller.file)
                        self.controller.machine_thread = MachineThread(self.controller.machine,
                                            self.controller.continue_event,
                                            self.controller.finish_event,
                                            self.controller.machine_events)
                        self.controller.machine_thread.start()

                    elif type(uievent) == InterfaceThread.UIEventDialogConfirmed:
                        pass
                        #if type(uievent.reason) == MachineThread.MachineToolEvent:
                        #    self.controller.continue_event.set()
                    elif type(uievent) == InterfaceThread.UIEventLoadFile:
                        self.controller.load_file(uievent.filename)
                    elif type(uievent) == InterfaceThread.UIEventHome:
                        self.controller.continue_event.clear()
                        if self.controller.machine_thread != None:
                            self.controller.machine_thread.dispose() 
                        self.controller.machine_thread = MachineThread(self.controller.machine,
                                            self.controller.continue_event,
                                            self.controller.finish_event,
                                            self.controller.machine_events)
                        self.controller.home(uievent.x, uievent.y, uievent.z)
                        self.controller.machine_thread.start()
                except queue.Empty:
                    pass
    
    class Machine2UI(threading.Thread):
        def __init__(self, controller):
            threading.Thread.__init__(self)
            self.controller = controller
        
        def run(self):
            while not self.controller.finish_event.is_set():
                try:
                    mevent = self.controller.machine_events.get(timeout=0.5)

                    if type(mevent) == MachineThread.MachineLineEvent:
                        line = mevent.line
                        self.controller.uicommands.put(InterfaceThread.UICommandActiveLine(line))

                    elif type(mevent) == MachineThread.MachineToolEvent:
                        tool = mevent.tool
                        message = "Insert tool #%i" % tool
                        self.controller.uicommands.put(InterfaceThread.UICommand.ModePaused)
                        self.controller.uicommands.put(InterfaceThread.UICommandShowDialog(message, mevent))
                    
                    elif type(mevent) == MachineThread.MachineEventPaused:
                        self.controller.uicommands.put(InterfaceThread.UICommand.ModePaused)
                        if mevent.display:
                            self.controller.uicommands.put(InterfaceThread.UICommandShowDialog("Paused"))
                    
                    elif mevent == MachineThread.MachineEvent.Running:
                        self.controller.uicommands.put(InterfaceThread.UICommand.ModeRun)

                    elif mevent == MachineThread.MachineEvent.Finished:
                        self.controller.uicommands.put(InterfaceThread.UICommandShowDialog("Program finished"))
                        self.controller.uicommands.put(InterfaceThread.UICommand.ModeInitial)
                    
                except queue.Empty:
                    pass

    def __init__(self, sender, file=None):
        self.frames = []

        self.sender = sender

        self.uievents = queue.Queue()
        self.uicommands = queue.Queue()
        self.ui = InterfaceThread(self.uicommands, self.uievents)

        self.finish_event = threading.Event()
        self.continue_event = threading.Event()
        self.load_file(file)
        
        self.machine_events = queue.Queue()
        self.machine_thread = None

    def __readfile(self, infile):
        if infile is None:
            return []
        res = []
        f = open(infile, "r")
        gcode = f.readlines()
        if infile != None:
            f.close()
        for l in gcode:
            res.append(l.splitlines()[0])
        return res

    def __load_file(self, name):
        """ Load and parse gcode file """
        parser = GLineParser()
        gcode = self.__readfile(name)
        self.frames = []

        self.uicommands.put(InterfaceThread.UICommand.Clear)

        try:
            for line in gcode:
                print("line %s" % line)
                frame = parser.parse(line)
                if frame == None:
                    raise Exception("Invalid line")
                self.frames.append(frame)
                self.uicommands.put(InterfaceThread.UICommandAddLine(line))

            self.machine.load(self.frames)
        except Exception as e:
            print("Except %s" % e)
            self.machine.init()

    def run(self):
        self.ui.start()
        self.uicommands.put(InterfaceThread.UICommand.ModeInitial)
        ui2m = self.UI2Machine(self)
        m2ui = self.Machine2UI(self)
        ui2m.start()
        m2ui.start()
        self.finish_event.wait()
        m2ui.join()
        ui2m.join()
        self.sender.close()

    def load_file(self, name):
        """ Load and parse gcode file """
        self.machine = Machine(self.sender)
        self.file = name
        self.__load_file(self.file)

    def home(self, x, y, z):
        self.machine.homing(x, y, z)

def main():
    
    infile = None
    port = None
    brate = 57600
    
    try:
        optlist, _ = getopt.getopt(sys.argv[1:], "i:p:b:h")
    except getopt.GetoptError as err:
        print(err)
        sys.exit(1)

    for o, a in optlist:
        if o == "-i":
            infile = a
        if o == "-p":
            port = a
        if o == "-b":
            brate = int(a)
        elif o == "-h":
            usage()
            sys.exit(0)

    if port is None:
        print("Please, specify port -p")
        sys.exit(1)

    sender = serialsender.SerialSender(port, brate)

    ctl = Controller(sender, infile)
    ctl.run()
    sys.exit(0)

if __name__ == "__main__":
    main()
