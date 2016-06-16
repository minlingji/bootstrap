import serial, struct

def recv(s):
    r = ""
    while 1:
        c = s.read()
        if len(c)==0 : break
        r += c
    #print r,
    return r

def recv_wait_line(s):
    while 1:
        r = s.readline()
        if len(r): break
    #print r,
    return r

def stdcmd(s, cmd, retries):
    t = 0
    retry = 100
    while(retry):
        retries['\xde\xad\xbe\xef'] += 1
        s.write(cmd)
        l = recv_wait_line(s)
        l = recv_wait_line(s)
        if not l.startswith('NR'):
            retries['\xde\xad\xbe\xef'] -= 1
            break
        retry -= 1
        t += 1
    if retry is 0:
        err = "No reply."
        return {"r":-200, "err":err}
    err = ""
    return {"r":0, "err":err, "retry":t, "str":l}
    
class Bootloader:
    
    def __init__(self):
        self.nodes = []
        self.retries = {}
        self.s = None
        
    def open(self, com_name):
        self.nodes = []
        self.s = serial.Serial(com_name, 256000, timeout=0.1)
        self.s.write("q")
        l = recv(self.s)
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

        self.s.write("c")
        l = recv_wait_line(self.s)
        print l.strip(),
        l = recv_wait_line(self.s)
        if not l.startswith("OK!"):
            err = "Connection error. "
            return {"r":-200, "err":err}
        self.nodes = ['\xde\xad\xbe\xef']
        self.retries = {'\xde\xad\xbe\xef': 0}
        err = ""
        return {"r":0, "err":err, "nodes_cnt":1} # 1 node connected
        
    def get_hwinfo(self):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        r1 = stdcmd(self.s, "v", self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        ver = int(l[0:2], 16)
        chip = int(l[2:4], 16)
            
        r1 = stdcmd(self.s, "f3", self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        hwver = l[0:4]

        err = ""
        return {"r":0, "err":err, "blver":ver, "chip":chip, "hwver":hwver}
        
    def get_addrinfo(self):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        r1 = stdcmd(self.s, "f1", self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        addr = l[0:8]

        r1 = stdcmd(self.s, "f4", self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        fwver = l[0:8]

        err = ""
        return {"r":0, "err":err, "fwver":fwver, "addr":addr}
    
    def write_protect(self, enable):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
        
        if enable.lower() == "enable":
            self.s.write("P")
        elif enable.lower() == "disable":
            self.s.write("p")
        else:
            err = "Wrong param."
            return {"r":-100, "err":err}
        l = recv_wait_line(self.s)
        l = recv_wait_line(self.s)
        l = recv_wait_line(self.s)
        if not l.startswith("OK"):
            err = enable + " WP error."
            return {"r":-200, "err":err}
        err = ""
        return {"r":0, "err":err}

    def set_info(self, addr = None, prikey = None, fwver = None):
        # addr should be integer or string. 1 = '\x01\x00\x00\x00'
        # prikey and fwver should be strings
    
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
            
        r1 = stdcmd(self.s, "d", self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        if not l.startswith("D"):
            err = "Fetch device config error"
            return {"r":-200, "err":err}
        
        if addr is not None:
            if isinstance(addr, str):
                r1 = stdcmd(self.s, "F1" + addr + "\x00" * 12, self.retries)
            else:
                r1 = stdcmd(self.s, "F1" + struct.pack("L", addr) + "\x00" * 12, self.retries)
            if r1['r'] < 0:
                return r1
            l = r1['str']
            if not l.startswith("D"):
                err = "Set ADDR error"
                return {"r":-201, "err":err}
        
        if prikey is not None:
            r1 = stdcmd(self.s, "F2" + prikey, self.retries)
            if r1['r'] < 0:
                return r1
            l = r1['str']
            if not l.startswith("D"):
                err = "Set PRIKEY error"
                return {"r":-201, "err":err}

        if fwver is not None:
            r1 = stdcmd(self.s, "F4" + fwver + "\x00" * 12, self.retries)
            if r1['r'] < 0:
                return r1
            l = r1['str']
            if not l.startswith("D"):
                err = "Set FWVER error"
                return {"r":-201, "err":err}

        r1 = stdcmd(self.s, "D", self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        if not l.startswith("D"):
            err = "Commit device config error"
            return {"r":-200, "err":err}

        err = ""
        return {"r":0, "err":err}
        
    def set_hwver(self, hwver):
        # hwver should be string
    
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
            
        r1 = stdcmd(self.s, "d", self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        if not l.startswith("D"):
            err = "Fetch device config error"
            return {"r":-200, "err":err}

        if hwver is not None:
            r1 = stdcmd(self.s, "F3" + hwver + "\x00" * 14, self.retries)
            if r1['r'] < 0:
                return r1
            l = r1['str']
            if not l.startswith("D"):
                err = "Set HWVER error"
                return {"r":-201, "err":err}

        r1 = stdcmd(self.s, "D", self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        if not l.startswith("D"):
            err = "Commit device config error"
            return {"r":-200, "err":err}

        err = ""
        return {"r":0, "err":err}

    def run_app(self):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}
            
        r1 = stdcmd(self.s, "g", self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        if not l.startswith("D"):
            err = "Run app error"
            return {"r":-200, "err":err}

        err = ""
        return {"r":0, "err":err}
    
    def set_iv(self, iv):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        r1 = stdcmd(self.s, "i" + iv, self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        if not l.startswith("D"):
            err = "Set-IV failed"
            return {"r":-200, "err":err}

        err = ""
        return {"r":0, "err":err, "retry": r1['retry']}
    
    def flash_erase(self, addr):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        r1 = stdcmd(self.s, "e" + struct.pack('L', addr), self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        if not l.startswith("D"):
            err = "Erase failed @ %d" % addr
            return {"r":-200, "err":err}

        err = ""
        return {"r":0, "err":err, "retry": r1['retry']}

    def flash_write(self, addr, dat):
        if self.s is None:
            err = "Com port not open."
            return {"r":-100, "err":err}

        r1 = stdcmd(self.s, "w" + struct.pack('L', addr) + dat, self.retries)
        if r1['r'] < 0:
            return r1
        l = r1['str']
        if not l.startswith("D"):
            err = "Write failed @ %d" % addr
            return {"r":-200, "err":err}

        err = ""
        return {"r":0, "err":err, "retry": r1['retry']}
