from lxml import etree
import datetime

import logging
log = logging.getLogger()

import numpy as np
import numbers

import base64

def indi_bool(x):
    if x == 'On':
        return True
    if x == 'Off':
        return False
    return bool(x)

indi_messages = {
    "defTextVector"   : { 'mode': 'define', 'ptype': str,         'vector': True,  'itype': 'Text',   'setmsg': "setTextVector", 'newmsg': "newTextVector" },
    "defText"         : { 'mode': 'define', 'ptype': str,         'vector': False, 'itype': 'Text',   'onemsg': "oneText"},
    "defNumberVector" : { 'mode': 'define', 'ptype': float,       'vector': True,  'itype': 'Number', 'setmsg': "setNumberVector", 'newmsg': "newNumberVector"},
    "defNumber"       : { 'mode': 'define', 'ptype': float,       'vector': False, 'itype': 'Number', 'onemsg': "oneNumber"},
    "defSwitchVector" : { 'mode': 'define', 'ptype': indi_bool,   'vector': True,  'itype': 'Switch', 'setmsg': "setSwitchVector", 'newmsg': "newSwitchVector"},
    "defSwitch"       : { 'mode': 'define', 'ptype': indi_bool,   'vector': False, 'itype': 'Switch', 'onemsg': "oneSwitch"},
    "defLightVector"  : { 'mode': 'define', 'ptype': indi_bool,   'vector': True,  'itype': 'Light',  'setmsg': "setLightVector", 'newmsg': "newLightVector"},
    "defLight"        : { 'mode': 'define', 'ptype': indi_bool,   'vector': False, 'itype': 'Light',  'onemsg': "oneLight"},
    "defBLOBVector"   : { 'mode': 'define', 'ptype': base64.b64decode,         'vector': True,  'itype': 'BLOB',   'setmsg': "setBLOBVector", 'newmsg': "newBLOBVector"},
    "defBLOB"         : { 'mode': 'define', 'ptype': base64.b64decode,         'vector': False, 'itype': 'BLOB',   'onemsg': "oneBlob"},

    "setTextVector"   : { 'mode': 'set',    'ptype': str,         'vector': True,  'itype': 'Text'},
    "setNumberVector" : { 'mode': 'set',    'ptype': float,       'vector': True,  'itype': 'Number'},
    "setSwitchVector" : { 'mode': 'set',    'ptype': indi_bool,   'vector': True,  'itype': 'Switch'},
    "setLightVector"  : { 'mode': 'set',    'ptype': indi_bool,   'vector': True,  'itype': 'Light'},
    "setBLOBVector"   : { 'mode': 'set',    'ptype': base64.b64decode,         'vector': True,  'itype': 'BLOB'},

    "newTextVector"   : { 'mode': 'new',    'ptype': str,         'vector': True,  'itype': 'Text'},
    "newNumberVector" : { 'mode': 'new',    'ptype': float,       'vector': True,  'itype': 'Number'},
    "newSwitchVector" : { 'mode': 'new',    'ptype': indi_bool,   'vector': True,  'itype': 'Switch'},
    "newBLOBVector"   : { 'mode': 'new',    'ptype': base64.b64decode,         'vector': True,  'itype': 'BLOB'},

    "oneText"         : { 'mode': 'one',    'ptype': str,         'vector': False, 'itype': 'Text'},
    "oneNumber"       : { 'mode': 'one',    'ptype': float,       'vector': False, 'itype': 'Number'},
    "oneSwitch"       : { 'mode': 'one',    'ptype': indi_bool,   'vector': False, 'itype': 'Switch'},
    "oneLight"        : { 'mode': 'one',    'ptype': indi_bool,   'vector': False, 'itype': 'Light'},
    "oneBLOB"         : { 'mode': 'one',    'ptype': base64.b64decode,         'vector': False, 'itype': 'BLOB'},

    "getProperties"   : { 'mode': 'control'},
    "message"         : { 'mode': 'control'},
    "delProperty"     : { 'mode': 'control'},
    "enableBLOB"      : { 'mode': 'control'}
}


def getSpec(t):
    try:
        return indi_messages[t.tag]
    except:
        return { 'mode': 'unknown'}

class INDIBase(object):
    def getAttr(self, a):
        return self.attr[a]

    def setAttr(self, a, v):
        self.attr[a] = v
    
    def attrsFromEtree(self, t):
         for name, value in t.items():
             self.setAttr(name, value)
    


