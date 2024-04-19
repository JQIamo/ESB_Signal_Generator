/***********************************************************************************
 * This is the controller code for the PLL frequency synthesizer
 * that is used to generate the carrier frequency for the fiber
 * modulator that puts the offset and sidbands on the reference 
 * laser used in the PDH lock.  Modes:
 *       - manual mode, freqCarrier is set immediately upon call of 
 *         the command FC <newCarrierFrequency>
 *       - Table mode (or buffered mode) which stores a table of (rampfreqs)
 *         and upon each hardware trigger (from a pseudoclock eg. pulseblaster)
 *         updates the frequency to the new value, ramping over numloops
 *         for each ramp.
 * 
 * It is designed to receives instructions from the RedPitaya (RP) via serial, where 
 * the instructions consist of commands plus data, in the form of 
 *        instr = cmd <data>
 * namely a two-letter command followed by a single space, followed by the "data"
 * associated with the instruction.  The commands that the code recognizes are
 *    Q? - query the current setting of the frequency currentFInt
 *    SC - currently unused
 *    FC - set the current frequency to <data>
 *    FT - program the table: 
 *                write the (rampfreqs) array to memory.
 *    TT - transition to table mode, sets up the FrequencyChange() to be interrupt
 *         driven by the hardware triggerIn input (coming from the pseudoclcok. On each 
 *         trigger, it steps through and updates the frequency to the nextFInt, then
 *         it sets nextFInt to the next value in the table, based on the data sent by the 
 *         previous FT command).
 *    TM - transition to manual mode, turns off the triggering to FrequencyChange()
 * ************************************************************************************/
#define BUFFSIZE 20
#define MAXTABLESIZE 2197150 // max size of (startfreq,deltafreq,numloops,scanUP) arrays
#include <Arduino.h>
#include <ADF4351TTCTestSLTF.h>  //Import the necessary library for ADF4351 control

#define SWVERSION "1.2"
//#define DUMMY  // if DUMMY is defined, none of the PLL ADF4351 commands are called.

#define PIN_SS 10  ///< SPI minion select pin for ADF4351
#define PIN_SEN 9  ///< SPI minion select pin for HMC1044

/************************************
 * globals used for parsing strings into 
 * commands and data:  instruction = command: <data>
 * **********************************/
EXTMEM char instr[MAXTABLESIZE];// This holds the instruction table during parsing
bool parseError = false;  // was there an error parsing the instr string from RP
String errorString = "";  // holds the error message to return -> RedPitaya->LabScript
String cmdString =""; // temporarily holds the command from labscript
String dataString = "";//holds the data associated with each command

/*********************************************
 * globals used for the PLL settings
 * *******************************************/
int triggerIn = 4;  // input pin to trigger the freq table updates
const int ledPin = 13;
const int trigPin = 6;// output trigger used for various debug diagnostics to trigger scope

/*****************************************************************
* define an enum  type so that you can switch the command easily
* instantiate a global variable that will hold the cmd.
*****************************************************************/
enum cmd_type{ SC,FC,FT, TT,TM,QU, NO_CMD};
cmd_type cmd;// global instantiation of the command enum

/************************************************************************************
// It is not clear that the volatile memory is needed, it depends on the compiler
// optimization. But these variables are used in an interupt triggered code, and in 
// principle should be volatile.
*************************************************************************************/
volatile unsigned int freqIndex = 0;  // The index of the rampfreqs table
volatile unsigned long nextFInt; // next frequency, precalculated to speed up updates
volatile EXTMEM unsigned long rampfreqs[MAXTABLESIZE];  // the table of ramp freqs.
unsigned long currentFInt = 1000000000UL;  // set the startup frequency to 1GHz
unsigned int total_scan_steps; // not currently used, but could be useful for future.

#ifndef DUMMY  // If we aren't in test mode, instantiate the PLL device 
ADF4351TTCTestSLTF  vfo(PIN_SS, PIN_SEN, SPI_MODE0, 20000000 , MSBFIRST) ;
#else
#endif

void FrequencyChange();

