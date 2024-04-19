import select, socket, queue
from threading import Thread
from struct import *
from time import time
#import logging

########################################################################
# This parses the argv in order to determine the inputs to the server on startup.
# This particular implementation allows for choosing between local_host and actual IP address.
# You need to specify the operating system so that automatic IP address determination works:
# python TCPDH_controller.py -ip <specified ip adress> -os < macOS  or linux > -pt <port number>
# currently doeesn't allow choosing TCPIP_PORT, it is set to a defaultvalue
# used in main()
def argv_parse(args):
    if len(args)%2 !=0:# make sure the inputs are in key-value pairs, crash if not
        raise Exception("argv error, the inputs must come in '-key value' pairs.\n"+
             "Allowed inputs:\n"+
             "\t -os <'mac' or 'linux'>     -ip <IP address>     -pt < IP port>     -sp <serial port>")
    else: # separate out the input designation ind from the settings.
        ind = [ args[i] for i in range(0 , len(args),2)]
        settings=[args[i+1] for i in range(0 , len(args),2)]
        inpt = dict(zip(ind, settings))
    server_OS = ''
    serial_port = '/dev/ttyACM0'
    host_name = None
    TCPIP_PORT = 6750
    for d in ind: # crash if input designation is unknown
        if d not in [ '-ip','-os','-pt','-sp']:
            raise Exception("argv error, the inputs must come in '-key value' pairs.\n"+
             "Allowed inputs:\n"+
             "\t-os <'mac' or 'linux'>     -ip <IP address>     -pt <IP port>     -sp <serial port>")
        else:
            if d == '-os' :
                server_OS = inpt['-os']
            if d=='-ip' :
                host_name = inpt['-ip']
                if host_name == 'local_host':
                    host_name = '127.0.0.1'
            if d=='-pt':
                TCPIP_PORT = int(inpt['-pt'])
            if d== '-sp':
                serial_port=inpt['-sp']
    return server_OS, host_name, TCPIP_PORT, serial_port  

