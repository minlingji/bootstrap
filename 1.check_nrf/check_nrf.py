#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, serial, struct
import time
import os
from pybootloader import Bootloader_v2

BLVER = 2
SIGNAL_TEST_ENABLE = 1
SIGNAL_LOST_THRESHOLD_TOTAL = 15
SIGNAL_LOST_THRESHOLD_SEPARATE = 10

BATTERY_TEST_ENABLE = 1
BATTERY_THRESHOLD = 3.0

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

def press_enter_continue():
    print "请按回车键继续...".decode("utf8")
    raw_input()

def main():
    if (len(sys.argv) < 2):
        print "check_nrf.py comN [addr]"
        return

    while(1):
        if BLVER == 1:
            b = Bootloader_v1.Bootloader()
        elif BLVER == 2:
            b = Bootloader_v2.Bootloader()
        else:
            raise Exception("Bootloader Version Unspecified. ")
        r = b.open(sys.argv[1])
        if r['r'] < 0:
            print ("Adapter连接失败: %s" % r['err']).decode("utf8")
            return
   
        try:
            r = b.connect(max_nodes = 1)
            if r['r'] < 0:
                print "无设备连接，退出".decode("utf8")
                return
        except KeyboardInterrupt:
            print "Exit"
            return
        
        # get bootloader version
        r = b.get_hwinfo()
        if r['r'] < 0:
            print "Get HW Info Error: %s" % r['err']
            b.run_app()
            b.close()
            press_enter_continue()
            continue
            
        print "Bootloader version: %d" % r['blver']
        print "Chip type: %d" % r['chip']
        print "HW version: %s" % r['hwver']
        print "Battery: %.2fV" % r['battery']

        if BATTERY_TEST_ENABLE and r['battery'] < BATTERY_THRESHOLD :
            print_low_power()
            b.run_app()
            b.close()
            press_enter_continue()
            continue
        
        # get address version
        r = b.get_addrinfo()
        if r['r'] < 0:
            print "Get Addr Info Error: %s" % r['err']
            b.run_app()
            b.close()
            press_enter_continue()
            continue
            
        print "Addr: %s" % r['addr']
        print "FW version: %s" % r['fwver']
        if 'calinfo' in r:
            print "Calibration info: %s" % r['calinfo']
        
        if SIGNAL_TEST_ENABLE and BLVER == 2:
            signal_good = 1
            for c in range(0, 128, 32):
                # signal test
                r = b.signal_test(c)
                if r['r'] == 0:
                    for a in r['lost']:
                        sig = r['lost'][a]
                        break
                    if sig['total']/4.5 > SIGNAL_LOST_THRESHOLD_TOTAL or sig[0]/1.5 > SIGNAL_LOST_THRESHOLD_SEPARATE or sig[1]/1.5 > SIGNAL_LOST_THRESHOLD_SEPARATE or sig[2]/1.5 > SIGNAL_LOST_THRESHOLD_SEPARATE:
                        print "Channel %d: T/ %s%% A/ %s%% B/ %s%% C/ %s%%" % (c, format(sig['total']/4.5, '.2f'), format(sig[0]/1.5, '.2f'), format(sig[1]/1.5, '.2f'), format(sig[2]/1.5, '.2f'))
                        print "设备通信质量太差了不合格".decode("utf8")
                        signal_good = 0
                        break
                        #print "%d %s %s %s %s" % (c, format(r['lost'][a]['total']/4.5, '.2f'), format(r['lost'][a][0]/1.5, '.2f'), format(r['lost'][a][1]/1.5, '.2f'), format(r['lost'][a][2]/1.5, '.2f'))
                else:
                    print "测试通信质量过程出错，请重新上电设备重试".decode("utf8")
                    signal_good = 0
                    break
            if not signal_good:
                b.run_app()
                b.close()
                press_enter_continue()
                continue

        # start app
        r = b.run_app()
        if r['r'] < 0:
            print "Run App Error: %s" % r['err']
            b.close()
            press_enter_continue()
            continue

        b.close()
        
        print_seccuss()
        time.sleep(1)
        os.system('cls')

if __name__ == "__main__":
    main()
