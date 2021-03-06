###############################################################################
#
# Script:       tunnel-builder.py
#
# Author:       Chris Goodwin <chrisgoodwins@gmail.com>
#
# Description:  Build IPSec VPNs in bulk for a Palo Alto Networks firewall.
#               Feed the script a CSV file containing config for tunnel
#               interfaces, IKE gateways, and IPSec tunnels. See CSV example
#               in the Github repo for proper format.
#
# Requirements: pandevice
#
# Python:       Version 3
#
###############################################################################
###############################################################################


from pandevice import base, network, errors
import getpass
import sys
import re


# Prompts the user to enter an address, then checks it's validity
def getfwipfqdn():
    while True:
        fwipraw = input("\nPlease enter firewall IP or FQDN: ")
        ipr = re.match(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", fwipraw)
        fqdnr = re.match(r"(?=^.{4,253}$)(^((?!-)[a-zA-Z0-9-]{1,63}(?<!-)\.)+[a-zA-Z]{2,63}$)", fwipraw)
        if ipr:
            break
        elif fqdnr:
            break
        else:
            print("\nThere was something wrong with your entry. Please try again...\n")
    return fwipraw


# Prompts the user to enter a username
def getCreds():
    while True:
        username = input("Please enter your user name: ")
        usernamer = re.match(r"^[a-zA-Z0-9_-]{3,24}$", username)
        if usernamer:
            password = getpass.getpass("Please enter your password: ")
            break
        else:
            print("\nThere was something wrong with your entry. Please try again...\n")
    return username, password


# Opens the vpn config file, reads into a list and sets the proper format
def csv_reader(argv):
    if len(argv) < 2:
        csv_file = input('\nEnter the name of your VPN config file: ')
    else:
        csv_file = str(argv[1])
    print('')
    while True:
        try:
            with open(csv_file, 'r') as file:
                file = file.readlines()
                return [item.replace('\n', '').split(',') for item in file if item != file[0]]
        except FileNotFoundError:
            print('\nERROR - No such file or directory: {}'.format(csv_file))
            csv_file = input('\nEnter the name of your VPN config file: ')


# Parses the config file, and Instantiates the firewall and the objects to be used
def config_parser(fw_addr, fw_admin, fw_pw, configList):
    global pan
    while True:
        try:
            pan = base.PanDevice.create_from_device(fw_addr, fw_admin, fw_pw)
            break
        except errors.PanURLError as e:
            print('Error connecting to PAN Device {} with user {}: {}'.format(fw_addr, fw_admin, e))
            print('\n')
            fw_admin, fw_pw = getCreds()
            print('\n')
    config_builder(configList)


# Builds the pandevice objects from the csv file config elements
def config_builder(instanceList):
    global netObj_ike_list, netObj_ipsec_list, netObj_tunInt_list, netObj_vr_list, netObj_zone_list
    netObj_ike_list, netObj_ipsec_list, netObj_tunInt_list, netObj_vr_list, netObj_zone_list = [], [], [], [], []
    vrDict, zoneDict = {}, {}
    for item in instanceList:
        item = [i if i != '' else None for i in item[:]]
        netObj_tunInt = network.TunnelInterface()
        netObj_tunInt.name = item[0]
        netObj_tunInt.comment = item[1]
        netObj_tunInt.ip = item[2]
        netObj_tunInt.management_profile = item[3]
        netObj_tunInt_list.append(pan.add(netObj_tunInt))
        if item[4] not in vrDict.keys():
            vrDict[item[4]] = []
        vrDict[item[4]].append(item[0])
        if len(item[5]) > 31:
            print('*' * 6 + ' Warning -- IKE-GW - {} name truncated to {} due to length restriction'.format(item[5], item[5][:31]))
            item[5] = item[5][:31]
        if item[5] not in zoneDict.keys():
            zoneDict[item[5]] = []
        zoneDict[item[5]].append(item[0])
        if len(item[6]) > 31:
            print('*' * 6 + ' Warning -- IKE-GW - {} name truncated to {} due to length restriction'.format(item[6], item[6][:31]))
            item[6] = item[6][:31]
        netObj_ike = network.IkeGateway()
        netObj_ike.name = item[6]
        netObj_ike.interface = item[7]
        netObj_ike.local_ip_address_type = 'ip'
        netObj_ike.local_ip_address = item[8]
        netObj_ike.peer_ip_type = item[9]
        if netObj_ike.peer_ip_type != 'dynamic':
            netObj_ike.peer_ip_value = item[10]
        netObj_ike.pre_shared_key = item[11]
        if item[12] is not None:
            temp_item = item[12].replace(': ', ':').split(':')
            netObj_ike.local_id_type = temp_item[0]
            netObj_ike.local_id_value = temp_item[1]
        if item[13] is not None:
            temp_item = item[13].replace(': ', ':').split(':')
            netObj_ike.peer_id_type = temp_item[0]
            netObj_ike.peer_id_value = temp_item[1]
        if item[14] is not None and item[14].lower() == 'true':
            netObj_ike.enable_passive_mode = True
        else:
            netObj_ike.enable_passive_mode = False
        if item[15] is not None and item[15].lower() == 'true':
            netObj_ike.enable_nat_traversal = True
        else:
            netObj_ike.enable_nat_traversal = False
        netObj_ike.ikev1_exchange_mode = item[16]
        netObj_ike.ikev1_crypto_profile = item[17]
        if item[18] is not None and item[18].lower() == 'true':
            netObj_ike.enable_fragmentation = True
        else:
            netObj_ike.enable_fragmentation = False
        if item[19] is None or item[19].lower() == 'true':
            netObj_ike.enable_dead_peer_detection = True
        elif item[19].lower() == 'false':
            netObj_ike.enable_dead_peer_detection = False
        else:
            temp_item = item[19].replace('; ', ';').split(';')
            netObj_ike.enable_dead_peer_detection = True
            netObj_ike.dead_peer_detection_interval = temp_item[0]
            netObj_ike.dead_peer_detection_retry = temp_item[1]
        netObj_ike_list.append(pan.add(netObj_ike))
        if len(item[20]) > 31:
            print('*' * 6 + ' Warning -- IKE-GW - {} name truncated to {} due to length restriction'.format(item[20], item[20][:31]))
            item[20] = item[20][:31]
        netObj_ipsec = network.IpsecTunnel()
        netObj_ipsec.name = item[20]
        netObj_ipsec.tunnel_interface = item[21]
        if len(item[22]) > 31:
            print('*' * 6 + ' Warning -- IKE-GW - {} name truncated to {} due to length restriction'.format(item[22], item[22][:31]))
            item[22] = item[22][:31]
        netObj_ipsec.ak_ike_gateway = item[22]
        if item[23] is None:
            item[23] = 'default'
        netObj_ipsec.ak_ipsec_crypto_profile = item[23]
        netObj_ipsec_list.append(pan.add(netObj_ipsec))
        print('Building Config --- Tunnel-Int - {} // IKE-GW - {} // IPSec-Tunnel - {}'.format(netObj_tunInt.name, netObj_ike.name, netObj_ipsec.name))
    for key, value in vrDict.items():
        netObj_vr = network.VirtualRouter()
        netObj_vr.name = key
        netObj_vr.interface = value
        netObj_vr_list.append(pan.add(netObj_vr))
    for key, value in zoneDict.items():
        netObj_zone = network.Zone()
        netObj_zone.name = key
        netObj_zone.interface = value
        netObj_zone_list.append(pan.add(netObj_zone))


# Pushes the changes to the firewall
def config_push():
    try:
        print('\n\nCreating tunnel interfaces...')
        netObj_tunInt_list[0].create_similar()
        print('Adding interfaces to virtual routers...')
        [obj.create() for obj in netObj_vr_list]
        print('Adding interfaces to zones...')
        [obj.create() for obj in netObj_zone_list]
        print('Creating IKE config...')
        netObj_ike_list[0].create_similar()
        print('Creating IPsec config...')
        netObj_ipsec_list[0].create_similar()
        print('\n\nYour VPN config was successfully built and pushed to the firewall\n\nHave a great day!!\n\n')
    except errors.PanDeviceXapiError as e:
        print('\n\nThere was an error pushing the config:\n{}\n'.format(e))
        exit(1)


def main():
    fw_addr = getfwipfqdn()
    fw_admin, fw_pw = getCreds()
    configList = csv_reader(sys.argv)
    config_parser(fw_addr, fw_admin, fw_pw, configList)
    config_push()


if __name__ == '__main__':
    main()
