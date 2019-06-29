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

import numpy as np

import logging
logging.basicConfig(format="%(filename)s:%(lineno)d: %(message)s", level=logging.INFO)
log = logging.getLogger()

import indi_python.indi_base as indi
from indi_python.indi_loop import IndiLoop

def handleSnoop(msg, prop):
    print(prop)
    
    if prop.getAttr('name') == 'CCD1':
        blob = prop['CCD1'].native()
        f = open("test.fits", "wb")
        f.write(blob)
        f.close()

driver = IndiLoop(client_addr='localhost')

driver.handleSnoop = handleSnoop

driver.sendClient(indi.getProperties())
driver.timeout=1

time.sleep(1)
driver.loop1()
time.sleep(1)
driver.loop1()
time.sleep(1)
driver.loop1()

driver.sendClient(indi.enableBLOB("V4L2 CCD"))

#print(driver.properties)

driver.sendClientMessage("V4L2 CCD", "CCD_EXPOSURE", {"CCD_EXPOSURE_VALUE": 1})


driver.loop()

