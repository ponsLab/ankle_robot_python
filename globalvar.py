##############################################################################################
## Function to create global variables                                                      ##
## Mainly used when data need to transfer from GUI to M1 thread and FFTAI_M1_Simple.py file ##
##############################################################################################

#### Initialization ####
def _init():
    global _global_dict
    _global_dict = {}

#### Create a new global variable in the dictionary ####
def set_value(name, value):
    _global_dict[name] = value

#### Get the data from the dictionary ####
def get_value(name, defValue=None):
    try:
        return _global_dict[name]
    except KeyError:
        return defValue