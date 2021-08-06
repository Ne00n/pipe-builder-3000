import subprocess, random, time, json, re
from Class.templator import Templator
from threading import Thread

class Pipe:
    def __init__(self,config="hosts.json"):
        print("Loading",config)
        with open(config) as handle:
            self.targets = json.loads(handle.read())

    def cmd(self,server,command):
        cmd = ['ssh','root@'+server,command]
        for run in range(4):
            try:
                p = subprocess.run(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                if p.returncode != 0:
                    print("Warning got returncode",p.returncode,"on",server)
                    print("Error:",p.stderr.decode('utf-8'))
                if p.returncode != 255: break
            except Exception as e:
                print("Error:",e)
            print("Retrying",cmd,"on",server)
            time.sleep(random.randint(5, 15))
        return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]

    def checkResolve(self,server):
        ip = subprocess.check_output(['dig','ANY','+short',server]).decode("utf-8")
        if not ip: return False
        return True

    def prepare(self,server,threading=False,Filter=True,delete=False,ignorelist=[],clean=False,reconfigure=[]):
        print("---",server,"Preparing","---")
        #Check if v6 only
        serverSuffix,threads,files = "",[],[]
        if self.checkResolve(server) is False and self.checkResolve(server+"v6") is True:
            print("Switching",server,"to v6 only")
            serverSuffix ="v6"
        #Fetch old configs
        configs = self.cmd(server+serverSuffix,'ls /etc/wireguard/')[0]
        #Parse configs
        parsed = re.findall("^"+self.targets['prefix']+"[A-Za-z0-9]+",configs, re.MULTILINE)
        #Disable old configs
        for client in parsed:
            #Only shutdown connections the server is in charge
            if client.endswith("Serv") and Filter == True or Filter == False:
                #Stop Server
                clientName = client.replace("Serv","").replace(self.targets['prefix'],"").replace("v6","")
                #Reconfigure
                if reconfigure[0] != "" and (clientName not in reconfigure and server not in reconfigure): continue
                print("Stopping",client.replace("Serv",""),"on",server)
                if threading:
                    threads.append(Thread(target=self.cmd, args=([server+serverSuffix,'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client])))
                else:
                    self.cmd(server+serverSuffix,'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client)
                if delete == True and clientName not in ignorelist or clean == True and clientName in ignorelist:
                    print("Deleting",client.replace("Serv",""),"on",server)
                    if threading:
                        files.append(Thread(target=self.cmd, args=([server+serverSuffix,'rm -f /etc/wireguard/'+client+'.conf'])))
                    else:
                        self.cmd(server+serverSuffix,'rm -f /etc/wireguard/'+client+'.conf')
                #Stop Client
                v6 = 'v6' if client.endswith("v6Serv") else ''
                if self.checkResolve(clientName) is False and self.checkResolve(clientName+"v6") is True:
                    print("Switching",clientName,"to v6 only")
                    suffix ="v6"
                else:
                    suffix = ""
                print("Stopping",self.targets['prefix']+server+v6,"on",clientName+suffix)
                if threading and clientName not in ignorelist:
                    threads.append(Thread(target=self.cmd, args=([clientName+suffix,'systemctl stop wg-quick@'+self.targets['prefix']+server+v6+' && systemctl disable wg-quick@'+self.targets['prefix']+server+v6])))
                elif clientName not in ignorelist:
                    self.cmd(clientName+suffix,'systemctl stop wg-quick@'+self.targets['prefix']+server+v6+' && systemctl disable wg-quick@'+self.targets['prefix']+server+v6)
                if delete == True and clientName not in ignorelist or clean == True and clientName not in ignorelist and server in ignorelist:
                    print("Deleting",self.targets['prefix']+server+v6,"on",clientName+suffix)
                    if threading:
                        files.append(Thread(target=self.cmd, args=([clientName+suffix,'rm -f /etc/wireguard/'+self.targets['prefix']+server+v6+'.conf'])))
                    else:
                        self.cmd(clientName+suffix,'rm -f /etc/wireguard/'+self.targets['prefix']+server+v6+'.conf')
        if threading:
            self.lunchThreads(threads)
            self.lunchThreads(files)

    def clean(self):
        threads,ignoreList = [],[]
        answer = input("Use Threading? (y/n): ")
        ignore = input("Any nodes to ignore? (Name,Name../n): ")
        if ignore != "n":
            ignoreList = ignore.split(",")
        for server,data in self.targets['servers'].items():
            if server in ignoreList: continue
            if answer != "y":
                self.prepare(server,False,False,True,ignoreList)
            else:
                threads.append(Thread(target=self.prepare, args=([server,False,False,True,ignoreList])))
        if answer == "y": self.lunchThreads(threads)

    def check(self):
        for server,data in self.targets['servers'].items():
            print("---",server,"Checking","---")
            suffix = ""
            if self.checkResolve(server) is False and self.checkResolve(server+"v6") is True:
                print("Switching",server,"to v6 only")
                suffix = "v6"
            nics = self.cmd(server+suffix,'ip addr show')[0]
            if self.targets['prefix'] in nics:
                print("connections detected")
            else:
                print("no connections detected")

    def reboot(self):
        print("WARNING, this is going to reboot all machines!")
        answer = input("Continue? (y/n): ")
        if answer == "y":
            for server,data in self.targets['servers'].items():
                print("---",server,"Rebooting","---")
                suffix = ""
                if self.checkResolve(server) is False and self.checkResolve(server+"v6") is True:
                    print("Switching",server,"to v6 only")
                    suffix = "v6"
                self.cmd(server+suffix,'reboot')

    def shutdown(self):
        threads = []
        answer = input("Use Threading? (y/n): ")
        for server,data in self.targets['servers'].items():
            if answer != "y":
                self.prepare(server,False,False)
            else:
                threads.append(Thread(target=self.prepare, args=([server,False])))
        if answer == "y": self.lunchThreads(threads)

    def lunchThreads(self,threads,rate=0.2):
        if threads:
            for thread in threads:
                thread.start()
                time.sleep(rate)
            for thread in threads:
                thread.join()

    def isClient(self,client):
        return False if client.replace("v6","") in self.targets['servers'] else True

    def increaseDis(self,start,port):
        start +=2
        port +=1
        return start,port

    def execute(self,clients,data,start,port,client,server,privateServer,publicServer,ipv6=False,dummy=False):
        v6only = False
        #Templator
        T = Templator()
        #Generate Client private key
        privateClient = self.cmd(client,'wg genkey')[0]
        #Generate Client public key
        publicClient = self.cmd(client,'echo "'+privateClient+'" | wg pubkey')[0]
        #Check if we are on v6 only
        if self.checkResolve(server.replace("v6","")) is False: v6only = True
        #Generate Server config
        serverConfig = T.genServer(self.targets['servers'],data,start,port,privateServer.rstrip(),publicClient.rstrip(),self.targets,v6only)
        #Type Check
        if data['type'] == 'boringtun':
            serviceConfig = T.genBoringtun()
            self.cmd(server,'mkdir -p /etc/systemd/system/wg-quick@'+self.targets['prefix']+client+'Serv.service.d/; echo "'+serviceConfig+'" > /etc/systemd/system/wg-quick@'+self.targets['prefix']+client+'Serv.service.d/boringtun.conf')
        #Put Server config & Start
        print('Creating & Starting',client,'on',server)
        self.cmd(server,'echo "'+serverConfig+'" > /etc/wireguard/'+self.targets['prefix']+client+'Serv.conf && systemctl enable wg-quick@'+self.targets['prefix']+client+'Serv && systemctl start wg-quick@'+self.targets['prefix']+client+'Serv')
        if dummy is True: return True
        #Resolve hostname
        ip = subprocess.check_output(['dig','ANY','+short',server]).decode("utf-8")
        ip = '['+ip.rstrip()+']' if ipv6 else ip
        #Generate Client config
        clientIP = False
        if self.isClient(client) and client not in clients:
            clients.append(client)
            clientIP = True
        clientConfig = T.genClient(self.targets['servers'],ip.rstrip(),data['id'],start,port,privateClient.rstrip(),publicServer.rstrip(),clientIP,clients,client.replace("v6",""),self.targets)
        #Type Check
        if client.replace("v6","") in self.targets['servers'] and self.targets['servers'][client.replace("v6","")]['type'] == 'boringtun':
            serviceConfig = T.genBoringtun()
            self.cmd(client,'mkdir -p /etc/systemd/system/wg-quick@'+self.targets['prefix']+server+'.service.d/; echo "'+serviceConfig+'" > /etc/systemd/system/wg-quick@'+self.targets['prefix']+server+'.service.d/boringtun.conf')
        #Put Client config & Start
        print('Creating & Starting',server,'on',client)
        self.cmd(client,'echo "'+clientConfig+'" > /etc/wireguard/'+self.targets['prefix']+server+'.conf && systemctl enable wg-quick@'+self.targets['prefix']+server+' && systemctl start wg-quick@'+self.targets['prefix']+server)
        print('Done',client,'on',server)

    def run(self):
        threading,cleanList,start = False,[],4
        crossConnect,clients,threads = [],[],[]
        answer = input("Use Threading? (y/n): ")
        clean = input("Any servers to ignore and remove? (Name,Name../n): ")
        reconfigure = input("Reconfigure any servers? (Name,Name../n): ")
        clean = clean.split(",")
        reconfigure = reconfigure.split(",")
        if answer == "y": threading = True
        print("Launching")
        time.sleep(3)
        for server,data in self.targets['servers'].items():
            #Prepare
            if data['basePort'] == "random":
                self.targets['servers'][server]['basePort'] = port = random.randint(1500, 55000)
            else:
                port = data['basePort']
            if "rate" in self.targets['servers'][server]:
                rate = self.targets['servers'][server]['rate']
            else:
                rate = 0.2
            self.prepare(server,threading,True,False,clean,bool(clean),reconfigure)
            print("---",server,"Deploying","---")
            print(server,"Using rate",rate)
            #Check if v6 only
            v6only,suffix = False,""
            if self.checkResolve(server) is False and self.checkResolve(server+"v6") is True:
                print("Switching",server,"to v6 only")
                v6only,suffix = True,"v6"
            #Generate Server private key
            privateServer = self.cmd(server+suffix,'wg genkey')[0]
            #Generate Server public key
            publicServer = self.cmd(server+suffix,'echo "'+privateServer+'" | wg pubkey')[0]
            for client in data['Targets']:
                if client == "*":
                    crossConnect.append(server)
                    execute = False
                    print("cross-connectv4|v6™")
                    for target,targetData in self.targets['servers'].items():
                        if "*" not in targetData['Targets'] and server not in targetData['Targets']:
                            print("Skipping",target,"since no crossConnect")
                            continue
                        v4,v6 = False,False
                        if self.checkResolve(server) and self.checkResolve(target): v4 = True
                        if self.checkResolve(server+"v6") and self.checkResolve(target+"v6"): v6 = True
                        #Prevent double connections
                        if target in crossConnect: continue
                        #Threading
                        if answer != "y":
                            if v4:
                                if reconfigure[0] == "" or reconfigure[0] != "" and (target in reconfigure or server in reconfigure):
                                    self.execute(clients,data,start,port,target,server,privateServer,publicServer)
                                start,port = self.increaseDis(start,port)
                            if v6:
                                if reconfigure[0] == "" or reconfigure[0] != "" and (target in reconfigure or server in reconfigure):
                                    self.execute(clients,data,start,port,target+"v6",server+"v6",privateServer,publicServer,True)
                                start,port = self.increaseDis(start,port)
                        else:
                            if v4:
                                if reconfigure[0] == "" or reconfigure[0] != "" and (target in reconfigure or server in reconfigure):
                                    threads.append(Thread(target=self.execute, args=([clients,data,start,port,target,server,privateServer,publicServer])))
                                start,port = self.increaseDis(start,port)
                            if v6:
                                if reconfigure[0] == "" or reconfigure[0] != "" and (target in reconfigure or server in reconfigure):
                                    threads.append(Thread(target=self.execute, args=([clients,data,start,port,target+"v6",server+"v6",privateServer,publicServer,True])))
                                start,port = self.increaseDis(start,port)
                        execute = True
                else:
                    v4,v6 = False,False
                    if client in crossConnect: continue
                    if self.checkResolve(server) and self.checkResolve(client): v4 = True
                    if self.checkResolve(server+"v6") and self.checkResolve(client+"v6"): v6 = True
                    print("direct-connectv4|v6™")
                    #Threading
                    if answer != "y":
                        if v4:
                            if reconfigure[0] == "" or reconfigure[0] != "" and (client in reconfigure or server in reconfigure):
                                self.execute(clients,data,start,port,client,server,privateServer,publicServer)
                            start,port = self.increaseDis(start,port)
                        if v6:
                            if reconfigure[0] == "" or reconfigure[0] != "" and (client in reconfigure or server in reconfigure):
                                self.execute(clients,data,start,port,client+"v6",server+"v6",privateServer,publicServer,True)
                            start,port = self.increaseDis(start,port)
                    else:
                        if v4:
                            if reconfigure[0] == "" or reconfigure[0] != "" and (client in reconfigure or server in reconfigure):
                                threads.append(Thread(target=self.execute, args=([clients,data,start,port,client,server,privateServer,publicServer])))
                            start,port = self.increaseDis(start,port)
                        if v6:
                            if reconfigure[0] == "" or reconfigure[0] != "" and (client in reconfigure or server in reconfigure):
                                threads.append(Thread(target=self.execute, args=([clients,data,start,port,client+"v6",server+"v6",privateServer,publicServer,True])))
                            start,port = self.increaseDis(start,port)
                    execute = True
            #Check if target has any wg configuration
            if execute is False:
                print("Adding dummy for",server+suffix,"so vxlan works fine")
                if answer != "y":
                    self.execute(clients,data,start,port,server+suffix,server+suffix,privateServer,publicServer,False,True)
                else:
                    threads.append(Thread(target=self.execute, args=([clients,data,start,port,server+suffix,server+suffix,privateServer,publicServer,False,True])))
            if answer == "y":
                if rate == 0.2 and len(threads) > 4:
                    rate = len(threads) * 0.05
                    if rate > 2: rate = 2
                    print(server,"Updated rate",rate)
                self.lunchThreads(threads,rate)
            #Reset stuff
            threads,start = [],4
