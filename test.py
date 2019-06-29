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

driver = IndiLoop(driver=True)
driver.defineProperties("""
        <INDIDriver>
            <defNumberVector device="Test" name="prop" label="prop" group="Main Control" state="Idle" perm="rw">
                <defNumber name="n1">
                    1.0
                </defNumber>
                <defNumber name="n2">
                    2.0
                </defNumber>
            </defNumberVector>
        </INDIDriver>
        """)
        
#    driver.loop()

device = driver['Test']
device['prop'] += 1

print(device['prop'])


