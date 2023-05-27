####
## Socket thread, communication between Unity and Python ##


from socket import *
import threading
from PyQt5.QtCore import QThread, pyqtSignal

####
class recs(QThread):
    signal = pyqtSignal('PyQt_PyObject')

    def __init__(self):
        QThread.__init__(self)
        print('Initializing the TCP socket')
        address = '127.0.0.1'
        port = 25001
        self.s = socket(AF_INET, SOCK_STREAM)
        self.s.bind((address, port))
        self.s.listen(5)  # Max Connect
        self.conn_list = []
        self.conn_dt = {}

    def tcplink(self, sock, addr):
        while True:
            try:
                recvdata = sock.recv(1024).decode('utf-8')    # Receive data from Unity
                if not recvdata:
                    break
            except:
                sock.close()
                print(addr, 'offline')
                _index = self.conn_list.index(addr)
                self.conn_dt.pop(addr)
                self.conn_list.pop(_index)
                break

    def run(self):
        while True:
            clientsock, clientaddress = self.s.accept()
            if clientaddress not in self.conn_list:
                self.conn_list.append(clientaddress)
                self.conn_dt[clientaddress] = clientsock
            print('connect from:', clientaddress)
            # Create New thread to keep different sockets
            t = threading.Thread(target=self.tcplink, args=(clientsock, clientaddress))  # t---New Thread
            t.start()

class Server:
    def __init__(self, cdt, clist, input1, input2):
        self.conn_dt = cdt
        self.conn_list = clist
        self.input1 = input1
        self.input2 = input2

        # time.sleep(0.01)  # sleep 0.5 sec
        self.startPos = [-0.14, self.input1, self.input2]  # Vector3   x = -0.14, y = pos, z = 0
        self.startPos2 = [-0.14, self.input1, self.input2]
        posString = ','.join(map(str, self.startPos))  # Converting Vector3 to a string, example "0,0,0"
        posString2 = ','.join(map(str, self.startPos2))  # Converting Vector3 to a string, example "0,0,0"
        try:
            self.conn_dt[self.conn_list[-1]].sendall(posString.encode('utf-8'))
        except:
           print('No Unity Connected')
           pass

        try:
            self.conn_dt[self.conn_list[-2]].sendall(posString2.encode('utf-8'))
        except:
            # print('No Second Unity Connected')
            pass