void setup(){
  pinMode(trigPin, OUTPUT);
  pinMode(ledPin, OUTPUT);
  pinMode(triggerIn,INPUT);
  digitalWrite(ledPin, HIGH);
  //digitalWrite(ledPin, HIGH);  // useful diagnostic
  Serial.begin(9600) ;
  while(!Serial&&millis()<5000);
  //Serial.print("Serial Active\r\n") ;
  //Serial.println(SWVERSION) ;  // diagnostics
  Wire.begin();

#ifndef DUMMY
  /*! Setup the chip 
     pwrlevel controls the power output of the ADF4351, which doesn't affect the final output of ADL5375, since 
     ADL5375 will compensate the change in its input power.
     (RD2refdouble,RD1Rdiv2) are defaults, they will need to be changed when we want to boost up the lock speed 
     of the PLL in the future
     (ClkDiv,BandSelClock,RCounter,ChanStep)control the lock parameters,the appropriate set of parameters will be 
     automatically selected when setf funciton is called
     ChanStep determines the step resolution (it is suggested not to make this number unnecessarily small since 
     it affect the noise performance)       */
  vfo.pwrlevel = 3; ///< sets to +5 dBm output (0=-4dBm,1=-1dBm,2=2dBm,3=5dBm)
  vfo.RD2refdouble = 0 ; ///< ref doubler off
  vfo.RD1Rdiv2 = 0 ;   ///< ref divider off
  vfo.ClkDiv = 150 ;
  vfo.BandSelClock = 200 ;
  vfo.RCounter = 1 ;  ///< R counter to 1 (no division)
  vfo.ChanStep = 10000 ;  ///< set to 10 kHz steps, it determines the MOD value used. When ChanStep is 
                          // too small such that MOD is out of range, than error message should occur. 
 
 //    sets the reference frequency to 25 Mhz, since we are using a 25 MHz oscillator as an onboard reference, 
 //     if an external frequenc reference is used, the ref freg needs to be updated
  delay(1000);
  if ( vfo.setrf(25000000UL) ==  0 )
    Serial.println("ref freq set to 25 Mhz") ;
    else
      Serial.println("ER: ref freq set error") ;
        // initialize the chiP
   vfo.init() ;

  vfo.enable() ;//enable frequency output
  vfo.setf(currentFInt);  
#else
#endif
attachInterrupt(triggerIn, FrequencyChange, RISING);//in case we want to use interrupt funciton to                                                        //update the frequency instead of serial input.
interrupts();
}

// subroutine used to get some visual input that the Teensy is doing something. 
// void blink(int btime, int bnum){
//     for(int i =0;i<bnum; i++ ){
//       digitalWrite(ledPin, LOW);
//       delay(btime*10);
//       digitalWrite(ledPin, HIGH);
//       delay(btime*50);
//     }
// }

// This is a very kludgy way to deal with the string<-->unsigned long conversion. 
// Using unions would probably be better in general (and faster for passing data 
// over serial from the RedPitay.) But for now we pass the cmd and rampfreqs as char arrays
// It is perhaps dangerous that we distinguish the homemeade programs from the built-in
// commands  StrtoUL vs strtoul.
unsigned long StrtoUL(String instr){
  char tmpBuff[21] ;
  instr.toCharArray(tmpBuff,instr.length()+1);
  return(strtoul(tmpBuff,NULL,10));
}      
String ULtoStr(unsigned long inUL){
  char tmpBuff[21];
  sprintf(tmpBuff, "%lu",inUL);
  return(tmpBuff);
}

// // a diagonistic printing function for debugging
// void diagnost(){
//   // Serial.print(ULtoStr(startfreqs[rampIndex]));Serial.print(',');
//   // Serial.print(ULtoStr(deltafreqs[rampIndex]));Serial.print(',');
//   // Serial.print(numloops[rampIndex]);Serial.print(',');
//   // Serial.print(scanUP[rampIndex]);Serial.print(',');
//   // Serial.print(iloop);Serial.print(',');
//   // Serial.print(rampIndex);Serial.print(',');
//   // Serial.print(ULtoStr(nextFInt));Serial.print(',');
//   Serial.print(ULtoStr(currentFInt));Serial.println(' ');
// }

