###################################################
#                                                 #
#     MeteoPI                                     #
#     by F.C. - sn3ik@hotmail.com                 #
#                                                 #
#     Thanks to Sint Wind PI & Tonino Tarsi       #
#                                                 #
###################################################

"""MeteoData class"""

import time
import sqlite3
import datetime
import TTLib
import config
import math
import os
import globalvars

def log(message) :
    print (datetime.datetime.now().strftime("[%d/%m/%Y-%H:%M:%S] [METEODATA____] -") , message)

def  cloud_base_altitude(temp,dew_point,station_altitude):
    if (temp == None or dew_point == None or station_altitude == None):
        return None
    delta = (((temp-dew_point)*1.8/4.5 ) * 1000 )
#    if ( delta < 10 ):
#        return -1
#    else:
    return ( delta + (station_altitude * 3.2808) ) / 3.2808

def dew_point(temp, hum):
    """Compute dew point, using formula from
    http://en.wikipedia.org/wiki/Dew_point.

    """
    if temp == None or hum == None:
        return None
    a = 17.27
    b = 237.7
    if (hum == 0):
        return None
    gamma = ((a * temp) / (b + temp)) + math.log(float(hum) / 100.0)
    return (b * gamma) / (a - gamma)

def wind_chill(temp, wind):
    """Compute wind chill, using formula from
    http://en.wikipedia.org/wiki/wind_chill

    """
    if temp == None or wind == None:
        return None
    #wind_kph = wind * 3.6
    wind_kph = wind
    if wind_kph <= 4.8 or temp > 10.0:
        return temp
    return min(13.12 + (temp * 0.6215) +
               (((0.3965 * temp) - 11.37) * (wind_kph ** 0.16)),
               temp)

def apparent_temp(temp, rh, wind):
    """Compute apparent temperature (real feel), using formula from
    http://www.bom.gov.au/info/thermal_stress/
    """
    if ( temp == None or rh == None or wind == None ):
        return None
    wind_ms = wind / 3.6
    if temp == None or rh == None or wind == None:
        return None
    vap_press = (float(rh) / 100.0) * 6.105 * math.exp(
        17.27 * temp / (237.7 + temp))
    return temp + (0.33 * vap_press) - (0.70 * wind_ms) - 4.00

class MeteoData(object):

    def __init__(self,cfg=None):

        self.cfg = cfg

        self.last_measure_time = None
        self.previous_measure_time = None

        self.wind_trend = None
        self.pressure_trend = None
        # Station data
        self.idx = None
        self.status = -9999
        self.wind_dir = None
        self.wind_ave = None
        self.wind_gust = None

        self.temp_out = None
        self.hum_out = None
        self.abs_pressure = None
        self.rel_pressure = None
        self.rain = None
        self.the_real_rain = None
        self.rain_rate = None
        self.rain_rate_24h = None
        self.rain_rate_1h= None
        #self.the_real_rain = None

        self.temp_in = None
        self.hum_in = None
        self.uv = None
        self.illuminance = None

        self.lux = None
        self.luxfull = None
        self.ir = None

        self.pm2 = None
        self.pm10 = None

        if ( cfg != None):
            self.rb_wind_dir = TTLib.RingBuffer(cfg.number_of_measure_for_wind_dir_average)
            self.rb_wind_trend = TTLib.RingBuffer(cfg.number_of_measure_for_wind_trend)

        #calculated values
        self.wind_dir_code = None
        self.wind_chill = None
        self.temp_apparent = None
        self.dew_point = None
        self.cloud_base_altitude = None
        self.previous_rain = None
        self.wind_dir_ave = None

        if ( not self.getLastTodayFromDB() ):

            self.ResetStatistic()

    def newday(self):
        if ( self.previous_measure_time == None ):
            self.previous_measure_time = self.last_measure_time
            return True
        elif (  self.last_measure_time != None and ( datetime.datetime.strftime(self.last_measure_time,'%m/%d/%Y') !=
            datetime.datetime.strftime(self.previous_measure_time,'%m/%d/%Y') ) ) :
            self.previous_rain = self.rain
            return True
        else:
            return False

