######################################################
## EMG thread to send the EMG to the main thread    ##
######################################################

from PyQt5.QtCore import QThread, pyqtSignal
from queue import Queue

from EMG_receive import EMG_collector


class EMGThread(QThread):
    signal = pyqtSignal('PyQt_PyObject')

    def __init__(self,out_q, out_EMG):
        QThread.__init__(self)
        print('Initializing EMG thread')
        self.EMG_queue = Queue()
        self.EMG_data_ch1 = 0
        self.EMG_data_ch2 = 0

        self.emg = EMG_collector()
        self.emg.initialize()
        self.timenow = 0
        self.EMGcounter = 0
        self.Out = out_q
        self.OutEMG = out_EMG

    def run(self):
        while True:
            self.EMG_data_ch1, self.EMG_data_ch2 = self.emg.collect_EMG()
            self.EMGcounter = self.EMGcounter + 1

######## Data Communication with main file, using Queue ########
            self.OutEMG.put(self.EMG_data_ch1)
            self.OutEMG.put(self.EMG_data_ch2)

            self.Out.put(self.EMGcounter)

######## Use this counter to sychronize the EMG with M1 device ########
            if self.EMGcounter >= 5:
                self.EMGcounter = 0

        print("Exit run")