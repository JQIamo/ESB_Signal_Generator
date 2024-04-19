#from threading import Thread 
import numpy as np
#from redpitaya.overlay.mercury import mercury as overlay
from PLLserial_dummy import PLLTeensy_dummy
import serial
import time
    
################################################################
# This is the parent device class that contains all the RedPitaya 
# data and methods for handling instructions in string format. 
# The RP_handle_instr is the parser/device action.
# The PLLsend_serial sends the instr to the PLL/Teensy.
# In order to debug the software without having the full hardware
# available, I have written "dummy" versions that simulate the 
# hardware. There are a total of four device classes, with all combinations
# of real vs. dummy hardware:  Real RP and real Teensy/PLL, 
# dummy RP and real Teensy/PLL, real RP and dummy Teensy and both dummy.
class TCPDH_device():#amp_mod_in = 0.2,freq_mod_in = 3e6,ref_phase_in =20):
    def __init__(self,start_time, amp_mod_in = 0.2,freq_mod_in = 500000,ref_phase_in =20,serial_port_in = '/dev/ttyACM0'):
        self.debug_mode = False
        self.buff = ''
        self.start_time = start_time
        self.delta_time = 0
        self.startup_banner(serial_port_in) #This onlly needs to be called onece, in the parent class of all the others.
        #Set the internal IQ modulator parameters.
        self.serial_port = serial_port_in
        self.beta2 = np.pi / 4 #
        self.x = np.linspace(0, 2*np.pi, 16000)# a fixed linear x scale that covers 2 pi
        self.IQ_OFFSET_sin = 0.042        
        self.IQ_OFFSET_cos = 0.025
        self.ALLOWED_FMOD = [500000, 625000, 781250, 1000000, 1250000, 1562500, 1953125, 2500000, \
                    3125000, 3906250, 5000000, 6250000, 7812500, 12500000]
        self.FM_MAX = 125000000
        self.cos_scale = 1.0
        self.sin_scale = 1.0
        self.sin_phase = 5/360*2*np.pi
        i=0 #find the closest commensurate analog frequency the requested input frequency
        while( (self.ALLOWED_FMOD[i+1]+self.ALLOWED_FMOD[i])< 2*(freq_mod_in) and i+1< len(self.ALLOWED_FMOD)-1):
            i+=1
        self.freq_mod= 500000 #self.ALLOWED_FMOD[i]
        self.ref_data_length = int(self.FM_MAX/self.freq_mod)
        delay = int(ref_phase_in * self.ref_data_length/360)
        self.ref_phase = int(360*delay/self.ref_data_length)
        #define a 50% duty cycle pulse with ref_data_length to phase match the analog signals.
        self.refwaveform = [0x0080 if i<self.ref_data_length/2 else 0 for i in range(0,self.ref_data_length)]
        self.refwaveform = self.refwaveform[delay:]+self.refwaveform[ :delay]
        self.amp_mod =amp_mod_in
        # depending on whether the dummy or real Teensy gets used,
        # override this:
        self.PLLTeensy_device= PLLTeensy_dummy(self.serial_port)
    
    # this should be overided by the actual class
    # implementations, so the banner matches the class
    def startup_banner(self,serial_port):
        pass

    def set_amp_mod(self,inputamp):
        self.amp_mod =inputamp
        
    def set_freq_mod(self,fin):
        i=0 #find the closest commensurate analog frequency the requested input frequency
        while( (self.ALLOWED_FMOD[i+1]+self.ALLOWED_FMOD[i])< 2*(fin) and i+1< len(self.ALLOWED_FMOD)-1):
            i+=1
        self.freq_mod= self.ALLOWED_FMOD[i]
     
    def set_ref_phase(self,inputphase):
        delay = int(inputphase * self.ref_data_length/360)
        self.ref_phase = int(360*delay/self.ref_data_length)
        #define a 50% duty cycle pulse with ref_data_length to phase match the analog signals.
        waveform = [0x0080 if i<self.ref_data_length/2 else 0 for i in range(0,self.ref_data_length)]
        waveform = waveform[delay:]+waveform[ delay:]
 
    def Cos_Quad(self):
        return self.IQ_OFFSET_cos + self.cos_scale*self.amp_mod * np.cos(self.beta2 * np.sin( self.x ))

    def Sin_Quad(self):    
        return self.IQ_OFFSET_sin + self.sin_scale*self.amp_mod * np.sin(self.beta2 * np.sin( self.x ) +self.sin_phase)

    def get_query(self):
        response= str(self.PLLsend_serial('Q?')+ ';'\
            +'FM '+str(self.freq_mod)+';'\
                +'PM '+str(self.ref_phase)+';')
        # print(response)
        return response

    def __del__(self):
        if self.debug_mode:
            self.delta_time = time.time() - self.start_time
            print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"closing down the RP signal Generators")
 
    def open_serial(self):
        return self.PLLTeensy_device

