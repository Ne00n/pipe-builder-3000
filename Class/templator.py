import random

class Templator:
    def getUniqueClients(self,targets,target="",count=False):
        clients = []
        for node,data in targets.items():
            for client in data['Targets']:
                if client not in clients and client != "*":
                    clients.append(client)
                if client == target and count == True:
                    return len(clients)
        return clients

    def genVXLAN(self,servers,targets):
        template = ""
        for node,data in servers.items():
            template += f'bridge fdb append 00:00:00:00:00:00 dev vxlan{targets["vxlanID"]} dst {targets["prefixSub"]}.{data["id"]}.1;'
        clients = self.getUniqueClients(targets['servers'])
        count = 1
        for client in clients:
            template += f'bridge fdb append 00:00:00:00:00:00 dev vxlan{targets["vxlanID"]} dst {targets["prefixSub"]}.250.{count};'
            count += 1
        return template

    def genServer(self,targets,ip,data,server,port,privateKey,publicKey,v6only=False):
        randomMac = "52:54:00:%02x:%02x:%02x" % (random.randint(0, 255),random.randint(0, 255),random.randint(0, 255),)
        mtu = 1412 if "[" in ip else 1420
        template = f'''[Interface]
        Address = {targets["prefixSub"]}.{data["id"]}.{server}/31, fe99:{data["id"]}::{server}/127
        MTU = {mtu}
        ListenPort = {port}
        PrivateKey = {privateKey}'''
        if port == data['basePort']:
            if data['type'] != "boringtun" and data['type'] != "container":
                template += f'\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; echo 1 > /proc/sys/net/ipv6/conf/all/forwarding; echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter; echo 0 > /proc/sys/net/ipv4/conf/default/rp_filter; echo "fq" > /proc/sys/net/core/default_qdisc; echo "bbr" > /proc/sys/net/ipv4/tcp_congestion_control; ip addr add {targets["prefixSub"]}.{data["id"]}.1/30 dev lo; ip addr add fc00:0:0:{data["id"]}::1/64 dev lo;'
            else:
                template += f'\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; echo 1 > /proc/sys/net/ipv6/conf/all/forwarding; echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter; echo 0 > /proc/sys/net/ipv4/conf/default/rp_filter; ip addr add {targets["prefixSub"]}.{data["id"]}.1/30 dev lo; ip addr add fc00:0:0:{data["id"]}::1/64 dev lo;'
            if v6only is False and port == data['basePort']:
                if data['type'] == "boringtun" or data['type'] == "container":
                    template += "iptables -t nat -A POSTROUTING -o venet0 -j MASQUERADE;"
                else:
                    template += "iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {print $5}' | tail -1) -j MASQUERADE;"
            template += f'ip link add vxlan{targets["vxlanID"]} type vxlan id {targets["vxlanID"]} dstport {targets["vxlanID"]}789 local {targets["prefixSub"]}.{data["id"]}.1; ip link set vxlan{targets["vxlanID"]} up;'
            template += f'ip link set dev vxlan{targets["vxlanID"]} address {randomMac};'
            template += f'ip addr add {targets["prefixSub"]}.{targets["vxlanSub"]}.{data["id"]}/24 dev vxlan{targets["vxlanID"]};'
            template += self.genVXLAN(targets['servers'],targets)
            template += f'\nPostDown = ip addr del {targets["prefixSub"]}.{data["id"]}.1/30 dev lo; ip addr del fc00:0:0:{data["id"]}::1/64 dev lo; ip link delete vxlan{targets["vxlanID"]};'
        template += f'''
        SaveConfig = false
        Table = off
        [Peer]
        PublicKey = {publicKey}
        AllowedIPs = 0.0.0.0/0, ::0/0'''
        return template

    def genClient(self,targets,ip,subnet,server,port,privateKey,publicKey,clientIP,clients,client):
        mtu = 1412 if "[" in ip else 1420
        template = f'''[Interface]
        Address = {targets["prefixSub"]}.{subnet}.{server+1}/31, fe99:{subnet}::{server+1}/127
        MTU = {mtu}
        PrivateKey = {privateKey}'''
        if clientIP == True:
            vxlanIP = 255 - self.getUniqueClients(targets['servers'],client,True)
            template += f'\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; echo 1 > /proc/sys/net/ipv6/conf/all/forwarding; echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter; echo 0 > /proc/sys/net/ipv4/conf/default/rp_filter; echo "fq" > /proc/sys/net/core/default_qdisc; echo "bbr" > /proc/sys/net/ipv4/tcp_congestion_control; ip addr add {targets["prefixSub"]}.250.{len(clients)}/32 dev lo;'
            template += f'ip link add vxlan{targets["vxlanID"]} type vxlan id {targets["vxlanID"]} dstport {targets["vxlanID"]}789 local {targets["prefixSub"]}.250.{len(clients)}; ip link set vxlan{targets["vxlanID"]} up;'
            template += f'ip addr add {targets["prefixSub"]}.{targets["vxlanSub"]}.{vxlanIP}/24 dev vxlan{targets["vxlanID"]};'
            template += self.genVXLAN(targets['servers'],targets)
            template += f'\nPostDown = ip addr del {targets["prefixSub"]}.250.{len(clients)}/32 dev lo; ip link delete vxlan{targets["vxlanID"]};'
        template += f'''
        SaveConfig = false
        Table = off
        [Peer]
        PublicKey = {publicKey}
        AllowedIPs = 0.0.0.0/0, ::0/0
        Endpoint = {ip}:{port}'''
        if clientIP == True: template += '\nPersistentKeepalive = 20'
        return template

    def genBoringtun(self):
        template = '''[Service]
Environment=WG_QUICK_USERSPACE_IMPLEMENTATION=boringtun
Environment=WG_SUDO=1
        '''
        return template
