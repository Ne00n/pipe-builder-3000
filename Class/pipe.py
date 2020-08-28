import subprocess, json, re
from Class.templator import Templator

targets = []

class Pipe:
    def __init__(self):
        global targets
        print("Loading config")
        with open('hosts.json') as handle:
            targets = json.loads(handle.read())

    def cmd(self,server,command,interactive):
        cmd = ['ssh','root@'+server,command]
        if interactive == True:
            return subprocess.check_output(cmd).decode("utf-8")
        else:
            subprocess.run(cmd)

    def prepare(self):
        print("Preparing")
        for server,data in targets.items():
            #Fetch current configs
            configs = self.cmd(server,'ls /etc/wireguard/',True)
            #Remove current configs
            #self.cmd(data['IP'],'rm /etc/wireguard/*',False)
            #Parse configs
            parsed = re.findall("^[A-Za-z]+",configs, re.MULTILINE)
            #Disable old configs
            for config in parsed:
                self.cmd(server,'systemctl stop wg-quick@'+config+' && systemctl disable wg-quick@w'+config,False)

    def run(self):
        global targets
        subnet,start,port = 1,1,51194
        self.prepare()
        T = Templator()
        print("Launching")
        for server,data in targets.items():
            print('---',server,'---')
            #Generate private key
            privateKey = self.cmd(server,'wg genkey',True)
            #Generate public key
            publicKey = self.cmd(server,'echo "'+privateKey+'" | wg pubkey',True)
            for client in data['Targets']:
                #Generate Server config
                serverConfig = T.genServer(subnet,start,port,privateKey,publicKey)
                #Put Server config
                print('Creating',client,'on',server)
                self.cmd(server,'echo "'+serverConfig+'" > /etc/wireguard/'+client+".conf",False)
                #Resolve hostname
                ip = subprocess.check_output(['resolveip','-s',server]).decode("utf-8")
                #Generate Client config
                clientConfig = T.genClient(ip.rstrip(),subnet,start,port,privateKey,publicKey)
                #Put Client config
                print('Creating',server,'on',client)
                self.cmd(client,'echo "'+clientConfig+'" > /etc/wireguard/'+server+".conf",False)
                #Enable Server
                self.cmd(server,'systemctl enable wg-quick@w'+client+' && systemctl start wg-quick@'+client,False)
                #Enable Client
                self.cmd(client,'systemctl enable wg-quick@w'+server+' && systemctl start wg-quick@'+server,False)
                start +=2
                port +=1
            subnet +=1
