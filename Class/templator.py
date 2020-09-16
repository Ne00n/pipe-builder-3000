class Templator:
    def genServer(self,subnet,server,port,privateKey,publicKey):
        template = '''[Interface]
        Address = 10.0.'''+str(subnet)+'''.'''+str(server)+'''/31
        ListenPort = '''+str(port)+'''
        PrivateKey = '''+str(privateKey)
        if port == 51194:
            template += '\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; ip addr add 10.0.'+str(subnet)+'.1/30 dev lo;'
            template += "iptables -t nat -A POSTROUTING -o $(ip route show default | awk '/default/ {print $5}') -j MASQUERADE;"
            template += '\nPostDown = ip addr del 10.0.'+str(subnet)+'.1/30 dev lo;'
        template += '''
        SaveConfig = true
        Table = off
        [Peer]
        PublicKey = '''+publicKey+'''
        AllowedIPs = 10.0.0.0/8'''
        return template
    def genClient(self,ip,subnet,server,port,privateKey,publicKey,clientIP,clients):
        template = '''[Interface]
        Address = 10.0.'''+str(subnet)+'''.'''+str(server+1)+'''/31
        PrivateKey = '''+str(privateKey)
        if clientIP == True:
            template += '\nPostUp =  echo 1 > /proc/sys/net/ipv4/ip_forward; ip addr add 10.0.250.'+str(len(clients))+'/32 dev lo;'
            template += '\nPostDown = ip addr del 10.0.250.'+str(len(clients))+'/32 dev lo;'
        template += '''
        Table = off
        [Peer]
        PublicKey = '''+str(publicKey)+'''
        AllowedIPs = 10.0.0.0/8
        Endpoint = '''+str(ip)+''':'''+str(port)+'''
        PersistentKeepalive = 20'''
        return template