// function to change the output frequency and update the next 
// frequency, upon hardware trigger from the pseudoclock. Since it is an 
// interrupt function, it cannot take inputs or return anything. 
// And the variables it changes/sets should be 'volatile'
void FrequencyChange(){
  #ifndef DUMMY
// First things first, set the current frequency
  // vfo.setf(nextFInt);   // this is the slow frequency update, we use the fast update
  vfo.FastScanSetF(nextFInt);
  //digitalWrite(trigPin, HIGH);//used to trigger the spectrum analyser when debugging
      // delayMicroseconds(1);
  //digitalWrite(trigPin, LOW);
  #else
  #endif
  freqIndex += 1;
  nextFInt = rampfreqs[freqIndex];
}

/* *******************************************************************
 *  split the instruction string of form "cmdString dataString" 
 *  set the enum cmd to the correct cmd, to be used by the switch call
 *  inside doInstr.  */
void splitInstr(String inputString){
  if(inputString.length() >1){
    cmdString=inputString.substring(0,2);
    if(cmdString == "SC"){cmd =  SC;}
    else if(cmdString == "FC"){ cmd =  FC;}
    else if(cmdString == "FT"){ cmd =  FT;}
    else if(cmdString == "TT"){ cmd =  TT;}
    else if(cmdString == "TM"){ cmd =  TM;}
    else if(cmdString == "Q?"){ cmd =  QU;}
    else cmd=NO_CMD;
  } else { 
    parseError = true; 
    errorString="ER: split command parsing error: at least two chars needed";
  }
  if(inputString.length()>3 && !parseError){
    dataString=inputString.substring(3);  // data exists, store it in dataString. (ignoring first 3 chars)
  }
}

/* **********************************************************************
 * Splits the ','-separated data string. Note we use strtok pointer to avoid
 * recopying the entire data string.           */
void FTset(){
  char *ptr;  // pointer to the current comma separated char[]
  ptr = strtok(instr+3,","); // get the first substring, skipping first 3 chars.
  unsigned long i = 0;
  while(ptr != NULL) {
    rampfreqs[i] = strtoul(ptr,NULL,10); // int(*(ptr+3));
    ptr = strtok(NULL,",");
    i++;
  }
  Serial.println("FT successfuly completed");
  total_scan_steps = i;
}

bool doInstr(cmd_type cmdin, String data){
  parseError =false;
  //delay(10000);// used for testing timeouts
  switch(cmdin){
    case SC:{    // -------parse the SC command:
      break;
    }
    case FC:{   // ----------- parse the FC command: set the carrier frequency to a value.
      currentFInt= StrtoUL(data);
      Serial.print("FC: "); Serial.println(ULtoStr(currentFInt));
    #ifndef DUMMY
      // digitalWrite(trigPin, HIGH);//used to trigger the spectrum analyser when debugging
      // // delayMicroseconds(1);
      // digitalWrite(trigPin, LOW);
      vfo.setf(currentFInt);
    #else
    #endif
      break;
    }
    case FT:{   // ----------- parse the Table program command:
      FTset();
      break;
    }
    case TT:{   // ----------- parse the transition to table mode command:
      // vfo.setf(nextFInt);
      freqIndex = 0;
      nextFInt = rampfreqs[freqIndex];
      Serial.println("TT ");
      delay(50); // This delay is necessary to allow time for the serial command
      break;
      }
    case TM:{   // ----------- parse the transition to manual command:
      Serial.println("TM transitioned to manual"); 
      currentFInt = rampfreqs[freqIndex-1];
      freqIndex = 0;
      break;
      }
    case QU:{   // ----------- parse the QUERY command:
      Serial.print("FC "); 
      Serial.println(ULtoStr(currentFInt));
      break;
      }
    default :{
      parseError = true;
      Serial.println("ER: command not recognized");
      break;
      }
  }  return(parseError );
}

void loop()
{
  cmdString ="";
  dataString = "";
  parseError=false;
  errorString="";
  int bytesread = 0;
 
  while(Serial.available()>0){
    bytesread = Serial.readBytesUntil('\n',(char*)instr, MAXTABLESIZE);
  //  Serial.println(bytesread);
  }
  if(bytesread>0){
    splitInstr(instr);
    if(!parseError){
      doInstr(cmd,dataString);
    } 
    if(parseError) {
      Serial.println(errorString);
    } 
  }
}