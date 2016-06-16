import serial, struct
from time import time

def recv_cmd(s, timeout = 0):
    rr = {}
    while 1:
        if timeout and time() > timeout: 
            rr['type'] = 'TO'
            break
        r = s.readline()
        if not len(r): continue
        if r.startswith('(BB)'):
            rr['type'] = 'B'
            rr['raw'] = r[4:].strip()
        elif r.startswith('(EE)'):
            rr['type'] = 'E'
            rr['raw'] = r[4:].strip()
        elif r.startswith('(DD)'):
            rr['type'] = 'D'
            rr['raw'] = r[4:].strip()
            i = 0
            for d in rr['raw'].split(' '):
                rr[i] = d.decode("hex")
                i += 1
            rr['len'] = i
        elif r.startswith('(QQ)'):
            rr['type'] = 'Q'
            rr['raw'] = r[4:].strip()
        else:
            continue
        break
    return rr
    
def connect(ser, timeout = 10, maxnode = 127):
    print "Waiting for %d secs for %d nodes max." % (timeout, maxnode)

    ser.write("c" + chr(maxnode))
    l = recv_cmd(ser)
    if l['type'] != 'B':
        print "ERROR, cannot start connection."
        return -1
    
    print "Connecting...", 
    
    rr = []
    if timeout:
        timeout = timeout + time()
    while 1:
        l = recv_cmd(ser, timeout)
        if l['type'] == 'D':
            rr.append(l[0])
            print (l['raw'] + ";"),
        elif l['type'] == 'Q':
            print "Done."
            break
        elif l['type'] == 'E':
            print "Error:" + l['raw']
            break
        elif l['type'] == 'TO':
            print "Timeout, done."
            ser.write("q")
            l = recv_cmd(ser)
            break
    
    return rr

def stdcmd(ser, cmd, addrlist, retries, force_unicast = 0):
    if isinstance(addrlist, basestring):
        addrlist = [addrlist]
    alist = addrlist[:]
    rr = {}
    
    #print ("Command %s(%d)..." %(cmd[0], len(addrlist))),
    node_cnt = len(alist)
    b = 0
    while len(alist) >= 3 and b <= 2 and not force_unicast:
        for a in alist:
            if a in retries: 
                retries[a] += 1
        ser.write(cmd)
        ser.write('B' + chr(node_cnt) + '000')
        l = recv_cmd(ser)
        if l['type'] != 'B':
            print "ERROR, cannot start command."
            return rr
        while 1:
            l = recv_cmd(ser)
            if l['type'] == 'D':
                if l[0] in alist:
                    alist.remove(l[0])
                if l[0] in retries:
                    retries[l[0]] -= 1
                rr[l[0]] = l[1]
                #print (l['raw'] + ";"),
            elif l['type'] == 'Q':
                break
            elif l['type'] == 'E':
                print "Error:" + l['raw']
                return rr
        b = b + 1
    
    #print "unicast...",
    
    r = 0
    while len(alist):
        a = alist[0]
        if a in retries: 
            retries[a] += 1
        ser.write(cmd)
        ser.write("-" + a[::-1])
        l = recv_cmd(ser)
        if l['type'] != 'B':
            print "ERROR, cannot start command."
            print l['raw']
            return rr
        r = r + 1
        l = recv_cmd(ser, time() + 0.5)
        if l['type'] == 'D':
            alist.remove(a)
            if a in retries: 
                retries[a] -= 1
            rr[a] = l[1]
            r = 0
            #print (l['raw'] + "; "),
        elif l['type'] == 'Q' or l['type'] == 'TO':
            if r > 1000:
                print "Give-up: " + a.encode("hex")
                alist.remove(a)
                r = 0
        elif l['type'] == 'E':
            print "Error:" + l['raw']
            return rr
    
    # strip if single target
    if len(addrlist) == 1 and len(rr) == 1:
        if addrlist[0] in rr:
            rr = rr[addrlist[0]]
    #print "Done."
    return rr

def check_all_responses(res, nodes):
    # check the responses from all nodes and return the response if they are the same
    # return "" if they are not same
    if isinstance(res, basestring):
        return {"r":res, "n":[]}
    r = ""
    badnodes = []
    for n in nodes:
        if n in res:
            if r == "":
                r = res[n]
            elif r != res[n]:
                return {"r":"", "n":[n]}
        else:
            badnodes.append(n)
    return {"r":r, "n":badnodes}