# This sends an instruction on to the Teensy/PLL. after
# sending, it reads a single, newline ended response. It
# is blocking on the read, but there is a 5 second timeout.
    def PLLsend_serial(self,instr):
        response = ""
        try:
            s = self.open_serial() # This is the Teensy
            s.baudrate  =115200
            s.write_timeout = 5 # I have no idea if this will ever by used, 
            s.timeout = 5   # keep from hanging on bad Teensy response
            #length_of_buffer=len(buffer).to_bytes(2,'little')
            #self.connection.sendall(length_of_buffer)
            try:
                # fp = open('PLLsend_serial.txt','w')
                s.write((instr+'\n').encode()) # PLL/Teensy needs the '\n' to end the read
                # fp.write((instr+'\n'))
                response = s.read_until(b'\n') # read until newline or timeout
                if response[-1:] ==b"\n": # if we read the entire response:
                    #response = response.decode().strip() #strip() the '\n'
                    response = response.decode().strip() #strip() the '\n'
                    if self.debug_mode:
                        self.delta_time = time.time() - self.start_time
                        print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"Teensy response: "+response)
                else:               # didnt read the whole response
                    response="ER: Timeout in PLLsend_serial "
                    if self.debug_mode:
                        self.delta_time = time.time() - self.start_time
                        print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"Teensy response: "+response)
                s.close() #everything succesful, close
                # fp.close()
            except serial.SerialTimeoutException as msg:
                response = "ER: Timeout in PLLsend_serial - {}".format(msg)
                if self.debug_mode:
                    self.delta_time = time.time() - self.start_time
                    print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"Teensy response: "+response)
        except serial.SerialException as msg:
            response ="ER: could not open port {}: {}".format(self.serial_port, msg)
            if self.debug_mode:
                self.delta_time = time.time() - self.start_time
                print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"Teensy response: "+response)
        return(response)

