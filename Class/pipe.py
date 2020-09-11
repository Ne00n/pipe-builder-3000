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

    def prepare(self,server,Filter=True,delete=False):
        print("---",server,"Preparing","---")
        #Fetch old configs
        configs = self.cmd(server,'ls /etc/wireguard/',True)
        #Parse configs
        parsed = re.findall("^pipe[A-Za-z0-9]+",configs, re.MULTILINE)
        #Disable old configs
        for client in parsed:
            #Only shutdown connections the server is in charge
            if client.endswith("Server") and Filter == True or Filter == False:
                #Stop Server
                print("Stopping","pipe"+server,"on",client.replace("pipe","").replace("Server",""))
                self.cmd(server,'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client,False)
                if delete == True:
                    self.cmd(server,'rm -f /etc/wireguard/'+client+".conf",False)
                #Stop Client
                client = client.replace("pipe","").replace("Server","")
                print("Stopping",client,"on",server)
                self.cmd(client.replace("pipe",""),'systemctl stop wg-quick@pipe'+server+' && systemctl disable wg-quick@pipe'+server,False)
                if delete == True:
                    self.cmd(client.replace("pipe",""),'rm -f /etc/wireguard/pipe'+server+".conf",False)

    def clean(self):
        global targets
        for server,data in targets.items():
            self.prepare(server,False,True)

    def shutdown(self):
        global targets
        for server,data in targets.items():
            self.prepare(server,False)

    def execute(self,subnet,start,port,client,server,privateServer,publicServer):
        T = Templator()
        #Generate Client private key
        privateClient = self.cmd(client,'wg genkey',True)
        #Generate Client public key
        publicClient = self.cmd(client,'echo "'+privateClient+'" | wg pubkey',True)
        #Generate Server config
        serverConfig = T.genServer(subnet,start,port,privateServer.rstrip(),publicClient.rstrip())
        #Put Server config
        print('Creating',client,'on',server)
        self.cmd(server,'echo "'+serverConfig+'" > /etc/wireguard/pipe'+client+"Server.conf",False)
        #Resolve hostname
        ip = subprocess.check_output(['resolveip','-s',server]).decode("utf-8")
        #Generate Client config
        clientConfig = T.genClient(ip.rstrip(),subnet,start,port,privateClient.rstrip(),publicServer.rstrip())
        #Put Client config
        print('Creating',server,'on',client)
        self.cmd(client,'echo "'+clientConfig+'" > /etc/wireguard/pipe'+server+".conf",False)
        #Enable Server
        self.cmd(server,'systemctl enable wg-quick@pipe'+client+'Server && systemctl start wg-quick@pipe'+client+'Server',False)
        #Enable Client
        self.cmd(client,'systemctl enable wg-quick@pipe'+server+' && systemctl start wg-quick@pipe'+server,False)
        print('Done',client,'on',server)

    def run(self):
        global targets
        subnet,start,port = 1,2,51194
        crossConnect = []
        print("Launching")
        time.sleep(3)
        for server,data in targets.items():
            #Prepare
            self.prepare(server)
            print("---",server,"Deploying","---")
            #Generate Server private key
            privateServer = self.cmd(server,'wg genkey',True)
            #Generate Server public key
            publicServer = self.cmd(server,'echo "'+privateServer+'" | wg pubkey',True)
            for client in data['Targets']:
                if client == "*":
                    crossConnect.append(server)
                    print("cross-connect™")
                    for target in targets:
                        #Prevent double connections
                        if target not in crossConnect:
                            self.execute(subnet,start,port,target,server,privateServer,publicServer)
                            start +=2
                            port +=1
                else:
                    self.execute(subnet,start,port,client,server,privateServer,publicServer)
                    start +=2
                    port +=1
            #Reset port and increase subnet
            port = 51194
            start = 2
            subnet +=1
