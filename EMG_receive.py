##############################
## Collect EMG data by NI   ##
##############################

import nidaqmx
from nidaqmx import constants
import numpy as np


class EMG_collector:

    def initialize(self):
        try:
            self.task = nidaqmx.task.Task()
            self.task.ai_channels.add_ai_voltage_chan("Dev1/ai0:1")  # "Dev2/ai0:1" "Dev3/ai0:1"?
            ######## Sampling rate: 500Hz ########
            self.task.timing.cfg_samp_clk_timing(rate=500, sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
            self.connected = True
            print("EMG Connected!")
        except:
            self.connected = False
            print('No EMG Connection! Please check and restart.')  # If No EMG connection, the system will not work.

    def collect_EMG(self):
        if self.connected:
            self.data = self.task.read(number_of_samples_per_channel=1)
            temp = np.array(self.data)
            print(temp.shape)
            ch1 = temp[0,:]
            ch2 = temp[1,:]
        else:
            ch1 = 0
            ch2 = 0
        return ch1, ch2