# This version of PLLsend was used during debugging to read more than
# one response from the Teensy/PLL. It is not reallly needed for the
# final version, altough if you don't use it, you need to make sure that
# that the code sends only  one newline terminated response, including
# all debugging Serial.print()  calls.   
    def PLLsend_and_read_all(self,instr):
        response = ""
        try:
            s = self.open_serial() # This is the Teensy
            s.baudrate  =115200
            s.write_timeout = 7 # I have no idea if this will ever by used, 
            s.timeout = 7   # keep from hanging on bad Teensy response
            #length_of_buffer=len(buffer).to_bytes(2,'little')
            #self.connection.sendall(length_of_buffer)
            try:
                s.write((instr+'\n').encode()) # PLL/Teensy needs the '\n' to end the read
                response = s.read_until(b'\n') # read until newline or timeout
                if response[-1:] ==b"\n": # if we read the entire response:
                    #response = response.decode().strip() #strip() the '\n'
                    response = response.decode().strip() #strip() the '\n'
                else:               # didnt read the whole response
                    response="ER: Timeout in PLLsend_serial "
                    if self.debug_mode:
                        self.delta_time = time.time() - self.start_time
                        print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+
                              "PLLsend_and_read_all(instr) response = "+response)
                    #s.close() #everything succesful, close
            except serial.SerialTimeoutException as msg:
                response = "ER: Timeout in PLLsend_serial - {}".format(msg)
            print(response)
        except serial.SerialException as msg:
            response ="ER: could not open port {}: {}".format(serial_port, msg)
            if self.debug_mode:
                self.delta_time = time.time() - self.start_time
                print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"PLLsend_and_read_all(instr) response = "+response)
        time.sleep(2)
        #read the buffer fully):
        while(s.in_waiting >0):
            if self.debug_mode:
                self.delta_time = time.time() - self.start_time
                print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"PLLsend_and_read_all(instr)...bytes waiting to be read {}".format(s.in_waiting))
            try:
             #bufwrote += s.write((instr+'\n').encode()) # PLL/Teensy needs the '\n' to end the read
                binresp = s.read_until(b'\n') # read until newline or timeout
                if binresp[-1:] ==b"\n": # if we read the entire response:
                    response += binresp.decode() #strip() the '\n'
                    #s.close() #everything succesful, close
                else:
                    if self.debug_mode:
                        self.delta_time = time.time() - self.start_time
                        print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+'didnt read entire buffer\n')
            except serial.SerialTimeoutException as msg:
                err = "ER: Timeout in PLLread - {}".format(msg)
                if self.debug_mode:
                    self.delta_time = time.time() - self.start_time
                    print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+'PLLsend_and_read_all(instr)'+err)
        return(response)


    ######################################################################
    # This is the instruction handler, that takes input instructions,
    # in the form of a string, and implements them.  It allow for multiple
    # commands separated by ";" so that you can send several commands at
    # once and the Red Pitaya will parse them and handle them separately
    # in order. Note my terminology "instruction" = "command" + "data" + ";"
    def handle_instr(self,instr):
        # fp = open('log.txt','a')
        # fp.write("\ninstr upon entering handle_inst:  \n")
        # fp.write(instr+'\n')
        cmdList ={  # list of acceptable two-character commands and their action functions
            "FC": self.setFrequencyCarrier,  # Frequency Carrier (sets the PLL carrier frequency in manual mode)  (TEENSYPLL/SERIAL)
            "FT": self.progFrequencyTable,  # Frequency Table programs the tableable frequencies to step through.  (TEENSYPLL/SERIAL)
            "SC": self.ScanCarrier,  # not actually implemented at the current moment. TT starts the scanning
            "TT": self.TransitionTable_mode,  # Transition to Table mode.  After the table prog, the mode is set to triggered table (TEENSYPLL/SERIAL)
            "TM": self.TransitionManual_mode,  # Transition to Manual mode.  (TEENSYPLL/SERIAL)
            "FM": self.setFrequencyMod,  # Freq. MOD. (sets the modulation frequency) (REDPITAYA)
            "AM": self.setAmpMod,  # Freq. MOD. (sets the modulation frequency) (REDPITAYA)
            "PM": self.setPhaseMod,  # Phase Mod. (sets the phase of the modulation/ demodulation) (REDPITAYA)
            ###########################################################################
            # New functions:
            "MD": self.setModDepth, # sets beta, the modulation depth
            "SA": self.setSineAmpMod, # adjusts amplitude of the sine quadrature
            "CA": self.setCosineAmpMod, # adjusts the amplitude of the cosine quadrature
            "SP": self.setSinePhase, # adjusts the phase offset of the sine quadrature
            "ST": self.retrigger, # restart/resync and retrigger the I and Q outputs
            ###########################################################################
            "Q?": self.query, # Query:returns the variable status. 
        }

        if instr[-1] != ';' and instr[-1] != '\r':
            # fp.write('\n\tINSIDE IF STATEMENT instr (in handle_instr): '+instr[-10:]+'\n')
            # fp.write('\n\tINSIDE IF STATEMENT buff before (in handle_instr): '+self.buff[-10:]+'\n')
            self.buff += instr.strip('\n')
            # fp.write('\n\tINSIDE IF STATEMENT buff after (in handle_instr): '+self.buff[-10:]+'\n')
            return "PR WARNING: partial read!"
        
        # fp.write('\n\tOUTSIDE IF STATEMENT: '+instr[-5:]+'\n')
        if self.buff != '':
            instr =  self.buff+instr.strip('\n') 
            # fp.write('\tstitched together instr: '+ instr[:20] + '...'+ instr[-20:]+'\n')
        # fp.write('\tOUTSIDE IF STATEMENT (after instr update): '+instr[-10:]+'\n')
        self.buff = ''

        instrList = instr.split(';')  #split off the separate commands
        if instrList[-1] == '': # there is a Null string at the end, should be dealt with earlier
            instrList.pop(-1)   # but we just kludge it here.
        returnstr=""
        if self.debug_mode:
            self.delta_time = time.time() - self.start_time
            print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+
                  "before command implementation: "+(instrList[-1][:10]).replace('\n','[EOL]'))
        for inst in instrList:   # call the function associated with the two-character cmd.
            if self.debug_mode:
                self.delta_time = time.time() - self.start_time
                print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+
                      "handle_instr()/Teensy returnstr before command implementation: ",returnstr.replace('\n','[EOL]'))
            returnstr=returnstr+cmdList.get(inst[0:2],self.default_resp)(inst)+";"
            if self.debug_mode:
                self.delta_time = time.time() - self.start_time
                print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+
                      "handle_instr()/Teensy returnstr after command implementation: ",returnstr.replace('\n','[EOL]'))
        returnstr += '\r'
        # fp.write('RETURN string:\n')
        # fp.write(returnstr+'\n')
        # fp.close()
        return returnstr

    def setModDepth(self,instr):
        print("setModDepth: "+instr)
        self.set_mod_depth(float(instr[3:]))
        response = "OK:"+str(self.beta2)
        return response
    
    def setSineAmpMod(self,instr):
        print("setSineAmpMod: "+instr)
        is_safe_sin_amp = (self.IQ_OFFSET_sin - float(instr[3:])*self.amp_mod >= 0) & (self.IQ_OFFSET_sin + float(instr[3:])*self.amp_mod <= 1) 
        if True:
            self.set_sin_scale(float(instr[3:]))
            response = "OK:"+str(self.sin_scale)
        else:
            response = "ERROR: sine amplitude out of bounds. Must be between 0 and 1."
        return response

    def setCosineAmpMod(self,instr):
        print("setCosineAmpMod: "+instr)
        is_safe_cos_amp = (self.IQ_OFFSET_cos - float(instr[3:])*self.amp_mod >= 0) & (self.IQ_OFFSET_cos + float(instr[3:])*self.amp_mod <= 1)
        if True:
            self.set_cos_scale(float(instr[3:]))
            response = "OK:"+str(self.cos_scale)
        else:
            response = "ERROR: cosine amplitude out of bounds. Must be between 0 and 1."
        return response
    
    def setSinePhase(self,instr):
        print("setSinePhase: "+instr)
        self.set_sin_phase(float(instr[3:]))
        response = "OK:"+str(self.sin_phase)
        return response
    
    def retrigger(self,instr):
        print("retrigger: " + instr)
        self.start_and_trigger()
        response = "OK: retriggered"
        return response
    
    # not used at the moment
    def ScanCarrier(self,instr):
        return self.PLLsend_serial(instr)
    # send the instr to     the PLL/Teensy    
    def setFrequencyCarrier(self,instr):
        print("FrequencyCarrier: "+instr)
        return self.PLLsend_serial(instr)
    # send the instr to the PLL/Teensy    
    def progFrequencyTable(self,instr):
        self.delta_time = time.time() - self.start_time
        print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+
              "progFrequencyTable: length=",len(instr), " instr ="+instr[:20]+"..."+instr[-20:])
        if instr[0:1] == 'PR':
            return 'WARNING: partial read in handle_instr'
        else:
            return self.PLLsend_serial(instr)
        #Comment out the follwoing for real operations. This code is for debugging
        # we write the programmed instructions to a file.
        # programmed_table = self.PLLsend_and_read_all(instr)
        # with open("FTcommandlog.txt", "w") as file:
        #     file.write(instr[3:] +'\n'+programmed_table+'\n')
        #     file.close()
        # return programmed_table[:8]
        # uncomment out the following to run in normal mode.
        

    # send the transition to table mode instr to the PLL/Teensy    
    def TransitionTable_mode(self,instr):
        print("TCPDH_device_class_wrap.py: "+"TransitionTable_mode: "+instr)
        #resp = self.PLLsend_and_read_all(instr)
        #with open("FTcommandlog.txt", "a") as file:
        #    file.write(resp+'\n')
        #    file.close()
        if self.debug_mode:
            self.delta_time = time.time() - self.start_time
            print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)
                  +"before TT's PLLsend_serial \n")
        resp = self.PLLsend_serial(instr)
        if self.debug_mode:
            self.delta_time = time.time() - self.start_time 
            print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)
                  +"TT response = "+resp[:8])
        return resp+"::"+instr+'\n'
    # send the instr to the PLL/Teensy   

    def TransitionManual_mode(self,instr):
        self.delta_time = time.time() - self.start_time
        print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"TransitionManual_mode: "+instr)
        resp = self.PLLsend_serial(instr)
        return resp
    # Set the modulation amplitude on the RedPitaya
    # This is not implemented in the RedPitaya as of now
    def setAmpMod(self,instr):
        print("setAmp_Mod: "+instr)
        is_safe_sin_amp = (self.IQ_OFFSET_sin - self.sin_scale*float(instr[3:]) >= 0) & (self.IQ_OFFSET_sin + self.sin_scale*float(instr[3:]) <= 1) 
        is_safe_cos_amp = (self.IQ_OFFSET_cos - self.cos_scale*float(instr[3:]) >= 0) & (self.IQ_OFFSET_cos + self.cos_scale*float(instr[3:]) <= 1)
        if True:
            self.set_amp_mod(float(instr[3:]))
            response = "OK:"+str(self.amp_mod)
        else:
            response = "ERROR: amplitude out of bounds. I/Q waveforms must be between 0 and 1 V."
        return response
    # Set the modulation frequency on the RedPitasya
    def setFrequencyMod(self,instr):
        print("setFrequencyMod: "+instr)
        print(int(instr[3:]))
        self.set_freq_mod(int(instr[3:]))
        response = "OK:"+str(self.freq_mod)
        return response
    # Set the modulation phase
    def setPhaseMod(self,instr):
        print("setPhaseMod: "+instr)
        self.set_ref_phase(int(instr[3:]))
        response = "OK:"+instr[0:2]
        return response
    #answer query
    def query(self,instr):
        if self.debug_mode:
            self.delta_time = time.time() - self.start_time
            print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"query: "+instr)
        return self.get_query()
    # Default: unknown command
    def default_resp(self,instr):
        self.delta_time = time.time() - self.start_time
        print("TCPDH_device_class_wrap.py: "+'{} : '.format(self.delta_time)+"Unknown command: "+instr[0:2]+'\n')
        response = "ER: unknown command: "+instr[0:7] #don't report back all the data
        return response

