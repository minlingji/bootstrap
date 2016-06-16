#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, serial, struct
import time
import os

def recv_cmd(s, timeout = 0):
    rr = {}
    while 1:
        if timeout and time.time() > timeout:
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

def connect(ser, timeout = 120, maxnode = 127):
    print "Waiting for %d secs for %d nodes max." % (timeout, maxnode)

    ser.write("c" + chr(maxnode))
    l = recv_cmd(ser)
    if l['type'] != 'B':
        print "ERROR, cannot start connection."
        return -1

    print "Connecting...",

    rr = []
    if timeout:
        timeout = timeout + time.time()
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

def stdcmd(ser, cmd, addrlist, force_unicast = 0):
    if isinstance(addrlist, basestring):
        addrlist = [addrlist]
    alist = addrlist[:]
    rr = {}

    #print ("Command %s(%d)..." %(cmd[0], len(addrlist))),
    node_cnt = len(alist)
    b = 0
    while len(alist) >= 3 and b <= 2 and not force_unicast:
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
        ser.write(cmd)
        ser.write("-" + a[::-1])
        l = recv_cmd(ser)
        if l['type'] != 'B':
            print "ERROR, cannot start command."
            print l['raw']
            return rr
        r = r + 1
        l = recv_cmd(ser, time.time() + 0.5)
        if l['type'] == 'D':
            alist.remove(a)
            rr[a] = l[1]
            r = 0
            #print (l['raw'] + "; "),
        elif l['type'] == 'Q' or l['type'] == 'TO':
            if r > 20:
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

def print_seccuss():
    print """
     #####  #     #  #####   #####  #######  #####   #####     ###
    #     # #     # #     # #     # #       #     # #     #    ###
    #       #     # #       #       #       #       #          ###
     #####  #     # #       #       #####    #####   #####      #
          # #     # #       #       #             #       #
    #     # #     # #     # #     # #       #     # #     #    ###
     #####   #####   #####   #####  #######  #####   #####     ###

    """

def print_low_power():
    print "电池电量低!!!不合格!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!".decode("utf8")

def main():
    if (len(sys.argv) < 2):
        print "download.py com1 [addr]"
        return

    while(1):
        s = serial.Serial(sys.argv[1], 256000, timeout=0.1)
        s.write("q")
        l = recv_cmd(s)
        if l['type'] != 'Q':
            print "ERROR, Please reset the adapter hardware."
            return
        s.write("2")
        l = recv_cmd(s)
        if l['type'] != 'Q':
            print "Adapter version wrong! "
            return
        nodes = connect(s, timeout = 120, maxnode=1)
        os.system('cls')
        print "%d nodes connected. " % len(nodes)
        if len(nodes) == 0:
            print "Abort."

        vs = stdcmd(s, "v", nodes)
        if len(vs) == 0:
            print "Version error, try again."
        if not len(vs) == 0:
            ver = ord(vs[0])
            chip = ord(vs[1])
            chips = ["LOW-PWR", "STM32MD", "RESV", "STM32CONN", "STM8MD"]
            bat = (ord(vs[3])*256+ord(vs[4]))/4096.0 * 3.6
            print "Bootloader version: %d" % ver
            print "Chip type: %d (%s)" % (chip, chips[chip])
            print "电池电量 = %.2fV".decode("utf8") % bat

            r = stdcmd(s, "d", nodes)
            if not len(r):
                print "Fetch device config error"
            r = stdcmd(s, "f1", nodes)
            if len(r) and ord(r[0]) == 1:
                print "Current Address: " + r[2:6].encode("HEX")
            else:
                print "Get Address error."
            r = stdcmd(s, "f3", nodes)
            if len(r) and ord(r[0]) == 3:
                print "Hardware version: " + r[2:4].encode("HEX")
            else:
                print "Get Hardware version error."
            r = stdcmd(s, "f4", nodes)
            if len(r) and ord(r[0]) == 4:
                print "Firmware version: " + r[2:6].encode("HEX")
            else:
                print "Get Firmware version error."

            # start app
            i = 1
            while(i==1):
                r = stdcmd(s, "g", nodes)
                if not r == {}:
                    print "Run App OK"
                    break
                if  r == {}:
                    i = 0
                    print "Run App error, reset and try again"
                    break
                i -= 1

            time.sleep(0.5)

            if not r == {} and bat > 3.0 :
                print_seccuss()
            if not bat > 3.0 :
                print_low_power()

        s.close()

if __name__ == "__main__":
    main()
