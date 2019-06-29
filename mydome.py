#!/usr/bin/env python3
"""
A basic INDI driver.

"""

import sys
import time
import os
import requests

from http.server import HTTPServer, BaseHTTPRequestHandler
import re

import logging
logging.basicConfig(format="%(filename)s:%(lineno)d: %(message)s", level=logging.INFO)
log = logging.getLogger()

import indi_python.indi_base as indi
from indi_python.indi_loop import IndiLoop

class Handler(BaseHTTPRequestHandler):

    timeout = 0.5
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type','text/plain')
            self.end_headers()
            self.wfile.write(self.server.indi_driver.print_state().encode())
        else:
            self.send_response(200)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write('<html><head><title>INDI Node Exporter</title></head><body><h1>INDI Node Exporter</h1><p><a href="/metrics">Metrics</a></p></body></html>'.encode())




class MyDome(IndiLoop):
    def __init__(self):
        super(MyDome, self).__init__(driver=True, client_addr="127.0.0.1")
        self.defineProperties("""
        <INDIDriver>
            <defSwitchVector device="MyDome" name="DOME_PARK" label="Open" group="Main Control" state="Idle" perm="rw" rule="OneOfMany">
                <defSwitch name="UNPARK" label="Open">
                    Off
                </defSwitch>
                <defSwitch name="PARK" label="Close">
                    On
                </defSwitch>
            </defSwitchVector>
        </INDIDriver>
        """)
        
        self.telescope = "EQMod Mount"
        self.power_switch = 'Power Switch'
        self.sensors = 'Sensors'
        self.coolcam = 'coolcam'
        self.phase = 'closed'
        self.connect_cnt = 0
        self.sendClient(indi.getProperties())

        self.http_server = HTTPServer(('', 9900), Handler)
        self.http_server.indi_driver = self

        self.addExtraInput(self.http_server.fileno())
        self.timeout = 10

    def loop(self):
        while True:
            self.loop1()
            if self.phase == 'open_connect' and self.checkValue(self.power_switch, "CONNECTION", "CONNECT") == "On":
                self.message("Connected, start opening")
                self.sendClientMessage(self.power_switch, "BATTERY", {"ON": "On"})
                self.sendClientMessage(self.power_switch, "MOUNT_SWITCH", {"ON": "On"})
                if self.checkValue(self.power_switch, "ROOF_CLOSE", "ON") == "On":
                    self.sendClientMessage(self.power_switch, "ROOF_CLOSE", {"ON": "Off"})
                    time.sleep(1)
                time.sleep(0.1)
                self.sendClientMessage(self.power_switch, "ROOF_OPEN", {"ON": "On"})
                self.phase = 'open_start_move1'
            elif self.phase == 'close_connect' and self.checkValue(self.power_switch, "CONNECTION", "CONNECT") == "On":
                self.message("Connected, wait for telescope")
                if self.checkValue(self.power_switch, "ROOF_OPEN", "ON") == "On":
                    self.sendClientMessage(self.power_switch, "ROOF_OPEN", {"ON": "Off"})
                    time.sleep(1)
                self.phase = 'close_wait_park'
            elif self.phase == 'close_wait_park':
                try:
                    if self.checkValue(self.telescope, "TELESCOPE_PARK", "PARK") == "On":
                        try:
                            s_ha = float(self.checkValue(self.sensors, "COORD", "HA"))
                            s_dec = float(self.checkValue(self.sensors, "COORD", "DEC"))
                            s_pier_east = self.checkValue(self.sensors, "TELESCOPE_PIER_SIDE", "PIER_EAST")

                        except:
                            s_ha = 0
                            s_dec = 0
                            s_pier_east = 'unknown'
                            log.exception("checkCoords")
                        
                        if s_ha > 0 and s_ha < 16 and s_dec > 50 and s_dec < 70 and s_pier_east == "On":
                            self.message("Telescope parked, start closing")
                            self.sendClientMessage(self.power_switch, "ROOF_CLOSE", {"ON": "On"})
                            self.phase = 'close_start_move1'
                        else:
                            self.message("Telescope parked in wrong position {} {} {}".format(s_ha, s_dec, s_pier_east))
                            self.phase = 'close_error'
                    elif self.checkState(self.telescope, "TELESCOPE_PARK") == 'Alert':
                        self.message("Telescope parking failed, abort")
                        self.phase = 'close_error'
                except KeyError:
                    self.message("Telescope not found, start closing")
                    self.phase = 'close_start_move1'

            elif self.phase == 'open_start_move1' and self.checkValue(self.power_switch, "ROOF_OPEN", "ON") == "On":
                self.message("Opening")
                self.phase = 'open_start_move2'

            elif self.phase == 'open_start_move2' and self.checkValue(self.power_switch, "ROOF_OPEN", "ON") == "Off":
                self.message("Opened")
                self.properties["MyDome"]["DOME_PARK"].setAttr('state', 'Ok')
                self.properties["MyDome"]["DOME_PARK"].enforceRule("UNPARK", 'On')
                self.sendDriverMessage("MyDome", "DOME_PARK")
                open("/root/alert/enable", 'a').close()
                self.phase = 'opened'

            elif self.phase == 'close_start_move1' and self.checkValue(self.power_switch, "ROOF_CLOSE", "ON") == "On":
                self.message("Closing")
                self.phase = 'close_start_move2'

            elif self.phase == 'close_start_move2' and self.checkValue(self.power_switch, "ROOF_CLOSE", "ON") == "Off":
                self.message("Closed")
                self.properties["MyDome"]["DOME_PARK"].setAttr('state', 'Ok')
                self.properties["MyDome"]["DOME_PARK"].enforceRule("UNPARK", 'Off')
                self.sendDriverMessage("MyDome", "DOME_PARK")
                self.phase = 'closed'
                try:
                    os.remove("/root/alert/enable")
                except:
                    log.exception("rm enable")

            elif self.phase == 'open_connect' and self.checkState(self.power_switch, "CONNECTION", 'Alert') == 'Alert':
                self.message("Arduino disconnected")
                self.phase = 'open_error'

            elif self.phase == 'close_connect' and self.checkState(self.power_switch, "CONNECTION", 'Alert') == 'Alert':
                self.message("Arduino disconnected")
                self.phase = 'close_error'

            elif self.phase == 'close_error':
                self.properties["MyDome"]["DOME_PARK"].setAttr('state', 'Alert')
                self.properties["MyDome"]["DOME_PARK"].enforceRule("UNPARK", 'On')
                self.sendDriverMessage("MyDome", "DOME_PARK")
                self.phase = 'opened'

            elif self.phase == 'open_error':
                self.properties["MyDome"]["DOME_PARK"].setAttr('state', 'Alert')
                self.properties["MyDome"]["DOME_PARK"].enforceRule("UNPARK", 'Off')
                self.sendDriverMessage("MyDome", "DOME_PARK")
                self.phase = 'closed'

            if  self.phase == 'opened' and os.path.exists("/root/alert/alert"):
                self.startClose()
                self.message("closing: alert")




    def handleExtraInput(self, in_s):
        if in_s == self.http_server.fileno():
            self.http_server.handle_request()



    def handleSnoop(self, msg, prop):
        if prop.getAttr("device") == self.telescope and prop.getAttr("name") == "ACTIVE_DEVICES" and prop.checkValue("ACTIVE_DOME") != "MyDome":
            self.sendClientMessage(self.telescope, "ACTIVE_DEVICES", {"ACTIVE_DOME": "MyDome"})

        if prop.getAttr("device") == self.telescope and prop.getAttr("name") == "DOME_POLICY" and prop.checkValue("LOCK_AND_FORCE") != "On":
            self.sendClientMessage(self.telescope, "DOME_POLICY", {"LOCK_AND_FORCE": "On"})

        if prop.getAttr("device") == self.telescope and prop.getAttr("name") == "CONNECTION" and self.checkValue(self.telescope, "CONFIG_PROCESS", "CONFIG_LOAD") and prop.checkValue("CONNECT") == 'On':
            self.sendClientMessage(self.telescope, "CONFIG_PROCESS", {"CONFIG_LOAD": "On"})
            self.connect_cnt = 5

        if prop.getAttr("device") == self.telescope and prop.getAttr("name") == "TELESCOPE_PARK" and self.checkValue(self.telescope, "TELESCOPE_PARK", "UNPARK") == 'On':
            self.connect_cnt = 5

        if prop.getAttr("device") == self.telescope and prop.getAttr("name") == "TIME_LST":
            if (self.connect_cnt > 0):
                self.connect_cnt -= 1
                
                if (self.connect_cnt == 0):
                    try:
                        self.checkCoords()
                    except:
                        log.exception("checkCoords")
                        pass

        if prop.getAttr("device") == self.sensors and prop.getAttr("name") == "TELESCOPE_ABORT_MOTION" and prop.checkValue("ABORT") == "On":
            try:
                self.sendClientMessage(self.telescope, "TELESCOPE_ABORT_MOTION", {"ABORT": "On"})
            except:
                log.exception("abort")
                pass

        if prop.getAttr("device") == self.power_switch and prop.getAttr("name") =="SENSORS" and float(self.checkValue(self.power_switch, "SENSORS", "V_SUPPLY")) < 13.0 and self.phase == 'opened':
            self.startClose()
            self.message("closing: battery " + self.checkValue(self.power_switch, "SENSORS", "V_SUPPLY"))

    def checkCoords(self):
        log.info('checkCoords start')
        lst = float(self.checkValue(self.telescope, "TIME_LST", "LST"))
        t_ra = float(self.checkValue(self.telescope, "EQUATORIAL_EOD_COORD", "RA"))
        t_dec = float(self.checkValue(self.telescope, "EQUATORIAL_EOD_COORD", "DEC"))
        t_pier = self.checkValue(self.telescope, "TELESCOPE_PIER_SIDE", "PIER_WEST")

        s_ha = float(self.checkValue(self.sensors, "COORD", "HA")) / 180.0 * 12.0
        s_dec = float(self.checkValue(self.sensors, "COORD", "DEC"))
        s_pier_west = self.checkValue(self.sensors, "TELESCOPE_PIER_SIDE", "PIER_WEST")
        s_pier_east = self.checkValue(self.sensors, "TELESCOPE_PIER_SIDE", "PIER_EAST")

        s_ra = s_ha + lst
        if s_ra >= 24.0:
            s_ra -= 24.0

        ra_dif = abs(t_ra - s_ra)
        if ra_dif > 12.0:
            ra_dif = 24 - ra_dif

        #print >> sys.stderr, 'checkCoords', t_ra, t_dec, s_ra, s_dec, s_pier_west, t_pier
        if ra_dif > 0.5 or abs(t_dec - s_dec) > 8.0 or s_pier_west != t_pier:
            #print >> sys.stderr, 'checkCoords sync'
            self.sendClientMessage(self.telescope, 'ON_COORD_SET', {'SYNC': 'On'})
            self.sendClientMessage(self.telescope, 'TARGETPIERSIDE', {'PIER_WEST': s_pier_west, 'PIER_EAST': s_pier_east})
            self.sendClientMessage(self.telescope, 'EQUATORIAL_EOD_COORD', {'RA': str(s_ra), 'DEC': str(s_dec)})
            self.sendClientMessage(self.telescope, 'ON_COORD_SET', {'TRACK': 'On'})
        else:
            self.sendClientMessage(self.telescope, 'TARGETPIERSIDE', {'PIER_WEST': s_pier_west, 'PIER_EAST': s_pier_east})


    def startClose(self):
        
        try:
            response = requests.post('http://localhost:8080/button', data = {'cmd':'navigator', 'tgt':'guider'})
        except:
            response = 'Request to localhost:8080 failed'

        self.message("http notify: " + str(response))

        self.properties["MyDome"]["DOME_PARK"].setAttr('state', 'Busy')
        self.phase = 'close_connect'
        self.sendClientMessage(self.power_switch, "CONNECTION", {"CONNECT": "On"})
        self.sendClientMessage(self.sensors, "CONNECTION", {"CONNECT": "On"})
        if self.checkValue(self.telescope, "CONNECTION", "CONNECT") != 'On':
            self.sendClientMessage(self.telescope, "CONNECTION", {"CONNECT": "On"})
            time.sleep(2)
        self.sendDriverMessage("MyDome", "DOME_PARK")
    
    def handleNewValue(self, msg, prop):

        device = prop.getAttr("device")
        name = prop.getAttr("name")
        if name != 'DOME_PARK':
            return;
        prev_val = prop["UNPARK"].getValue()
        prop.newFromEtree(msg)
        new_val = prop["UNPARK"].getValue()
        if prev_val == new_val and prop.getAttr('state') in ['Ok', 'Idle']:
            pass
        elif new_val == 'On':
            try:
                os.remove("/root/alert/alert")
            except:
                log.exception("rm alert")
            prop.setAttr('state', 'Busy')
            self.phase = 'open_connect'
            self.sendClientMessage(self.power_switch, "CONNECTION", {"CONNECT": "On"})
            self.sendClientMessage(self.sensors, "CONNECTION", {"CONNECT": "On"})
            self.sendDriverMessage("MyDome", "DOME_PARK")

        elif new_val == 'Off': 
            self.startClose()
            
#        self.sendDriverMessage(msg.getAttr("device"), msg.getAttr("name"))

#        self.sendDriver(prop.setMessage())


    def print_state(self):
        ret = ''
        try:
            for device in self.properties:
                for prop in self.properties[device]:
                    for element in self.properties[device][prop].getElements():
                        #if isinstance(element, indiXML.DefBLOB):
                        #    continue

                        out_prop = "{}_{}_{}".format(device, prop, element.getAttr("name"))
                        change_ch = r'[ -]'
                        drop_ch = r'[^A-Za-z0-9_]'
                        value = element.getValue()
                        out_prop = re.sub(change_ch, '_', out_prop)
                        out_prop = re.sub(drop_ch, '', out_prop)
                        if value == 'On':
                            value = 1
                        elif value == 'Off':
                            value = 0
                        try:
                            value = float(value)
                        except:
                            value = re.sub(change_ch, '_', value)
                            value = re.sub(drop_ch, '', value)
    
                            out_prop += '{' + 'value="{}"'.format(value) + '}'
                            value = 1
                        ret += "{} {}\n".format(out_prop, value)

        except:
            log.exception('print_state')
        return ret


if __name__ == '__main__':
    driver = MyDome()
    driver.loop()

