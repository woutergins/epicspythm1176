import numpy as np
import time
from pcaspy import Driver, SimpleServer, Severity
import threading as th
import queue
import thm1176MF
import usbtmc
from usbtmc.usbtmc import find_device

prefix = 'METROLAB:'

pvdb = {
        'Block'   : {'type': 'int', 'value': 1},
        'Average' : {'type': 'int', 'value': 200},
        'Period'  : {'type': 'float', 'value': 0.001},

        'Trigger' : {'type': 'enum', 'enums': [''], 'value': 0},
        'Range'   : {'type': 'enum', 'enums': [''], 'value': 0},

        'B'       : {'type': 'float', 'value': 0, 'unit': 'T'},
        'Bx'      : {'type': 'float', 'value': 0, 'unit': 'T'},
        'By'      : {'type': 'float', 'value': 0, 'unit': 'T'},
        'Bz'      : {'type': 'float', 'value': 0, 'unit': 'T'},

        'dt'      : {'type': 'float', 'value': 0, 'unit': 's'},
        'dB'      : {'type': 'float', 'value': 0, 'unit': 'T/s'},
        'dBx'     : {'type': 'float', 'value': 0, 'unit': 'T/s'},
        'dBy'     : {'type': 'float', 'value': 0, 'unit': 'T/s'},
        'dBz'     : {'type': 'float', 'value': 0, 'unit': 'T/s'},

        'Timer'    : {'type': 'float', 'value': 0.5},
        'Connected': {'type': 'enum', 'enums': ['Not connected', 'Connected'], 'states': [Severity.MAJOR_ALARM, Severity.NO_ALARM], 'value': 0},
       }

class THM1176MFDriver(Driver):
    def __init__(self):
        Driver.__init__(self)

        r = find_device(idVendor=0x1bfa, idProduct=0x0498)
        period = self.getParam('Period')
        average = self.getParam('Average')
        block = self.getParam('Block')
        api = 'usbtmc'

        self.setParam('Connected', 0)
        self.updatePVs()
        self.instruction_queue = queue.Queue()
        self.device = thm1176MF.thm1176(address=r, period=period, average=average, block=block, api=api)

        ranges = list(self.device.ranges)
        ranges.append('AUTO')
        self.setParamEnums('Range', ranges)

        res, auto = self.device.range
        details = self.getParamInfo('Range')
        if auto:
            self.setParam('Range', details['enums'].index('AUTO'))
        else:
            self.setParam('Range', details['enums'].index(res))

        self.setParamEnums('Trigger', list(self.device.triggers))
        self.setParam('Trigger', self.getParamInfo('Trigger', info_keys=['enums'])['enums'].index(self.device.trigger.capitalize()))
        self.setParam('Connected', 1)
        self.updatePVs()

        self.mapping = {
                'Block': self.setBlock,
                'Average': self.setAverage,
                'Period': self.setPeriod,
                'Trigger': self.setTrigger,
                'Range': self.setRange,
                'Timer': self.setTimer,
                }

        self.looping = True
        self.t = time.perf_counter()
        self.timerThread = th.Thread(target=self.signalData)
        self.timerThread.setDaemon(True)

        self.loopThread = th.Thread(target=self.loop)
        self.loopThread.setDaemon(True)
        self.loopThread.start()
        self.timerThread.start()

    def signalData(self):
        while self.looping:
            if self.instruction_queue.empty():
                self.instruction_queue.put('DATA')
                time.sleep(self.getParam('Timer'))

    def setRange(self, range):
        range = self.getParamInfo('Range', info_keys=['enums'])['enums'][range]
        self.device.range = range
        res, auto = self.device.range
        details = self.getParamInfo('Range')
        if auto:
            self.setParam('Range', details['enums'].index('AUTO'))
        else:
            self.setParam('Range', details['enums'].index(res))
        self.updatePVs()

    def setTrigger(self, trigger):
        trigger = self.getParamInfo('Trigger', info_keys=['enums'])['enums'][trigger]
        self.device.trigger = trigger
        trigger = self.device.trigger.capitalize()
        details = self.getParamInfo('Trigger')
        self.setParam('Range', details['enums'].index(trigger))

    def setBlock(self, block):
        block = max(1, block)
        self.checkTimer(block=block)
        self.device.block = int(block)
        self.setParam('Block', self.device.block)

    def setAverage(self, average):
        average = max(10, average)
        self.checkTimer(average=average)
        self.device.average = int(average)
        self.setParam('Average', self.device.average)

    def setPeriod(self, period):
        period = max(0.05, period)
        self.checkTimer(period=period)
        self.device.period = int(period)
        self.setParam('Period', self.device.period)

    def checkTimer(self, block=None, average=None, period=None, timer=None):
        if block is None:
            block = self.device.block
        if average is None:
            average = self.device.average
        if period is None:
            period = self.device.period
        if timer is None:
            timer = self.getParam('Timer')
        min_timer = (block + 1) * period
        self.setParam('Timer', max(min_timer, timer))

    def setTimer(self, timer):
        self.checkTimer(timer=timer)

    def loop(self):
        while self.looping:
            instr = self.instruction_queue.get(block=True)
            try:
                if instr == 'DATA':
                    self.device.get_data_array()
                    try:
                        B = self.device.B[-1]
                        X = self.device.X[-1]
                        Y = self.device.Y[-1]
                        Z = self.device.Z[-1]
                        dt = self.device.dt

                        dB = (B - self.getParam('B')) / dt
                        dX = (X - self.getParam('Bx')) / dt
                        dY = (Y - self.getParam('By')) / dt
                        dZ = (Z - self.getParam('Bz')) / dt

                        self.setParam('B', B)
                        self.setParam('Bx', X)
                        self.setParam('By', Y)
                        self.setParam('Bz', Z)

                        self.setParam('dB', dB)
                        self.setParam('dBx', dX)
                        self.setParam('dBy', dY)
                        self.setParam('dBz', dZ)

                        self.setParam('dt', dt)
                    except IndexError:
                        pass
                else:
                    reason, value = instr
                    reason = reason.split(':')[-1]
                    if reason in self.mapping.keys():
                        self.mapping[reason](value)
                self.setParam('Connected', 1)
            except:
                self.setParam('Connected', 0)
                self.device.close()
                r = find_device(idVendor=0x1bfa, idProduct=0x0498)
                period = self.getParam('Period')
                average = self.getParam('Average')
                block = self.getParam('Block')
                api = 'usbtmc'

                self.device = thm1176MF.thm1176(address=r, period=period, average=average, block=block, api=api)
            self.updatePVs()

    def write(self, reason, value):
        r = reason.split(':')[-1]
        if reason in self.mapping.keys():
            try:
                self.instruction_queue.put((reason, value), block=True)
                super().write(reason, value)
            except:
                pass

    def stop(self):
        self.looping = False

if __name__ == '__main__':
    server = SimpleServer()
    server.createPV(prefix, pvdb)
    driver = THM1176MFDriver()

    while True:
        server.process(0.001)