class INDIElement(INDIBase, np.lib.mixins.NDArrayOperatorsMixin):
    def __init__(self, t):
        spec = indi_messages[t.tag]
        self.__dict__.update(spec)
        if self.mode != 'define' and self.vector != False:
            raise RuntimeError('cant define ' + t.tag)
        
        self.definemsg = t.tag
        self.attr = {}
        self.fromEtree(t)

    def getValue(self):
        return self.value

    def setValue(self, v):
        if v is True:
            v = 'On'
        elif v is False:
            v = 'Off'
        self.value = v

    def fromEtree(self, t):
        self.attrsFromEtree(t)
        text = t.text or ''
        self.setValue(text.strip())

    def __str__(self):
        return str(self.value)

    def __float__(self):
        return float(self.value)

    def __repr__(self):
        if self.itype == 'BLOB':
            return str(self.attr) + ': blob(' + str(len(self.value)) + ')'
        return str(self.attr) + ': ' + self.value

    def native(self):
        return self.ptype(self.value)

    def __getitem__(self, key):
        return self.attr[key]
            
    def __setitem__(self, key, val):
        self.attr[key] = val

    def setMessageTree(self, value = None):
        attrs = {}
        for a in ['name']:
            try:
                attrs[a] = self.getAttr(a)
            except:
                pass
            
        tree = etree.Element(self.onemsg, attrib=attrs)
        if value is not None:
            tree.text = str(value)
        else:
            tree.text = str(self.value)
        return tree

    def setMessage(self):
        tree = self.setMessageTree()
        return etree.tostring(tree)

    def defineMessageTree(self):
        tree = etree.Element(self.definemsg, attrib=self.attr)
        tree.text = str(self.value)
        return tree

    def defineMessage(self):
        tree = self.defineMessageTree(message)
        return etree.tostring(tree)


    _HANDLED_TYPES = (np.ndarray, numbers.Number, bool, str)

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        out = kwargs.get('out', ())
        for x in inputs + out:
            # Only support operations with instances of _HANDLED_TYPES.
            # Use INDIElement instead of type(self) for isinstance to
            # allow subclasses that don't override __array_ufunc__ to
            # handle INDIElement objects.
            if not isinstance(x, self._HANDLED_TYPES + (INDIElement,)):
                return NotImplemented

        # Defer to the implementation of the ufunc on unwrapped values.
        inputs = tuple(x.native() if isinstance(x, INDIElement) else x
                       for x in inputs)
        if out:
            kwargs['out'] = tuple(
                x.to_array() if isinstance(x, INDIElement) else x
                for x in out)
        result = getattr(ufunc, method)(*inputs, **kwargs)

        return result


