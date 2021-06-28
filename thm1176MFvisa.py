from pyvisa import util
import pyvisa as visa
import numpy as np
from collections import deque
import time
import atexit

range_dict = {'0.100000 T': '0.1 T', '0.300000 T': '0.3 T', '1.000000 T': '1 T', '3.000000 T': '3 T'}

class thm1176():
    id_fields = ['Manufacturer', 'Model', 'Serial', 'Version']

    def __init__(self, **kwargs):
        self.errors = deque([None]*10, 10)
        self.time_offset = time.time()
        r = kwargs.pop('address', None)
        if r is None:
            raise ValueError('address/device not given')

        self.device = visa.ResourceManager().open_resource(r)
        self.device.read_termination = '\n'
        self.device.chunk_size = 49216
        self.device.timeout = 10000

        def cleanup():
            self.device.write(':ABOR')
            self.device.close()

        atexit.register(cleanup)

        self.reset()
        header = self.get_id()
        for key in header.keys():
            setattr(self, key, header[key])

        res = self.device.query(':SENS:FLUX:RANG:ALL?')
        self.ranges = res.split(',')
        self.triggers = ['Immediate', 'Timer', 'Bus']

        self.block = kwargs.pop('block', 1)
        self.trigger = 'Timer'
        self.period = kwargs.pop('period', 0.01)
        self.range = kwargs.pop('range', 'AUTO')
        self.average = kwargs.pop('average', 10)
        self.format = kwargs.pop('format', 'ASCII')
        self.continuous = True
        self.enable_trigger()
        # get rid of erroneously large values
        self.timestamp = 0
        for _ in range(3):
            self.get_data_array()

    def close(self):
        self.disable_trigger()
        self.device.close()

    def reset(self):
        self.device.write('*RST')

    def read_errors(self, source):
        code = 1
        while code != 0:
            code, message = self.device.query(':SYSTEM:ERROR?').split(',')
            now = time.time() - self.time_offset
            code = int(code)
            error = 'Writing {}; code and message: {}, {}; time: {:.2f}'.format(source, code, message, now)
            self.errors.append(error)

    @property
    def format(self):
        return self.device.query(':FORMAT:DATA?')

    @format.setter
    def format(self, f):
        self.device.write(':FORMAT:DATA ' + f)
        self.read_errors('format')

    @property
    def range(self):
        res = self.device.query(':SENS:FLUX:RANG?')
        res = range_dict[res]
        auto = self.device.query(':SENS:FLUX:RANG:AUTO?')
        if auto == 'ON':
            auto = True
        else:
            auto = False
        return res, auto

    @range.setter
    def range(self, r):
        if r.upper() in self.ranges:
            self.device.write(':SENS:FLUX:RANG:AUTO OFF')
            self.device.write(':SENS:FLUX:RANG:UPP {}'.format(r.upper()))
            self.read_errors('manual range')
        elif r.upper() == 'AUTO':
            self.device.write(':SENS:FLUX:RANG:AUTO ON')
            self.read_errors('auto range')

    @property
    def average(self):
        return int(self.device.query(':AVERAGE:COUNT?'))

    @average.setter
    def average(self, av):
        av = int(av)
        self.device.write(':AVERAGE:COUNT {}'.format(av))
        self.read_errors('average')
        self.average_saved = av

    @property
    def trigger(self):
        return self.device.query(':TRIG:SOUR?')

    @trigger.setter
    def trigger(self, t):
        if t in self.triggers:
            self.device.write(':TRIG:SOUR {}'.format(t[:3].upper()))
            self.read_errors('trigger source')

    @property
    def period(self):
        p = self.device.query(':TRIG:TIM?')
        return float(p[:-2])
    
    @period.setter
    def period(self, p):
        p = np.clip(p, 122e-6, 2.79)
        self.device.write(':TRIG:TIM {:f}S'.format(p))
        self.read_errors('trigger period')
        self.period_saved = p

    @property
    def block(self):
        return int(self.device.query(':TRIG:COUNT?'))
    
    @block.setter
    def block(self, b):
        b = int(b)
        self.device.write(':TRIG:COUNT {}'.format(b))
        self.read_errors('block size')
        self.block_saved = b

    @property
    def continuous(self):
        return self.device.query(':INIT:CONTINUOUS?')

    @continuous.setter
    def continuous(self, c):
        if c:
            c = 'ON'
        else:
            c = 'OFF'
        self.device.write(':INIT:CONTINUOUS {}'.format(c))
        self.read_errors('continous')

    def enable_trigger(self):
        self.device.write(':INIT:IMM:ALL')
        self.read_errors('enable triggers')

    def disable_trigger(self):
        self.device.write(':ABOR')
        self.read_errors('abort triggers')

    def get_id(self):
        """Code taken from https://github.com/Hyperfine/pyTHM1176/blob/master/pyTHM1176/api/thm_visa_api.py (copyright Cedric Hugon)"""
        self.device.write('*IDN?')
        res = self.device.read()
        id_vals = res.split(',')
        header = {field: val for field, val in zip(self.id_fields, id_vals)}
        return header

    def get_data_array(self):
        res = self.device.query(':FETC:ARR:X? {0},{1};:FETC:ARR:Y? {0},{1};:FETC:ARR:Z? {0},{1};:FETC:TIMESTAMP?'.format(self.block_saved, 'MAX'))
        self.X, self.Y, self.Z, t = res.split(';')
        self.X = np.fromstring(self.X.replace(' T', ''), sep=',')
        self.Y = np.fromstring(self.Y.replace(' T', ''), sep=',')
        self.Z = np.fromstring(self.Z.replace(' T', ''), sep=',')
        self.B = np.sqrt(self.X*self.X+self.Y*self.Y+self.Z*self.Z)
        self.new_timestamp = int(t, 0) * 1e-9
        self.dt = self.new_timestamp - self.timestamp
        self.timestamp = self.new_timestamp
        self.read_errors('data')

    def stop_acquisition(self):
        res = self.device.query(':ABORT;*STB?')
        while res[0] != '0':
            print("Error code: {}".format(res))
            res = self.device.query(':SYSTEM:ERROR?;*STB?')
            self.errors.append(res)
        print("THM1176 status: {}".format(res))

