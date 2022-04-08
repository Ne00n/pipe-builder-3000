import subprocess, random, time, json, re
from Class.templator import Templator
from threading import Thread

class Pipe:
    def __init__(self,config="hosts.json"):
        print("Loading",config)
        with open(config) as handle:
            self.targets = json.loads(handle.read())

    def cmd(self,server,command,runs=4):
        cmd = ['ssh','root@'+server,command]
        for run in range(runs):
            try:
                p = subprocess.run(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                if p.returncode != 0:
                    print("Warning got returncode",p.returncode,"on",server)
                    print("Error:",p.stderr.decode('utf-8'))
                if p.returncode != 255: return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]
            except Exception as e:
                print("Error:",e)
            print("Retrying",cmd,"on",server)
            time.sleep(random.randint(5, 15))
        return ["failed","failed"]

    def resolveHostname(self,hostname):
        return subprocess.check_output(['dig','ANY','+short',hostname]).decode("utf-8")

    def checkResolve(self,server):
        ip = self.resolveHostname(server)
        if not ip: return False
        return True

    def preflight(self):
        print("Pre-flight")
        names,ips = [],[]
        for server,data in self.targets['servers'].items():
            print(f"Checking {server}")
            v4 = self.resolveHostname(server)
            v6 = self.resolveHostname(f"{server}v6")
            if not v4 and not v6: exit(f"Could not resolve {server}")
            if v4:
                wg = self.cmd(server,'wg help',2)[0]
                if "Usage: wg <cmd>" not in wg: exit(f"Connectivity issue or Wireguard not installed on {server}")
            if v6:
                wg = self.cmd(f"{server}v6",'wg help',2)[0]
                if "Usage: wg <cmd>" not in wg: exit(f"Connectivity issue or Wireguard not installed on {server}v6")
            if server in names: exit(f"name collision on {server}")
            if data['id'] in ips: exit(f"id collision on {data['id']}")
            names.append(server)
            ips.append(data['id'])
        input("Pre-flight done, press any key to launch")

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
            clientName = client.replace("Serv","").replace(self.targets['prefix'],"").replace("v6","")
            #Only shutdown connections the server is in charge
            if client.endswith("Serv") and Filter == True or Filter == False or clean == True and clientName in ignorelist:
                #Reconfigure
                if reconfigure and reconfigure[0] != "" and (clientName not in reconfigure and server not in reconfigure): continue
                #Stop Server
                print("Stopping",client.replace("Serv",""),"on",server)
                if threading:
                    threads.append(Thread(target=self.cmd, args=([server+serverSuffix,'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client])))
                else:
                    self.cmd(server+serverSuffix,'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client)
                if delete == True or clean == True and clientName in ignorelist:
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
                    if clientName == "dummy":
                        print("Skipping",client)
                        continue
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

    def match(self):
        serverSuffix = ""
        for server,data in self.targets['servers'].items():
            print("---",server,"Checking","---")
            if self.checkResolve(server) is False and self.checkResolve(server+"v6") is True:
                print("Switching",server,"to v6 only")
                serverSuffix ="v6"
            configs = self.cmd(server+serverSuffix,'ls /etc/wireguard/')[0]
            #Parse configs
            parsed = re.findall("^"+self.targets['prefix']+"[A-Za-z0-9]+",configs, re.MULTILINE)
            #Disable old configs
            for client in parsed:
                clientName = client.replace("Serv","").replace(self.targets['prefix'],"").replace("v6","")
                if clientName not in self.targets['servers']:
                    print("Could not find",clientName,"in servers")

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

    def average(self,result):
        parsed = re.findall("([0-9a-z.:]+).*?([0-9]+.[0-9]).*?([0-9])% loss",result, re.MULTILINE)
        total = 0
        for ip,ms,loss in parsed:
            total += float(ms)
        return total / len(parsed)

    def execute(self,clients,data,start,port,client,server,privateServer,publicServer,ipv6=False,dummy=False):
        v6only = False
        #Templator
        T = Templator()
        #Generate Client and Public key
        keys = self.cmd(client,'key=$(wg genkey) && echo $key && echo $key | wg pubkey')[0]
        privateClient, publicClient = keys.splitlines()
        #Check if we are on v6 only
        if self.checkResolve(server.replace("v6","")) is False: v6only = True
        #Resolve hostname
        ip = self.resolveHostname(server)
        ip = '['+ip.rstrip()+']' if ipv6 else ip
        #Generate Server config
        serverConfig = T.genServer(self.targets['servers'],ip.rstrip(),data,start,port,privateServer.rstrip(),publicClient.rstrip(),self.targets,v6only)
        #Type Check
        if data['type'] == 'boringtun':
            serviceConfig = T.genBoringtun()
            self.cmd(server,'mkdir -p /etc/systemd/system/wg-quick@'+self.targets['prefix']+client+'Serv.service.d/; echo "'+serviceConfig+'" > /etc/systemd/system/wg-quick@'+self.targets['prefix']+client+'Serv.service.d/boringtun.conf')
        #Put Server config & Start
        if dummy is True: client = "dummy"
        print('Creating & Starting',client,'on',server)
        self.cmd(server,'echo "'+serverConfig+'" > /etc/wireguard/'+self.targets['prefix']+client+'Serv.conf && systemctl enable wg-quick@'+self.targets['prefix']+client+'Serv && systemctl start wg-quick@'+self.targets['prefix']+client+'Serv')
        if dummy is True: return True
        #Generate Client config
        clientIP = False
        if self.isClient(client) and client.replace("v6","") not in clients:
            clients.append(client.replace("v6",""))
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
        threading,cleanList,start = False,[],50
        crossConnect,clients,threads = [],[],[]
        answer = input("Use Threading? (y/enter): ")
        clean = input("Any servers to ignore and remove? (Name,Name../enter): ")
        reconfigure = input("Reconfigure any servers? (Name,Name../enter): ")
        clean = clean.split(",")
        reconfigure = reconfigure.split(",")
        if reconfigure[0] != "":
            reconfigure.append("dummy")
        if answer == "y": threading = True
        self.preflight()
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
            #Generate Server keys
            keys = self.cmd(server+suffix,'key=$(wg genkey) && echo $key && echo $key | wg pubkey')[0]
            privateServer, publicServer = keys.splitlines()
            for client in data['Targets']:
                if client == "*" or client == "geo":
                    crossConnect.append(server)
                    execute = False
                    print("cross-connectv4|v6™")
                    for target,targetData in self.targets['servers'].items():
                        if "*" not in targetData['Targets'] and "geo" not in targetData['Targets'] and server not in targetData['Targets']:
                            print("Skipping",target,"since no crossConnect")
                            continue
                        #Prevent double connections
                        if target in crossConnect: continue
                        #Resolve
                        v4,v6 = False,False
                        if self.checkResolve(server) and self.checkResolve(target): v4 = True
                        if self.checkResolve(server+"v6") and self.checkResolve(target+"v6"): v6 = True
                        #Geo
                        if "geo" in targetData['Targets'] or "geo" in data['Targets']:
                            if v4: 
                                targetv4 = self.resolveHostname(target)
                                print(f"Getting Latency for {target} for GEO")
                                result = self.cmd(server,f'fping -c 3 {targetv4}')[0]
                                latency = self.average(result)
                                if latency > 200: 
                                    print(f"Skipping link to {target} latency to high")
                                    v4 = False
                            if v6: 
                                targetv6 = self.resolveHostname(f"{target}v6")
                                print(f"Getting Latency for {target}v6 for GEO")
                                result = self.cmd(f"{server}v6",f'fping -c 3 {targetv6}')[0]
                                latency = self.average(result)
                                if latency > 200: 
                                    print(f"Skipping link to {target} latency to high")
                                    v6 = False
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
                    self.execute(clients,data,start,port,target,server+suffix,privateServer,publicServer,False,True)
                else:
                    threads.append(Thread(target=self.execute, args=([clients,data,start,port,target,server+suffix,privateServer,publicServer,False,True])))
            if answer == "y":
                if rate == 0.2 and len(threads) > 4:
                    rate = len(threads) * 0.05
                    if rate > 2: rate = 2
                    print(server,"Updated rate",rate)
                self.lunchThreads(threads,rate)
            #Reset stuff
            threads,start = [],50