##############################################################
# These are the three actual device classes that implement 
# RP_TCPDH_device(): the full device control including RedPitaya and Teensy
# RP_TCPDH_device_PLL_Dummy(): the device control including RedPitaya and fake Teensy
# TCPDH_device_Dummy(): the dummy device with fake RedPitaya and fake Teensy

class TCPDH_device_Dummy(TCPDH_device):
    def __init__(self, amp_mod_in = 0.2,freq_mod_in = 3e6,ref_phase_in =20,serial_port_in = '/dev/ttyACM0'):
        TCPDH_device.__init__(self, amp_mod_in = amp_mod_in,freq_mod_in = freq_mod_in,ref_phase_in =ref_phase_in,serial_port_in = serial_port_in)
        self.PLLTeensy_device = PLLTeensy_dummy(self.serial_port) # This is the Teensy
    
    def startup_banner(self,serial_port):
        print("----------------------------------------------------------------")
        print("--- TCPDH_controller started in Dummy mode: ")
        print("-------     both Red Pitaya and PLLTeensey are simulated")
        print('-------     Serial port: (although irrelevant) {0}'.format(serial_port))
        print("---------------------------------------------------------------")

class TCPDH_device_RP_Dummy(TCPDH_device):
    def __init__(self, amp_mod_in = 0.2,freq_mod_in = 3e6,ref_phase_in =20,serial_port_in = '/dev/ttyACM0'):
        TCPDH_device.__init__(self, amp_mod_in =amp_mod_in,freq_mod_in = freq_mod_in,ref_phase_in =ref_phase_in,serial_port_in = serial_port_in)
        self.PLLsend_serial('Q?')#test serial port to kick error if it doesn't work
        
    def startup_banner(self,serial_port):
        print("---------------------------------------------------------------")
        print("------- TCPDH_controller started in Dummy mode: ")
        print("-------     Red Pitaya is simulated and PLLTeensey is real")
        print('-------     Serial port: {0}'.format(serial_port))        
        print("---------------------------------------------------------------")
        return

    def open_serial(self):    
        return serial.Serial(self.serial_port)

