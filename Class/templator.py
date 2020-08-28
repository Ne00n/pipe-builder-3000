class Templator:
    def genServer(self,subnet,server,port,privateKey,publicKey):
        return '[Interface]\nAddress = 10.0.'+str(subnet)+'.'+str(server)+'/31\nListenPort = '+str(port)+'\nPrivateKey = '+str(privateKey)+'SaveConfig = true\n[Peer]\nPublicKey = '+publicKey+'AllowedIPs = 10.0.'+str(subnet)+'.'+str(server+1)+'/32'
    def genClient(self,ip,subnet,server,port,privateKey,publicKey):
        return '[Interface]\nPrivateKey = '+str(privateKey)+'Address = 10.0.'+str(subnet)+'.'+str(server+1)+'/32\n[Peer]\nPublicKey = '+str(publicKey)+'AllowedIPs = 10.0.'+str(subnet)+'.'+str(server)+'/31\nEndpoint = '+str(ip)+':'+str(port)+'\nPersistentKeepalive = 20'
