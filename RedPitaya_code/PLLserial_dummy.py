# cmdList ={  # list of acceptable two-character commands and their action functions
#         "SC": StatusCarrier,  # Status Carrier (effectively checks the stats both RedPitaya and PLLTeensy) (TEENSY/SERIAL)
#         "FC": setFrequencyCarrier,  # Frequency Carrier (sets the PLL carrier frequency in manual mode)  (TEENSY/SERIAL)
#         "FT": progFrequencyTable,  # Frequency Table programs the tableable frequencies to step through.  (TEENSY/SERIAL)
#         "TT": TransitionTable_mode,  # Transition to Table mode.  After the table prog, the mode is set to triggered table (TEENSY/SERIAL)
#         "TM": TransitionManual_mode,  # Transition to Manual mode.  (TEENSY/SERIAL)
#         "FM": setFrequencyMod,  # Freq. MOD. (sets the modulation frequency) (REDPITAYA)
#         "PM": setPhaseMod,  # Phase Mod. (sets the phase of the modulation/ demodulation) (REDPITAYA) 
#     }    
####################################################
# This is a software emulation of the Teensy controlled
# PLL that is useful for debugging the Labscript code
# without having to have actual PLL device to play with.
# (you do need a Teensy programmed to act as a dummy, though.)
# The error trapping is done by hand and does not use
# python's handler

class PLLTeensy_dummy():
    def __init__(self,com_port):
        # serial emulation variables basically unused buckets so the dummy looks real.
        self.com_port = com_port
        self.baudrate = 19200  # set Baud rate to 9600
        self.bytesize = 8     # Number of data bits = 8
        self.parity   ='N'    # No parity
        self.stopbits = 1
        self.response ="" 
        self.sentinstr=""
        self.write_timeout = 5 # I have no idea if this will ever by used, 
        self.timeout = 5
        
        #teensy response emulation variables
        self.parseError = False
        self.cmdString =""
        self.dataString = ""
        self.inputString=""
        self.errorString = ""
        self.currentFInt=int(1e6)

    def splitInstr(self,inputString=""): # split instr into cmd+data
        #print("Teensy_dummy:splitInst:"+inputString)
        if(len(inputString) >1):
            self.cmdString=inputString[0:2]
            #print(self.cmdString)
        else: 
            self.parseError = True
            self.errorString+="ER: split command parsing error: at least two chars needed"
        #print(len(inputString))
        if(len(inputString)>3 &  (not (self.parseError))):
            self.dataString=inputString[3:]

    # emulate the action of the Teensy's response to the instr.
    def doInstr(self,cmd="", data=""):
        if cmd =="Q?":
            print(str(self.currentFInt))
            self.response= 'FC '+str(self.currentFInt)
            return  
        if cmd=="SC":    # -------parse the SC command: check the status of the device.
            pass
            #self.response= "OK"
            #print(self.response+"; cmd")
        if cmd == "TM":
            self.response = "TM mode dummy"
            return
        if cmd =="TT":
            self.response = "TT dummy response: TT "+data
            return
        elif len(data)>0 :
            if cmd == "FC":      # ----------- parse the FC command: set the carrier frequency to a value.
                for i in range(0,len(data)):
                    if not data[i].isdigit():
                       self.parseError = True
                       self.errorString+="ER:data parsing error: FC data must be digits."
                       break
                if not self.parseError:
                    self.currentFInt=int(data)
                    self.response= "FC "+data 
                    #do hardware setting of parameters here
            elif cmd =="FT":
                self.response= "FT "+data
            else :  #    -------------- no recognized command
                self.parseError = True
                self.errorString +="ER:cmd parsing error: cmd not recognized"  
        else : 
            self.parseError = True
            self.errorString += "ER:data error: data string empty"
        return
    # dummy close()
    def close(self):
        pass
        
    # dummy write, basically store the written command into memory
    def write(self,sendbytes ):
        self.sentinstr =  sendbytes
        return
    # dummy readline, basically reads from the dummy sent line and responds.
    def read_until(self,endchar):
        self.response = ""
        #print("Teensy_dummy:read_until:"+self.sentinstr.decode())
        if self.sentinstr != b"":
            self.splitInstr(self.sentinstr.decode().strip())#decode from binary to emulate the real thing
        if(not self.parseError):
            # print(f"before doInstr() {self.cmdString},{self.dataString}")
            self.doInstr(self.cmdString,self.dataString)
            #(self.response+":: doinstr")
            # print(self.errorString)
        if(not self.parseError):
            self.sentinstr=""
            self.cmdString=""
            self.dataString=""
            return((self.response+"\n").encode()) #encode to binary to emulate the real thing
        else :
            return ("ER: "+self.errorString+"\n").encode()
