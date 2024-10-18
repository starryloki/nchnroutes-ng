#!/usr/bin/env python3
import argparse
import csv
from ipaddress import IPv4Network, IPv6Network
import math

parser = argparse.ArgumentParser(description='Generate IPv4/IPv6 routes for specific countries, custom IPs, and non-China routes for BIRD.')
parser.add_argument('--exclude', metavar='CIDR', type=str, nargs='*',
                    help='IPv4/IPv6 ranges to exclude in CIDR format')
parser.add_argument('--next', default="wg0", metavar = "INTERFACE OR IP",
                    help='Next hop for non-China IP addresses, this is usually the tunnel interface')
parser.add_argument('--ipv4-list', choices=['apnic', 'ipip'], default=['apnic', 'ipip'], nargs='*',
                    help='IPv4 lists to use when subtracting China-based IP')
parser.add_argument('--country-exit', metavar='COUNTRY:INTERFACE', type=str, nargs='*',
                    help='Mapping between country codes and exit interfaces, e.g., US:eth0 CN:eth1')
parser.add_argument('--custom-exit', metavar='CIDR:INTERFACE', type=str, nargs='*',
                    help='Custom IPv4/IPv6 ranges with specific exit interfaces, e.g., 192.168.10.0/24:eth2 10.0.0.0/8:eth3 2001:db8::/32:eth4')

args = parser.parse_args()
country_exit_map = dict()
if args.country_exit:
    for country_exit in args.country_exit:
        country_code, exit_interface = country_exit.split(':')
        country_exit_map[country_code.upper()] = exit_interface

custom_exit_map_v4 = []
custom_exit_map_v6 = []
if args.custom_exit:
    for custom_exit in args.custom_exit:
        cidr, exit_interface = custom_exit.split(':')
        try:
            cidr = IPv4Network(cidr)
            custom_exit_map_v4.append((cidr, exit_interface))
        except ValueError:
            cidr = IPv6Network(cidr)
            custom_exit_map_v6.append((cidr, exit_interface))

class Node:
    def __init__(self, cidr, parent=None):
        self.cidr = cidr
        self.child = []
        self.dead = False
        self.parent = parent

    def __repr__(self):
        return "<Node %s>" % self.cidr

def dump_tree(lst, ident=0):
    for n in lst:
        print("+" * ident + str(n))
        dump_tree(n.child, ident + 1)

def dump_bird(lst, f, next_hop):
    for n in lst:
        if n.dead:
            continue
        if len(n.child) > 0:
            dump_bird(n.child, f, next_hop)
        elif not n.dead:
            f.write('route %s via "%s";\n' % (n.cidr, next_hop))

RESERVED = [
    IPv4Network('0.0.0.0/8'),
    IPv4Network('10.0.0.0/8'),
    IPv4Network('127.0.0.0/8'),
    IPv4Network('169.254.0.0/16'),
    IPv4Network('172.16.0.0/12'),
    IPv4Network('192.0.0.0/29'),
    IPv4Network('192.0.0.170/31'),
    IPv4Network('192.0.2.0/24'),
    IPv4Network('192.168.0.0/16'),
    IPv4Network('198.18.0.0/15'),
    IPv4Network('198.51.100.0/24'),
    IPv4Network('203.0.113.0/24'),
    IPv4Network('240.0.0.0/4'),
    IPv4Network('255.255.255.255/32'),
    IPv4Network('169.254.0.0/16'),
    IPv4Network('127.0.0.0/8'),
    IPv4Network('224.0.0.0/4'),
    IPv4Network('100.64.0.0/10'),
]

RESERVED_V6 = [
    IPv6Network('::1/128'),
    IPv6Network('fc00::/7'),
    IPv6Network('fe80::/10'),
    IPv6Network('ff00::/8'),
]

if args.exclude:
    for e in args.exclude:
        if ":" in e:
            RESERVED_V6.append(IPv6Network(e))
        else:
            RESERVED.append(IPv4Network(e))

IPV6_UNICAST = IPv6Network('2000::/3')

