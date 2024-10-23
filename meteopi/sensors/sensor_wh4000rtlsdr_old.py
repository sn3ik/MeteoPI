###################################################
#                                                 #
#     MeteoPI                                     #
#     by F.C. - sn3ik@hotmail.com                 #
#                                                 #
#     Thanks to Sint Wind PI & Tonino Tarsi       #
#                                                 #
###################################################

"""This module defines the WH4000_RTL-SDR sensor."""
from __future__ import print_function

import threading
import time
import config
import random
import datetime
import sqlite3
from TTLib import *
import TTLib
import sys
import subprocess
import globalvars
import meteodata
import sensors.sensor_thread
import sensors.sensor_external 
import RPi.GPIO as GPIO
import TTLib
import _thread
import os
import json
import socket
import json
import psutil

# You can run rtl_433 and this script on different machines,
# start rtl_433 with `-F syslog:YOURTARGETIP:1433`, and change
# to `UDP_IP = "0.0.0.0"` (listen to the whole network) below.
UDP_IP = "127.0.0.1"
UDP_PORT = 1433
#sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#sock.close()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


DEBUG = True

def log(message) :
    print (datetime.datetime.now().strftime("[%d/%m/%Y-%H:%M:%S] [WH4000RTLSDR_] -") , message)
    
def get_wind_dir_text(wind_dir):
    """Return an array to convert wind direction integer to a string."""
    wind_dir_degr = [0, 23, 45, 68, 90, 113, 135, 158, 180, 203, 225, 248, 270, 293, 315, 338]
    wind_dir_s = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW','N']
    wind_dir_index = 0
    while wind_dir_index < 16 and wind_dir_degr[wind_dir_index] < wind_dir: wind_dir_index += 1
    return wind_dir_s[wind_dir_index]

def get_datetime():
    try:
        #t = os.path.getmtime(filename)
        return datetime.datetime.now()#.strftime("[%Y/%m/%d-%H:%M:%S]")
    except:
        return None

def getrevision():
    # Extract board revision from cpuinfo file
    myrevision = "0000"
    try:
        f = open('/proc/cpuinfo','r')
        for line in f:
            if line[0:8]=='Revision':
                myrevision = line[11:-1]
        f.close()
    except:
        myrevision = "0000"
    
    return myrevision


