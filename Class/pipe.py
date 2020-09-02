import subprocess, time, json, re
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
            #Fetch old configs
            configs = self.cmd(server,'ls /etc/wireguard/',True)
            #Remove old configs
            #self.cmd(data['IP'],'rm /etc/wireguard/*',False)
            #Parse configs
            parsed = re.findall("^pipe[A-Za-z0-9]+",configs, re.MULTILINE)
            #Disable old configs
            print("---",server,"---")
            for client in parsed:
                #Stop Server
                print("Stopping","pipe"+server,"on",client.replace("pipe",""))
                self.cmd(server.replace("pipe",""),'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client,False)
                #Stop Client
                print("Stopping",client,"on",server.replace("pipe",""))
                self.cmd(client.replace("pipe","") ,'systemctl stop wg-quick@pipe'+server+' && systemctl disable wg-quick@pipe'+server,False)

    def run(self):
        global targets
        subnet,start,port = 1,2,51194
        self.prepare()
        T = Templator()
        print("Launching")
        time.sleep(3)
        for server,data in targets.items():
            print('---',server,'---')
            #Generate Server private key
            privateServer = self.cmd(server,'wg genkey',True)
            #Generate Server public key
            publicServer = self.cmd(server,'echo "'+privateServer+'" | wg pubkey',True)
            for client in data['Targets']:
                #Generate Client private key
                privateClient = self.cmd(client,'wg genkey',True)
                #Generate Client public key
                publicClient = self.cmd(client,'echo "'+privateClient+'" | wg pubkey',True)
                #Generate Server config
                serverConfig = T.genServer(subnet,start,port,privateServer.rstrip(),publicClient.rstrip())
                #Put Server config
                print('Creating',client,'on',server)
                self.cmd(server,'echo "'+serverConfig+'" > /etc/wireguard/pipe'+client+".conf",False)
                #Resolve hostname
                ip = subprocess.check_output(['resolveip','-s',server]).decode("utf-8")
                #Generate Client config
                clientConfig = T.genClient(ip.rstrip(),subnet,start,port,privateClient.rstrip(),publicServer.rstrip())
                #Put Client config
                print('Creating',server,'on',client)
                self.cmd(client,'echo "'+clientConfig+'" > /etc/wireguard/pipe'+server+".conf",False)
                #Enable Server
                self.cmd(server,'systemctl enable wg-quick@pipe'+client+' && systemctl start wg-quick@pipe'+client,False)
                #Enable Client
                self.cmd(client,'systemctl enable wg-quick@pipe'+server+' && systemctl start wg-quick@pipe'+server,False)
                print('Done',client,'on',server)
                start +=2
                port +=1
            #Reset port and increase subnet
            port = 51194
            subnet +=1
