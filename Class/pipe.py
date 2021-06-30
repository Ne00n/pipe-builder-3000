import subprocess, time, json, re
from Class.templator import Templator

targets = []

class Pipe:
    def __init__(self,config="hosts.json"):
        print("Loading",config)
        with open(config) as handle:
            self.targets = json.loads(handle.read())

    def cmd(self,server,command,interactive):
        cmd = ['ssh','root@'+server,command]
        if interactive == True:
            return subprocess.check_output(cmd).decode("utf-8")
        else:
            subprocess.run(cmd)

    def checkResolve(self,server):
        ip = subprocess.check_output(['dig','ANY','+short',server]).decode("utf-8")
        if not ip: return False
        return True

    def prepare(self,server,Filter=True,delete=False):
        print("---",server,"Preparing","---")
        #Check if v6 only
        suffix = ""
        if self.checkResolve(server) is False and self.checkResolve(server+"v6") is True:
            print("Switching",server,"to v6 only")
            suffix ="v6"
        #Fetch old configs
        configs = self.cmd(server+suffix,'ls /etc/wireguard/',True)
        #Parse configs
        parsed = re.findall("^pipe[A-Za-z0-9]+",configs, re.MULTILINE)
        #Disable old configs
        for client in parsed:
            #Only shutdown connections the server is in charge
            if client.endswith("Serv") and Filter == True or Filter == False:
                #Stop Server
                print("Stopping",client.replace("Serv",""),"on",server)
                self.cmd(server+suffix,'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client,False)
                if delete == True:
                    self.cmd(server+suffix,'rm -f /etc/wireguard/'+client+".conf",False)
                #Stop Client
                v6 = 'v6' if client.endswith("v6Serv") else ''
                client = client.replace("Serv","").replace("pipe","").replace("v6","")
                if self.checkResolve(client) is False and self.checkResolve(client+"v6") is True:
                    print("Switching",client,"to v6 only")
                    suffix ="v6"
                else:
                    suffix = ""
                print("Stopping","pipe"+server+v6,"on",client+suffix)
                self.cmd(client+suffix,'systemctl stop wg-quick@pipe'+server+v6+' && systemctl disable wg-quick@pipe'+server+v6,False)
                if delete == True:
                    self.cmd(client+suffix,'rm -f /etc/wireguard/pipe'+server+v6+".conf",False)

    def clean(self):
        for server,data in self.targets.items():
            self.prepare(server,False,True)

    def shutdown(self):
        for server,data in self.targets.items():
            self.prepare(server,False)

    def isClient(self,client):
        return False if client.replace("v6","") in self.targets else True

    def execute(self,clients,data,start,port,client,server,privateServer,publicServer,ipv6=False,dummy=False):
        v6only = False
        #Templator
        T = Templator()
        #Generate Client private key
        privateClient = self.cmd(client,'wg genkey',True)
        #Generate Client public key
        publicClient = self.cmd(client,'echo "'+privateClient+'" | wg pubkey',True)
        #Check if we are on v6 only
        if self.checkResolve(server.replace("v6","")) is False: v6only = True
        #Generate Server config
        serverConfig = T.genServer(self.targets,data,start,port,privateServer.rstrip(),publicClient.rstrip(),v6only)
        #Put Server config & Start
        print('Creating & Starting',client,'on',server)
        self.cmd(server,'echo "'+serverConfig+'" > /etc/wireguard/pipe'+client+'Serv.conf && systemctl enable wg-quick@pipe'+client+'Serv && systemctl start wg-quick@pipe'+client+'Serv',False)
        if dummy is True: return True
        #Resolve hostname
        ip = subprocess.check_output(['dig','ANY','+short',server]).decode("utf-8")
        ip = '['+ip.rstrip()+']' if ipv6 else ip
        #Generate Client config
        clientIP = False
        if self.isClient(client) and client not in clients:
            clients.append(client)
            clientIP = True
        clientConfig = T.genClient(self.targets,ip.rstrip(),data['id'],start,port,privateClient.rstrip(),publicServer.rstrip(),clientIP,clients,client.replace("v6",""))
        #Put Client config & Start
        print('Creating & Starting',server,'on',client)
        self.cmd(client,'echo "'+clientConfig+'" > /etc/wireguard/pipe'+server+'.conf && systemctl enable wg-quick@pipe'+server+' && systemctl start wg-quick@pipe'+server,False)
        print('Done',client,'on',server)

    def run(self):
        start = 4
        crossConnect,clients = [],[]
        print("Launching")
        time.sleep(3)
        for server,data in self.targets.items():
            #Prepare
            port = data['basePort']
            self.prepare(server)
            print("---",server,"Deploying","---")
            #Check if v6 only
            v6only,suffix = False,""
            if self.checkResolve(server) is False and self.checkResolve(server+"v6") is True:
                print("Switching",server,"to v6 only")
                v6only,suffix = True,"v6"
            #Generate Server private key
            privateServer = self.cmd(server+suffix,'wg genkey',True)
            #Generate Server public key
            publicServer = self.cmd(server+suffix,'echo "'+privateServer+'" | wg pubkey',True)
            for client in data['Targets']:
                if client == "*":
                    crossConnect.append(server)
                    execute = False
                    print("cross-connect™")
                    for target in self.targets:
                        #Prevent v4 connections to v6 only hosts
                        if self.checkResolve(target) is False and self.checkResolve(target+"v6") is True: continue
                        #Prevent double connections
                        if target not in crossConnect:
                            self.execute(clients,data,start,port,target,server,privateServer,publicServer)
                            execute = True
                            start +=2
                            port +=1
                    if data['v6'] == True:
                        print("cross-connectv6™")
                        for target,row in self.targets.items():
                            #Prevent double connections & v4 peers
                            if target not in crossConnect and row['v6'] == True:
                                self.execute(clients,data,start,port,target+"v6",server+"v6",privateServer,publicServer,True)
                                execute = True
                                start +=2
                                port +=1
                    #Check if target has any wg configuration
                    if execute is False:
                        print("Adding dummy for",server+suffix,"so vxlan works fine")
                        port = 51194
                        self.execute(clients,data,start,port,server+suffix,server+suffix,privateServer,publicServer,False,True)
                else:
                    print("direct-connect™")
                    self.execute(clients,data,start,port,client,server,privateServer,publicServer)
                    start +=2
                    port +=1
            #Reset port
            start = 4
