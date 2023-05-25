#############################################
## Address and unit transfer for M1 device ##
#############################################

target_torque = 0x6071
target_position = 0x607A
target_velocity = 0x60ff
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


def rpss2dec(rpss):
    # unit of speed is rpm and internal unit is dec
    # max acceleration 1500ish
    encoder_res = 10000
    dec = rpss * 65536 * encoder_res / 4000000
    return int(dec)


def rpm2dec(rpm):
    # unit of speed is rpm and internal unit is dec
    # max velocity 4000ish
    encoder_res = 10000
    dec = rpm * 512 * encoder_res / 1875
    return int(dec)


def dec2rpm(dec):
    encoder_res = 10000
    rpm = dec * 1875 / (512 * encoder_res)
    return rpm


def degree2cnt(deg):
    count = deg * 10000 / 5.14
    return count


def count2deg(count):
    deg = count * 5.14 / 10000
    return deg
