#!/usr/bin/env python3
"""
A basic INDI driver.

"""

import socket
import sys
import time
import os
import fcntl
import datetime
import select
from lxml import etree
import threading

import indi_python.indi_base as indi

import logging
logging.basicConfig(format="%(filename)s:%(lineno)d: %(message)s", level=logging.INFO)
log = logging.getLogger()


class IndiLoop(object):

    def __init__(self, client_addr = None, driver = False, client_port = 7624):

        self.my_devices = []
        self.properties = { }
        
        self.stdin = None
        self.stdout = None
        self.client_socket = None
        
        self.input_sockets = []
        
        if driver:
            self.stdin = sys.stdin
            self.stdout = sys.stdout
            self.input_sockets.append(self.stdin)
            #self.stdin.settimeout(0.1)
            fd = self.stdin.fileno()
            flag = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
            self.driver_write_lock = threading.Lock()
        
        if client_addr:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((client_addr, client_port))
            self.input_sockets.append(self.client_socket)
            self.client_socket.settimeout(0.1)
            self.client_write_lock = threading.Lock()

        self.buf = [''] * len(self.input_sockets)

        self.extra_input = []
        self.timeout = None
        self.reply_timeout = None
        self.snoop_condition = threading.Condition()
 
    def close(self):
        pass

    def addExtraInput(self, s):
        self.extra_input.append(s)

    def defineProperties(self, xml):
        tree = etree.fromstring(xml)
        for p in tree:
            prop = indi.INDIVector(p)
            self.properties.setdefault(prop.getAttr('device'), {})[prop.getAttr('name')] = prop
        
        self.my_devices = list(self.properties.keys())

    def loop1(self, timeout = None):
    
        if timeout is None:
            timeout = self.timeout
    
        readable, writable, exceptional = select.select(self.input_sockets + self.extra_input, [], self.input_sockets + self.extra_input, timeout)

        for i, in_s in enumerate(self.input_sockets):
            if in_s in readable:
                tree = []
                try:
                    if hasattr(in_s, 'recv'):
                        d = in_s.recv(1000000).decode()
                    else:
                        d = in_s.read(1000000)
                        if d == '':
                            log.error("closed stdin")
                            self.handleEOF()

                    self.buf[i] += d
                    tree = etree.fromstring('<msg>' + self.buf[i] + '</msg>')
                    self.buf[i] = ''
                except etree.ParseError:
                    pass
            
                for msg in tree:
                    spec = indi.getSpec(msg)
                
                
                    if spec['mode'] == 'define':
                        try:
                            prop = indi.INDIVector(msg)
                            self.properties.setdefault(prop.getAttr('device'), {})[prop.getAttr("name")] = prop
                        except:
                            log.exception('define')
                            
                    elif spec['mode'] == 'set':
                        try:
                            prop = self.properties[msg.get("device")][msg.get("name")]
                            with self.snoop_condition:
                                prop.updateFromEtree(msg)
                                self.snoop_condition.notify_all()
                            self.handleSnoop(msg, prop)
                        except:
                            log.exception('set')
                    elif spec['mode'] == 'new':
                        try:
                            device = msg.get("device")
                            if device in self.my_devices:
                                prop = self.properties[device][msg.get("name")]
                                self.handleNewValue(msg, prop, from_client_socket=(in_s is self.client_socket))
                        except:
                            log.exception('new')
                    elif spec['mode'] == 'control':
                        if msg.tag == 'getProperties':
                            try:
                                devices = [ msg["device"] ]
                            except:
                                devices = self.my_devices

                            for device in devices:
                                if device not in self.my_devices:
                                    continue
                                for prop in self.properties[device]:
                                    self.sendDriver(self.properties[device][prop].defineMessage())
                        elif msg.tag == 'delProperty':
                            try:
                                device = msg.get("device")
                                propname = msg.get("name")
                                if propname:
                                    del self.properties[device][propname]
                                else:
                                    self.properties[device] = {}
                            except:
                                log.exception('delProperty')

        for in_s in self.extra_input:
            if in_s in readable:
                self.handleExtraInput(in_s)


    def loop(self):
        while True:
            self.loop1()

    def sendClient(self, msg):
        if self.client_socket:
            with self.client_write_lock:
                self.client_socket.send(msg)

    def sendDriver(self, msg):
        if self.stdout:
            with self.driver_write_lock:
                self.stdout.buffer.write(msg)
                self.stdout.flush()

    def handleNewValue(self, msg, prop, from_client_socket=False):
        if from_client_socket:
            return

        prop.newFromEtree(msg)

        prop.setAttr('state', 'Ok')
        self.sendDriver(prop.setMessage())

    def handleSnoop(self, msg, prop):
        pass

    def handleExtraInput(self, in_s):
        pass

    def handleEOF(self):
        sys.exit(1)

    def snoopDevice(self, device, prop = None):
        if prop is None:
            msg = indi.getProperties(device=device)
        else:
            msg = indi.getProperties(device=device, name=prop)

        self.sendDriver(msg)

    def checkValue(self, device, prop, item, state = ['Ok', 'Idle'], defvalue = None):
        try:
            prop = self.properties[device][prop]
            return prop.checkValue(item, state, defvalue)
        except KeyError:
            log.exception('checkValue')
            return defvalue

    def checkState(self, device, prop_name, defvalue=None):
        try:
            prop = self.properties[device][prop_name]
            return prop.getAttr('state')
        except KeyError:
            return defvalue


    def message(self, text, device=None):
        if device is None:
            device = self.my_devices[0]
        log.info(text)
        self.sendDriver(indi.message(device, text))

    def sendDriverMessage(self, device, prop_name, message = None):
        prop = self.properties[device][prop_name]
        self.sendDriver(prop.setMessage(message))
          
    def sendClientMessage(self, device, name, changes={}):
        try:
            baseprop = self.properties[device][name]
            baseprop.setAttr('state', 'Busy')
            self.sendClient(baseprop.newMessage(changes))
        except:
            log.exception("sendClientMessage")

    def sendClientMessageWait(self, device, name, changes={}, timeout=None, call_loop=False):
        if timeout is None:
            timeout = self.reply_timeout
    
        log.error("sendClientMessageWait start %s %s", device, name)
        with self.snoop_condition:
            try:
                baseprop = self.properties[device][name]
                cnt = baseprop.update_cnt
                self.sendClientMessage(device, name, changes)
                t0 = time.time()
            except:
                log.exception("sendClientMessageWait")
                return
            
            while baseprop.update_cnt == cnt:
                if call_loop:
                    self.loop1(timeout)
                else:
                    self.snoop_condition.wait(timeout)
                
                if timeout and t0 + timeout < time.time():
                    raise RuntimeError('Prop is still busy')
                    
        log.error("sendClientMessageWait end %s %s", device, name)



    def __getitem__(self, key):
        return self.properties[key]
        