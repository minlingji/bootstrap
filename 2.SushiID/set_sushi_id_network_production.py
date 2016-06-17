#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, serial, struct, json, os, fnmatch
# from Crypto.Cipher import AES
import time
from datetime import datetime
from pybootloader import *

BLVER = 2
FILE_PATH = 'label_dont_touch/'
HWVER = '0801'

def press_enter_continue():
    print "请按回车键继续...".decode("utf8")
    raw_input()
    
def check_source_file():
    source_file_counter = 0
    source_db_name = ''
    for root,dirnames,filenames in os.walk(os.path.join(os.getcwd(), FILE_PATH)):
        for filename in fnmatch.filter(filenames, '*.csv'):
            file_name_content = filename.split('.')
            if(len(file_name_content) != 5):
                continue
            if file_name_content[3].isdigit():
                source_db_name = filename
                source_file_counter = source_file_counter + 1

    if source_file_counter != 1:
        print "源文件有问题！！！请于幻腾工作人员联系！！！！".decode("utf8")
        return 0

    return source_db_name

def get_dirname():
    current_dir = os.getcwd()
    dir_content = current_dir.split('\\')
    name_index = 0
    for item in dir_content:
        if item[0:10] == 'Production':
            break
        name_index = name_index + 1
    if name_index > len(dir_content):
        print "文件夹内容损坏，请与幻腾工作人员联系".decode("utf8")
        return 0
    folder_name = dir_content[name_index] + dir_content[name_index + 1]
    return folder_name
	
#coding=utf-8
def result_is_first_use(path, file):
    for root, dirs, files in os.walk(path):
        if file in files:
            return 0
    
    return 1

def get_line_infos(l):
    OUTPUT_COLUMN_NUM = 4
    line = l.strip()
    content = line.split(',')
    if(len(content) != OUTPUT_COLUMN_NUM):
        print "文件出错！！！错误类型为1，请与幻腾工作人员联系！！！".decode("utf8")
        raise Exception("Phantom Production type 1")

    return content
    
def get_last_producted_unumber(path, file):
    #need to handle: 1. file not exit. 2. file empty. 3. file with corrupted data
    if(result_is_first_use(path, file)):
        return 0
    else:
        for line in reversed(open(path + file).readlines()):
            lastline = line
            line_content = get_line_infos(lastline)
            if(line_content != 0) and (line_content[2] == '0'):
                unumber = line_content[1]
                return unumber
                
    return 0
        
def get_infos(path, infile, resultfile):
    #this function is intended to return 1. unumber 2. addr 3. qr 4. private keys
    #this should find the first unused line in input file automatically
    #should know if it is first used, or has value already
    lastunumber = get_last_producted_unumber(path, resultfile)
    f = open(path+infile,"r")
    if (lastunumber != 0):
        count = 0
        for line in f:
            count = count + 1
            line_content = get_line_infos(line)
            if(line_content[0] == lastunumber):
                break
            
        if (count >= int(infile.split('.')[1])):
            print "文件出错！！！错误类型为2，请与幻腾工作人员联系！！！".decode("utf8")
            raise Exception("Phantom Production type 2")
        
    line = f.next().strip()
    content = line.split(',')
    return content
    
def log_out(path, file, unumber = '0', result = 0, info = '0'):
    #0:success. 1:
    f = open(path+file,"a")
    write_content = str(datetime.now()) + ',' + unumber + ',' + str(result) + ',' + info + '\n'
    f.write(write_content)
    f.close()

def check_input_availability(file):
    use_before = int(file.split('.')[3])
    current_time = int(time.time())
    if(current_time > use_before):
        print "文件出错！！！错误类型为3，请与幻腾工作人员联系！！！".decode("utf8")
        raise Exception("Phantom Production type 3")
    else:
        return

