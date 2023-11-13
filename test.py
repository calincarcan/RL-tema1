#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

def calin():
    return 'calin'

def main():
    i = 0
    while True:
        i = i + 1
        if i==5:
            continue
        if i == 10:
            break;
        print(i)

        
if __name__ == "__main__":
    main()
