###################################################
#                                                 #
#     MeteoPI                                     #
#     by F.C. - sn3ik@hotmail.com                 #
#                                                 #
#     Thanks to Sint Wind PI & Tonino Tarsi       #
#                                                 #
###################################################

"""This module defines the base sensorssimulator ."""


import threading
import time
import config
import random
import datetime
import sqlite3
from TTLib import  *
import sys
import subprocess
import globalvars
import meteodata
import sensors.sensor_thread
import sensors.sensor_external 

class Sensor_Simulator(sensors.sensor_external.Sensor):
    
    def __init__(self,cfg ):
        sensors.sensor_external.Sensor.__init__(self,cfg )
        
    def Detect(self):
        return True,"","",""
    
    def GetData(self):
             
        seconds = datetime.datetime.now().second
        if ( seconds < 30 ):
            time.sleep(30-seconds)
        else:
            time.sleep(90-seconds)  
        globalvars.meteo_data.last_measure_time = datetime.datetime.now()
        globalvars.meteo_data.idx = globalvars.meteo_data.last_measure_time
        globalvars.meteo_data.status  = 0
        globalvars.meteo_data.delay = 0       
        globalvars.meteo_data.hum_in  = random.randrange(1,100)     
        globalvars.meteo_data.temp_in  = random.randrange(1,100)    
        globalvars.meteo_data.hum_out  = random.randrange(1,100)    
        globalvars.meteo_data.temp_out   =random.randrange(-5,38)  
        globalvars.meteo_data.abs_pressure = random.randrange(950,1030)
        globalvars.meteo_data.wind_ave     = random.randrange(1,50)
        globalvars.meteo_data.wind_gust    = random.randrange(50,100)
        globalvars.meteo_data.wind_dir     = random.randrange(1,360)
        globalvars.meteo_data.wind_dir_code = random.choice(['N','S','E','W','NW','NE','SW','SE'])
        globalvars.meteo_data.rain  = random.randrange(1,100)      
        globalvars.meteo_data.illuminance = random.randrange(1,100)
        globalvars.meteo_data.uv = random.randrange(1,100)
             
        sensors.sensor_external.Sensor.GetData(self)


if __name__ == '__main__':

   
    configfile = 'meteopi.cfg'
       
    cfg = config.config(configfile)
    
    ss = Sensor_Simulator(cfg)
    
    while ( 1 ) :
        ss.GetData()
        
        #print (logData("http://localhost/swpi_logger.php"))
        time.sleep(0.2)
    
    