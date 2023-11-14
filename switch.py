#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

global root_bridge_ID, root_path_cost, own_bridge_ID
global interfaces, interface_state, vlan, table

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec():
    # TODO Send BDPU every second if necessary
    while True:
        if own_bridge_ID == root_bridge_ID:
            for interface in interfaces:
                if vlan.get(get_interface_name(interface)) != 'T':
                    continue
                mac_cast = struct.pack('!BBBBBB', 0x01, 0x80, 0xc3, 0x00, 0x00, 0x00)
                own_bid = struct.pack('!q', own_bridge_ID)
                root_bid = struct.pack('!q', root_bridge_ID)
                cost_path = struct.pack('!I', root_path_cost)
                data = mac_cast + own_bid + root_bid + cost_path
                send_to_link(interface, data, len(data))
                print('sent BDPU on interface ', interface, ' with data ', data, ' and length ', len(data))
        time.sleep(1)

def is_Unicast(mac):
    return mac[0] & 1 == 0
    # return mac != b'\xff\xff\xff\xff\xff\xff'

def init_resources():
    table = {}
    vlan = {}
    switch_id = sys.argv[1]
    own_bridge_ID = root_bridge_ID = -1
    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)
    interface_state = [True] * num_interfaces

    name = 'configs/switch'+switch_id+'.cfg'
    
    f = open(name, 'r')
    own_bridge_ID = f.readline().strip()
    own_bridge_ID = int(own_bridge_ID)
    root_bridge_ID = own_bridge_ID
    root_path_cost = 0

    for line in f:
        line = line.strip()
        print('line: ', line)
        vlan.update({line.split()[0]: line.split()[1]})

    print("# Starting switch with id {}".format(switch_id), flush=True)
    print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))
    print(vlan)

    # for interface in interfaces:
    #     if vlan.get(get_interface_name(interface)) == 'T':
    #         interface_state[interface] = False
    
    return table, vlan, switch_id, own_bridge_ID, root_bridge_ID, root_path_cost, num_interfaces, interfaces, interface_state

    # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
    # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"

def inspect(dest_mac, src_mac, ethertype, vlan_id, interface, length):
    # Print the MAC src and MAC dst in human readable format
    p_dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
    p_src_mac = ':'.join(f'{b:02x}' for b in src_mac)
    print(f'Destination MAC: {p_dest_mac}')
    print(f'Source MAC: {p_src_mac}')
    print(f'EtherType: {ethertype}')
    print('VLAN_ID: ', vlan_id)
    print('ETHERTYPE: ', ethertype)
    print("Received frame of size {} on interface {}".format(length, interface), flush=True)

def translate_trunk(vlan: str) -> int:
    if vlan == 'T':
        return 0
    return int(vlan)

def trunk_forwarding(dest_mac, vlan_id: int, interface, data, length, table, vlan, interfaces):
    notag_data = data[0:12] + data[16:]
    print('TRUNK Forwarding')
    if is_Unicast(dest_mac):
        print('Unicast')
        if dest_mac in table:
            vlan_path = vlan.get(get_interface_name(table.get(dest_mac)))
            vlan_path = translate_trunk(vlan_path)
            # pachetul se duce pe trunk
            if vlan_path == 0:
                send_to_link(table.get(dest_mac), data, length)
                print('sent to trunk next hop')
            else:
                send_to_link(table.get(dest_mac), notag_data, length - 4)
                print('sent to acces next hop')
        else:
            print('broadcast')
            for i in interfaces:
                if i == interface:
                    continue
                vlan_path = vlan.get(get_interface_name(i))
                vlan_path = translate_trunk(vlan_path)
                if vlan_path == 0:
                    send_to_link(i, data, length)
                    print('sent to trunk')
                elif vlan_path == vlan_id:
                    send_to_link(i, notag_data, length - 4)
                    print('sent to acces')
    else:
        print('Multicast')
        for i in interfaces:
            if i == interface:
                continue
            vlan_path = vlan.get(get_interface_name(i))
            vlan_path = translate_trunk(vlan_path)
            if vlan_path == 0:
                send_to_link(i, data, length)
                print('sent to trunk')
            elif vlan_path == vlan_id:
                send_to_link(i, notag_data, length - 4)
                print('sent to acces')