def check_input_format(unumber, private_key, addr):
    if len(unumber) != 10:
        print "文件出错！！！错误类型为4，请与幻腾工作人员联系！！！".decode("utf8")
        print "unumber Error !!!!!!!!!!!!"
        return -1
    if len(private_key) != 32 or not (addr > 0 or addr < 256**4):
        print "文件出错！！！错误类型为5，请与幻腾工作人员联系！！！".decode("utf8")
        print "addr or prikey Error !!!!!!!!!!!!!!!"
        return -1
    return 0

def setid(comport, input_content, logout_path, logout_file):
    private_key = input_content[1]
    addr = int(input_content[2])
    unumber = input_content[0]
    qr = input_content[3]
    
    result = check_input_format(unumber, private_key, addr)
    if(result < 0):
        return -1

    pkey = private_key.decode("hex")
    
    if BLVER == 1:
        b = Bootloader_v1.Bootloader()
    elif BLVER == 2:
        b = Bootloader_v2.Bootloader()
    else:
        raise Exception("Bootloader Version Unspecified. ")

    r = b.open(comport)
    if r['r'] < 0:
        print "幻腾Adapter连接有问题，请检查COM口是否正常".decode("utf8")
        print "Adapter com port error: %s !!!!!!!!!!!!!" % r['err']
        return -1
        
    while 1:
        # wait for a capable device!
        # abort previous connection and begin new connection
        r = b.connect(max_nodes = 1)
        if r['r'] < 0:
            print "设备连接错误，请重新上电设备重试".decode("utf8")
            print "Error: %s" % r['err']
            log_out(logout_path, logout_file, unumber, 1)
            continue
        print "%d nodes connected." % r['nodes_cnt']
        if r['nodes_cnt'] == 0:
            print "设备连接错误，请重新上电设备重试".decode("utf8")
            log_out(logout_path, logout_file, unumber, 2)
            print "Abort."
            return -1
        # now connected

        # get bootloader version
        r = b.get_hwinfo()
        if r['r'] < 0:
            print "读取设备信息失败，请重新上电设备重试".decode("utf8")
            log_out(logout_path, logout_file, unumber, 3)
            b.run_app()
            continue
        chips = ["LOW-PWR", "STM32MD", "RESV", "STM32CONN", "STM8MD"]
        print "Bootloader version: %d" % r['blver']
        print "Chip type: %d (%s)" % (r['chip'], chips[r['chip']])
        print "HW version: %s" % r['hwver']        
        bat = r['battery']
        print "bat = %.2fV"%bat
        
        if ((BLVER == 1 and r['hwver'] != 'FFFF') or (BLVER == 2)) and HWVER.upper() != r['hwver']:
            print "设备类型不符，请检查是否使用了正确的生产脚本".decode("utf8")
            log_out(logout_path, logout_file, unumber, 4)
            b.run_app()
            continue        
            
        if bat < 3.0 : 
            print "电池电量过低！！！！请更换电池！！！".decode("utf8")
            log_out(logout_path, logout_file, unumber, 20)
            # start app
            r = b.run_app()
            if r['r'] < 0:
                print "运行设备失败，请重新上电设备重试，并使用强制刷入新地址脚本".decode("utf8")
                log_out(logout_path, logout_file, unumber, 15)
                print "Error: %s" % r['err']
                return -1
            continue 

        # get address version
        r = b.get_addrinfo()
        if r['r'] < 0:
            print "获取设备地址失败，请重新上电设备重试".decode("utf8")
            log_out(logout_path, logout_file, unumber, 5)
            b.run_app()
            continue
        print "Addr: %s" % r['addr']
        print "FW version: %s" % r['fwver']
        print "Calibration Info: %s" % r['calinfo']
        cali_info = r['calinfo']

        if r['addr'].lower() != "ffffffff" and "override" not in sys.argv:
            print "设备地址已存在，请使用强制刷入新地址脚本".decode("utf8")
            log_out(logout_path, logout_file, unumber, 6)
            b.run_app()
            continue
        
        # check firmware
        if r['fwver'].lower()[4:8] == "ffff" and "override" not in sys.argv:
            print "固件版本不正确，请使用强制刷入新地址脚本".decode("utf8")
            log_out(logout_path, logout_file, unumber, 7)
            b.run_app()
            continue
            
        flag_success = 0 
        
        # disable wp
        r = b.write_protect('disable')
        if r['r'] < 0:
            print "解写保护失败，请重新上电设备重试，并使用强制刷入新地址脚本".decode("utf8")
            log_out(logout_path, logout_file, unumber, 10)
            return -1
        # now wp disabled

        r = b.set_info(addr = addr, prikey = pkey)
        if r['r'] < 0:
            print "刷入地址失败，请重新上电设备重试，并使用强制刷入新地址脚本".decode("utf8")
            log_out(logout_path, logout_file, unumber, 11)
            return -1
        if BLVER == 1:
            print "V1 bootloader. Set HWVER to %s" % HWVER
            r = b.set_hwver(hwver = HWVER.decode("hex"))
            if r['r'] < 0:
                print "Error: %s" % r['err']
                return -1

        r = b.get_addrinfo()
        if r['r'] < 0:
            print "获取设备地址失败，请重新上电设备重试，并使用强制刷入新地址脚本".decode("utf8")
            log_out(logout_path, logout_file, unumber, 12)
            return -1
        print "Addr: %s" % r['addr']
        print "FW version: %s" % r['fwver']

        newaddr = r['addr'].decode("hex")

        if newaddr != struct.pack("L", addr):
            print "本次刷入新地址有问题！！！请重新上电设备重试，并使用强制刷入新地址脚本".decode("utf8")
            log_out(logout_path, logout_file, unumber, 13)
            return -1
        else:
            flag_success = 1
            
        # Enable wp
        r = b.write_protect('enable')
        if r['r'] < 0:
            print "写保护失败，请重新上电设备重试，并使用强制刷入新地址脚本".decode("utf8")
            log_out(logout_path, logout_file, unumber, 14)
            print "Error: %s" % r['err']
        # now wp Enabled
        
        # start app
        r = b.run_app()
        if r['r'] < 0:
            print "运行设备失败，请重新上电设备重试，并使用强制刷入新地址脚本".decode("utf8")
            log_out(logout_path, logout_file, unumber, 15)
            print "Error: %s" % r['err']
            return -1

        b.close()

        
        if flag_success == 0:
            print "本次刷入新地址有问题！！！请重新上电设备重试，并使用强制刷入新地址脚本".decode("utf8")
            continue 
        else :
            print "开始打印二维码，请等待".decode("utf8")
            print "Now printing sticker with QR: "+qr+ " and SN: "+unumber
            file = open("label_dont_touch/qr.txt", "w")
            file.write('http://huantengsmart.com/qr/'+qr)
            file.close()            
            file1 = open("label_dont_touch/unumber.txt", "w")
            file1.write(unumber)
            file1.close()
            
            oserr = os.system('""bartend.exe" /F=30x40-sushi.btw /P"')
            print "Bartender Result" + str(oserr)
            log_out(logout_path, logout_file, unumber, 0, cali_info) #yeah! success
            print """       #######  ##    ## 
              ##     ## ##   ##  
              ##     ## ##  ##   
              ##     ## #####    
              ##     ## ##  ##   
              ##     ## ##   ##  
               #######  ##    ## 
               """
            return 0

def main():
    if (len(sys.argv) < 2):
        print "%s com3" % sys.argv[0]
        return

    input_file = check_source_file()
    output_file = input_file.split('.')
    print "生产批次号：".decode("utf8") + output_file[0]
    output_file = '.'.join(output_file[0:-1]) + '.result.' + output_file[-1]

    while (1):
        input_content = get_infos(FILE_PATH, input_file, output_file)
        r = setid(sys.argv[1], input_content, FILE_PATH, output_file)
        if r == 0:
            time.sleep(1)
            os.system('cls')
        else:
            press_enter_continue()

        if 'override' in sys.argv:
            break                
if __name__ == "__main__":
    main()
