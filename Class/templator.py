class Templator:
    def genServer(self,subnet,server,port,privateKey,publicKey):
        return '[Interface]\nAddress = 10.0.'+str(subnet)+'.'+str(server)+'/31\nListenPort = '+str(port)+'\nPrivateKey = '+str(privateKey)+'\nSaveConfig = true\n[Peer]\nPublicKey = '+publicKey+'\nAllowedIPs = 10.0.'+str(subnet)+'.'+str(server+1)+'/32'
    def genClient(self,ip,subnet,server,port,privateKey,publicKey):
        return '[Interface]\nPrivateKey = '+str(privateKey)+'\nAddress = 10.0.'+str(subnet)+'.'+str(server+1)+'/32\n[Peer]\nPublicKey = '+str(publicKey)+'\nAllowedIPs = 10.0.'+str(subnet)+'.0/24\nEndpoint = '+str(ip)+':'+str(port)+'\nPersistentKeepalive = 20'
