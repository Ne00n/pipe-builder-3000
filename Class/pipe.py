import subprocess, time, json, re
from Class.templator import Templator

targets = []

class Pipe:
    def __init__(self,config="hosts.json"):
        global targets
        print("Loading",config)
        with open(config) as handle:
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
            if client.endswith("Serv") and Filter == True or Filter == False:
                #Stop Server
                print("Stopping",client.replace("Serv",""),"on",server)
                self.cmd(server.replace("v6",""),'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client,False)
                if delete == True:
                    self.cmd(server.replace("v6",""),'rm -f /etc/wireguard/'+client+".conf",False)
                #Stop Client
                v6 = 'v6' if client.endswith("v6Serv") else ''
                client = client.replace("Serv","").replace("pipe","").replace("v6","")
                print("Stopping","pipe"+server+v6,"on",client)
                self.cmd(client,'systemctl stop wg-quick@pipe'+server+v6+' && systemctl disable wg-quick@pipe'+server+v6,False)
                if delete == True:
                    self.cmd(client,'rm -f /etc/wireguard/pipe'+server+v6+".conf",False)

    def clean(self):
        global targets
        for server,data in targets.items():
            self.prepare(server,False,True)

    def shutdown(self):
        global targets
        for server,data in targets.items():
            self.prepare(server,False)

    def isClient(self,client):
        global targets
        return False if client.replace("v6","") in targets else True

    def execute(self,clients,subnet,start,port,client,server,privateServer,publicServer,ipv6=False):
        global targets
        T = Templator()
        #Generate Client private key
        privateClient = self.cmd(client.replace("v6",""),'wg genkey',True)
        #Generate Client public key
        publicClient = self.cmd(client.replace("v6",""),'echo "'+privateClient+'" | wg pubkey',True)
        #Generate Server config
        serverConfig = T.genServer(targets,subnet,start,port,privateServer.rstrip(),publicClient.rstrip())
        #Put Server config & Start
        print('Creating & Starting',client,'on',server)
        self.cmd(server.replace("v6",""),'echo "'+serverConfig+'" > /etc/wireguard/pipe'+client+'Serv.conf && systemctl enable wg-quick@pipe'+client+'Serv && systemctl start wg-quick@pipe'+client+'Serv',False)
        #Resolve hostname
        ip = subprocess.check_output(['dig','ANY','+short',server]).decode("utf-8")
        ip = '['+ip.rstrip()+']' if ipv6 else ip
        #Generate Client config
        clientIP = False
        if self.isClient(client) and client not in clients:
            clients.append(client)
            clientIP = True
        clientConfig = T.genClient(targets,ip.rstrip(),subnet,start,port,privateClient.rstrip(),publicServer.rstrip(),clientIP,clients,client.replace("v6",""))
        #Put Client config & Start
        print('Creating & Starting',server,'on',client)
        self.cmd(client.replace("v6",""),'echo "'+clientConfig+'" > /etc/wireguard/pipe'+server+'.conf && systemctl enable wg-quick@pipe'+server+' && systemctl start wg-quick@pipe'+server,False)
        print('Done',client,'on',server)

    def run(self):
        global targets
        start,port = 4,51194
        crossConnect,clients = [],[]
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
                            self.execute(clients,data['id'],start,port,target,server,privateServer,publicServer)
                            start +=2
                            port +=1
                    if data['v6'] == True:
                        print("cross-connectv6™")
                        for target,row in targets.items():
                            #Prevent double connections & v4 peers
                            if target not in crossConnect and row['v6'] == True:
                                self.execute(clients,data['id'],start,port,target+"v6",server+"v6",privateServer,publicServer,True)
                                start +=2
                                port +=1
                else:
                    print("direct-connect™")
                    self.execute(clients,data['id'],start,port,client,server,privateServer,publicServer)
                    start +=2
                    port +=1
            #Reset port
            start,port = 4,51194
