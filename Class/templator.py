class Templator:
    def genServer(self,subnet,server,port,privateKey,publicKey):
        template = '''[Interface]
        Address = 10.0.'''+str(subnet)+'''.'''+str(server)+'''/31
        ListenPort = '''+str(port)+'''
        PrivateKey = '''+str(privateKey)+'''
        SaveConfig = true
        Table = off
        [Peer]
        PublicKey = '''+publicKey+'''
        AllowedIPs = 10.0.0.0/8'''
        return template
    def genClient(self,ip,subnet,server,port,privateKey,publicKey):
        template = '''[Interface]
        PrivateKey = '''+str(privateKey)+'''
        Address = 10.0.'''+str(subnet)+'''.'''+str(server+1)+'''/31
        Table = off
        [Peer]
        PublicKey = '''+str(publicKey)+'''
        AllowedIPs = 10.0.0.0/8
        Endpoint = '''+str(ip)+''':'''+str(port)+'''
        PersistentKeepalive = 20'''
        return template
