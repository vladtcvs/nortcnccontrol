#/usr/bin/env python3

import abc
import euclid3
import math

import homing
import linear

class Machine(object):
    outcode = []
    actions = []
    feed = 1
    fastfeed = 1200
    acc = 1000
    jump = 2000
    pos = euclid3.Vector3()
    relative = False

    def __init__(self):
        self.curaction = self.__none

    def __none(self, cmds):
        pass

    def __move(self, cmds):
        newpos = self.pos
        fast = False
        for cmd in cmds:
            if cmd.type == "G" and cmd.value == 0:
                fast = True
        if self.relative:
            for cmd in cmds:
                if cmd.type == "X":
                    newpos = euclid3.Vector3(cmd.value + newpos.x, newpos.y, newpos.z)
                elif cmd.type == "Y":
                    newpos = euclid3.Vector3(newpos.x, cmd.value + newpos.y, newpos.z)
                elif cmd.type == "Z":
                    newpos = euclid3.Vector3(newpos.x, newpos.y, newpos.z + cmd.value)
        else:
            for cmd in cmds:
                if cmd.type == "X":
                    newpos = euclid3.Vector3(cmd.value, newpos.y, newpos.z)
                elif cmd.type == "Y":
                    newpos = euclid3.Vector3(newpos.x, cmd.value, newpos.z)
                elif cmd.type == "Z":
                    newpos = euclid3.Vector3(newpos.x, newpos.y, cmd.value)
        for cmd in cmds:
            if cmd.type == "F":
                self.feed = cmd.value
        delta = newpos - self.pos
        if not fast:
            self.actions.append(linear.LinearMovement(delta, self.feed, self.acc))
        else:
            self.actions.append(linear.LinearMovement(delta, self.fastfeed, self.acc))
        self.pos = newpos

    def __tobegin(self, cmds):
        x = False
        y = False
        z = False
        for cmd in cmds:
            if cmd.type == "X":
                x = True
            elif cmd.type == "Y":
                y = True
            elif cmd.type == "Z":
                z = True
        self.actions.append(homing.ToBeginMovement(x, y, z))

    def __set_curaction(self, action):
        if self.curaction != self.__none:
            raise Exception ("Invalid command")
        self.curaction = action

    def __set_acceleration(self, frame):
        for cmd in frame.commands:
            if cmd.type == "T":
                self.acc = cmd.value
            elif cmd.type == "F":
                self.jump = cmd.value

    def process(self, frame):
        for cmd in frame.commands:
            if cmd.type == "G" and (cmd.value == 0 or cmd.value == 1):
                self.__set_curaction(self.__move)
            elif cmd.type == "G" and cmd.value == 90:
                self.relative = False
            elif cmd.type == "G" and cmd.value == 91:
                self.relative = True
            elif cmd.type == "G" and cmd.value == 28:
                self.__set_curaction(self.__tobegin)
            elif cmd.type == "M" and cmd.value == 204:
                self.__set_acceleration(frame)
        if self.curaction != None:
            self.curaction(frame.commands)
        self.curaction = self.__none

    def concat_moves(self):
        prevmove = None
        prevfeed = 0
        prevdir = euclid3.Vector3(0, 0, 0)
        moves = [action for action in self.actions if action.is_moving()]
        for move in moves:
            curfeed = move.feed
            curdir = move.dir0()

            if prevmove != None:
                cosa = curdir.x * prevdir.x + curdir.y * prevdir.y + curdir.z * prevdir.z
                if cosa > 0:
                    sina = math.sqrt(1-cosa**2)
                    if sina < 1e-3:
                        # The same direction
                        #
                        # startfeed = prevfeed
                        # endfeed <= prevfeed
                        # startfeed <= curfeed

                        startfeed = min(curfeed, prevfeed)
                        endfeed = startfeed
                        move.feed0 = startfeed
                        prevmove.feed1 = endfeed
                    else:
                        # Have direction change
                        #
                        # endfeed = startfeed * cosa
                        # startfeed * sina <= jump
                        # endfeed <= prevfeed
                        # startfeed <= curfeed

                        startfeed = curfeed
                        startfeed = min(startfeed, self.jump / sina)
                        endfeed = startfeed * cosa

                        move.feed0 = startfeed
                        prevmove.feed1 = endfeed
                else:
                    # Change direction more than 90
                    #
                    # endfeed = 0
                    # startfeed = 0
                    prevmove.feed1 = 0
                    move.feed0 = 0
            else:
                # first move
                move.feed0 = 0

            prevfeed = curfeed
            prevmove = move           
            prevdir = move.dir1()

    def generate_control(self):
        for act in self.actions:
            self.outcode.append(act.make_code())