#    def CalcMeanWindDir(self):
#        rb = TTLib.RingBuffer(self.cfg.number_of_measure_for_wind_dir_average)
#        while 1:
#            rb.append(self.wind_dir)
#            yield  rb.getMeanDir()

    def ResetStatistic(self):

            #statistics values
            self.winDayMin = None
            self.winDayMax = None

            self.winDayGustMin = None
            self.winDayGustMax = None

            self.TempInMin = None
            self.TempInMax = None

            self.TempOutMin = None
            self.TempOutMax = None

            self.UmInMin = None
            self.UmInMax = None

            self.UmOutMin = None
            self.UmOutMax = None

            self.PressureMin = None
            self.PressureMax = None

            self.previous_measure_time = None
            self.previous_rain = self.rain

    def CalcStatistics(self):

        while globalvars.bAnswering:
            #TTLib.log("DEBUG ... waiting for Calculating Meteo data and statistics")
            time.sleep(1)

        log("Calculating Meteo data and statistics")

        ############## Calucelated parameters
        #

        self.wind_chill = wind_chill(self.temp_out, self.wind_ave)
        self.temp_apparent = apparent_temp(self.temp_out, self.hum_out, self.wind_ave)
        self.dew_point = dew_point(self.temp_out, self.hum_out)
        self.cloud_base_altitude = cloud_base_altitude(self.temp_out,self.dew_point,self.cfg.location_altitude)


        if ( self.cfg.wind_speed_units == "knots"):
            self.wind_ave = self.wind_ave * 0.539956803456
            self.wind_gust = self.wind_gust * 0.539956803456

        self.rb_wind_trend.append(self.wind_ave)
        self.wind_trend = self.rb_wind_trend.getTrend()


        if ( self.cloud_base_altitude != None) :
            self.cloud_base_altitude = self.cloud_base_altitude * self.cfg.cloudbase_calib


        if ( self.abs_pressure != None and self.abs_pressure != 0.0):
            if ( self.cfg.location_altitude != 0 ):
                p0 = (self.abs_pressure*100) / pow( 1 - (0.225577000e-4*self.cfg.location_altitude ),5.25588 )
            else:
                p0 = self.abs_pressure*100
            self.rel_pressure = float(p0/100 )
            #print self.abs_pressure,self.rel_pressure


        if ( self.rain != None and self.previous_rain != None and self.previous_measure_time != None ):
            self.rain_rate = self.rain - self.previous_rain


        ###############################################

        if ( self.newday() ):
            self.ResetStatistic()
        else:
            if ( self.winDayMin is None or self.wind_ave < self.winDayMin ):
                self.winDayMin  = self.wind_ave
            if ( self.winDayMax is None or self.wind_ave > self.winDayMax ) :
                self.winDayMax  = self.wind_ave
            if ( self.winDayGustMin is None or self.wind_gust < self.winDayGustMin ) :
                self.winDayGustMin  = self.wind_gust
            if ( self.winDayGustMax is None or self.wind_gust > self.winDayGustMax ) :
                self.winDayGustMax  = self.wind_gust
            if ( self.TempOutMin is None or self.temp_out < self.TempOutMin ) :
                self.TempOutMin  = self.temp_out
            if ( self.TempOutMax is None or self.temp_out > self.TempOutMax ) :
                self.TempOutMax  = self.temp_out
            if ( self.TempInMin is None or self.temp_in < self.TempInMin ) :
                self.TempInMin  = self.temp_in
            if ( self.TempInMax is None or self.temp_in > self.TempInMax ) :
                self.TempInMax  = self.temp_in
            if ( self.UmInMin is None or self.hum_in < self.UmInMin ) :
                self.UmInMin  = self.hum_in
            if (  self.UmInMax is None or self.hum_in > self.UmInMax ) :
                self.UmInMax  = self.hum_in
            if ( self.UmOutMin is None or self.hum_out < self.UmOutMin ) :
                self.UmOutMin  = self.hum_out
            if ( self.UmOutMax is None or self.hum_out > self.UmOutMax ) :
                self.UmOutMax  = self.hum_out
            if ( self.PressureMin is None or  self.rel_pressure < self.PressureMin ) :
                self.PressureMin  = self.rel_pressure
            if ( self.PressureMax is None or self.rel_pressure > self.PressureMax ) :
                self.PressureMax  = self.rel_pressure

        self.rb_wind_dir.append(self.wind_dir)
        self.wind_dir_ave = self.rb_wind_dir.getMeanDir()
        self.previous_measure_time = self.last_measure_time

        #self.previous_rain = self.rain
        if (self.rain != None ):
            conn = sqlite3.connect('db/meteopi.s3db',200)
            dbCursor = conn.cursor()
            dbCursor.execute("SELECT * FROM METEO order by rowid desc limit 1")
            data = dbCursor.fetchall()
            if ( len(data) == 1 ):
                the_old_rain = (data[0][33])
                real_rain = (data[0][9])
        if (the_old_rain != None):
            if ( the_old_rain > self.rain):
                self.the_real_rain = real_rain + self.rain
            else:
                self.the_real_rain = real_rain + (self.rain - the_old_rain)

        # Rain 24h - rain 1h - pressure_trend
        if ( self.rain != None or self.rel_pressure != None):
            if (self.rain != None ):
                dbCursor.execute("SELECT * FROM METEO where datetime(TIMESTAMP_LOCAL) > datetime('now','-1 day','localtime') order by rowid asc limit 1")
                data = dbCursor.fetchall()
                if ( len(data) == 1):
                    therain = (data[0][9])
                    if (therain != None) :
                        self.rain_rate_24h = real_rain - therain

            dbCursor.execute("SELECT * FROM METEO where datetime(TIMESTAMP_LOCAL) > datetime('now','-1 hour','localtime') order by rowid asc limit 1")
            data = dbCursor.fetchall()
            if ( len(data) == 1):
                therain = (data[0][9])
                if (therain != None and self.rain != None ) :
                    self.rain_rate_1h = real_rain - therain
                thepress= (data[0][7])
                if ( thepress != None and self.rel_pressure != None):
                    self.pressure_trend = self.rel_pressure - thepress

            if conn:
                conn.close()

    def LogDataToDB(self):

            while globalvars.bAnswering:
                time.sleep(1)

            log("Logging data to Database")
            if ( self.last_measure_time == None ):
                return

            conn = sqlite3.connect('db/meteopi.s3db',200)
            dbCursor = conn.cursor()
            #dbCursor.execute("insert into METEO(TIMESTAMP_LOCAL,TIMESTAMP_IDX,WINDIR_CODE,WIND_DIR,WIND_AVE,WIND_GUST,TEMP,PRESSURE,HUM,RAIN,RAIN_RATE,TEMPINT,HUMINT,WIND_CHILL,TEMP_APPARENT,DEW_POINT,UV_INDEX,SOLAR_RAD,WIND_DAY_MIN,WIND_DAY_MAX) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (self.last_measure_time,self.last_measure_time,self.wind_dir_code,self.wind_dir,self.wind_ave,self.wind_gust,self.temp_out,self.abs_pressure,self.hum_out,self.rain,0,self.temp_in,self.hum_in,self.wind_chill,self.temp_apparent,self.dew_point,self.uv,self.illuminance,self.winDayMin,self.winDayMax))
            #print self.last_measure_time,self.last_measure_time,self.wind_dir_code,self.wind_dir,self.wind_ave,self.wind_gust,self.temp_out,self.abs_pressure,self.hum_out,self.the_real_rain,0,self.temp_in,self.hum_in,self.wind_chill,self.temp_apparent,self.dew_point,self.uv,self.illuminance,self.winDayMin,self.winDayMax,self.winDayGustMin,self.winDayGustMax,self.TempOutMin,self.TempOutMax,self.TempInMin,self.TempInMax,self.UmOutMin,self.UmOutMax,self.UmInMin,self.UmInMax,self.PressureMin,self.PressureMax,self.wind_dir_ave
            dbCursor.execute("insert into METEO(TIMESTAMP_LOCAL,TIMESTAMP_IDX,WINDIR_CODE,WIND_DIR,WIND_AVE,WIND_GUST,TEMP,PRESSURE,HUM,RAIN,RAIN_RATE,TEMPINT,HUMINT,WIND_CHILL,TEMP_APPARENT,DEW_POINT,UV_INDEX,SOLAR_RAD,WIND_DAY_MIN,WIND_DAY_MAX,WIND_DAY_GUST_MIN ,WIND_DAY_GUST_MAX ,TEMP_OUT_DAY_MIN ,TEMP_OUT_DAY_MAX,TEMP_IN_DAY_MIN ,TEMP_IN_DAY_MAX ,HUM_OUT_DAY_MIN ,HUM_OUT_DAY_MAX ,HUM_IN_DAY_MIN ,HUM_IN_DAY_MAX ,PRESSURE_DAY_MIN ,PRESSURE_DAY_MAX,WIND_DIR_AVE,RAIN_OLD,PM2,PM10 ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (self.last_measure_time,self.last_measure_time,self.wind_dir_code,self.wind_dir,self.wind_ave,self.wind_gust,self.temp_out,self.rel_pressure,self.hum_out,self.the_real_rain,self.rain_rate,self.temp_in,self.hum_in,self.wind_chill,self.temp_apparent,self.dew_point,self.uv,self.illuminance,self.winDayMin,self.winDayMax,self.winDayGustMin,self.winDayGustMax,self.TempOutMin,self.TempOutMax,self.TempInMin,self.TempInMax,self.UmOutMin,self.UmOutMax,self.UmInMin,self.UmInMax,self.PressureMin,self.PressureMax,self.wind_dir_ave,self.rain, self.pm2, self.pm10))
            conn.commit()
            conn.close()

            #usa il datbase interno
            if ( self.cfg.logdata_internal == False ):
                #print (self.cfg.logdata_internal)
                log("Delete old data to Database")
                conn_del = sqlite3.connect('db/meteopi.s3db',200)
                dbCursor_del = conn_del.cursor()
                dbCursor_del.execute("DELETE FROM METEO where datetime(TIMESTAMP_LOCAL) < datetime('now','-2 day','localtime')")
                conn_del.commit()
                conn_del.close()

            msg = ""
            msg = msg + "Processed data:"
            if self.wind_dir_code !=None :
                msg = msg +     "\n     Wind Dir: " + str(self.wind_dir_code)
            if self.wind_ave != None :
                msg = msg +     " - Wind Speed: " + str(self.wind_ave) + " km"
            if self.wind_gust != None :
                msg = msg +     " - Wind Gust: " + str(self.wind_gust) + " km"
            if self.winDayMin != None :
                msg = msg + " - Min: %d" % self.winDayMin + " km"
            if self.winDayMax != None :
                msg = msg + " - Max: %d" % self.winDayMax + " km"
            if self.temp_out != None :
                msg = msg +     "\n     Temp out: %.1f" % self.temp_out + " *"
            if self.temp_in  != None :
                msg = msg +     " - Temp in: %.1f" % self.temp_in + " *"
            if self.TempOutMin != None :
                msg = msg + " - Temp Min: %d" % self.TempOutMin + " *"
            if self.TempOutMax != None :
                msg = msg + " - Temp Max: %d" % self.TempOutMax + " *"
            if self.hum_out != None :
                msg = msg +     "\n     Humidity out: %.1f" % self.hum_out + " %"
            if self.hum_in  != None :
                msg = msg +     " - Humidity in: %.1f" % self.hum_in + " %"
            if self.rel_pressure != None :
                msg = msg +     "\n     Pressure: %d" % self.rel_pressure + " hPa"
            if self.the_real_rain != None :
                msg = msg +     "\n     Rain tot: %.1f" % self.the_real_rain + " mm"
            if self.rain_rate != None :
                msg = msg +     " - Rain Day: %.1f" % self.rain_rate + " mm"
            if self.rain_rate_1h != None :
                msg = msg +     " - Rain 1h: %.1f" % self.rain_rate_1h + " mm"
            if self.rain_rate_24h != None :
                msg = msg +     " - Rain 24h: %.1f" % self.rain_rate_24h + " mm"
            if self.cloud_base_altitude != None :
                msg = msg +     "\n     Cloud Base: %d" % self.cloud_base_altitude + " meter"
            if self.wind_trend != None :
                msg = msg +     " - Trend: %.2f" % self.wind_trend
            if self.uv != None :
                msg = msg +     " - UV: %d" % self.uv
            if self.illuminance != None :
                msg = msg +     " - Lux: %.1f" % self.illuminance
                msg = msg +     " - Watts/m: %.1f" % (self.illuminance*0.0079)
            if self.lux != None :
                msg = msg +     "\n     Lux: %.1f" % self.lux
            if self.luxfull != None :
                msg = msg +     " - LuxFull: %.1f" % self.luxfull
            if self.ir != None :
                msg = msg +     " - IR: %.1f" % self.ir
            if self.pm2  != None :
                msg = msg +     "\n     PM 2.5: %.1f" % self.pm2 + " um"
            if self.pm10  != None :
                msg = msg +     " - PM 10: %.1f" % self.pm10 + " um"
            msg = msg + "\n"
            log(msg)
            #if ( self.cfg.sensor_type.upper()  == "WH4000_RTL-SDR" ):
            #    os.remove('/dev/shm/wh4000-rtl_433.txt')            



    def getLastTodayFromDB(self):
        conn = sqlite3.connect('db/meteopi.s3db',200)

        dbCursor = conn.cursor()
        try:
            dbCursor.execute("SELECT * FROM METEO where date(TIMESTAMP_LOCAL) = date('now','localtime') order by rowid desc limit 1")
        except sqlite3.Error:
            log("Ripristino Database")
            os.system( "sudo cp -f db/meteopiori.s3db db/meteopi.s3db" )
            os.system("sudo reboot")
        data = dbCursor.fetchall()
        if ( len(data) != 1):
            if conn:
                conn.close()
            return False

# "2012-10-19 11:15:50.375000"

        self.previous_measure_time = datetime.datetime.strptime(data[0][0],"%Y-%m-%d %H:%M:%S.%f")
#        self.idx = datetime.datetime.strptime(data[0][1],"%Y-%m-%d %H:%M:%S.%f")
#        self.wind_dir_code = (data[0][2])
#        self.wind_dir = (data[0][3])
#        self.wind_ave = (data[0][4])
#        self.wind_gust = (data[0][5])
#        self.temp_out = (data[0][6])
#        self.abs_pressure = (data[0][7])
#        self.hum_out = (data[0][8])
        self.rain = (data[0][9])
        #print "-----------------------------------------",self.rain
        self.rain_rate = (data[0][10])
        self.the_real_rain = (data[0][33])
#        self.temp_in = (data[0][11])
#        self.hum_in = (data[0][12])
#        self.wind_chill = (data[0][13])
#        self.temp_apparent = (data[0][14])
#        self.dew_point = (data[0][15])
#        self.uv = (data[0][16])
#        self.illuminance = (data[0][17])
        self.winDayMin = (data[0][18])
        self.winDayMax = (data[0][19])
        self.winDayGustMin = (data[0][20])
        self.winDayGustMax = (data[0][21]     )
        self.TempOutMin = (data[0][22])
        self.TempOutMax = (data[0][23])
        self.TempInMin = (data[0][24])
        self.TempInMax = (data[0][25])
        self.UmOutMin = (data[0][26])
        self.UmOutMax = (data[0][27])
        self.UmInMin = (data[0][28])
        self.UmInMax = (data[0][29])
        self.PressureMin = (data[0][30])
        self.PressureMax = (data[0][31])


        dbCursor.execute("SELECT * FROM METEO where date(TIMESTAMP_LOCAL) = date('now','localtime') order by rowid asc limit 1")
        data = dbCursor.fetchall()
        if ( len(data) == 1):
            self.previous_rain = (data[0][9])
        else:
            self.previous_rain = None
#        self.previous_measure_time = self.last_measure_time


        if conn:
            conn.close()

        return True


#    def getLastFromDB(self):
#        conn = sqlite3.connect('db/swpi.s3db',200)
#        dbCursor = conn.cursor()
#        dbCursor.execute('SELECT * FROM METEO order by rowid desc limit 1')
#        data = dbCursor.fetchall()
#        if ( len(data) != 1):
#            if conn:
#                conn.close()
#            return
#
#        self.last_measure_time = data[0][0]
#        self.idx = data[0][1]
#        self.wind_dir_code = data[0][2]
#        self.wind_dir = data[0][3]
#        self.wind_ave = data[0][4]
#        self.wind_gust = data[0][5]
#        self.temp_out = data[0][6]
#        self.abs_pressure = data[0][7]
#        self.hum_out = data[0][8]
#        self.rain = data[0][9]
#        self.rain_rate = data[0][10]
#        self.temp_in = data[0][11]
#        self.hum_in = data[0][12]
#        self.wind_chill = data[0][13]
#        self.temp_apparent = data[0][14]
#        self.dew_point = data[0][15]
#        self.uv = data[0][16]
#        self.illuminance = data[0][17]
#        self.winDayMin = data[0][18]
#        self.winDayMax = data[0][19]
#        self.TempOutMin = data[0][20]
#        self.TempOutMax = data[0][21]
#        self.TempInMin = data[0][22]
#        self.TempInMax = data[0][23]
#        self.UmOutMin = data[0][24]
#        self.UmOutMax = data[0][25]
#        self.UmInMin = data[0][26]
#        self.UmInMax = data[0][27]
#        self.PressureMin = data[0][28]
#        self.PressureMax = data[0][29]
#
#        self.previous_rain = self.rain
#
#        if conn:
#            conn.close()

class CameraFiles(object):

    def __init__(self):
        self.img1FileName = None
        self.img2FileName = None
        self.fotos = None
        self.img1IPFileName = None
        self.img2IPFileName = None
        self.cPIFilemane = None

    def reset(self):
        self.img1FileName = None
        self.img2FileName = None
        self.fotos = None
        self.img1IPFileName = None
        self.img2IPFileName = None
        self.cPIFilemane = None


if __name__ == '__main__':

    configfile = 'meteopi.cfg'

    cfg = config.config(configfile)

    mt = MeteoData(cfg)

    conn = sqlite3.connect('db/meteopi.s3db',200)
    dbCursor = conn.cursor()
    dbCursor.execute("SELECT * FROM METEO where datetime(TIMESTAMP_LOCAL) > datetime('now','-1 day','localtime') order by rowid asc limit 1")
    data = dbCursor.fetchall()
    if ( len(data) == 1):
        therain = (data[0][9])
        mt.rain_rate_24h = therain
        print  (mt.rain_rate_24h)
    else : print (" nodara")
    dbCursor.execute("SELECT * FROM METEO where datetime(TIMESTAMP_LOCAL) > datetime('now','-1 hour','localtime') order by rowid asc limit 1")
    data = dbCursor.fetchall()
    if ( len(data) == 1):
        therain = (data[0][9])
        mt.rain_rate_1h = therain
        print  (mt.rain_rate_1h)
    else : print (" nodara")
    if conn:
        conn.close()
#        except:
#            pass

#    mt.getLastFromDB()
#    mt.getLastTodayFromDB()
