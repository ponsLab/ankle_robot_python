##############################
## Collect EMG data by NI   ##
##############################

import nidaqmx
from nidaqmx import constants
import numpy as np


class EMG_collector:

    def initialize(self):
        self.task = nidaqmx.task.Task()
        self.task.ai_channels.add_ai_voltage_chan("Dev3/ai0:1")  # "Dev2/ai0:1"
        ######## Sampling rate: 500Hz ########
        self.task.timing.cfg_samp_clk_timing(rate=500, sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)


    def collect_EMG(self):
            self.data = self.task.read(number_of_samples_per_channel=1)
            temp = np.array(self.data)
            ch1 = temp[0,:]
            ch2 = temp[1,:]

            return ch1, ch2