def subtract_cidr(sub_from, sub_by):
    for cidr_to_sub in sub_by:
        for n in sub_from:
            if n.cidr == cidr_to_sub:
                n.dead = True
                break

            if n.cidr.supernet_of(cidr_to_sub):
                if len(n.child) > 0:
                    subtract_cidr(n.child, sub_by)
                else:
                    n.child = [Node(b, n) for b in n.cidr.address_exclude(cidr_to_sub)]
                break

root = []
root_v6 = [Node(IPV6_UNICAST)]

with open("ipv4-address-space.csv", newline='') as f:
    f.readline()
    reader = csv.reader(f, quoting=csv.QUOTE_MINIMAL)
    for cidr in reader:
        if cidr[5] == "ALLOCATED" or cidr[5] == "LEGACY":
            block = cidr[0]
            cidr = "%s.0.0.0%s" % (block[:3].lstrip("0"), block[-2:])
            root.append(Node(IPv4Network(cidr)))

country_specific_nodes_v4 = {code: [] for code in country_exit_map}
country_specific_nodes_v6 = {code: [] for code in country_exit_map}

with open("delegated-apnic-latest") as f:
    for line in f:
        if 'apnic' in args.ipv4_list and "apnic|CN|ipv4|" in line:
            line = line.split("|")
            a = "%s/%d" % (line[3], 32 - math.log(int(line[4]), 2))
            a = IPv4Network(a)
            subtract_cidr(root, (a,))

        for code in country_exit_map:
            if f"apnic|{code}|ipv4|" in line:
                line = line.split("|")
                a = "%s/%d" % (line[3], 32 - math.log(int(line[4]), 2))
                a = IPv4Network(a)
                country_specific_nodes_v4[code].append(Node(a))
                subtract_cidr(root, (a,))

            elif 'apnic' in args.ipv4_list and "apnic|CN|ipv6|" in line:
                line = line.split("|")
                a = "%s/%s" % (line[3], line[4])
                a = IPv6Network(a)
                subtract_cidr(root_v6, (a,))

        for code in country_exit_map:
            if f"apnic|{code}|ipv6|" in line:
                line = line.split("|")
                a = "%s/%s" % (line[3], line[4])
                a = IPv6Network(a)
                country_specific_nodes_v6[code].append(Node(a))
                subtract_cidr(root_v6, (a,))

if 'ipip' in args.ipv4_list:
    with open("china_ip_list.txt") as f:
        for line in f:
            line = line.strip('\n')
            a = IPv4Network(line)
            subtract_cidr(root, (a,))

custom_specific_nodes_v4 = []
for cidr, exit_interface in custom_exit_map_v4:
    custom_specific_nodes_v4.append(Node(cidr))
    subtract_cidr(root, (cidr,))
    for code in country_specific_nodes_v4:
        subtract_cidr(country_specific_nodes_v4[code], (cidr,))

custom_specific_nodes_v6 = []
for cidr, exit_interface in custom_exit_map_v6:
    custom_specific_nodes_v6.append(Node(cidr))
    subtract_cidr(root_v6, (cidr,))
    for code in country_specific_nodes_v6:
        subtract_cidr(country_specific_nodes_v6[code], (cidr,))

subtract_cidr(root, RESERVED)
subtract_cidr(root_v6, RESERVED_V6)

with open("routes4.conf", "w") as f:
    for country_code, next_hop in country_exit_map.items():
        dump_bird(country_specific_nodes_v4[country_code], f, next_hop)

    for node, next_hop in zip(custom_specific_nodes_v4, [x[1] for x in custom_exit_map_v4]):
        dump_bird([node], f, next_hop)

    dump_bird(root, f, args.next)

with open("routes6.conf", "w") as f:
    for country_code, next_hop in country_exit_map.items():
        dump_bird(country_specific_nodes_v6[country_code], f, next_hop)

    for node, next_hop in zip(custom_specific_nodes_v6, [x[1] for x in custom_exit_map_v6]):
        dump_bird([node], f, next_hop)

    dump_bird(root_v6, f, args.next)