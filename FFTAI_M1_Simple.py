import canopen
import time
import numpy as np
import math

import M1_MISC
import globalvar as gl


target_torque = 0x6071
target_position = 0x607A
target_velocity = 0x60ff
target_current = 0x60F6
profile_velocity = 0x6081
profile_acceleration = 0x6083
profile_deceleration = 0x6084

profile_position = 0x6086  # not right

actual_position = 0x6063
actual_velocity = 0x606c
actual_torque = 0x6077
actual_current = 0x6078
error_code = 0x603f  # not right
status_word = 0x6041
control_word = 0x6040
operation_mode = 0X6060
# error_code = 0x2601

velocity_offset = 0x60B1
torque_offset = 0x60B2
pos_control = 0x60FB


class FFTAI_M1:

    def __init__(self, bustype='pcan', channel='PCAN_USBBUS1', bitrate=1000000):
        # Start with creating a network representing one CAN bus
        self.network = canopen.Network()

        # Connect to the CAN bus
        # (see https://python-can.readthedocs.io/en/latest/bus.html).
        self.network.connect(bustype=bustype, channel=channel, bitrate=bitrate)

        self.node = self.network.add_node(1, 'CopleyAmp_yw.eds')
        self.sensor = self.network.add_node(2, 'torque_sensor.eds')

        # # reset error
        self.reset_error()
        self.position = 0
        self.velocity = 0
        self.torque = 0
        self.current = 0
        self.torque_s = 0
        self.Kvff = 256
        self.maxAssist = 10     # the assistance threshold, set a large value to disable this function

        # for admittance control
        self.pos = 0
        self.vel = 0
        self.torque_s_hist = [0 for k in np.arange(0, 3, 1)]
        self.compency = 3 # 1 for position compensation, 2 for velocity compensation, 3 for friction compensation
        self.k = 1          # gain of position error
        self.b = 0.02       # gain of velocity error
        self.gain = 10
        self.Mass = 0.01
        self.count = 0
        # self.torque_emg = 0;

        self.EMG1 = 0
        self.EMG2 = 0
        self.torCMD_record = 0
        self.torEMG_record = 0
        self.torFF_record = 0
        self.mode = 0

    def reset_error(self):
        # shutdown
        control_word_node = self.node.sdo[control_word]
        control_word_node.raw = 0x06
        # reset fault
        control_word_node = self.node.sdo[control_word]
        control_word_node.raw = 0x80
        # enable operation
        control_word_node = self.node.sdo[control_word]
        control_word_node.raw = 0x06

    def sensor_init(self):
        index = 1
        self.sensor.tpdo[index].clear()
        self.sensor.tpdo[index].add_variable(0x7050)  # Torque Sensor
        self.sensor.tpdo[index].add_variable(profile_velocity) # 0x6081
        self.sensor.tpdo[index].trans_type = 1  # http://www.ars-informatica.com/Root/Code/CANOPEN/CommunicationParametersTPDO.aspx
        self.sensor.tpdo[index].inhibit_time = 0
        self.sensor.tpdo[index].enabled = True

        self.sensor.tpdo[1].cob_id = 0x191  # change torque sensor address based on M1 (unflashed 0x192, flashed 0x191)
        self.sensor.tpdo[1].add_subscribe()  # does not exist in canopen 1.2.1 (canopen 2.1.0 has subscribe() function)

    def initialization(self, mode):
        self.sensor_init()
        self.mode = mode
        if mode == 1:                     # free move: ROM measurement
            # self.initialization_velocity()
            if self.compency == 1:
                self.initialization_position()
                self.set_position_mode()  # compensate with torque reading
            elif self.compency == 2:
                # compensate with velocity
                self.initialization_velocity()
            elif self.compency == 3:
                self.initialization_torque()

        elif mode == 2:                    # position control: MVC mode
            self.initialization_position()
            self.set_position_mode()

        elif mode == 3:             # compensate control: Tracking task
            if self.compency == 1:
                self.initialization_position()
                self.set_position_mode()  # compensate with torque reading
            elif self.compency == 2:
                # compensate with velocity
                self.initialization_velocity()
            elif self.compency == 3:
                self.initialization_torque()

        elif mode == 4:         # position control: CPM mode
            self.initialization_position()
            self.set_position_mode()

        elif mode == 5:         # compensation: Visual feedback mode
            if self.compency == 1:
                self.initialization_position()
                self.set_position_mode()  # compensate with torque reading
            elif self.compency == 2:
                # compensate with velocity
                self.initialization_velocity()
            elif self.compency == 3:
                self.initialization_torque()

        elif mode == 6:         # compensation: Haptic feedback mode
            if self.compency == 1:
                self.initialization_position()
                self.set_position_mode()  # compensate with torque reading
            elif self.compency == 2:
                # compensate with velocity
                self.initialization_velocity()
            elif self.compency == 3:
                self.initialization_torque()

    def initialization_record(self):
        print("Initializing recoding mode")
        # set control word to power up
        control_word_node = self.node.sdo[control_word]
        control_word_node.raw = 0x06

    def initialization_position(self):
        print("Initializing position mode")
        # set control word to power up
        control_word_node = self.node.sdo[control_word]
        control_word_node.raw = 0x0f
        # set operation model to position control
        operation_mode_node = self.node.sdo[operation_mode]
        operation_mode_node.raw = 0x01

    def initialization_velocity(self):
        print("Initializing velocity mode")
        # set control word to power up
        control_word_node = self.node.sdo[control_word]
        control_word_node.raw = 0x0f
        # set control model to velocity control
        operation_mode_node = self.node.sdo[operation_mode]
        operation_mode_node.raw = 0x03

    def initialization_torque(self):
        print("Initializing torque mode")
        # set control word to power up
        control_word_node = self.node.sdo[control_word]
        control_word_node.raw = 0x0f
        # set operation model to torque control
        operation_mode_node = self.node.sdo[operation_mode]
        operation_mode_node.raw = 0x04

    def pdo_conf(self):
        ''' Setup tPDO, rPDO'''
        # Save new configuration (node must be in pre-operational)
        self.node.nmt.state = 'RESET'
        time.sleep(1)
        self.node.nmt.state = 'PRE-OPERATIONAL'

        # PDO settings
        self.rpdo_conf()
        self.tpdo_conf()

    def rpdo_conf(self):
        # Re-map RPDO[1]
        # sent data to device
        self.node.rpdo.read()
        self.node.rpdo[1].clear()
        self.node.rpdo[1].add_variable(target_velocity)
        self.node.rpdo[1].add_variable(control_word)
        self.node.rpdo[1].trans_type = 1  # 254
        # self.node.rpdo[1].inhibit_time = 2
        self.node.rpdo[1].enabled = True

        self.node.rpdo[2].clear()
        self.node.rpdo[2].add_variable(target_position)
        self.node.rpdo[2].add_variable(profile_velocity)
        self.node.rpdo[2].trans_type = 1  # 254
        # self.node.rpdo[2].inhibit_time = 2
        self.node.rpdo[2].enabled = True

        self.node.rpdo[3].clear()
        self.node.rpdo[3].add_variable("Current loop control parameters", "CMD_q")
        self.node.rpdo[3].trans_type = 1  # 254
        # self.node.rpdo[2].inhibit_time = 2
        self.node.rpdo[3].enabled = True

        self.node.rpdo[4].clear()
        self.node.rpdo[4].add_variable('Velocity control parameters', 'Proportional gain for velocity loop')
        self.node.rpdo[4].add_variable('Velocity control parameters', 'Integral gain for velocity loop')
        self.node.rpdo[4].trans_type = 1  # 254
        # self.node.rpdo[1].inhibit_time = 2
        self.node.rpdo[4].enabled = True

        self.node.rpdo[5].clear()
        self.node.rpdo[5].add_variable('Position control parameter set', 'Proportional gain for position loop')
        self.node.rpdo[5].add_variable('Position control parameter set', 'Velocity feed forward for position loop')
        self.node.rpdo[5].trans_type = 1  # 254
        # self.node.rpdo[1].inhibit_time = 2
        self.node.rpdo[5].enabled = True

        # self.node.rpdo[3].clear()
        # # node.rpdo[3].add_variable(target_torque)
        # self.node.rpdo[3].add_variable(target_current, 0x08)
        # # node.rpdo[3].add_variable(control_word)
        # self.node.rpdo[3].trans_type = 1
        # # node.rpdo[2].inhibit_time = 2
        # self.node.rpdo[3].enabled = True

        # Save new PDO configuration to node
        self.node.rpdo.save()

    def tpdo_conf(self):
        # Re-map TPDO[1]
        # receive data from device
        self.node.tpdo.read()
        index = 1
        self.node.tpdo[index].clear()
        self.node.tpdo[index].add_variable(status_word)
        self.node.tpdo[index].trans_type = 1  # http://www.ars-informatica.com/Root/Code/CANOPEN/CommunicationParametersTPDO.aspx
        # self.node.tpdo[index].inhibit_time = 0
        self.node.tpdo[index].enabled = True

        # Re-map TPDO[2]
        index = 2
        self.node.tpdo[index].clear()
        self.node.tpdo[index].add_variable(actual_position)
        self.node.tpdo[index].add_variable(actual_velocity)
        self.node.tpdo[index].trans_type = 1  # http://www.ars-informatica.com/Root/Code/CANOPEN/CommunicationParametersTPDO.aspx
        self.node.tpdo[index].enabled = True

        # # Re-map TPDO[3]
        index = 3
        self.node.tpdo[index].clear()
        self.node.tpdo[index].add_variable(actual_torque)
        self.node.tpdo[index].add_variable(actual_current)
        self.node.tpdo[index].trans_type = 1  # http://www.ars-informatica.com/Root/Code/CANOPEN/CommunicationParametersTPDO.aspx
        self.node.tpdo[index].enabled = True

        index = 4
        self.node.tpdo[index].clear()
        self.node.tpdo[index].add_variable('Velocity control parameters', 'Proportional gain for velocity loop')
        self.node.tpdo[index].add_variable('Velocity control parameters', 'Integral gain for velocity loop')
        self.node.tpdo[index].trans_type = 1  # http://www.ars-informatica.com/Root/Code/CANOPEN/CommunicationParametersTPDO.aspx
        self.node.tpdo[index].enabled = True

        index = 5
        self.node.tpdo[index].clear()
        self.node.tpdo[index].add_variable('Position control parameter set', 'Proportional gain for position loop')
        self.node.tpdo[index].add_variable('Position control parameter set', 'Velocity feed forward for position loop')
        self.node.tpdo[index].trans_type = 1  # http://www.ars-informatica.com/Root/Code/CANOPEN/CommunicationParametersTPDO.aspx
        self.node.tpdo[index].enabled = True

        self.node.tpdo.save()

    def set_recording_mode(self):
        # power-off motor to allow free movement
        control_word_node = self.node.sdo[control_word]
        control_word_node.raw = 0x06

    def set_position_mode(self):
        ''' Setting profile velocity, acceleration, deceleration'''
        # set velocity
        velocity_node = self.node.sdo[profile_velocity]
        velocity_node.raw = M1_MISC.rpm2dec(600)
        # set acceleration
        acc_node = self.node.sdo[profile_acceleration]
        acc_node.raw = M1_MISC.rpss2dec(500)  # acceleration too high will cause
        # set deceleration
        dec_node = self.node.sdo[profile_deceleration]
        dec_node.raw = M1_MISC.rpss2dec(500)

        # instant position mode; important
        control_word_node = self.node.sdo[control_word]
        control_word_node.raw = 0x103f

    def start_mnt(self, frequncy=400):
        ''' Start sync'''
        # Transmit SYNC every 0.01 s
        # the actual cycle is about 100hz with 0.009
        self.network.sync.start(1/frequncy)

        # Change state to operational (NMT start)
        self.node.nmt.state = 'OPERATIONAL'
        # time.sleep(1)

    def stop_mnt(self):
        self.node.rpdo.stop()
        self.network.sync.stop()

    # not in use
    def set_callback(self, process):
        self.node.tpdo[1].add_callback(process)

    def run(self, function=None):
        while True:
            self.node.tpdo[1].wait_for_reception()
            # print(time.time())
            # status['status'] = self.node.tpdo[1]['Status word'].phys
            p = self.node.tpdo[2]["Actual motor position"].raw
            # status['position'] = M1_MISC.count2deg(p)
            print("Position: %f" % M1_MISC.count2deg(p))
            if function is not None:
                function(p)
            # v = self.node.tpdo[2]["Actual motor velocity"].raw
            # status['velocity'] = M1_MISC.dec2rpm(v)
            # t = self.node.tpdo[2]["Torque actual value"].phys
            # status['torque'] = t

    def wait_for_data(self):
        Torque_Offset = gl.get_value('TorqueOffset')
        self.node.tpdo[2].wait_for_reception()
        # print(time.time())
        # status['status'] = self.node.tpdo[1]['Status word'].phys
        p = self.node.tpdo[2]["Actual motor position"].raw
        v = self.node.tpdo[2]["Actual motor velocity"].raw
        t = self.node.tpdo[3]["Torque actual value"].raw
        c = self.node.tpdo[3]["Current_actual_value"].raw
        Kvp = self.node.tpdo[4]['Velocity control parameters.Proportional gain for velocity loop'].raw
        Kvi = self.node.tpdo[4]['Velocity control parameters.Integral gain for velocity loop'].raw
        Kpp = self.node.tpdo[5]['Position control parameter set.Proportional gain for position loop'].raw
        self.Kvff = self.node.tpdo[5]['Position control parameter set.Velocity feed forward for position loop'].raw
        t_s = self.sensor.tpdo[1]["Torque sensor"].raw
        # c = self.node.tpdo[3]["Current_actual_value"].phys
        # self.sensor.tpdo[1]
        self.position = M1_MISC.count2deg(p)
        self.velocity = M1_MISC.dec2rpm(v)
        self.torque = t
        self.torque_s = t_s *0.0707-107.6735-Torque_Offset # torque sensor calibration
        self.current = c

    def position_loop(self, position):
        self.torque_s_hist = self.torque_s_hist[1:]
        self.torque_s_hist.append(self.torque_s)
        torque = np.mean(self.torque_s_hist)

        position_error = position - self.position
        gain = 200
        velocity = position_error*gain
        velocity_dec = M1_MISC.rpm2dec(velocity)
        self.node.rpdo[1]['Target velocity'].raw = velocity_dec
        self.node.rpdo[1]['Control word'].raw = 0x0f  # this velocity is very important for fast tracking
        self.node.rpdo[1].transmit()

    def set_velocity(self, velocity):
        velocity_dec = M1_MISC.rpm2dec(velocity)
        self.node.rpdo[1]['Target velocity'].raw = velocity_dec
        self.node.rpdo[1]['Control word'].raw = 0x0f  # this velocity is very important for fast tracking
        self.node.rpdo[1].transmit()

        self.node.rpdo[4]['Velocity control parameters.Proportional gain for velocity loop'].raw = 60
        self.node.rpdo[4]['Velocity control parameters.Integral gain for velocity loop'].raw = 5
        self.node.rpdo[4].transmit()

        self.node.rpdo[5]['Position control parameter set.Proportional gain for position loop'].raw = 1000
        self.node.rpdo[5]['Position control parameter set.Velocity feed forward for position loop'].raw = 256
        self.node.rpdo[5].transmit()

    def set_position(self, position):
        cnt = M1_MISC.degree2cnt(position)
        pv = M1_MISC.rpm2dec(1000)
        self.node.rpdo[2]['Profile target position'].raw = cnt
        self.node.rpdo[2]['Profile target velocity'].raw = pv  # this velocity is very important for fast tracking
        self.node.rpdo[2].transmit()

        self.node.rpdo[4]['Velocity control parameters.Proportional gain for velocity loop'].raw = 180
        self.node.rpdo[4]['Velocity control parameters.Integral gain for velocity loop'].raw = 5
        self.node.rpdo[4].transmit()

        self.node.rpdo[5]['Position control parameter set.Proportional gain for position loop'].raw = 950
        self.node.rpdo[5]['Position control parameter set.Velocity feed forward for position loop'].raw = 50
        self.node.rpdo[5].transmit()

    def set_current(self, current):
        # set current through PDO
        self.node.rpdo[3]["Current loop control parameters.CMD_q"].raw = current
        self.node.rpdo[3].transmit()

    def set_torque(self, torque):
        # set torque through sdo
        torque_node = self.node.sdo[target_torque]
        torque_node.raw = torque

    def compensation(self, compen = 3):
        EMGSignal1 = gl.get_value('EMGSignal1')
        EMGSignal2 = gl.get_value('EMGSignal2')
        EMGGain_TA = gl.get_value('TA EMGGain')
        EMGGain_GAS = gl.get_value('GAS EMGGain')
        saveMaxPos = gl.get_value('saveMaxPos')     # Max dorsi-flexion angle
        saveMinPos = gl.get_value('saveMinPos')     # Max plantar-flexion angle
        footweight = gl.get_value('FootWeight')     # User foot weight

        self.torque_s_hist = self.torque_s_hist[1:]
        self.torque_s_hist.append(self.torque_s)
        torque = np.mean(self.torque_s_hist)
        Tor_filt_prev = 0
        dt = 0.01
        self.compency = compen

        # Values estimated using system identification
        c0 = 2.15
        c1 = 1.2
        para_cos = 0.37 + 0.37 * footweight
        para_sin = 1.1 + footweight
        tor2cur = 7


        if self.compency == 1:
            # tor_cmd = torque - Ks*self.pos - B*self.vel
            # acc = tor_cmd/Mass
            # self.vel = self.vel + acc*dt
            # self.pos = self.pos + self.vel*dt
            # velocity = gain*(self.pos - self.position) + self.vel
            # cnt = M1_MISC.degree2cnt(self.pos)
            ratio = 3
            position = self.position + torque*ratio
            cnt = M1_MISC.degree2cnt(position)
            # self.position
            pv = M1_MISC.rpm2dec(200)
            self.node.rpdo[2]['Profile target position'].raw = cnt
            self.node.rpdo[2]['Profile target velocity'].raw = pv  # this velocity is very important for fast tracking
            self.node.rpdo[2].transmit()

        elif self.compency == 2:
            tor_cmd = torque - self.k*self.position - self.b*self.vel  # calculate torque
            acc = tor_cmd/self.Mass    # calculate acceleration
            self.vel = self.vel + self.gain*acc*dt   # calculate velocity
            # self.pos = self.pos + self.vel*dt
            # velocity = gain*(self.pos - self.position) + self.vel
            if self.position > 30 or self.position < -30:
                velocity = self.vel*0.5
            else:
                velocity = self.vel
            # print('position error: %f' % (self.pos - self.position))
            # velocity = self.velocity*0.5 + acc*0.01
            # print('velocity: %f' % velocity)
            # update velocity command through PDO
            velocity_dec = M1_MISC.rpm2dec(velocity)
            self.node.rpdo[1]['Target velocity'].raw = velocity_dec
            self.node.rpdo[1]['Control word'].raw = 0x0f  # this velocity is very important for fast tracking
            self.node.rpdo[1].transmit()

        elif self.compency == 3:

            if self.mode > 1 and (self.position > saveMaxPos+3 or self.position < saveMinPos-3):  # Limit the range of motion
                # disable this function if m1 is in rom mode, i.e., mode equals to 1
                cur_cmd = 0
                print('Out of ROM! Motor Off!')

            else:
                # Filter measured torque data with a first order filter
                torque_error = self.torque_s  # Calculate torque
                torCutoffFreq = 6
                alphaTor = (2*np.pi*0.01*torCutoffFreq)/(2*np.pi*0.01*torCutoffFreq+1)
                Tor_filt = alphaTor * torque_error + (1 - alphaTor) * Tor_filt_prev
                Tor_filt_prev = Tor_filt


                tor_fb = Tor_filt  # Interaction torque
                vel_act = self.velocity / 69 / 60 * math.pi * 2 # Foot plate velocity in radians
                position_rad = self.position * math.pi / 180

                # Estimated torque based on EMG signals. Uses velocity thresholds for stability
                if (vel_act > 0.2) and EMGSignal1 > 0.1:
                    self.torEMG_record = EMGGain_TA*EMGSignal1 + 0 * EMGGain_GAS*EMGSignal2
                elif (vel_act < -0.2) and EMGSignal2 > 0.1:
                    self.torEMG_record = 0 * EMGGain_TA * EMGSignal1 - EMGGain_GAS * EMGSignal2
                elif (vel_act > 0.01) and EMGSignal1 > 0.1:
                    self.torEMG_record = EMGGain_TA * EMGSignal1*1/3
                elif (vel_act < -0.01) and EMGSignal2 > 0.1:
                    self.torEMG_record = - EMGGain_GAS * EMGSignal2*1/3
                else:
                    self.torEMG_record = 0

                # provide assist
                if self.torEMG_record > self.maxAssist:
                    self.torEMG_record = self.maxAssist
                elif self.torEMG_record < -self.maxAssist:
                    self.torEMG_record = -self.maxAssist

                # Feedforward term calculation. Uses either the ankle velocity, interaction torque, or estimated EMG torque to calculate user intention
                if np.abs(vel_act) < 0.05: # 0.05
                    if(np.abs(Tor_filt)> 0.2):  # 0.3
                        self.torFF_record = c0 * np.sign(tor_fb) + para_sin * np.sin(position_rad) + para_cos * np.cos(position_rad)
                        # Static friction, dynamic friction compensation
                    # elif(np.abs(self.torEMG_record)>0.5):
                    #     self.torFF_record = c0 * np.sign(self.torEMG_record) + para_sin * np.sin(position_rad) + para_cos * np.cos(position_rad)
                    else:
                        self.torFF_record = para_sin * np.sin(position_rad) + para_cos * np.cos(position_rad)
                else:
                    self.torFF_record = c0 * np.sign(vel_act) + c1 * (vel_act) + para_sin * np.sin(position_rad) + para_cos * np.cos(position_rad)

                # Torque command sent to the M1 device. Constant multipliers are based on manual tuning.
                tor_cmd = (self.torFF_record*0.8 + tor_fb*3.3) + self.torEMG_record
                cur_cmd = tor_cmd * tor2cur  # Motor torque to current transition

                # Limit the current command for user-safety.
                if cur_cmd > 100:
                    cur_cmd = 100
                elif cur_cmd < -100:
                    cur_cmd = -100
                else:
                    cur_cmd = cur_cmd

            self.torCMD_record = cur_cmd        # To save current command. Can be deleted.
            self.set_current(cur_cmd)

    def close(self):
        # Stop transmission of RxPDO
        self.node.rpdo.stop()
        self.network.sync.stop()
        # self.network.disconnect()

def print_current(message):
    print("%s received" % message.name)
    for var in message:
        print("%s = 0x%x" % (var.name, var.raw))

def process(p):
    print("Position: %f" % p)