def access_forwarding(dest_mac, vlan_id: int, interface, data, length, table, vlan, interfaces):
    print('ACCES Forwarding')
    if is_Unicast(dest_mac):
        print('Unicast')
        if dest_mac in table:
            vlan_path = vlan.get(get_interface_name(table.get(dest_mac)))
            vlan_path = translate_trunk(vlan_path)
            # pachetul se duce pe trunk
            if vlan_path == 0:
                tagged_frame = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
                send_to_link(table.get(dest_mac), tagged_frame, length + 4)
                print('sent to trunk next hop')
            else:
                send_to_link(table.get(dest_mac), data, length)
                print('sent to acces next hop')
        else:
            print('broadcast')
            for i in interfaces:
                if i == interface:
                    continue
                vlan_path = vlan.get(get_interface_name(i))
                vlan_path = translate_trunk(vlan_path)
                if vlan_path == 0:
                    tagged_frame = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
                    send_to_link(i, tagged_frame, length + 4)
                    print('sent to trunk')
                elif vlan_path == vlan_id:
                    send_to_link(i, data, length)
                    print('sent to acces')
    else:
        print('Multicast')
        for i in interfaces:
            if i == interface:
                continue
            vlan_path = vlan.get(get_interface_name(i))
            vlan_path = translate_trunk(vlan_path)
            if vlan_path == 0:
                tagged_frame = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
                send_to_link(i, tagged_frame, length + 4)
                print('sent to trunk')
            elif vlan_path == vlan_id:
                send_to_link(i, data, length)
                print('sent to acces')

def check_for_trunk(vlan_src: int):
    return vlan_src == 0

def main():
    table, vlan, switch_id, own_bridge_ID, root_bridge_ID, root_path_cost, num_interfaces, interfaces, interface_state = init_resources()
    root_port = None

    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    while True:
        interface, data, length = recv_from_any_link()
        if interface_state[interface] == False:
            continue
        mac_cast = data[0:6]

        #           6 bytes  8 bytes  8 bytes  4 bytes
        # data = mac_cast + own_bid + root_bid + cost_path
        if mac_cast == b'\x01\x80\xc2\x00\x00\x00':
            bpdu_src_bid = data[6:14]
            bpdu_root_bid = data[14:22]
            bpdu_cost_path = data[22:26]
            bpdu_cost_path = int.from_bytes(bpdu_cost_path, byteorder='big')

            we_were_root = None
            if own_bridge_ID == root_bridge_ID:
                we_were_root = True

            if bpdu_root_bid < root_bridge_ID:
                root_bridge_ID = bpdu_root_bid
                root_path_cost = bpdu_cost_path + 10
                root_port = interface

                if we_were_root:
                    for i in interfaces:
                        if i != root_port and vlan.get(get_interface_name(i)) == 'T':
                            interface_state[i] = False

                if interface_state[root_port] == False:
                    interface_state[root_port] = True

                mac_cast = struct.pack('!BBBBBB', 0x01, 0x80, 0xc3, 0x00, 0x00, 0x00)
                own_bid = struct.pack('!q', own_bridge_ID)
                root_bid = struct.pack('!q', root_bridge_ID)
                cost_path = struct.pack('!I', root_path_cost)
                data = mac_cast + own_bid + root_bid + cost_path
                for i in interfaces:
                    if i != root_port and vlan.get(get_interface_name(i)) == 'T':
                        send_to_link(i, data, len(data))
                        print('updated BDPU on interface ', i, ' with data ', data, ' and length ', len(data))

            elif bpdu_root_bid == root_bridge_ID:
                if interface == root_port and bpdu_cost_path + 10 < root_path_cost:
                    root_path_cost = bpdu_cost_path + 10
                
                elif interface != root_port and bpdu_cost_path > root_path_cost:
                    # TODO: posibil incorect
                    interface_state[interface] = True

            elif bpdu_src_bid == own_bridge_ID:
                interface_state[interface] = False
            
            if own_bridge_ID == root_bridge_ID:
                for i in interfaces:
                    if i != root_port and vlan.get(get_interface_name(i)) == 'T':
                        interface_state[i] = True
            continue
        
        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        if vlan_id == -1:
            vlan_id = vlan.get(get_interface_name(interface))
            vlan_id = translate_trunk(vlan_id)
            
        inspect(dest_mac, src_mac, ethertype, vlan_id, interface, length)

        # TODO: Implement forwarding with learning
        table.update({src_mac: interface})

        vlan_src = vlan.get(get_interface_name(interface))
        vlan_src = translate_trunk(vlan_src)

        # print("NORMAL Forwarding")
        # if is_Unicast(dest_mac):
        #     if dest_mac in table:
        #         send_to_link(table.get(dest_mac), data, length)
        #     else:
        #         for i in interfaces:
        #             if i != interface:
        #                 send_to_link(i, data, length)
        # else:
        #     for i in interfaces:
        #         if i != interface:
        #             send_to_link(i, data, length)

        if check_for_trunk(vlan_src):
            trunk_forwarding(dest_mac, 
                             vlan_id, 
                             interface, 
                             data, length, 
                             table, vlan, 
                             interfaces)
        else:
            access_forwarding(dest_mac, 
                              vlan_id, 
                              interface, 
                              data, length, 
                              table, vlan, 
                              interfaces)
            
        # TODO: Implement VLAN support
        # TODO: Implement STP support

if __name__ == "__main__":
    main()
