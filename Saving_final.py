######################################################################
## Input: Number of thread, queue name, column of data, File name   ##
## Example: my_thread = DataSave(1, tickets_queue, 3, 'EMGraw.csv') ##
######################################################################

from threading import Thread
import csv
import numpy as np
import os

class DataSave(Thread):

    def __init__(self, thread_id, data_queue, nData, name):
        super().__init__()
        self.thread_id = thread_id
        self.data_queue = data_queue
        self.exitFlag = False
        self.number = nData
        self.filename = name

    def run(self):
        super().run()
        global tickets
        rows = np.zeros([100,self.number])
        while True:
            if self.exitFlag:
                break
            # if self.data_queue.empty():
            #     print("empty")
            # else:
            try:
                for k in range(100):
                    for i in range(self.number):
                        tickets = self.data_queue.get()
                        # print(self.data_queue.qsize())  ## Check whether the data is stacked
                        rows[k,i] = tickets

                with open(self.filename, 'a', newline = '') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerows(rows)
            except:
                print('Something is wrong in the saving thread!')

    def terminate(self):
        self.exitFlag = True


#### Can remove a certain csv file, not used in main code ####

def clear_csv(csv_file):
    flag = os.path.isfile(csv_file)
    print(flag)
    if flag:
        os.remove(csv_file)

