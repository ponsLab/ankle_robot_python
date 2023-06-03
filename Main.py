import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui
import sys  # We need sys so that we can pass argv to QApplication
import math
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QSlider
from queue import Queue
import time
import PyServer
import random

from FFTAI_M1_Simple import FFTAI_M1
from Saving_final import DataSave
from EMGThread import EMGThread
import globalvar as gl
from ChildGUIWindow import SineGUI, RampGUI, RandomGUI, UserInfoGUI, ResetGUI
import pandas as pd
import os

class mode_const:
    ROM_MODE = 0
    MVC_MODE = 1
    TRC_MODE = 2
    CPM_MODE = 3
    VFB_MODE = 4
    HFB_MODE = 5
    TSO_MODE = 6

class M1Thread(QThread):
    signal = pyqtSignal('PyQt_PyObject')

    def __init__(self, function, in_q, in_EMG):
        QThread.__init__(self)
        print('Initializing M1 thread')
        #### Initial setup for M1 device
        self.m1 = FFTAI_M1(bustype='pcan', channel='PCAN_USBBUS1')
        self.m1.pdo_conf()
        #### Use the M1 thread input ####
        self.callback = function    # Get current data by update plot function
        self.In = in_q              # Get the EMG counter from queue
        self.InEMG = in_EMG         # Get the raw EMG from queue

        #### Other Init ####
        self.Unity = PyServer.recs()    # Unity thread connected
        self.mode = 0                   # Mode selection init
        self.timenow = 0                # time init
        self.All_queue = Queue()        # Define a queue for saving

        #### EMG baseline offset init ####
        self.EMG1_filt_Sum = 0
        self.EMG2_filt_Sum = 0
        self.EMGCounter = 0
        self.EMG1_offset = 0
        self.EMG2_offset = 0
        self.EMGCali = 0

        #### Torque sensor calibration init ####
        self.TorSum = 0
        self.TorCounter = 0
        self.TorCali = 0

        #### MVC init ####
        self.EMG1_Max = 0
        self.EMG2_Max = 0
        self.TorMax = 0
        self.TorMin = 0
        self.EMG1_fault_cnt = 0
        self.EMG2_fault_cnt = 0

    def setmode(self, mode):
        print('Mode changed')
        self.mode = mode
        self.m1.initialization(mode + 1)

    def stopM1(self):
        print('Stop')
        self.m1.set_recording_mode()

    # run method gets called when we start the thread
    def run(self):

        self.m1.start_mnt()

        ###########################
        ###### Initial Value ######
        ###########################

        #### EMG Processing Init #####
        # ## Moving average ##
        # EMG1Mean = 0
        # EMG2Mean = 0
        # self.EMG1_Matrix = [0 for k in np.arange(0, 40, 1)] # Window size of EMG moving average Ch1
        # self.EMG2_Matrix = [0 for k in np.arange(0, 40, 1)] # Window size of EMG moving average Ch2

        # ## 1st order Low pass filter ##
        # EMG1_filt_prev = 0
        # EMG1_filt = 0
        # EMG2_filt_prev = 0
        # EMG2_filt = 0
        # emgCutoffFreq = 3

        ## 2nd order Low pass filter ##
        x_2 = 0
        x_1 = 0
        EMG1_filt_2 = 0
        EMG1_filt_1 = 0

        x_2_1 = 0
        x_2_2 = 0
        EMG2_filt_2 = 0
        EMG2_filt_1 = 0
        emgCutoffFreq = 3

        #### Desire Trajectory (Point) init ####
        target = 0

        while True:
            ########################
            #### Get GUI input  ####
            ########################
            posOffset = gl.get_value('posOffset')
            saveMaxPos = gl.get_value('saveMaxPos')
            saveMinPos = gl.get_value('saveMinPos')
            NeutralPos = gl.get_value('NeutralPosition')
            saveMaxMVC1 = gl.get_value('saveMaxMVC1')
            saveMaxMVC2 = gl.get_value('saveMaxMVC2')

            ########################
            #### EMG processing ####
            ########################
            #### 1. Get raw EMG data & timer ####
            checkingpoint = self.In.get()
            EMG1Raw = self.InEMG.get()
            EMG2Raw = self.InEMG.get()

            #### 2. EMG rectification ####
            EMG1 = np.abs(EMG1Raw)
            EMG2 = np.abs(EMG2Raw)

            ## Way 3: 2nd order Low pass filter ##
            betaEMG = (2*np.pi*emgCutoffFreq*0.002)
            EMG1_filt = (betaEMG**2*x_2)+(2-np.sqrt(2)*betaEMG)*EMG1_filt_1+(np.sqrt(2)*betaEMG-betaEMG**2-1)*EMG1_filt_2
            x_2 = x_1
            x_1 = EMG1
            EMG1_filt_2 = EMG1_filt_1
            EMG1_filt_1 = EMG1_filt

            EMG2_filt = (betaEMG**2*x_2_2)+(2-np.sqrt(2)*betaEMG)*EMG2_filt_1+(np.sqrt(2)*betaEMG-betaEMG**2-1)*EMG2_filt_2
            x_2_2 = x_2_1
            x_2_1 = EMG2
            EMG2_filt_2 = EMG2_filt_1
            EMG2_filt_1 = EMG2_filt

            #### 4. EMG Baseline offset ####
            if self.EMGCali == 1:
                self.EMG1_filt_Sum = self.EMG1_filt_Sum + EMG1_filt
                self.EMG2_filt_Sum = self.EMG2_filt_Sum + EMG2_filt
                self.EMGCounter = self.EMGCounter + 1

            EMG1_filt = EMG1_filt - self.EMG1_offset
            EMG2_filt = EMG2_filt - self.EMG2_offset

            ##########
            if self.mode == mode_const.HFB_MODE:
                if EMG1_filt > saveMaxMVC1*1.5:
                    EMG1_filt = 0
                    self.EMG1_fault_cnt = self.EMG1_fault_cnt + 1

                if EMG2_filt > saveMaxMVC2*1.5:
                    EMG2_filt = 0
                    self.EMG2_fault_cnt = self.EMG2_fault_cnt + 1

            #### 5. MVC normalization ####
            if self.EMG1_Max < EMG1_filt:
                self.EMG1_Max = EMG1_filt

            if self.EMG2_Max < EMG2_filt:
                self.EMG2_Max = EMG2_filt

            #### 6. Send processed EMG data to the EMG controller (in FFTAI_M1 file)
            gl.set_value('EMGSignal1', EMG1_filt/saveMaxMVC1)
            gl.set_value('EMGSignal2', EMG2_filt/saveMaxMVC2)
            offset = gl.get_value("MVCTorqueOffset")

            ###########################################################
            #### M1 thread, use checkingpoint as syncronized timer ####
            ###########################################################

            if checkingpoint == 5:
                # #### Moving average, moving step = checkingpoint ####
                # EMG1Mean = np.mean(self.EMG1_Matrix)
                # EMG2Mean = np.mean(self.EMG2_Matrix)

                self.m1.wait_for_data()

                #### Torque Sensor Calibration ####
                if self.TorCali == 1:
                    self.TorSum = self.TorSum + self.m1.torque_s
                    self.TorCounter = self.TorCounter + 1

                # Check for Torque max and min
                TorTemp = self.m1.torque_s - offset  # account for MVC offset
                if self.TorMax < TorTemp:
                    self.TorMax = TorTemp
                if self.TorMin > TorTemp:
                    self.TorMin = TorTemp

                #### Mode selection ####
                if self.mode == mode_const.ROM_MODE:  # ROM measurement
                    target = self.callback([self.m1.position, self.m1.torque_s - offset])
                    self.m1.compensation()

                elif self.mode == mode_const.MVC_MODE:  # MVC measurement
                    target = self.callback([self.m1.position])
                    self.m1.set_position(NeutralPos)

                elif self.mode == mode_const.TRC_MODE:  # Tracking mode
                    target = self.callback([self.m1.position, self.m1.torque_s - offset])
                    self.m1.compensation()
                    self.Unity.start()
                    self.UnityServer = PyServer.Server(self.Unity.conn_dt, self.Unity.conn_list, self.m1.position-posOffset, target-posOffset)

                elif self.mode == mode_const.CPM_MODE:  # CPM mode
                    target = self.callback([self.m1.position])
                    self.m1.set_position(target)

                elif self.mode == mode_const.VFB_MODE:  # Visual feedback mode
                    target = self.callback([self.m1.position, self.m1.torque_s - offset])
                    self.m1.compensation()
                    self.Unity.start()
                    self.UnityServer = PyServer.Server(self.Unity.conn_dt, self.Unity.conn_list, self.m1.position-posOffset, target-posOffset)

                elif self.mode == mode_const.HFB_MODE:    # Haptic feedback mode
                    target = self.callback([self.m1.position, self.m1.torque_s - offset])
                    self.m1.compensation()
                    self.Unity.start()
                    self.UnityServer = PyServer.Server(self.Unity.conn_dt, self.Unity.conn_list, self.m1.position-posOffset, target-posOffset)

                elif self.mode == mode_const.TSO_MODE:    # Torque sensor offset mode
                    target = self.callback([self.m1.position])
                    self.m1.set_position(0)

            #####################
            #### Data saving ####
            #####################
            # Will be saved to csv file. To save additional variables, add below and change DataSave in MainWindow
            self.All_queue.put(self.timenow)
            self.All_queue.put(target)
            self.All_queue.put(self.m1.position)
            self.All_queue.put(self.m1.torque_s - offset)
            self.All_queue.put(EMG1Raw)
            self.All_queue.put(EMG2Raw)
            self.All_queue.put(saveMaxMVC1)
            self.All_queue.put(saveMaxMVC2)
            self.All_queue.put(self.m1.torCMD_record)
            self.All_queue.put(self.m1.torEMG_record)
            self.All_queue.put(self.m1.torFF_record)
            self.All_queue.put(saveMaxPos)
            self.All_queue.put(saveMinPos)
            self.All_queue.put(NeutralPos)
            self.All_queue.put(self.m1.velocity)

            #### Update Time ####
            self.timenow = self.timenow + 0.002
        print("Exit run")


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setGeometry(500, 100, 985, 900)

        ###########################
        ######  GUI Design   ######
        ###########################

        ####### Line 0 (Graph plot) ########
        self.graphWidget = pg.PlotWidget()

        # Add Background colour to white
        self.graphWidget.setBackground('w')
        self.graphWidget.setTitle("M1 real-time control")
        self.graphWidget.setLabel('left', 'Angle (degrees)', color='red', size=30)
        self.graphWidget.setLabel('bottom', 'Time (seconds)', color='red', size=30)
        self.graphWidget.addLegend()
        self.graphWidget.showGrid(x=True, y=True)

        self.lh0 = QtWidgets.QHBoxLayout()
        self.lh0.addWidget(self.graphWidget)
        self.h_wid0 = QtWidgets.QWidget()
        self.h_wid0.setLayout(self.lh0)

        ####### Line 1 ########
        self.btn_connect = QtWidgets.QPushButton('Connect')
        self.btn_connect.clicked.connect(self.connectpcan)

        self.cbmode = QtWidgets.QComboBox()
        self.cbmode.addItem("ROM Measurement")
        self.cbmode.addItem("MVC Measurement")
        self.cbmode.addItem("Tracking Measurement")
        self.cbmode.addItem("CPM Mode")
        self.cbmode.addItem("Visual Feedback Mode")
        self.cbmode.addItem("Haptic Feedback Mode")
        self.cbmode.addItem("Torque Sensor Offset Mode")
        self.cbmode.currentIndexChanged.connect(self.modechange)

        self.btn_start = QtWidgets.QPushButton('Start')
        self.btn_start.clicked.connect(self.start)

        self.btn_Exit = QtWidgets.QPushButton('Exit')
        self.btn_Exit.clicked.connect(self.Exit)
        self.btn_Exit.setDisabled(True)

        self.lh1 = QtWidgets.QHBoxLayout()
        self.lh1.addWidget(self.btn_connect)
        self.lh1.addWidget(self.cbmode)
        self.lh1.addWidget(self.btn_start)
        self.lh1.addWidget(self.btn_Exit)
        self.h_wid1 = QtWidgets.QWidget()
        self.h_wid1.setLayout(self.lh1)

        ####### Line 2 ########
        self.btn_UserInfo = QtWidgets.QPushButton("User Infomation")
        self.btn_UserInfo.clicked.connect(self.UserInfo)

        self.cbTraj = QtWidgets.QComboBox()
        self.cbTraj.addItem("Ramp")
        self.cbTraj.addItem("Sinusoid")
        self.cbTraj.addItem("Random")
        self.cbTraj.currentIndexChanged.connect(self.Trajectorychange)

        self.btn_load = QtWidgets.QPushButton("Trajectory Setting")
        self.btn_load.clicked.connect(self.Load)
        self.btn_load.setDisabled(False)

        self.btn_Saving = QtWidgets.QPushButton("Start Sampling!")
        self.btn_Saving.clicked.connect(self.Saving)
        self.btn_Saving.setDisabled(False)

        self.lh2 = QtWidgets.QHBoxLayout()
        self.lh2.addWidget(self.btn_UserInfo)
        self.lh2.addWidget(self.cbTraj)
        self.lh2.addWidget(self.btn_load)
        self.lh2.addWidget(self.btn_Saving)
        self.h_wid2 = QtWidgets.QWidget()
        self.h_wid2.setLayout(self.lh2)

        ####### Line 3 ########
        self.btn_TorCali = QtWidgets.QPushButton("Torque Offset")
        self.btn_TorCali.clicked.connect(self.TorCali_Func)
        self.btn_TorCali.setDisabled(True)

        self.btn_Neutral = QtWidgets.QPushButton("Neutral Position")
        self.btn_Neutral.clicked.connect(self.Neutral)
        self.btn_Neutral.setDisabled(True)

        self.btn_MaxROM = QtWidgets.QPushButton("Max Dorsiflexion")
        self.btn_MaxROM.clicked.connect(self.MaxROM)
        self.btn_MaxROM.setDisabled(True)

        self.btn_MinROM = QtWidgets.QPushButton("Max Plantarflexion")
        self.btn_MinROM.clicked.connect(self.MinROM)
        self.btn_MinROM.setDisabled(True)

        self.lh3 = QtWidgets.QHBoxLayout()
        self.lh3.addWidget(self.btn_TorCali)
        self.lh3.addWidget(self.btn_Neutral)
        self.lh3.addWidget(self.btn_MaxROM)
        self.lh3.addWidget(self.btn_MinROM)
        self.h_wid3 = QtWidgets.QWidget()
        self.h_wid3.setLayout(self.lh3)

        ####### Line 4 ########
        # 'DF Angle'
        # 'PF Angle'
        self.showMaxPos = QtWidgets.QLabel(self)
        self.showMaxPos.setText('DF Angle: 0')
        self.showMinPos = QtWidgets.QLabel(self)
        self.showMinPos.setText('PF Angle: 0')
        self.showAmp = QtWidgets.QLabel(self)
        self.showAmp.setText('Amp of Sine Wave: 0')
        self.showOffset = QtWidgets.QLabel(self)
        self.showOffset.setText('DC offset: 0')

        self.lh4 = QtWidgets.QHBoxLayout()
        self.lh4.addWidget(self.showMaxPos)
        self.lh4.addWidget(self.showMinPos)
        self.lh4.addWidget(self.showAmp)
        self.lh4.addWidget(self.showOffset)
        self.h_wid4 = QtWidgets.QWidget()
        self.h_wid4.setLayout(self.lh4)

        ####### Line 5 ########
        self.btn_EMGCali = QtWidgets.QPushButton("EMG Offset")
        self.btn_EMGCali.clicked.connect(self.EMGBaseLine)
        self.btn_EMGCali.setDisabled(True)

        self.btn_MVC = QtWidgets.QPushButton("MVC")
        self.btn_MVC.clicked.connect(self.MVC)
        self.btn_MVC.setDisabled(True)

        # 'DF Torque'
        # 'PF Torque'
        self.showMVC1 = QtWidgets.QLabel(self)
        self.showMVC1.setText('TA MVC: 0')
        self.showMVC2 = QtWidgets.QLabel(self)
        self.showMVC2.setText('GAS MVC: 0')
        self.showTorMax = QtWidgets.QLabel(self)
        self.showTorMax.setText('DF Torque: 0')
        self.showTorMin = QtWidgets.QLabel(self)
        self.showTorMin.setText('PF Torque: 0')

        self.lh5 = QtWidgets.QHBoxLayout()
        self.lh5.addWidget(self.btn_EMGCali)
        self.lh5.addWidget(self.btn_MVC)
        self.lh5.addWidget(self.showMVC1)
        self.lh5.addWidget(self.showMVC2)
        self.lh5.addWidget(self.showTorMax)
        self.lh5.addWidget(self.showTorMin)
        self.h_wid5 = QtWidgets.QWidget()
        self.h_wid5.setLayout(self.lh5)

        ####### Line 6 ########
        self.slider1 = QSlider(QtCore.Qt.Horizontal)
        self.slider1.setMinimum(0)  # Max
        self.slider1.setMaximum(100)  # Min
        self.slider1.setSingleStep(1)  # Step
        self.slider1.setValue(0)    #Current Value
        self.slider1.setTickPosition(QSlider.TicksBelow)  #Tick Position
        self.slider1.setTickInterval(10)
        self.slider1.valueChanged.connect(self.valuechange)

        ####### Line 7 ########
        self.showslider1 = QtWidgets.QLabel(self)
        self.showslider1.setText('TA EMG Gain: 0')

        ####### Line 8 ########
        self.slider2 = QSlider(QtCore.Qt.Horizontal)
        self.slider2.setMinimum(0)  # Max
        self.slider2.setMaximum(100)  # Min
        self.slider2.setSingleStep(1)  # Step
        self.slider2.setValue(0)    #Current Value
        self.slider2.setTickPosition(QSlider.TicksBelow)  #Tick Position
        self.slider2.setTickInterval(10)
        self.slider2.valueChanged.connect(self.valuechange)

        ####### Line 9 ########
        self.showslider2 = QtWidgets.QLabel(self)
        self.showslider2.setText('GAS EMG Gain: 0')

        # create layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.h_wid0)
        layout.addWidget(self.h_wid1)
        layout.addWidget(self.h_wid2)
        layout.addWidget(self.h_wid3)
        layout.addWidget(self.h_wid4)
        layout.addWidget(self.h_wid5)
        layout.addWidget(self.slider1)
        layout.addWidget(self.showslider1)
        layout.addWidget(self.slider2)
        layout.addWidget(self.showslider2)

        # add layout to widget and display
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        ###########################
        ###### Initial Value ######
        ###########################
        self.csvfilename = ''

        #### Sin Wave Init ######
        self.magnitude = 10
        self.freq = 0.2 * 2 * np.pi
        self.offset = 0
        #### Ramp Wave Init ######
        self.rampA1 = -20
        self.rampA2 = 20
        self.rampT1 = 0
        self.rampT2 = 5
        self.rampT3 = 8
        self.rampT4 = 13
        self.rampT5 = 16

        #### Random Wave Init ######
        self.ranmagnitude = 10
        self.phi = np.array([random.random(), random.random(), random.random()])

        #### ComboBox Init ####
        self.Trajmode = 0  # Trajectory, 0 = Ramp, 1 = Sine, 2 = Random (Multiple Sine)
        self.mode = mode_const.ROM_MODE  # Mode selection, 0 = ROM Measurement, 1 = MVC measurement, 2 = CPM mode,
                       # 3 = Visual feedback mode, 4 = Haptic feedback mode

        #### Status Init ####
        self.status = 0  # Connection status, 0 = Not Connected, 1 = Connected and start, 2 = Connected and stop
        self.Savingstatus = 1  # Saving status, 1 = Start saving, 2 = Stop saving
        self.MVCstatus = 1  # MVC measurement status, 1 = Start MVC measurement, 2 = Stop MVC measurement

        #### ROM init ####
        self.saveMaxPos = 100
        self.saveMinPos = -100
        self.NeutralPosition = 0
        self.saveSineAmp = 10
        self.posOffset = 10

        #### Queue Init ####
        # Use Queue to send data from EMG thread to M1 thread. MainWindow (GUI thread) to coordinate.
        self.check = Queue()   # Timer(Counter) to synchronize M1 and EMG thread
        self.EMGQ = Queue()    # Raw EMG (TA & GAS)

        #### Global value Init ####
        gl.set_value('TA EMGGain', self.slider1.value())
        gl.set_value('GAS EMGGain', self.slider2.value())
        gl.set_value('saveMaxPos', self.saveMaxPos)
        gl.set_value('saveMinPos', self.saveMinPos)
        gl.set_value('NeutralPosition', self.NeutralPosition)
        gl.set_value('posOffset', self.posOffset)
        gl.set_value('FootWeight', 0)
        gl.set_value('saveMaxMVC1', 1)
        gl.set_value('saveMaxMVC2', 1)
        gl.set_value('TorqueOffset', 0)
        gl.set_value('MVCTorqueOffset', 0)

        #### Plot Init ####
        self.plot_init = 0
        self.plotcounter = 0   # This is used to set FPS of plotting
        self.postr1 = 0        # Starting position of the trajectory, used to update the plot and move the curve
        self.init_dynamic_plot()

        # mode and start
        self.cbmode.setEnabled(False)
        self.btn_start.setDisabled(True)
        # saving
        self.btn_UserInfo.setEnabled(False)
        self.btn_Saving.setEnabled(False)
        # ROM buttons
        self.btn_Neutral.setEnabled(False)
        self.btn_MinROM.setEnabled(False)
        self.btn_MaxROM.setEnabled(False)
        # mvc buttons
        self.btn_TorCali.setEnabled(False)
        self.btn_EMGCali.setEnabled(False)
        self.btn_MVC.setEnabled(False)
        # trajectory and load
        self.cbTraj.setEnabled(False)
        self.btn_load.setEnabled(False)
        # EMG sliders
        self.slider1.setEnabled(False)
        self.slider2.setEnabled(False)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_A:
            # print("Killing")
            # self.deleteLater()
            # mode and start
            self.cbmode.setEnabled(True)
            self.btn_start.setEnabled(True)
            # saving
            self.btn_Saving.setEnabled(True)
            # ROM buttons
            self.btn_Neutral.setEnabled(True)
            self.btn_MinROM.setEnabled(True)
            self.btn_MaxROM.setEnabled(True)
            # mvc buttons
            self.btn_TorCali.setEnabled(True)
            self.btn_EMGCali.setEnabled(True)
            self.btn_MVC.setEnabled(True)
            # trajectory and load
            self.cbTraj.setEnabled(True)
            self.btn_load.setEnabled(True)
            # EMG sliders
            self.slider1.setEnabled(True)
            self.slider2.setEnabled(True)
            # self.btn_Exit.setEnabled(True)

        elif event.key() == QtCore.Qt.Key_R:
            resetting_tmp = ResetGUI(self)
            # initialize values
            resetting_tmp.posNeu.setText("{:.2f}".format(self.NeutralPosition))
            resetting_tmp.posDF.setText("{:.2f}".format(self.saveMaxPos - self.NeutralPosition))
            resetting_tmp.posPF.setText("{:.2f}".format(self.saveMinPos - self.NeutralPosition))
            resetting_tmp.TAMVC.setText("{:.2f}".format(gl.get_value('saveMaxMVC1')))
            resetting_tmp.GMMVC.setText("{:.2f}".format(gl.get_value('saveMaxMVC2')))
            # update values
            NeutralPosition, saveMaxPos, saveMinPos, saveMaxMVC1, saveMaxMVC2, self.res = resetting_tmp.getResult_n()
            if self.res:
                self.NeutralPosition = NeutralPosition
                self.saveMaxPos = saveMaxPos
                self.saveMinPos = saveMinPos
                self.saveSineAmp = 0.5*(self.saveMaxPos - self.saveMinPos)
                self.posOffset = 0.5*(self.saveMaxPos + self.saveMinPos)
                self.showMaxPos.setText('DF Angle: %.2f' % (self.saveMaxPos - self.NeutralPosition))
                self.showMinPos.setText('PF Angle: %.2f' % (self.saveMinPos - self.NeutralPosition))
                self.showAmp.setText('Amp of Sine Wave: %.2f' % self.saveSineAmp)
                self.showOffset.setText('DC offset: %.2f' % self.posOffset)
                self.showMVC1.setText('TA MVC: %.2f' % saveMaxMVC1)
                self.showMVC2.setText('GAS MVC: %.2f' % saveMaxMVC2)
                gl.set_value('NeutralPosition', self.NeutralPosition)
                gl.set_value('saveMinPos', self.saveMinPos)
                gl.set_value('saveMaxPos', self.saveMaxPos)
                gl.set_value('posOffset', self.posOffset)
                gl.set_value('saveMaxMVC1', saveMaxMVC1)
                gl.set_value('saveMaxMVC2', saveMaxMVC2)

        event.accept()

    def disable_btns(self):
        # ROM buttons
        self.btn_Neutral.setEnabled(False)
        self.btn_MinROM.setEnabled(False)
        self.btn_MaxROM.setEnabled(False)
        # mvc buttons
        self.btn_TorCali.setEnabled(False)
        self.btn_EMGCali.setEnabled(False)
        self.btn_MVC.setEnabled(False)
        #
        self.cbTraj.setEnabled(False)
        self.btn_load.setEnabled(False)
        self.btn_Saving.setEnabled(False)           # disable saving button
        self.slider1.setEnabled(False)              # disable EMG slider1
        self.slider2.setEnabled(False)              # disable EMG slider2
        #
        self.btn_start.setEnabled(False)            # disable start button
        self.cbmode.setEnabled(False)               # disable mode selection
        self.btn_connect.setEnabled(False)          # disable connection
        # self.btn_Exit.setEnabled(False)

    def button_config(self):
        ###### button config for mode change and start/stop button
        if self.status == 1:            ##### preparation mode
            self.disable_btns()                     # disable all buttons
            self.cbmode.setEnabled(True)            # enable mode selection
            # self.btn_Exit.setEnabled(True)

            # if self.mode == mode_const.ROM_MODE:      # ROM measurement
            # elif self.mode == mode_const.MVC_MODE:    # MVC measurement
            # elif self.mode == mode_const.CPM_MODE:    # CPM mode
            # elif self.mode == mode_const.VFB_MODE:    # Visual feedback mode
            # elif self.mode == mode_const.HFB_MODE:    # Haptic feedback mode

            if self.mode == mode_const.ROM_MODE:  # ROM measurement
                self.btn_start.setEnabled(True)
            elif self.mode == mode_const.MVC_MODE:  # MVC measurement
                self.btn_start.setEnabled(True)
            elif self.mode == mode_const.CPM_MODE:  # CPM mode
                # self.cbTraj.setEnabled(True)
                self.cbTraj.setCurrentIndex(0)
                self.btn_load.setEnabled(True)
            elif self.mode == mode_const.VFB_MODE:  # Visual feedback mode
                # self.cbTraj.setEnabled(True)
                self.cbTraj.setCurrentIndex(2)
                self.btn_load.setEnabled(True)
            elif self.mode == mode_const.HFB_MODE:  # Haptic feedback mode
                # self.cbTraj.setEnabled(True)
                self.cbTraj.setCurrentIndex(2)
                self.btn_load.setEnabled(True)
                self.slider1.setEnabled(True)
                self.slider2.setEnabled(True)
            elif self.mode == mode_const.TRC_MODE:  # Tracking mode
                self.cbTraj.setCurrentIndex(1)
                # self.cbTraj.setEnabled(True)
                self.btn_load.setEnabled(True)
            elif self.mode == mode_const.TSO_MODE:  # Torque sensor offset mode
                self.btn_start.setEnabled(True)

        elif self.status == 2:              ####### running mode
            self.disable_btns()                     # disable all buttons
            if self.mode == mode_const.ROM_MODE:      # ROM measurement
                self.btn_Neutral.setEnabled(True)
                self.btn_Saving.setEnabled(True)
                self.btn_start.setEnabled(True)
            elif self.mode == mode_const.MVC_MODE:    # MVC measurement
                self.btn_EMGCali.setEnabled(True)
                self.btn_TorCali.setEnabled(True)
                self.btn_Saving.setEnabled(True)
            elif self.mode == mode_const.CPM_MODE:    # CPM mode
                self.Saving()
            elif self.mode == mode_const.VFB_MODE:    # Visual feedback mode
                self.Saving()
            elif self.mode == mode_const.HFB_MODE:    # Haptic feedback mode
                self.btn_Saving.setEnabled(True)
                # self.btn_EMGCali.setEnabled(True)
                # self.btn_TorCali.setEnabled(True)
                self.slider1.setEnabled(True)
                self.slider2.setEnabled(True)
            elif self.mode == mode_const.TRC_MODE:
                self.btn_Saving.setEnabled(True)
            elif self.mode == mode_const.TSO_MODE:
                self.btn_TorCali.setEnabled(True)
                self.btn_start.setEnabled(True)

    ##########################################################
    #### Line1: Functions about connection and start/exit ####
    ##########################################################
    def connectpcan(self):
        if self.status == 0:
            self.status = 1

            #### EMG connection ####
            try:
                self.EMGthread = EMGThread(self.check, self.EMGQ)
            except:
                print('EMG initialization error.')

            #### M1 thread connection ####
            try:
                self.m1thread = M1Thread(self.update_plot, self.check, self.EMGQ)
                self.m1thread.setmode(self.mode)
            except:
                print('M1 initialization error.')

            #### Button activation ####
            self.btn_connect.setEnabled(False)
            self.btn_start.setEnabled(True)
            self.btn_start.setEnabled(True)
            self.cbmode.setEnabled(True)

    def start(self):
        if self.status == 1:
            #### Start M1 and EMG thread ####
            try:
                # Update the mode after selection
                self.m1thread.setmode(self.mode)
                self.EMGthread.start()
                self.m1thread.start()
            except:
                pass

            #### Change button, press the same button again can stop ####
            self.btn_start.setText("Stop")
            self.status = 2
            self.button_config()

        elif self.status == 2:
            #### Change back to start status
            self.status = 1
            try:
                self.m1thread.stopM1()    # Change into recording mode
                self.btn_connect.setDisabled(True)
            except:
                pass

            #### Change button, press the same button again can start ####
            self.btn_start.setText("Start")
            self.button_config()

    def Exit(self):
        print("Exit run")
        self.m1thread.m1.close()
        self.close()

    ################################################################################
    #### Line2: Functions about user information, trajectory setting and saving ####
    ################################################################################
    def UserInfo(self):
        #### compensate for foot weight, also can change the assistance level ####
        self.Weight, self.Height, self.Gender, self.Assistance, self.res = UserInfoGUI.getResult(self)
        print(self.Gender, 'User weight', self.Weight, '(kg) and height', self.Height, '(cm) and assistance', self.Assistance,'%')
        if self.Gender == 'M':
            GenderEffect = 1.43/100
        elif self.Gender == 'F':
            GenderEffect = 1.33/100
        else:
            GenderEffect = 0
        FootWeight = (GenderEffect*float(self.Weight)) * (float(self.Assistance)/100)
        gl.set_value('FootWeight', FootWeight)

    def Load(self):
        #### Get the trajectory parameters from the user input (Pop-ups) ####
        print('Load')
        if self.Trajmode == 0:    # Ramp wave
            rampGUI_tmp = RampGUI(self)
            rampGUI_tmp.rampAmp1.setText("{:.2f}".format(self.saveMaxPos-self.NeutralPosition))
            rampGUI_tmp.rampAmp2.setText("{:.2f}".format(self.saveMinPos-self.NeutralPosition))
            rampA1, rampA2, self.rampT2, self.rampT3, self.rampT4, self.rampT5, self.res = rampGUI_tmp.getResult_n()
            print('Ramp Mode with a', self.rampT5, 's cycle')
            self.rampA1 = rampA1 + self.NeutralPosition
            self.rampA2 = rampA2 + self.NeutralPosition
        elif self.Trajmode == 1:    # Sine wave
            sinGUI_tmp = SineGUI(self)
            sinGUI_tmp.sinAmp.setText("{:.2f}".format(self.saveSineAmp))
            sinGUI_tmp.sinOffset.setText("{:.2f}".format(self.posOffset))
            self.sinAmp, self.sinfreq, self.sinOffset, self.res = sinGUI_tmp.getResult_n()
            print('Sine Mode with amplitude', self.sinAmp, 'and frequency', self.sinfreq, 'and Offset', self.sinOffset)
            self.freq = float(self.sinfreq) * 2 * np.pi
            self.magnitude = float(self.sinAmp)
            self.offset = float(self.sinOffset)
        elif self.Trajmode == 2:    # Multiple sine wave
            randGUI_tmp = RandomGUI(self)
            randGUI_tmp.ranAmp.setText("{:.2f}".format(self.saveSineAmp))
            self.ranAmp, self.res = randGUI_tmp.getResult_n()
            print('Random Mode with amplitude', self.ranAmp)
            self.ranmagnitude = float(self.ranAmp)
        self.init_dynamic_plot()
        if self.res == 1:
            self.btn_start.setEnabled(True)

    def Saving(self):
        if self.Savingstatus == 1:
            self.btn_Saving.setText("Stop Sampling!")
            self.Savingstatus = 2

            #### Start saving thread ####
            savingtime = 'Data\\Data' + time.strftime('_%m%d_%H%M%S') + '.csv'
            try:
                self.m1thread.All_queue.queue.clear()
                self.EMG_saving = DataSave(1, self.m1thread.All_queue, 15, savingtime)    # The number here (15) is decided by the kinds of data you want to save
                self.EMG_saving.start()
                self.csvfilename = savingtime
            except:
                pass

            # disable all buttons
            self.disable_btns()

            # enable buttons
            self.btn_Saving.setEnabled(True)
            if self.mode == mode_const.ROM_MODE:  # ROM measurement
                self.btn_MinROM.setEnabled(True)
                self.btn_MaxROM.setEnabled(True)
            elif self.mode == mode_const.MVC_MODE:  # MVC measurement
                self.btn_MVC.setEnabled(True)
            # elif self.mode == mode_const.CPM_MODE:  # CPM mode
            #     # self.start()
            # elif self.mode == mode_const.VFB_MODE:  # Visual feedback mode
            #     # self.start()
            # elif self.mode == mode_const.HFB_MODE:  # Haptic feedback mode
                # self.start()

        elif self.Savingstatus == 2:
            self.Savingstatus = 1
            self.btn_Saving.setText("Start Sampling!")
            try:
                self.EMG_saving.terminate()
                print('Stop Saving!')
            except:
                pass

            # disable buttons
            self.disable_btns()

            # not in sampling mode: enable start/stop button
            self.btn_start.setEnabled(True)
            # self.btn_Saving.setEnabled(True)
            # enable buttons
            if self.mode == mode_const.ROM_MODE:  # ROM measurement
                self.btn_Neutral.setEnabled(True)
                self.btn_Saving.setEnabled(True)
                self.display_data()
            elif self.mode == mode_const.MVC_MODE:  # MVC measurement
                self.btn_EMGCali.setEnabled(True)
                self.btn_TorCali.setEnabled(True)
                self.btn_Saving.setEnabled(True)
                self.display_data()
            elif self.mode == mode_const.TRC_MODE:  # Tracking mode
                self.btn_load.setEnabled(True)
                # self.cbTraj.setEnabled(True)
                self.btn_start.setEnabled(True)
                self.btn_Saving.setEnabled(True)
                self.display_data()
            elif self.mode == mode_const.CPM_MODE:  # CPM mode
                self.btn_load.setEnabled(True)
                self.cbTraj.setEnabled(True)
                self.btn_start.setEnabled(True)
                # self.btn_Saving.setEnabled(True)
                self.start()
            elif self.mode == mode_const.VFB_MODE:  # Visual feedback mode
                self.btn_load.setEnabled(True)
                self.cbTraj.setEnabled(True)
                self.btn_start.setEnabled(True)
                # self.btn_Saving.setEnabled(True)
                self.start()
            elif self.mode == mode_const.HFB_MODE:  # Haptic feedback mode
                self.btn_load.setEnabled(True)
                self.cbTraj.setEnabled(True)
                self.slider1.setEnabled(True)
                self.slider2.setEnabled(True)
                self.btn_start.setEnabled(True)
                # self.btn_Saving.setEnabled(True)
                self.start()


            msgBox = QtGui.QMessageBox()
            msgBox.setIcon(QtGui.QMessageBox.Information)
            msgBox.setWindowTitle("File name:")
            msgBox.setText("<font size=15>{}</font>".format(self.csvfilename))
            # msgBox.setText("<font size=15>{}</font>".format('Hello'))
            msgBox.exec_()

            print('TA EMG signal check: {}'.format(self.m1thread.EMG1_fault_cnt))
            print('GM EMG signal check: {}'.format(self.m1thread.EMG2_fault_cnt))

            # check EMG signal quality
            if self.m1thread.EMG1_fault_cnt > 100*60:
                print('TA EMG signal quality low!')
                self.m1thread.EMG1_fault_cnt = 0

            if self.m1thread.EMG2_fault_cnt > 100*60:
                print('GM EMG signal quality low!')
                self.m1thread.EMG2_fault_cnt = 0


    #############################################################################
    #### Line3,4: Functions about Torque sensor calibration, ROM measurement ####
    #############################################################################
    def Neutral(self):
        try:
            self.NeutralPosition = self.m1thread.m1.position
            gl.set_value('NeutralPosition', self.NeutralPosition)
        except:
            print('Neutral setting failed!')

    def MaxROM(self):
        try:
            self.saveMaxPos = self.m1thread.m1.position
        except:
            print('MaxROM setting failed!')
        self.saveSineAmp = 0.5*(self.saveMaxPos - self.saveMinPos)
        self.posOffset = 0.5*(self.saveMaxPos + self.saveMinPos)
        self.showMaxPos.setText('DF Angle: %.2f' % (self.saveMaxPos - self.NeutralPosition))
        self.showAmp.setText('Amp of Sine Wave: %.2f' % self.saveSineAmp)
        self.showOffset.setText('DC offset: %.2f' % self.posOffset)
        gl.set_value('saveMaxPos', self.saveMaxPos)
        gl.set_value('posOffset', self.posOffset)

    def MinROM(self):
        try:
            self.saveMinPos = self.m1thread.m1.position
        except:
            print('MinROM setting failed!')
        self.saveSineAmp = 0.5*(self.saveMaxPos - self.saveMinPos)
        self.posOffset = 0.5*(self.saveMaxPos + self.saveMinPos)
        self.showMinPos.setText('PF Angle: %.2f' % (self.saveMinPos - self.NeutralPosition))
        self.showAmp.setText('Amp of Sine Wave: %.2f' % self.saveSineAmp)
        self.showOffset.setText('DC offset: %.2f' % self.posOffset)
        gl.set_value('saveMinPos', self.saveMinPos)
        gl.set_value('posOffset', self.posOffset)

    def TorCali_Func(self):
        if self.m1thread.TorCali == 0:
            self.btn_TorCali.setText("Stop")
            if self.mode == mode_const.MVC_MODE:  # MVC measurement
                gl.set_value('MVCTorqueOffset', 0)
            elif self.mode == mode_const.TSO_MODE:  # Torque sensor offset
                gl.set_value('TorqueOffset', 0)  # FFTAI_M1 file uses this torque offset, so set it as global variable
            self.m1thread.TorSum = 0
            self.m1thread.TorCounter = 0
            self.m1thread.TorCali = 1

        elif self.m1thread.TorCali == 1:
            self.m1thread.TorCali = 0
            self.btn_TorCali.setText("Torque Offset")
            if self.mode == mode_const.MVC_MODE:  # MVC measurement
                gl.set_value('MVCTorqueOffset', self.m1thread.TorSum / self.m1thread.TorCounter)
                print('MVC offset: ', gl.get_value('MVCTorqueOffset'))
            elif self.mode == mode_const.TSO_MODE: # Torque sensor offset
                gl.set_value('TorqueOffset', self.m1thread.TorSum / self.m1thread.TorCounter)
                print('Torque sensor offset: ', gl.get_value('TorqueOffset'))

    ###############################################################################################
    #### Line5: Functions about EMG calibration, MVC measurement and EMG gain setting (slider) ####
    ###############################################################################################

    def EMGBaseLine(self):
        if self.m1thread.EMGCali == 0:
            self.btn_EMGCali.setText("Stop")
            self.m1thread.EMG1_filt_Sum = 0
            self.m1thread.EMG2_filt_Sum = 0
            self.m1thread.EMGCounter = 0
            self.m1thread.EMG1_offset = 0    # M1 thread uses this offset. Just call m1thread
            self.m1thread.EMG2_offset = 0
            self.m1thread.EMGCali = 1

        elif self.m1thread.EMGCali == 1:
            self.m1thread.EMGCali = 0
            self.btn_EMGCali.setText("EMG Offset")
            self.m1thread.EMG1_offset = self.m1thread.EMG1_filt_Sum/self.m1thread.EMGCounter
            self.m1thread.EMG2_offset = self.m1thread.EMG2_filt_Sum/self.m1thread.EMGCounter

    def MVC(self):
        if self.MVCstatus == 1:
            self.btn_MVC.setText("Stop MVC Measurement!")
            self.MVCstatus = 2
            try:
                self.m1thread.EMG1_Max = 0
                self.m1thread.EMG2_Max = 0
                self.m1thread.TorMax = 0
                self.m1thread.TorMin = 0
            except:
                print('MVC failed!')
            self.btn_Saving.setEnabled(False)

        elif self.MVCstatus == 2:
            self.MVCstatus = 1
            self.btn_MVC.setText("MVC")
            try:
                torMax = self.m1thread.TorMax
                torMin = self.m1thread.TorMin
                if self.m1thread.EMG1_Max == 0:
                    saveMaxMVC1 = 1
                else:
                    saveMaxMVC1 = self.m1thread.EMG1_Max

                if self.m1thread.EMG2_Max == 0:
                    saveMaxMVC2 = 1
                else:
                    saveMaxMVC2 = self.m1thread.EMG2_Max

                gl.set_value('saveMaxMVC1', saveMaxMVC1)
                gl.set_value('saveMaxMVC2', saveMaxMVC2)
            except:
                print('MVC failed!')
                torMax = 0
                torMin = 0
                saveMaxMVC1 = gl.get_value('saveMaxMVC1')
                saveMaxMVC2 = gl.get_value('saveMaxMVC2')
            self.showMVC1.setText('TA MVC: %.2f' % saveMaxMVC1)
            self.showMVC2.setText('GAS MVC: %.2f' % saveMaxMVC2)
            self.showTorMax.setText('DF Torque: %.2f' % torMax)
            self.showTorMin.setText('PF Torque: %.2f' % np.abs(torMin))
            # self.btn_Saving.setEnabled(True)
            self.Saving()

    #####################################
    #### Others: ComboBox and slider ####
    #####################################

    def modechange(self, i):
        self.mode = i
        self.button_config()
        # self.cbTraj.setEnabled(True)
        # self.btn_load.setEnabled(True)
        # if i <= 1:      # ROM measurement and MVC measurement
        #     self.magnitude = 10
        #     self.cbTraj.setEnabled(False)
        #     self.btn_load.setEnabled(False)
        #     self.btn_start.setEnabled(True)
        # elif i == 2:    # CPM mode
        #     self.magnitude = 30
        #     self.cbTraj.setCurrentIndex(0)
        #     self.btn_start.setEnabled(False)
        # elif i == 3:    # Visual feedback mode
        #     self.magnitude = 30
        #     self.cbTraj.setCurrentIndex(1)
        #     self.btn_start.setEnabled(False)
        # else:           # Haptic mode
        #     self.magnitude = 10
        #     self.cbTraj.setCurrentIndex(2)
        #     self.btn_start.setEnabled(False)
        #     self.slider1.setEnabled(True)
        #     self.slider2.setEnabled(True)
        print('Now in Mode %d' % i)
        self.init_dynamic_plot()

    def Trajectorychange(self, i):
        if i == 0:
            self.Trajmode = 0
            print('Ramp Mode')
        elif i == 1:
            self.Trajmode = 1
            print('Sine Mode')
        elif i == 2:
            self.Trajmode = 2
            print('Random Mode')

    def valuechange(self):    # Get EMG gain from the sliders
        print('Current TA slider value=%s'%self.slider1.value())
        self.showslider1.setText('TA EMG Gain: %s'%self.slider1.value())
        gl.set_value('TA EMGGain', self.slider1.value())

        print('Current GAS slider value=%s'%self.slider2.value())
        self.showslider2.setText('GAS EMG Gain: %s'%self.slider2.value())
        gl.set_value('GAS EMGGain', self.slider2.value())

    #########################
    #### Line0: Plotting ####
    #########################

    def init_dynamic_plot(self):
        self.graphWidget.setBackground('w')
        self.graphWidget.setYRange(self.saveMaxPos+10, self.saveMinPos-10, padding=0)
        if self.Trajmode == 1:
            self.x = list(np.arange(0, 5, 0.01))  # 100 time points
            self.y = [self.magnitude * math.sin(k*self.freq) + self.offset for k in np.arange(0, 5, 0.01)]  # 100 data p
            self.t = list(np.arange(0, 2, 0.01))  # 100 time points
            self.p = [0 for k in np.arange(0, 2, 0.01)]  # 100 data p
            self.v = [0 for k in np.arange(0, 2, 0.01)]  # 100 data p
        elif self.Trajmode == 0:
            self.x = list(np.arange(self.rampT1, self.rampT5, 0.01))  # 100 time points
            y1 = [self.rampA1 for k in np.arange(self.rampT1, self.rampT2, 0.01)]
            y2 = [((self.rampA2-self.rampA1)/(self.rampT3-self.rampT2))*k + ((self.rampA1*self.rampT3-self.rampA2*self.rampT2)/(self.rampT3-self.rampT2)) for k in np.arange(self.rampT2, self.rampT3, 0.01)]
            y3 = [self.rampA2 for k in np.arange(self.rampT3, self.rampT4, 0.01)]
            y4 = [((self.rampA2-self.rampA1)/(self.rampT4-self.rampT5))*k + ((self.rampA1*self.rampT4-self.rampA2*self.rampT5)/(self.rampT4-self.rampT5)) for k in np.arange(self.rampT4, self.rampT5, 0.01)]
            self.yramp_int = y1 + y2 + y3 + y4
            self.y = self.yramp_int
            self.t = list(np.arange(0, self.rampT5 / 2, 0.01))  # 100 time points
            self.p = [0 for k in np.arange(0, self.rampT5 / 2, 0.01)]  # 100 data p
            self.v = [0 for k in np.arange(0, self.rampT5 / 2, 0.01)]  # 100 data p
        elif self.Trajmode == 2:
            self.x = list(np.arange(0, 5, 0.01))  # 100 time points
            self.y = [self.ranmagnitude * (1/3)* (math.sin(2*np.pi*(0.5*k)+self.phi[0])+math.sin(2*np.pi*(0.2*k)+self.phi[1])+math.sin(2*np.pi*(0.15*k)+self.phi[2])) + self.NeutralPosition for k in np.arange(0, 5, 0.01)]  # 100 data p
            self.t = list(np.arange(0, 2, 0.01))  # 100 time points
            self.p = [0 for k in np.arange(0, 2, 0.01)]  # 100 data p
            self.v = [0 for k in np.arange(0, 2, 0.01)]  # 100 data p


        if self.plot_init == 0:
            self.graphWidget.clear()
            self.graphWidget.setLabel('left', 'Angle (degrees)', color='red', size=30)
            # plot init run only once
            self.plot_init = 1
            # target line
            pen = pg.mkPen(color=(51, 255, 255), width=3)
            self.target_line = self.graphWidget.plot(self.y, name='Target angle', pen=pen)
            #self.graphWidget.setXRange(self.x[0], self.x[-1], padding=0)

            # real line
            pen = pg.mkPen(color=(51, 51, 255), width=3, style=QtCore.Qt.DashLine)
            self.real_line = self.graphWidget.plot(self.p, name='M1 angle', pen=pen)
            #self.graphWidget.setXRange(self.x[0], self.x[-1], padding=0)
            # real line
            # pen = pg.mkPen(color=(51, 51, 0), width=3, style=QtCore.Qt.DashLine)
            # self.real_line_2 = self.graphWidget.plot(self.v, name='velocity', pen=pen)
            #self.graphWidget.setXRange(self.x[0], self.x[-1], padding=0)

            self.real_line.setPos(self.postr1, 0)
            # self.real_line_2.setPos(self.postr1, 0)
            self.target_line.setPos(self.postr1, 0)
        else:
            self.postr1 = 0
            self.real_line.setData(self.p, name='M1 angle')
            # self.real_line_2.setData(self.v)
            self.target_line.setData(self.y, name='Target angle')  # Update the data.
            self.real_line.setPos(self.postr1, 0)
            # self.real_line_2.setPos(self.postr1, 0)
            self.target_line.setPos(self.postr1, 0)

    def update_plot(self, y):
        self.postr1 = self.postr1 + 0.1

        # update real-time angle position
        self.t = self.t[1:]  # Remove the first y element.
        self.t.append(self.t[-1] + 0.01)  # Add a new value 1 higher than the last.
        self.p = self.p[1:]  # Remove the first
        self.p.append(y[0])  # Add a new random value.

        if len(y) == 2:
            self.v = self.v[1:]  # Remove the first
            self.v.append(y[1])  # Add a new random value.

        self.x = self.x[1:]  # Remove the first y element.
        self.x.append(self.x[-1] + 0.01)  # Add a new value 1 higher than the last.
        xjudge = self.x[-1]
        while xjudge > self.rampT5:
            xjudge = xjudge - self.rampT5

        if self.mode >= mode_const.TRC_MODE:      # visual feedback mode or CPM mode
            self.y = self.y[1:]  # Remove the first
            if self.Trajmode == 1:
                self.y.append(self.magnitude * math.sin(self.x[-1]*self.freq) + self.offset)  # Add a new random value.
                tpp = self.y[200]  # mid of the figure
            elif self.Trajmode == 0:
                yindex = int(np.round(xjudge * 100)) - 1
                self.y.append(self.yramp_int[yindex])  # Add a new random value.
                tpp = self.y[int(len(self.y) / 2)]  # mid of the figure
            elif self.Trajmode == 2:
                self.y.append(self.ranmagnitude * (1 / 3) * (math.sin(2 * np.pi * (0.5 * self.x[-1]) + self.phi[0]) + math.sin(2 * np.pi * (0.2 * self.x[-1]) + self.phi[1]) + math.sin(2 * np.pi * (0.15 * self.x[-1]) + self.phi[2])) + self.offset)   #  self.NeutralPosition Add a new random value.
                tpp = self.y[200]  # mid of the figure
        else:
            tpp = self.y[-1]

        # self.graphWidget.setXRange(self.x[0], self.x[-1], padding=0)

        ######## This is how we update the plot. Mainly for testing not clinical using.                          ########
        ######## Change plotcounter to change the FPS, small number makes plotting smooth but may freeze easily. ########
        # if self.plotcounter == 4:
        #     self.real_line.setData(self.p)
        #     # self.real_line_2.setData(self.v)
        #     self.target_line.setData(self.y)  # Update the data.
        #     # self.target_line_EMG2.setData(self.x, self.emg2)
        #     # self.graphWidget.setXRange(self.x[0], self.x[-1], padding=0)
        #     self.real_line.setPos(self.postr1, 0)
        #     # self.real_line_2.setPos(self.postr1, 0)
        #     self.target_line.setPos(self.postr1, 0)
        #     self.plotcounter = 0
        # self.plotcounter = self.plotcounter + 1
        # self.graphWidget.setYRange(self.saveMaxPos + 10, self.saveMinPos - 10, padding=0)

        return tpp

    def display_data(self):
        # self.csvfilename = 'Data_0408_155328.csv'
        flag = os.path.isfile(self.csvfilename)
        # print(flag)
        if flag:        # plot EMG if file exist
            # read csv file
            df = pd.DataFrame()
            df = pd.read_csv(self.csvfilename, header=None)
            # get EMG data
            time_x = df.loc[:, 0]
            angle = df.loc[:, 2]
            torque = df.loc[:, 3]
            emg_ta = df.loc[:, 4]
            emg_gm = df.loc[:, 5]
            time_x = (time_x - time_x[0])
            # plot EMG data
            self.graphWidget.clear()
            if self.mode == mode_const.ROM_MODE:
                pen = pg.mkPen(color=(51, 255, 255), width=3)
                self.graphWidget.plot(time_x, angle, name='Ankle angle', pen=pen)
                self.graphWidget.setYRange(self.saveMaxPos + 10, self.saveMinPos - 10, padding=0)
            elif self.mode == mode_const.MVC_MODE:
                pen = pg.mkPen(color=(51, 255, 255), width=3)
                self.graphWidget.plot(time_x, emg_ta+5, name='EMG TA', pen=pen)
                pen = pg.mkPen(color=(51, 51, 255), width=3)
                self.graphWidget.plot(time_x, emg_gm-5, name='EMG GM', pen=pen)
                pen = pg.mkPen(color=(51, 51, 0), width=3)
                self.graphWidget.plot(time_x, torque, name='Torque', pen=pen)
                torque[1] = 10
                ylim_t = max(abs(torque))
                self.graphWidget.setYRange(-ylim_t, ylim_t, padding=0)
                self.graphWidget.setLabel('left', 'EMG', color='red', size=30)
            self.plot_init = 0


    ##############################################################################################
    ######## Not Used, this is a dirty way to prevent the plot freezing                   ########
    ######## If used, uncomment this part and add 'self.refreshstatus = 1' at Status Init ########
    ##############################################################################################
    # def Refresh(self):
    #     while True:
    #         if self.refreshstatus == 1:
    #             self.resize(985 + self.refreshstatus, 900)
    #             # self.setGeometry(500, 100, 985 + self.refreshstatus, 900)
    #             self.refreshstatus = 0
    #         elif self.refreshstatus == 0:
    #             # self.setGeometry(500, 100, 985 + self.refreshstatus, 900)
    #             self.resize(985 + self.refreshstatus, 900)
    #             self.refreshstatus = 1
    #         QApplication.processEvents()


def main():
    gl._init()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet('.QLabel { font-size: 12pt;}')
    main = MainWindow()
    main.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()