class Bootloader:
    
    def __init__(self):
        self.s = None
        self.nodes = []
        self.retries = {}
        
    def open(self, com_name):
        self.s = serial.Serial(com_name, 256000, timeout=0.1)
        self.s.write("q")
        l = recv_cmd(self.s)
        if l['type'] != 'Q':
            err = "ERROR, Please reset the adapter hardware."
            return {'r':-100, 'err':err}
        self.s.write("2")
        l = recv_cmd(self.s)
        if l['type'] != 'Q':
            err = "Adapter version wrong! "
            return {'r':-100, 'err':err}
        return {'r':0, 'err':''}
    
    def close(self):
        if self.s is not None:
            self.s.close()
            self.s = None
            self.nodes = []
        self.err = ""

    def connect(self, max_nodes):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
            
        if max_nodes > 1:
            nodes = connect(self.s, timeout = 10, maxnode=max_nodes)
        else:
            nodes = connect(self.s, timeout = 120, maxnode=max_nodes)
            
        self.nodes = nodes
        self.retries = {}
        for a in nodes:
            self.retries[a] = 0
        err = ''
        return {"r":0, "err":err, "nodes_cnt":len(nodes)}

    def get_hwinfo(self):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        rs = stdcmd(self.s, "v", self.nodes, self.retries)
        v = check_all_responses(rs, self.nodes)
        if len(v['r']) != 6 or len(v['n']) != 0:
            err = "Version inconsistant. Abort (%s)" % (v['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        v = v['r']
        ver = ord(v[0])
        chip = ord(v[1])
        flash = v[2:6].encode("HEX")
        battery = (ord(v[3])*256+ord(v[4]))/4096.0 * 3.6
		
        rs = stdcmd(self.s, "f3", self.nodes, self.retries)
        v = check_all_responses(rs, self.nodes)
        if len(v['r']) == 0 or len(v['n']) != 0 or ord(v['r'][0]) != 3:
            err = "Hardware version inconsistant."
            return {"r":-200, "err":err}
        hwver = v['r'][2:4].encode("HEX")
        
        err = ""
        return {"r":0, "err":err, "blver":ver, "chip":chip, "hwver":hwver, "flash":flash, "battery": battery}

    def get_addrinfo(self):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        rs = stdcmd(self.s, "f1", self.nodes, self.retries)
        v = check_all_responses(rs, self.nodes)
        if len(v['r']) == 0 or len(v['n']) != 0 or ord(v['r'][0]) != 1:
            err = "Addr inconsistant."
            return {"r":-200, "err":err}
        addr = v['r'][2:6].encode("HEX")

        rs = stdcmd(self.s, "f2", self.nodes, self.retries)
        v = check_all_responses(rs, self.nodes)
        if len(v['r']) == 0 or len(v['n']) != 0 or ord(v['r'][0]) != 2:
            print "Calibration info wrong."
            calinfo = ""
        else:
            calinfo = v['r'][2:6].encode("HEX")
            
        rs = stdcmd(self.s, "f4", self.nodes, self.retries)
        v = check_all_responses(rs, self.nodes)
        if len(v['r']) == 0 or len(v['n']) != 0 or ord(v['r'][0]) != 4:
            err = "Firmware version inconsistant."
            return {"r":-200, "err":err}
        fwver = v['r'][2:6].encode("HEX")
        
        err = ""
        return {"r":0, "err":err, "fwver":fwver, "addr":addr, "calinfo":calinfo}
        
    def write_protect(self, enable):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
        
        if enable.lower() == "enable":
            r = stdcmd(self.s, "P", self.nodes, self.retries, 1)
        elif enable.lower() == "disable":
            r = stdcmd(self.s, "p", self.nodes, self.retries, 1)
        else:
            err = "Wrong param."
            return {"r":-100, "err":err}
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = enable + " WP error. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)
        
        err = ""
        return {"r":0, "err":err}

    def set_info(self, addr = None, prikey = None, fwver = None):
        # addr should be integer or string. 1 = '\x01\x00\x00\x00'
        # prikey and fwver should be strings
    
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        r = stdcmd(self.s, "d", self.nodes, self.retries)
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = "Fetch device config failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)

        if addr is not None:
            if len(self.nodes) > 1:
                err = "Cannot set addr to multiple nodes."
                return {"r":-200, "err":err}
            if isinstance(addr, str):
                r = stdcmd(self.s, "F1" + addr + "\x00" * 12, self.nodes, self.retries, 1)
            else:
                r = stdcmd(self.s, "F1" + struct.pack("L", addr) + "\x00" * 12, self.nodes, self.retries, 1)
            r = check_all_responses(r, self.nodes)
            if not len(r['r']) or ord(r['r'][0]) != 10:
                err = "Update addr failed. Abort (%s)" % (r['n'][0].encode("hex"))
                return {"r":-200, "err":err}
            elif len(r['n']) != 0:
                for bn in r['n']:
                    self.nodes.remove(bn)

        if prikey is not None:
            if len(self.nodes) > 1:
                err = "Cannot set prikey to multiple nodes."
                return {"r":-200, "err":err}
            r = stdcmd(self.s, "F2" + prikey, self.nodes, self.retries, 1)
            r = check_all_responses(r, self.nodes)
            if not len(r['r']) or ord(r['r'][0]) != 10:
                err = "Update prikey failed. Abort (%s)" % (r['n'][0].encode("hex"))
                return {"r":-200, "err":err}
            elif len(r['n']) != 0:
                for bn in r['n']:
                    self.nodes.remove(bn)

        if fwver is not None:
            r = stdcmd(self.s, "F4" + fwver + "\x00" * 12, self.nodes, self.retries, 1)
            r = check_all_responses(r, self.nodes)
            if not len(r['r']) or ord(r['r'][0]) != 10:
                err = "Update fwver failed. Abort (%s)" % (r['n'][0].encode("hex"))
                return {"r":-200, "err":err}
            elif len(r['n']) != 0:
                for bn in r['n']:
                    self.nodes.remove(bn)
                    
        r = stdcmd(self.s, "D", self.nodes, self.retries)
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = "Commit device config failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)

        err = ""
        return {"r":0, "err":err}

    def set_hwver(self, hwver):
        # hwver should be string
    
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
            
        r = stdcmd(self.s, "d", self.nodes, self.retries)
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = "Fetch device config failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)

        r = stdcmd(self.s, "F3" + hwver + "\x00" * 14, self.nodes, self.retries, 1)
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = "Update hwver failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)

        r = stdcmd(self.s, "D", self.nodes, self.retries)
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = "Commit device config failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)

        err = ""
        return {"r":0, "err":err}
        
    def run_app(self):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
        
        r = stdcmd(self.s, "g", self.nodes, self.retries)
        r = check_all_responses(r, self.nodes)
        if len(r['n']):
            err = "Run app failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}

        err = ""
        return {"r":0, "err":err}

    def set_iv(self, iv):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
        
        r = stdcmd(self.s, "i" + iv, self.nodes, self.retries)
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = "Set IV failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)

        err = ""
        return {"r":0, "err":err}
        
    def flash_erase(self, addr):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        r = stdcmd(self.s, "e" + struct.pack('L', addr), self.nodes, self.retries)
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = "Erase failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)

        err = ""
        return {"r":0, "err":err}
        
    def flash_write(self, addr, dat):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        r = stdcmd(self.s, "w" + struct.pack('L', addr) + dat, self.nodes, self.retries)
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = "Write failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)

        err = ""
        return {"r":0, "err":err}
        
    def flash_write_longwait(self, addr, dat):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        r = stdcmd(self.s, "W" + struct.pack('L', addr) + dat, self.nodes, self.retries)
        r = check_all_responses(r, self.nodes)
        if not len(r['r']) or ord(r['r'][0]) != 10:
            err = "Write failed. Abort (%s)" % (r['n'][0].encode("hex"))
            return {"r":-200, "err":err}
        elif len(r['n']) != 0:
            for bn in r['n']:
                self.nodes.remove(bn)

        err = ""
        return {"r":0, "err":err}

    def signal_test(self, channel = 0):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        rr = {}
        rr['r'] = 0
        rr['lost'] = {}
        for a in self.nodes:
            single_node_retry = 10
            while single_node_retry > 0:
                self.s.write("s" + chr(channel) + "-" + a[::-1])
                l = recv_cmd(self.s)
                if l['type'] != 'B':
                    print "ERROR, cannot start command."
                    print l['raw']
                    break
                l = recv_cmd(self.s, time() + 2)
                if l['type'] == 'D':
                    rr['lost'][a] = {}
                    rr['lost'][a]['total'] = struct.unpack(">H", l[1])[0]
                    rr['lost'][a][0] = struct.unpack(">H", l[2])[0]
                    rr['lost'][a][1] = struct.unpack(">H", l[3])[0]
                    rr['lost'][a][2] = struct.unpack(">H", l[4])[0]
                    if rr['lost'][a]['total'] < 450:
                        break
                    else:
                        single_node_retry -= 1
                else:
                    print "ERROR, test reply wrong."
                    break
        return rr
        
    def test_nrf(self):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
			
        if len(self.nodes) != 1:
            err = "Cannot process multiple nodes."
            return {"r":-200, "err":err}
	
        target_addr = self.nodes[0]
        receive_count = 0
#        print "time:" + str(time())
        print "entering wireless quality test..."
		
        for i in range(0,100):
            self.s.write("v")
            self.s.write("-" + target_addr[::-1])
            l = recv_cmd(self.s, time() + 1)
            if l['type'] != 'B':
                #print "receive err: " + l['type']
                continue		
            l = recv_cmd(self.s, time() + 1)
            if l['type'] == 'D':
                receive_count = receive_count + 1
#               print "count:" + str(receive_count)
#           else:
#               print "receive err: " + l['type']

            #now if test pass 80%, regard it as good
            if (i + 1 - receive_count) > 20:
                print ""
                print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                print "!!!!!! Wireless Quality Bad !!!!!!!!"
                print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                print ""
                return (i + 1 - receive_count)
			
#        print "time:" + str(time())
#        print "receive count:" + str(receive_count)
        print "quality test pass!"
        print "err count:" + str(100 - receive_count)
        return (100 - receive_count)