####################################################################
# design inspired by https://steelkiwi.com/blog/working-tcp-sockets/
# This is a simple socket-to-queue server thread that takes incoming socket
# instr and puts them in the outgoing queue q1, and then reads from
# the incoming queue q2. The read of the response q2 is blocked on the 
# completion of the q1 task_done() which must be handled by another 
# (hardware controller) thread. IT ASSUMES THERE IS ANOTHER THREAD OR FUNCTION 
# HANDLING THE OTHER END OF THE QUEUE. The user is responsible for
# 1) providing the hardware q-handler
# 2) ensuring that the hardware q-handler is run in the same main thread
# so that they both have access to the queue's
class SimpleServer(Thread):
    def __init__(self,start_time,q1,q2,server_OS, host_name,TCPIP_PORT):
        Thread.__init__(self)
        self.debug_mode = False
        self.start_time = start_time
        self.delta_time = 0
        self.qinstr = q1
        self.qresp = q2
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setblocking(0) # make the server non blocking so that it doesn't hang up
        # allow reconnect during "TIME_WAIT", i.e. when the client is down but
        # not officially closed:
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # get the host_name, which is OS dependent:
        if (host_name == None):
            import subprocess as sp
            if server_OS == 'mac': #run make OS commands
                host_name = sp.check_output('ipconfig getifaddr en0',shell = True).decode("utf-8").strip() 
            else: #run linux OS commands.  TODO: find out what the windows command is.
                host_name = sp.check_output('hostname -I',shell = True).decode("utf-8")
            if len(host_name.split()) > 1:
                host_name= host_name.split()[1]
 
        self.server.bind((host_name, TCPIP_PORT))
        self.server.listen(5)
        print("----------------------------------------------")
        print('-------- Server started: {0}'.format(host_name))
        print("----------------------------------------------")

    def read_all_data(self,connection,to_be_read, timeout = 5):
        buffer=b''
        now = time()
        time_elapsed=0
        while to_be_read > 0:
            data = b''
            if time_elapsed < timeout:
                try:
                    data = connection.recv(min(to_be_read,8))
                except:
                    pass
                if data:
                    now = time()
                time_elapsed = time() - now
            else:
                if len(data) == 0:
                    break 
                else:
                    raise TimeoutError('Timeout in read_all_data')

            to_be_read=to_be_read-len(data)
            self.delta_time = time() - self.start_time
            if self.debug_mode: print("simple_server.py: "+'{} : '.format(self.delta_time)+
                  "Sending long message of ", to_be_read.replace('\n','[EOL]'), " bytes.") 
            #print("Just received packet ")
            self.delta_time = time() - self.start_time
            if self.debug_mode: print('simple_server.py: '+'{} : '.format(self.delta_time)+
                  'sending data back to the client')
            #connection.sendall(data)
            buffer+=data
        return buffer 
 
    def run(self):
        #these variables are never needed outside of this routine,
        # which is intended to run indefinitely. Hence the lack of 'self.'
        inputs = [self.server]
        outputs = []
        while inputs:
            # get the status of sockets on the address/port:
            if self.debug_mode:
                print("-----------------------------------------------------------------------")
                print("----------in simple_server.py: while inputs:--------------")
                print("-----------------------------------------------------------------------")
            if self.debug_mode: print("Clients-  Inputs:",len(inputs)-1,"  Outputs: ",len(outputs))
            readable, writable, exceptional = select.select(inputs, outputs, inputs)
            for s in readable:  # loop over the sockets that have something ready/waiting
                if s is self.server: # the server is in "readable" if it has a connection request
                    connection, client_address = s.accept() # accept the connection request
                    connection.setblocking(0)               # set non-blocking
                    inputs.append(connection)               # add the new socket to inputs list

                    if self.debug_mode: 
                        self.delta_time = time() - self.start_time
                        print("simple_servery.py: "+'{} : '.format(self.delta_time)+
                              "connection made with {}".format(client_address[0])) 
                else:  # if this is a client socket that has sent something to the socket buffer,
                    try:
                        data = s.recv(4096) # read a 4096 byte (or less) chunk of the buffer
                        if self.debug_mode:
                            self.delta_time = time() - self.start_time
                            print("simple_server.py: "+'{} : '.format(self.delta_time)
                                  +"readable data, len(data):", len(data))
                    except ConnectionResetError: # if connection is closed
                        data =b""                # return no data
                    if data:                     # if something is received, put the data in the
                        self.qinstr.put(data)    # queue for this client. If this is the first
                        # self.qinstr.task_done()
                        if s not in outputs:     # time we read from it, we need to put it in the
                            if self.debug_mode:
                                self.delta_time = time() - self.start_time
                                print('simple_server.py: '+'{} : '.format(self.delta_time)+
                                      'data appended to outputs:',s)
                            outputs.append(s)    # list of clients that are going to receive a response
                    else:
                        if s in outputs:       # if there is no data then all data has been read,
                            if self.debug_mode:
                                self.delta_time = time() - self.start_time
                                print('simple_server.py: '+'{} : '.format(self.delta_time)
                                      +'no data... removing from outputs:',s)
                            outputs.remove(s)  # so remove it from inputs and close it from our end.
                        if self.debug_mode:
                            self.delta_time = time() - self.start_time
                            print('simple_server.py: '+'{} : '.format(self.delta_time)+
                                  'removing from inputs:',s)
                        inputs.remove(s)       
                        s.close()
                        self.qinstr.queue.clear()
                        self.qresp.queue.clear()


            for s in writable:
                try:
                    if self.debug_mode:
                        self.delta_time = time() - self.start_time
                        print('simple_server.py: '+'{} : '.format(self.delta_time)
                              +'We have "s in writable": Trying qinstr.join()...')
                    self.qinstr.join()# waits for the instr queue task to complete
                    next_msg = self.qresp.get_nowait()
                    if self.debug_mode:
                        self.delta_time = time() - self.start_time
                        print("simple_server.py: "+'{} : '.format(self.delta_time)+
                              "writable next_msg ",str(next_msg).replace('\n','[EOL]'))
                except queue.Empty:
                    if s in outputs:
                        if self.debug_mode:
                            self.delta_time = time() - self.start_time
                            print('simple_server.py: '+'{} : '.format(self.delta_time)
                                  +': s in writable: removing s: ',s)
                        outputs.remove(s)
                else:
                    # if you need to trap an error here, you can uncomment the code below
                    # placing s.send(next_msg) in the try: block
                    # try:
                    s.send(next_msg)
                    # except Exception as e:
                    #     if self.debug_mode:
                    #         self.delta_time = time() - self.start_time
                    #         print('simple_server.py : '+'{} : '.format(self.delta_time)+
                    #               's in writable: failed to send! Exception: ',e)
                    #     outputs.remove(s) 
                    #     if s in inputs:
                    #         inputs.remove(s)

            for s in exceptional:  # shut down the client socket and queue if 
                inputs.remove(s)   # there is an exception
                if s in outputs:
                    outputs.remove(s)
                s.close()
                self.qinstr.queue.clear()
                self.qresp.queue.clear()
                # del self.qinstr
                # del self.qresp
                