class INDIVector(INDIBase, np.lib.mixins.NDArrayOperatorsMixin):
    def __init__(self, t):
        spec = indi_messages[t.tag]
        self.__dict__.update(spec)
        if self.mode != 'define' and self.vector != True:
            raise RuntimeError('cant define ' + t.tag)

        self.definemsg = t.tag
        self.attr = {}
        self.elements = []
        self.elements_dict = {}
        self.update_cnt = 0
        self.defineFromEtree(t)
        

    def append(self, e):
        name = e.getAttr('name')
        self.elements_dict[name] = e
        self.elements.append(e)

    def getElements(self):
        return self.elements

    def getElement(self, i):
        return self.elements[i]

    def getElementByName(self, n):
        return self.elements_dict[n]

    def enforceRule(self, name = None, value = None):
        if name is not None and value is not None:
            self.elements_dict[name].setValue(value)

        try:
            rule = self.getAttr('rule')
            if rule != 'OneOfMany' and rule != 'AtMostOne':
                return
        except:
            return
            
        if name is None:
            name = self.elements[0].getAttr("name")
        
        value = self.elements_dict[name].getValue()
        
        if rule == 'AtMostOne' or (value == 'On' and rule == 'OneOfMany'):
            haveOn = (value == 'On')
            for e in self.elements:
                if e.getAttr("name") == name:
                    continue
                if haveOn:
                   e.setValue('Off')
                else:
                   if e.getValue() == 'On':
                       haveOn = True
        elif value == 'Off' and rule == 'OneOfMany':
            haveOn = False

            for e in self.elements:
               if e.getValue() == 'On':
                    haveOn = True
                    name = e.getAttr("name")
                    break

            for e in self.elements:
                if e.getAttr("name") == name:
                    continue

                if haveOn:
                    e.setValue('Off')
                else:
                    e.setValue('On')
                    haveOn = True

    def setValue(self, v):
        for i, e in enumerate(self.elements):
            e.setValue(v[i])


    def getActiveSwitch(self):
        for e in self.elements:
            if e.getValue() == 'On':
                return e.getAttr('name')
        return None

    def defineFromEtree(self, t):
        self.attrsFromEtree(t)
        for child in t:
            name = child.get('name')
            e = INDIElement(child)
            self.append(e)

    def updateFromEtree(self, t):
        self.update_cnt += 1
        spec = indi_messages[t.tag]

        self.attrsFromEtree(t)
        for child in t:
            name = child.get('name')
            e = self.getElementByName(name)
            e.fromEtree(child)

    def newFromEtree(self, t):
        self.updateFromEtree(t)
        try:
            child = t[0]
            name = child.get('name')
            self.enforceRule(name)
        except:
            pass
        

    def __repr__(self):
        r = str(self.attr) + ':\n'
        for e in self.elements:
            r += '                ' + repr(e) + '\n'
        return r
    
    def __getitem__(self, key):
        try:
            return self.attr[key]
        except KeyError:
            try:
                return self.elements_dict[key]
            except KeyError:
                return self.elements[key]
            
    def __setitem__(self, key, val):
        if key in self.attr:
            self.attr[key] = val
        elif key in self.elements_dict:
            self.elements_dict[key].setValue(val)
        else:
            self.elements[key].setValue(val)

    def setMessageTree(self, message = None):
        self.attr['timestamp'] = datetime.datetime.utcnow().replace(microsecond=0).isoformat()
        attrs = {}
        for a in ['device', 'name', 'state', 'timeout', 'timestamp']:
            try:
                attrs[a] = self.getAttr(a)
            except:
                pass

        if message is not None:
            attrs['message'] = message
            
        tree = etree.Element(self.setmsg, attrib=attrs)
        
        for e in self.elements:
            tree.append(e.setMessageTree())
        
        return tree

    def setMessage(self, message = None):
        tree = self.setMessageTree(message)
        return etree.tostring(tree)

    def defineMessageTree(self, message = None):
        self.attr['timestamp'] = datetime.datetime.utcnow().replace(microsecond=0).isoformat()
        tree = etree.Element(self.definemsg, attrib=self.attr)
        
        for e in self.elements:
            tree.append(e.defineMessageTree())
        
        return tree

    def defineMessage(self):
        tree = self.defineMessageTree()
        return etree.tostring(tree)

    def newMessageTree(self, changes = {}, message = None):
        attrs = {}
        for a in ['device', 'name']:
            try:
                attrs[a] = self.getAttr(a)
            except:
                pass

        attrs['timestamp'] = datetime.datetime.utcnow().replace(microsecond=0).isoformat()
        if message is not None:
            attrs['message'] = message
            
        tree = etree.Element(self.newmsg, attrib=attrs)

        if self.itype == 'Switch':
            tmpVector = INDIVector(self.defineMessageTree())
            for key,v in changes.items():
                tmpVector.enforceRule(key, v)
            for e in tmpVector.elements:
            	tree.append(e.setMessageTree())
                
        else:
            for key,v in changes.items():
                tree.append(self.elements_dict[key].setMessageTree(v))
        
        return tree

    def newMessage(self, changes = {}, message = None):
        tree = self.newMessageTree(changes, message)
        return etree.tostring(tree)

    def checkValue(self, item, state = ['Ok', 'Idle'], defvalue = None):
        try:
            if self.getAttr('state') in state:
                value = self.elements_dict[item].getValue()
            else:
                value = defvalue
        except KeyError:
            log.exception("checkValue element")
            value = defvalue
        return value

    def to_array(self):
        return np.array([x.native() for x in self.elements])

    _HANDLED_TYPES = (np.ndarray, numbers.Number, bool, str)

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        out = kwargs.get('out', ())
        for x in inputs + out:
            # Only support operations with instances of _HANDLED_TYPES.
            # Use INDIVector instead of type(self) for isinstance to
            # allow subclasses that don't override __array_ufunc__ to
            # handle INDIVector objects.
            if not isinstance(x, self._HANDLED_TYPES + (INDIVector,)):
                return NotImplemented

        # Defer to the implementation of the ufunc on unwrapped values.
        inputs = tuple(x.to_array() if isinstance(x, INDIVector) else x
                       for x in inputs)
        if out:
            kwargs['out'] = tuple(
                x.to_array() if isinstance(x, INDIVector) else x
                for x in out)
        result = getattr(ufunc, method)(*inputs, **kwargs)

        return result
#        if type(result) is tuple:
#            # multiple return values
#            return tuple(type(self)(x) for x in result)
#        elif method == 'at':
#            # no return value
#            return None
#        else:
#            # one return value
#            return type(self)(result)


def getProperties(device=None, name=None):
    if device is not None and name is not None:
        return "<getProperties version='1.7' device='{}' name='{}'/>".format(device, name).encode()
    elif device is not None:
        return "<getProperties version='1.7' device='{}'/>".format(device).encode()
    else:
        return "<getProperties version='1.7'/>".encode()

def enableBLOB(device, name=None, mode="Also"):
    if device is not None and name is not None:
        return "<enableBLOB device='{}' name='{}'>{}</enableBLOB>".format(device, name, mode).encode()
    else:
        return "<enableBLOB device='{}'>{}</enableBLOB>".format(device, mode).encode()

def message(device, text):
    tree = etree.Element('mesage', attrib={
        'device': device, 
        'timestamp': datetime.datetime.utcnow().replace(microsecond=0).isoformat(),
        'message': text})
    return etree.tostring(tree)
