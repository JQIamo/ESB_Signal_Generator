import queue
#from threading import Thread
from struct import *
from TCPDH_device_class_wrap import *
from simple_server import *
import sys
import time
#import logging


######################################################################
# This thread object manages the queue from the SimpleServer. It basically
# receives instr from the incoming queue and puts resp in the outgoing queue,
# calling the RedPitaya_TCPDH_device method RP_handle_instr().
# The hardware management of the Red Pitaya/PLLTeensy is entirely contained 
# in the RP_handle_instr() method.
class TCPDH_manager(Thread):
    next_command_length = None
    def __init__(self,start_time, q1,q2,serial_port_in): #must define queue inputs here because run() takes no args.
        Thread.__init__(self)
        self.debug_mode = False
        self.start_time = start_time
        self.delta_time = 0
        self.qinstr =q1
        self.qresp = q2
        self.serial_port =serial_port_in
        #instantiate the Red Pitaya device:
        self.RP = RP_TCPDH_device(start_time,serial_port_in = self.serial_port)
        #self.RP = TCPDH_device_Dummy(serial_port_in = self.serial_port)    #full dummy device that sims RP and Teensy    
        #self.RP = TCPDH_device_RP_Dummy(serial_port_in=self.serial_port)    #dummy device that sims RP and but not Teensy    
        #self.RP = RP_TCPDH_device_PLL_Dummy(self.serial_port) # dummy device that sims Teensy but real RP
        
    # define the thread action of the TCPDH_manager class
    # this will be run when .start() is called.
    def run(self):
        instr =""
        while True:
            # self.qinstr.join()
            instr =self.qinstr.get().decode()
            returnstr = self.RP.handle_instr(instr)# deal with the instruction
            if self.debug_mode:
                self.delta_time = time.time() - self.start_time
                print("TCPDH_controller.py: "+'{} : '.format(self.delta_time)+": in handle_instr : returnstr = "+returnstr)
            self.qresp.put(returnstr.encode())
            self.qinstr.task_done()

def main():
    # instantiate the instr/resp queues:
    q1=queue.Queue()  # instr queue
    q2=queue.Queue()  # response queue

    # Parse the command line to allow choosing between local_host and actual IP address.
    # You need to specify the operating system so that automatic IP address determination works:
    # python TCPDH_manager.py -ip <specified ip adress> -os < macOS  or linux > -pt <port number>
    server_OS,host_name,TCPIP_PORT,serial_port = argv_parse( sys.argv[1:])

    # instantiate the hardware manager thread
    print("---------------------------------------------------------------")
    print('-------- Starting server and RedPitaya/Teensy PLL device')
    print('-------- IP address: {0}  TCPIP port:{1}   Serial port: {2}'.format(host_name,TCPIP_PORT,serial_port))
    print("---------------------------------------------------------------")
    start_time = time.time()
    RP = TCPDH_manager(start_time,q1,q2,serial_port) 
    
    # instantiate the server thread
    serv = SimpleServer(start_time,q1,q2,server_OS, host_name,TCPIP_PORT) 
    
    #start the socket server and the RedPitaya controller
    serv.start()
    RP.start()
    
if __name__ == '__main__':
    main()
