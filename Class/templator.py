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
    def genVXLAN(self,targets):
        template,count = "",1
        for node in targets:
            template += 'bridge fdb append 00:00:00:00:00:00 dev vxlan1 dst 10.0.'+str(count)+'.1;'
            count += 1
        clients = self.getUniqueClients(targets)
        count = 1
        for client in clients:
            template += 'bridge fdb append 00:00:00:00:00:00 dev vxlan1 dst 10.0.250.'+str(count)+';'
            count += 1
        return template
    def genServer(self,targets,subnet,server,port,privateKey,publicKey):
        template = '''[Interface]
        Address = 10.0.'''+str(subnet)+'''.'''+str(server)+'''/31
        ListenPort = '''+str(port)+'''
        PrivateKey = '''+str(privateKey)
        if port == 51194:
            template += '\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; ip addr add 10.0.'+str(subnet)+'.1/30 dev lo;'
            template += "iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {print $5}') -j MASQUERADE;"
            template += 'ip link add vxlan1 type vxlan id 1 dstport 4789 local 10.0.'+str(subnet)+'.1; ip link set vxlan1 up;'
            template += 'ip addr add 10.0.251.'+str(subnet)+'/24 dev vxlan1;'
            template += self.genVXLAN(targets)
            template += '\nPostDown = ip addr del 10.0.'+str(subnet)+'.1/30 dev lo; ip link delete vxlan1;'
        template += '''
        SaveConfig = true
        Table = off
        [Peer]
        PublicKey = '''+publicKey+'''
        AllowedIPs = 10.0.0.0/8'''
        return template
    def genClient(self,targets,ip,subnet,server,port,privateKey,publicKey,clientIP,clients,client):
        template = '''[Interface]
        Address = 10.0.'''+str(subnet)+'''.'''+str(server+1)+'''/31
        PrivateKey = '''+str(privateKey)
        if clientIP == True:
            vxlanIP = self.getUniqueClients(targets,client,True) + len(targets)
            template += '\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; ip addr add 10.0.250.'+str(len(clients))+'/32 dev lo;'
            template += 'ip link add vxlan1 type vxlan id 1 dstport 4789 local 10.0.250.'+str(len(clients))+'; ip link set vxlan1 up;'
            template += 'ip addr add 10.0.251.'+str(vxlanIP)+'/24 dev vxlan1;'
            template += self.genVXLAN(targets)
            template += '\nPostDown = ip addr del 10.0.250.'+str(len(clients))+'/32 dev lo; ip link delete vxlan1;'
        template += '''
        Table = off
        [Peer]
        PublicKey = '''+str(publicKey)+'''
        AllowedIPs = 10.0.0.0/8
        Endpoint = '''+str(ip)+''':'''+str(port)+'''
        PersistentKeepalive = 20'''
        return template
