#! /usr/bin/env python3
# coding: utf-8
#
#  Cisco NXOS configuration reader (nxos_reader)
#
#  Copyright (C) 2019 Denis Pompilio (jawa) <denis.pompilio@gmail.com>
#
#  This file is part of nxos_reader
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the MIT License.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  MIT License for more details.
#
#  You should have received a copy of the MIT License along with this
#  program; if not, see <https://opensource.org/licenses/MIT>.

import argparse
import json
import netmiko


VERSION = "0.1.0"


class Nexus(object):
    """"""

    def __init__(self, conn_str):
        """"""
        self.user, self.fqdn = conn_str.split('@', 1)
        self.device = {
            'device_type': 'cisco_nxos',
            'host': self.fqdn,
            'username': self.user,
            "allow_agent": True
        }
        self._conn = None
        self._vlans = None
        self._vrfs = None
        self._vrf_ifaces = None
        self._interfaces = None
        self._hsrp = None

    @property
    def conn(self):
        """"""
        if not self._conn:
            self._conn = netmiko.ConnectHandler(**self.device)
        return self._conn

    @property
    def vlans(self):
        if not self._vlans:
            out = self.conn.send_command("show vlan all | json")
            self._vlans = json.loads(out)['TABLE_vlanbriefallports']
        return self._vlans['ROW_vlanbriefallports']

    @property
    def interfaces(self):
        if not self._interfaces:
            out = self.conn.send_command("show interface | json")
            self._interfaces = json.loads(out)["TABLE_interface"]
        return self._interfaces["ROW_interface"]

    def get_interface(self, name):
        for iface in self.interfaces:
            if name == iface["interface"]:
                return iface

    @property
    def vrfs(self):
        if not self._vrfs:
            out = self.conn.send_command("show vrf all | json")
            self._vrfs = json.loads(out)["TABLE_vrf"]
        return self._vrfs["ROW_vrf"]

    @property
    def vrf_ifaces(self):
        if not self._vrf_ifaces:
            out = self.conn.send_command("show vrf all interface | json")
            self._vrf_ifaces = json.loads(out)["TABLE_if"]
        return self._vrf_ifaces["ROW_if"]

    @property
    def hsrp(self):
        if not self._hsrp:
            out = self.conn.send_command("show hsrp all | json")
            self._hsrp = json.loads(out)["TABLE_grp_detail"]
        return self._hsrp['ROW_grp_detail']


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Cisco NXOS configuration reader')

    parser.add_argument('--version', dest='version', action='store_const',
                        const=True, default=False,
                        help='show script version')
    parser.add_argument('-m', '--connect-master', dest='m_conn',
                        help='specify a connection string user@device')
    parser.add_argument('-s', '--connect-slave', dest='s_conn',
                        help='specify a connection string user@device')

    args = parser.parse_args()

    if args.version:
        print("Script version: %s" % VERSION)
        exit()

    if not args.m_conn or not args.s_conn:
        parser.error('connection string not provided')
        exit(1)

    m_sw = Nexus(args.m_conn)
    s_sw = Nexus(args.s_conn)

    for vlan in m_sw.vlans:
        vlan_id = vlan['vlanshowbr-vlanid']

        # if vlan_id != "3951" and vlan_id != "3932":
        #     continue

        vrf_name = "default"
        for vrf in m_sw.vrf_ifaces:
            if vrf['if_name'] == "Vlan"+vlan_id:
                vrf_name = vrf['vrf_name']

        masterip = None
        slaveip = None
        vip = None
        for hsrp in m_sw.hsrp:
            if hsrp['sh_if_index'] == "Vlan"+vlan_id:
                masterip = hsrp['sh_active_router_addr']
                slaveip =  hsrp['sh_standby_router_addr']
                vip = hsrp.get('sh_vip')

        mask = None
        for iface in m_sw.interfaces:
            iface_name = "Vlan"+vlan_id
            if iface["interface"] == iface_name:
                mask = iface.get("svi_ip_mask")
                if not masterip:
                    masterip = iface.get('svi_ip_addr')
                    s_iface = s_sw.get_interface(iface_name)
                    if s_iface:
                        slaveip = s_iface.get('svi_ip_addr')
                # print(iface)

        if not masterip:
            print("- { name: '%s', vlan_id: %s }" % (
                      vlan['vlanshowbr-vlanname'], vlan_id
                  ))
        elif not vip:
            print("- { name: '%s', vlan_id: %s, vrf: '%s', "
                  "masterip: %s, slaveip: %s, mask: %s }" % (
                      vlan['vlanshowbr-vlanname'], vlan_id, vrf_name,
                      masterip, slaveip, mask
                  ))
        else:
            print("- { name: '%s', vlan_id: %s, vrf: '%s', "
                  "masterip: %s, slaveip: %s, vip: %s, mask: %s }" % (
                    vlan['vlanshowbr-vlanname'], vlan_id, vrf_name,
                    masterip, slaveip, vip, mask
                    ))