class Sensor_WH4000RTLSDR(sensors.sensor_external.Sensor):
    
    def __init__(self,cfg ):
    
        ret = self.Detect()
        if ( not ret ):
            log("*************************************************************")
            log("*                                                           *")
            log("*   ERROR : No RTL-SDR compatible USB DVB-T dongle found!   *")
            log("*                METEOPI execution aborted.                 *")
            log("*                                                           *")
            log("*************************************************************")
            os.system("sudo ./killmeteopi.sh")
        else:
            log("RTL-SDR-compatible USB DVB-T dongle detected." )
            time.sleep(5)
            
            # Open a UDP socket
            # Bind the UDP socket to a listening address
            sock.bind((UDP_IP, UDP_PORT))
            log("Listening syslog on: %s : %s" % (UDP_IP,UDP_PORT) )
            
        threading.Thread.__init__(self)
        sensors.sensor_external.Sensor.__init__(self,cfg )
        self.cfg = cfg

        self.active = True
        self.start()
        
    def readfreq(self):
        if self.cfg.rtlsdr_frequency == 433:
            return '433920000'
        elif self.cfg.rtlsdr_frequency == 868:
            return '868200000'
        elif self.cfg.rtlsdr_frequency == 915:
            return '915000000'  
    
    def startRFListenig(self):
        freq = (self.readfreq())
        bdl = str(self.cfg.rtlsdr_bdl)
        ppm = str(self.cfg.rtlsdr_ppm)
        #cmd = "sudo /usr/local/bin/rtl_433 -f %s -R 78 -p %s > /dev/null" % (freq,ppm)
        cmd = "sudo /usr/local/bin/rtl_433 -f %s -R 78 -p %s -F syslog:%s:%s > /dev/null" % (freq,ppm,UDP_IP,UDP_PORT)
        os.system(cmd)
    
    def run(self):
        
        freq = (self.readfreq())
        bdl = str(self.cfg.rtlsdr_bdl)
        ppm = str(self.cfg.rtlsdr_ppm)
        myrevision = getrevision()
        if myrevision == "0002" or myrevision == "0003" :
            s = 1
        else:
            s = 2
        log("Starting rtl_433 on %s MHz" % (freq))
        cmd = "sudo /usr/local/bin/rtl_433 -f %s -R 78 -p %s -F syslog:%s:%s > /dev/null" % (freq,ppm,UDP_IP,UDP_PORT)
        #cmd = "/usr/local/bin/rtlsdr -q -r '/swpi/gfile001.data' -R 32 -l 0  > /dev/null" 
        os.system(cmd)
        #log("Something went wrong with RF ... restarting")
        
    def checkIfRtlRunning(self):
        processName = "rtl_433"
        for proc in psutil.process_iter():
                try:
                        # Check if process name contains the given name string.
                        if processName.lower() in proc.name().lower():
                                return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
        return False;


    def Detect(self):
        p = subprocess.Popen("/usr/local/bin/rtl_eeprom",shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
        x = str(stderr)
        #print(x)
        if  x.find('Found') != -1:
            return True
        else:
            return False


    def parse_syslog(self,line):
        line = line.decode("ascii") 
        if line.startswith("<"):
            # fields should be "<PRI>VER", timestamp, hostname, command, pid, mid, sdata, payload
            fields = line.split(None, 7)
            line = fields[-1]
        return line
    

    def ReadData(self):
        
        # Loop forever
        #while True:
            # Receive a message
            line, addr = sock.recvfrom(1024)

            try:
                # Parse the message format
                line = self.parse_syslog(line)
                # Decode the message as JSON
                data = json.loads(line)

                #
                # Change for your custom handling below, this is a simple example
                #
                label = data["model"]
                if "channel" in data:
                    label += ".CH" + str(data["channel"])
                elif "id" in data:
                    label += ".ID" + str(data["id"])
                    
                station_id = data["id"]

                if "battery_ok" in data:
                    if data["battery_ok"] == 0:
                        log(label + ' Battery empty!')

                if "temperature_C" in data:
                    temp = float(data["temperature_C"])
                else:
                    temp = 0

                if "humidity" in data:
                    hum = (data["humidity"])
                else:
                    hum = 0
                    
                if "wind_dir_deg" in data:
                    dire = float(data["wind_dir_deg"])
                    dir_code = get_wind_dir_text(dire)

                if "wind_avg_m_s" in data:
                    Wind_speed = float(data["wind_avg_m_s"])
                    Wind_speed = round((Wind_speed*self.cfg.windspeed_gain + self.cfg.windspeed_offset)*3.6,1)
                    
                if "wind_max_m_s" in data:
                    Gust_Speed  = float(data["wind_max_m_s"])
                    Gust_Speed  = round((Gust_Speed*self.cfg.windspeed_gain + self.cfg.windspeed_offset)*3.6,1)

                if "rain_mm" in data:
                    rain = data['rain_mm']
                    rain = (round(rain,2))
                    
                if "uvi" in data:
                    uv_index = (data['uvi'])
                    
                if "light_lux" in data:
                    watts_sqmeter = float(data['light_lux'])
                    
                log("New data received from station %s. Processing..." % station_id)
                    
                return station_id,temp,hum,Wind_speed,Gust_Speed,dir_code,dire,rain,uv_index,watts_sqmeter 
   
                # Ignore unknown message data and continue
            except KeyError:
                pass

            except ValueError:
                pass
        
      

    def GetData(self):

        # get first good data
        good_data = False
        while ( not good_data ):
            station_id,temp,hum,Wind_speed,Gust_Speed,dir_code,dire,rain, uv_index, watts_sqmeter =  self.ReadData()
            if ( station_id != "None" and station_id != "Time"):
                good_data = True
            else:
                log("Bad data received from WH4000_RTL-SDR")
                time.sleep(48)
        log("First data received from WH4000_RTL-SDR, station %s. Processing..." % station_id)
        last_data_time = get_datetime()       
        
        while 1:
            
            if self.checkIfRtlRunning():
                log('rtl_433 is running...')
            else:
                log('rtl_433 is not running, restart...')
                cmd = "meteopi restart"
                os.system(cmd)
            
            if ( station_id != "None" and station_id != "Time" ):
                globalvars.meteo_data.status = 0
                globalvars.meteo_data.last_measure_time = last_data_time
                globalvars.meteo_data.idx = globalvars.meteo_data.last_measure_time
                globalvars.meteo_data.hum_out = hum
                globalvars.meteo_data.temp_out = temp
                globalvars.meteo_data.wind_ave   = Wind_speed
                globalvars.meteo_data.wind_gust = Gust_Speed
                globalvars.meteo_data.wind_dir = dire #*22.5
                globalvars.meteo_data.wind_dir_code = dir_code
                globalvars.meteo_data.rain = rain
                globalvars.meteo_data.uv = uv_index
                globalvars.meteo_data.illuminance = watts_sqmeter
    
                sensors.sensor_external.Sensor.GetData(self)
            
            
            tosleep = 50-(datetime.datetime.now()-last_data_time).seconds
            if DEBUG: print ("Sleeping  ", tosleep)
            if (tosleep > 0 and tosleep < 50 ): 
                time.sleep(tosleep)
            else:
                time.sleep(50)
            
            new_last_data_time = get_datetime()
            while ( new_last_data_time == None or new_last_data_time == last_data_time):
                time.sleep(10)
                new_last_data_time = get_datetime()               
            
            last_data_time = new_last_data_time

            station_id,temp,hum,Wind_speed,Gust_Speed,dir_code,dire,rain, uv_index, watts_sqmeter =  self.ReadData()
            
            #if ( station_id == "Time"):
            #    log("Sleeping while waiting for weather data...")
            #    tosleep = 50-(datetime.datetime.now()-last_data_time).seconds
            #    if DEBUG: print ("Sleeping  ", tosleep)
            #    if (tosleep > 0 and tosleep < 50 ): 
            #        time.sleep(tosleep)
            #    else:
            #        time.sleep(50)
            
            #if ( station_id == "None"):
            #    log("Bad data received from WH4000_RTL-SDR")


if __name__ == '__main__':

    configfile = 'meteopi.cfg'
    cfg = config.config(configfile)
    globalvars.meteo_data = meteodata.MeteoData(cfg)
    ss = Sensor_WH4000RTLSDR
    
    while 1:
        ss.GetData()
