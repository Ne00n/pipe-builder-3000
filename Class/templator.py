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
    def genVXLAN(self,targets,vxlan):
        template = ""
        for node,data in targets.items():
            template += 'bridge fdb append 00:00:00:00:00:00 dev vxlan'+str(vxlan)+' dst 10.0.'+str(data['id'])+'.1;'
        clients = self.getUniqueClients(targets)
        count = 1
        for client in clients:
            template += 'bridge fdb append 00:00:00:00:00:00 dev vxlan'+str(vxlan)+' dst 10.0.250.'+str(count)+';'
            count += 1
        return template
    def genServer(self,servers,ip,data,server,port,privateKey,publicKey,targets,v6only=False):
        randomMac = "52:54:00:%02x:%02x:%02x" % (random.randint(0, 255),random.randint(0, 255),random.randint(0, 255),)
        template = '''[Interface]
        Address = 10.0.'''+str(data['id'])+'''.'''+str(server)+'''/31
        ListenPort = '''+str(port)+'''
        PrivateKey = '''+str(privateKey)
        if port == data['basePort']:
            if data['type'] != "boringtun" and data['type'] != "container":
                template += '\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter; echo 0 > /proc/sys/net/ipv4/conf/default/rp_filter; echo "fq" > /proc/sys/net/core/default_qdisc; echo "bbr" > /proc/sys/net/ipv4/tcp_congestion_control; ip addr add 10.0.'+str(data['id'])+'.1/30 dev lo;'
            else:
                template += '\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter; echo 0 > /proc/sys/net/ipv4/conf/default/rp_filter; ip addr add 10.0.'+str(data['id'])+'.1/30 dev lo;'
            if v6only is False and port == data['basePort']:
                if data['type'] == "boringtun" or data['type'] == "container":
                    template += "iptables -t nat -A POSTROUTING -o venet0 -j MASQUERADE;"
                else:
                    template += "iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {print $5}' | tail -1) -j MASQUERADE;"
            template += f"ip link add vxlan{targets['vxlanID']} type vxlan id {targets['vxlanID']} dstport 4789 local 10.0.{data['id']}.1; ip link set vxlan{targets['vxlanID']} up;"
            template += f"ip link set dev vxlan{targets['vxlanID']} address {randomMac};"
            template += 'ip addr add 10.0.'+str(targets['vxlanSub'])+'.'+str(data['id'])+'/24 dev vxlan'+str(targets['vxlanID'])+';'
            template += self.genVXLAN(servers,targets['vxlanID'])
            template += '\nPostDown = ip addr del 10.0.'+str(data['id'])+'.1/30 dev lo; ip link delete vxlan'+str(targets['vxlanID'])+';'
        template += '''
        SaveConfig = true
        Table = off
        [Peer]
        PublicKey = '''+publicKey+'''
        AllowedIPs = 0.0.0.0/0'''
        return template
    def genClient(self,servers,ip,subnet,server,port,privateKey,publicKey,clientIP,clients,client,targets):
        template = f'''[Interface]
        Address = {targets['prefixSub']}.{subnet}.{server+1}/31
        PrivateKey = {privateKey}'''
        if clientIP == True:
            vxlanIP = 255 - self.getUniqueClients(servers,client,True)
            template += f'\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; echo 0 > /proc/sys/net/ipv4/conf/all/rp_filter; echo 0 > /proc/sys/net/ipv4/conf/default/rp_filter; echo "fq" > /proc/sys/net/core/default_qdisc; echo "bbr" > /proc/sys/net/ipv4/tcp_congestion_control; ip addr add {targets["prefixSub"]}.250.{len(clients)}/32 dev lo;'
            template += f'ip link add vxlan{targets["vxlanID"]} type vxlan id {targets["vxlanID"]} dstport 4789 local {targets["prefixSub"]}.250.{len(clients)}; ip link set vxlan{targets["vxlanID"]} up;'
            template += f'ip addr add {targets["prefixSub"]}.{targets["vxlanSub"]}.{vxlanIP}/24 dev vxlan{targets["vxlanID"]};'
            template += self.genVXLAN(servers,targets['vxlanID'])
            template += f'\nPostDown = ip addr del {targets["prefixSub"]}.250.{len(clients)}/32 dev lo; ip link delete vxlan{targets["vxlanID"]};'
        template += f'''
        Table = off
        [Peer]
        PublicKey = {publicKey}
        AllowedIPs = 0.0.0.0/0
        Endpoint = {ip}:{port}'''
        if clientIP == True: template += '\nPersistentKeepalive = 20'
        return template
    def genBoringtun(self):
        template = '''[Service]
Environment=WG_QUICK_USERSPACE_IMPLEMENTATION=boringtun
Environment=WG_SUDO=1
        '''
        return template