class RP_TCPDH_device_PLL_Dummy(TCPDH_device):
    def __init__(self,start_time,amp_mod_in = 0.2,freq_mod_in = 3e6,ref_phase_in =20,serial_port_in = '/dev/ttyACM0'):
        from redpitaya.overlay.mercury import mercury as overlay
        TCPDH_device.__init__(self,start_time,amp_mod_in = amp_mod_in,freq_mod_in = freq_mod_in,ref_phase_in =ref_phase_in,serial_port_in = serial_port_in)
        self.PLLTeensy_device = PLLTeensy_dummy(self.serial_port) # This is the Teensy
            
        # #Set up the RedPitaya FPGA for use:
        self.fpga = overlay()
        self.mgmt = self.fpga.mgmt()
        self.mgmt.gpio_mode = 0xffff
        self.lg = self.fpga.lg()

        # set up the generator boards to generate the modulation 
        # quadrature signals. Note that once its running, the
        # waveforms can be set on the fly and it will modify the
        # outputs.
        self.gen0 = self.fpga.gen(0)
        self.gen1 = self.fpga.gen(1)
        #load the IQ modulation signals
        self.gen0.amplitude = 1 #overall amplitude should be fixed at 1.
        self.gen0.offset    = 0. #overall offset should be fixed at 0
        self.gen0.waveform  =  self.Sin_Quad()
        self.gen1.amplitude = 1 #overall amplitude should be fixed at 1
        self.gen1.offset    = 0. #overall offset should be fixed at 0
        self.gen1.waveform  = self.Cos_Quad()
        #et the frequency to the output
        # NOTE:To get correct results, waveform must be loaded before the frequency is set.
        self.gen0.mode = 'PERIODIC'
        self.gen0.frequency = self.freq_mod
        self.gen1.mode = 'PERIODIC'
        self.gen1.frequency = self.freq_mod
    
        # set up the digital phase reference for the 
        # demodulation. currently supports 10 degree steps
        self.lg.waveform =self.refwaveform
        self.lg.burst_data_repetitions = 1
        self.lg.burst_data_length      = self.ref_data_length
        self.lg.burst_period_length    = self.ref_data_length
        self.lg.burst_period_number    = 0
        self.lg.enable   = 0x0080  # all pins have outputs enabled (for both output values 0/1)
        self.lg.mask     = 0x0000  # all bits come from ASG, none are constants
        self.lg.value    = 0x0000  # the constant pin values are irrelevant since they are not used
        
        # sync the gen1 and lg sources to gen0 and start and trigger them
        self.gen1.sync_src = self.fpga.sync_src["gen0"]
        self.gen1.phase = 0
        self.lg.sync_src = self.fpga.sync_src["gen0"]

        self.start_and_trigger()

    def start_and_trigger(self):
        self.gen0.start()
        self.gen0.enable = True
        self.lg.reset()
        self.lg.start()
        self.gen0.trigger()
        self.gen1.start()
        self.gen1.enable = True
        self.gen1.trigger()
   
    def startup_banner(self,serial_port):
        print("---------------------------------------------------------------")
        print("------- TCPDH_controller started in Dummy mode: ")
        print("-------     Red Pitaya server is real, but PLLTeensey is simulated")
        print('-------     Serial port: (although irrelevant) {0}'.format(serial_port))        
        print("---------------------------------------------------------------")
        return
    
    def set_amp_mod(self,inputamp):
        self.amp_mod =inputamp
        self.gen0.waveform  =  self.Sin_Quad()
        self.gen1.waveform  = self.Cos_Quad()
    
    def set_mod_depth(self,input_beta2):
        self.beta2 = input_beta2
        self.gen0.waveform  =  self.Sin_Quad()
        self.gen1.waveform  = self.Cos_Quad()

    def set_sin_scale(self,input_sin_scale):
        self.sin_scale = input_sin_scale
        self.gen0.waveform  =  self.Sin_Quad()
        self.gen1.waveform  = self.Cos_Quad()
    
    def set_cos_scale(self,input_cos_scale):
        self.cos_scale = input_cos_scale
        self.gen0.waveform  =  self.Sin_Quad()
        self.gen1.waveform  = self.Cos_Quad()
    
    def set_sin_phase(self,input_sin_phase):
        self.sin_phase = input_sin_phase
        self.gen0.waveform  =  self.Sin_Quad()
        self.gen1.waveform  = self.Cos_Quad()

    def set_freq_mod(self,fin):
        i=0 #find the closest commensurate analog frequency the requested input frequency
        while( (self.ALLOWED_FMOD[i+1]+self.ALLOWED_FMOD[i])< 2*(fin) and i+1< len(self.ALLOWED_FMOD)-1):
            i+=1
        self.freq_mod= self.ALLOWED_FMOD[i]
        self.ref_data_length = int(self.FM_MAX/self.freq_mod)
        delay = int(self.ref_phase * self.ref_data_length/360)
        self.ref_phase = int(360*delay/self.ref_data_length)
        #define a 50% duty cycle pulse with ref_data_length to phase match the analog signals.
        self.refwaveform = [0x0080 if i<self.ref_data_length/2 else 0 for i in range(0,self.ref_data_length)]
        self.refwaveform = self.refwaveform[delay:]+self.refwaveform[ :delay]
        self.gen0.frequency = self.freq_mod
        self.gen1.frequency = self.freq_mod
        self.lg.waveform =self.refwaveform   
        self.lg.burst_data_length      = self.ref_data_length
        self.lg.burst_period_length    = self.ref_data_length
        self.lg.burst_period_number    = 0
        self.lg.sync_src = self.fpga.sync_src["gen0"]
        self.gen1.sync_src = self.fpga.sync_src["gen0"]

        self.start_and_trigger() 

    def set_ref_phase(self,inputphase):
        delay = int(inputphase * self.ref_data_length/360)
        self.ref_phase = int(360*delay/self.ref_data_length)
        #define a 50% duty cycle pulse with ref_data_length to phase match the analog signals.
        self.refwaveform = [0x0080 if i<self.ref_data_length/2 else 0 for i in range(0,self.ref_data_length)]
        self.refwaveform = self.refwaveform[delay:]+self.refwaveform[ :delay]
        self.lg.waveform =self.refwaveform   
        self.lg.burst_data_length      = self.ref_data_length
        self.lg.burst_period_length    = self.ref_data_length
        self.lg.burst_period_number    = 0
        self.lg.sync_src = self.fpga.sync_src["gen0"]
        self.gen1.sync_src = self.fpga.sync_src["gen0"]

        self.start_and_trigger()       
 
    def __del__(self):
        print('TCPDH_device_class_wrap.py: '+"closing down the RP signal Generators")
        self.gen0.enable = False
        self.gen1.enable = False

class RP_TCPDH_device(RP_TCPDH_device_PLL_Dummy):
    def __init__(self,start_time,amp_mod_in = 0.2,freq_mod_in = 3e6,ref_phase_in =20,serial_port_in = '/dev/ttyACM0'):
        from redpitaya.overlay.mercury import mercury as overlay
        super().__init__(start_time)#self,amp_mod_in = amp_mod_in,freq_mod_in = freq_mod_in,ref_phase_in = ref_phase_in,serial_port_in=serial_port_in)
        # RP_TCPDH_device_PLL_Dummy.__init__(self,start_time,amp_mod_in = amp_mod_in,freq_mod_in = freq_mod_in,ref_phase_in = ref_phase_in,serial_port_in=serial_port_in)
        self.PLLsend_serial('Q?')

    def startup_banner(self,serial_port):
        print("-------------------------------------------------------")
        print("------- TCPDH_controller started: ")
        print("-------     Red Pitaya and PLLTeensy are actual devices")       
        print('-------     Serial port: {0}'.format(serial_port))        
        print("---------------------------------------------------------------")

    def open_serial(self): 
        return serial.Serial(self.serial_port)
