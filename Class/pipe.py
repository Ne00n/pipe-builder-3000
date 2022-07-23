import subprocess, random, time, json, re
from Class.templator import Templator
from threading import Thread
import multiprocessing

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

    def listToCmd(self,task):
        return self.cmd(task[0],task[1])

    def resolveHostname(self,hostname):
        return subprocess.check_output(['dig','ANY','+short',hostname]).decode("utf-8")

    def checkResolve(self,server):
        ip = self.resolveHostname(server)
        if not ip: return False
        return True

    def checkHost(self,host,serverData):
        v4 = self.resolveHostname(host).strip()
        v6 = self.resolveHostname(f"{host}v6").strip()
        suffix = "v6" if v6 and v4 is False else ""
        hostData = {"v4":v4,"v6":v6,"suffix":suffix}
        if not v4 and not v6: exit(f"Could not resolve {host}")
        if v4:
            wg = self.cmd(host,'wg help',2)[0]
            if "Usage: wg <cmd>" not in wg: exit(f"Connectivity issue or Wireguard not installed on {host}")
        if v6 and not "nDv6" in serverData:
            wg = self.cmd(f"{host}v6",'wg help',2)[0]
            if "Usage: wg <cmd>" not in wg: exit(f"Connectivity issue or Wireguard not installed on {host}v6")
        return hostData

    def preflight(self):
        print("Pre-flight")
        names,ips,resolve,clients = [],[],{},[]
        for server,serverData in self.targets['servers'].items():
            print(f"Checking {server}")
            resolve[server] = self.checkHost(server,serverData)
            if server in names: exit(f"name collision on {host}")
            if serverData['id'] in ips: exit(f"id collision on {serverData['id']}")
            names.append(server)
            ips.append(serverData['id'])
            print(f"Checking Clients of {server}")
            for client in serverData['Targets']:
                if client == "*" or client == "geo" or client in clients: continue
                resolve[client] = self.checkHost(client,{})
                clients.append(client)
        input("Pre-flight done, press any key to launch")
        return resolve

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
        parsed = re.findall("^"+self.targets['prefix']+"[A-Za-z0-9-]+",configs, re.MULTILINE)
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
                    threads.append([server+serverSuffix,'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client])
                else:
                    self.cmd(server+serverSuffix,'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client)
                if delete == True or clean == True and clientName in ignorelist:
                    print("Deleting",client.replace("Serv",""),"on",server)
                    if threading:
                        files.append([server+serverSuffix,'rm -f /etc/wireguard/'+client+'.conf'])
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
                    threads.append([clientName+suffix,'systemctl stop wg-quick@'+self.targets['prefix']+server+v6+' && systemctl disable wg-quick@'+self.targets['prefix']+server+v6])
                elif clientName not in ignorelist:
                    self.cmd(clientName+suffix,'systemctl stop wg-quick@'+self.targets['prefix']+server+v6+' && systemctl disable wg-quick@'+self.targets['prefix']+server+v6)
                if delete == True and clientName not in ignorelist or clean == True and clientName not in ignorelist and server in ignorelist:
                    print("Deleting",self.targets['prefix']+server+v6,"on",clientName+suffix)
                    if threading:
                        files.append([clientName+suffix,'rm -f /etc/wireguard/'+self.targets['prefix']+server+v6+'.conf'])
                    else:
                        self.cmd(clientName+suffix,'rm -f /etc/wireguard/'+self.targets['prefix']+server+v6+'.conf')
        if threading:
            #aggregation before dispatch
            threads = self.aggregate(threads)
            #shutdown the wireguards
            self.lunchPool(threads)
            #aggregation before dispatch
            files = self.aggregate(files)
            #removing the wireguards
            self.lunchPool(files)

    def aggregate(self,tasks,aggregation = 5):
        newTasks,loader = [],{}
        for task in tasks:
            if not task[0] in loader: loader[task[0]] = []
            loader[task[0]].append(task[1])
        for target,tasks in loader.items():
            for index in range(aggregation,len(tasks),aggregation):
                minimum = index - aggregation
                data = " && ".join(tasks[minimum:index])
                newTasks.append([target,data])
        random.shuffle(newTasks)
        return newTasks

    def clean(self):
        threads,ignoreList = [],[]
        answer = input("Use Threading? (y/n): ")
        ignore = input("Any nodes to ignore? (Name,Name../n): ")
        if ignore != "n":
            ignoreList = ignore.split(",")
        for server,serverData in self.targets['servers'].items():
            if server in ignoreList: continue
            if answer != "y":
                self.prepare(server,False,False,True,ignoreList)
            else:
                threads.append(Thread(target=self.prepare, args=([server,False,False,True,ignoreList])))
        if answer == "y": self.lunchThreads(threads)

    def check(self):
        for server,serverData in self.targets['servers'].items():
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
        for server,serverData in self.targets['servers'].items():
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
            for server,serverData in self.targets['servers'].items():
                print("---",server,"Rebooting","---")
                suffix = ""
                if self.checkResolve(server) is False and self.checkResolve(server+"v6") is True:
                    print("Switching",server,"to v6 only")
                    suffix = "v6"
                self.cmd(server+suffix,'reboot')

    def shutdown(self):
        threads = []
        answer = input("Use Threading? (y/n): ")
        for server,serverData in self.targets['servers'].items():
            if answer != "y":
                self.prepare(server,False,False)
            else:
                threads.append(Thread(target=self.prepare, args=([server,False])))
        if answer == "y": self.lunchThreads(threads)

    def lunchPool(self,tasks):
        pool = multiprocessing.Pool(processes = 10)
        results = pool.map(self.listToCmd, tasks)
        pool.close()
        pool.join()

    def lunchThreads(self,threads,rate=0.2):
        if threads:
            for thread in threads:
                thread.start()
                time.sleep(rate)
            for thread in threads:
                thread.join()

    def isClient(self,client):
        return False if client in self.targets['servers'] else True

    def average(self,result):
        parsed = re.findall("([0-9a-z.:]+).*?([0-9]+.[0-9]).*?([0-9])% loss",result, re.MULTILINE)
        if not parsed: return 65000
        total = 0
        for ip,ms,loss in parsed:
            try:
                total += float(ms)
            except:
                print(result)
                print(parsed)
                return 65000
        return total / len(parsed)

    def execute(self,clients,serverIP,basePort,client,server,privateServer,publicServer,ipv6=False,dummy=False):
        #Templator
        T = Templator()
        #Check for nDv6
        suffix = "v6" if ipv6 and not "nDv6" in self.targets['servers'][server] and client in self.targets['servers'] and not "nDv6" in self.targets['servers'][client] else ""
        wgSuffix = "v6" if ipv6 else ""
        #Generate Client and Public key
        keys = self.cmd(f"{client}{suffix}",'key=$(wg genkey) && echo $key && echo $key | wg pubkey')[0]
        privateClient, publicClient = keys.splitlines()
        #Prepare IP
        ip = f"[{self.resolve[server]['v6']}]" if ipv6 else self.resolve[server]['v4']
        #Generate Server config
        serverConfig = T.genServer(self.targets['servers'],ip.rstrip(),self.targets['servers'][server],serverIP,basePort,privateServer.rstrip(),publicClient.rstrip(),self.targets,bool(self.resolve[server]['suffix']))
        #Type Check
        if self.targets['servers'][server]['type'] == 'boringtun':
            serviceConfig = T.genBoringtun()
            self.cmd(f"{server}{suffix}",f'mkdir -p /etc/systemd/system/wg-quick@{self.targets["prefix"]}{client}{wgSuffix}Serv.service.d/; echo "{serviceConfig}" > /etc/systemd/system/wg-quick@{self.targets["prefix"]}{client}{wgSuffix}Serv.service.d/boringtun.conf')
        #Put Server config & Start
        if dummy is True: client = "dummy"
        print('Creating & Starting',client,'on',server)
        self.cmd(f"{server}{suffix}",f'echo "{serverConfig}" > /etc/wireguard/{self.targets["prefix"]}{client}{wgSuffix}Serv.conf && systemctl enable wg-quick@{self.targets["prefix"]}{client}{wgSuffix}Serv && systemctl start wg-quick@{self.targets["prefix"]}{client}{wgSuffix}Serv')
        if dummy is True: return True
        #Generate Client config
        clientIP = False
        if self.isClient(client) and client not in clients:
            clients.append(client)
            clientIP = True
        clientConfig = T.genClient(self.targets['servers'],ip.rstrip(),self.targets['servers'][server]['id'],serverIP,basePort,privateClient.rstrip(),publicServer.rstrip(),clientIP,clients,client,self.targets)
        #Type Check
        if client in self.targets['servers'] and self.targets['servers'][client]['type'] == 'boringtun':
            serviceConfig = T.genBoringtun()
            self.cmd(f"{client}{suffix}",f'mkdir -p /etc/systemd/system/wg-quick@{self.targets["prefix"]}{server}{wgSuffix}.service.d/; echo "{serviceConfig}" > /etc/systemd/system/wg-quick@{self.targets["prefix"]}{server}{wgSuffix}.service.d/boringtun.conf')
        #Put Client config & Start
        print('Creating & Starting',server,'on',client)
        self.cmd(f"{client}{suffix}",f'echo "{clientConfig}" > /etc/wireguard/{self.targets["prefix"]}{server}{wgSuffix}.conf && systemctl enable wg-quick@{self.targets["prefix"]}{server}{wgSuffix} && systemctl start wg-quick@{self.targets["prefix"]}{server}{wgSuffix}')
        print('Done',client,'on',server)

    def run(self):
        threading,cleanList,crossConnect,clients = False,[],[],[]
        answer = input("Use Threading? (y/enter): ")
        clean = input("Any servers to ignore and remove? (Name,Name../enter): ")
        reconfigure = input("Reconfigure any servers? (Name,Name../enter): ")
        clean = clean.split(",")
        reconfigure = reconfigure.split(",")
        if reconfigure[0] != "":
            reconfigure.append("dummy")
        if answer == "y": threading = True
        self.resolve = self.preflight()
        print("Launching")
        time.sleep(3)
        for server,serverData in self.targets['servers'].items():
            #Define/Reset stuff
            threads,serverIP = [],4
            #Prepare
            if serverData['basePort'] == "random":
                self.targets['servers'][server]['basePort'] = basePort = random.randint(1500, 55000)
            else:
                basePort = serverData['basePort']
            if "rate" in self.targets['servers'][server]:
                rate = self.targets['servers'][server]['rate']
            else:
                rate = 0.2
            self.prepare(server,threading,True,False,clean,bool(clean),reconfigure)
            print("---",server,"Deploying","---")
            print(server,"Using rate",rate)
            #Check if v6 only
            suffix = self.resolve[server]['suffix']
            #Generate Server keys
            keys = self.cmd(server+suffix,'key=$(wg genkey) && echo $key && echo $key | wg pubkey')[0]
            privateServer, publicServer = keys.splitlines()
            for client in serverData['Targets']:
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
                        v4 = True if self.resolve[server]['v4'] and self.resolve[target]['v4'] else False
                        v6 = True if self.resolve[server]['v6'] and self.resolve[target]['v6'] else False
                        #Geo, default 200ms however if defined we apply the actual limit on booth sides
                        threshold = targetData['latency'] if "geo" in targetData['Targets'] and "latency" in targetData else 200
                        threshold = serverData['latency'] if threshold == 200 and "geo" in serverData['Targets'] and "latency" in serverData else 200
                        if "geo" in targetData['Targets'] or "geo" in serverData['Targets']:
                            if v4: 
                                print(f"Getting Latency for {target} for GEO")
                                result = self.cmd(server,f'fping -c 3 {self.resolve[target]['v4']}')[0]
                                latency = self.average(result)
                                if latency > threshold: 
                                    print(f"Skipping link to {target} latency to high")
                                    v4 = False
                            if v6: 
                                print(f"Getting Latency for {target}v6 for GEO")
                                result = self.cmd(f"{server}v6",f'fping -c 3 {self.resolve[target]['v6']}')[0]
                                latency = self.average(result)
                                if latency > threshold: 
                                    print(f"Skipping link to {target}v6 latency to high")
                                    v6 = False
                        #Threading
                        if answer != "y":
                            if v4:
                                if reconfigure[0] == "" or reconfigure[0] != "" and (target in reconfigure or server in reconfigure):
                                    self.execute(clients,serverIP,basePort,target,server,privateServer,publicServer)
                                execute,serverIP,basePort = True, serverIP+2, basePort+1
                            if v6:
                                if reconfigure[0] == "" or reconfigure[0] != "" and (target in reconfigure or server in reconfigure):
                                    self.execute(clients,serverIP,basePort,target,server,privateServer,publicServer,True)
                                execute,serverIP,basePort = True, serverIP+2, basePort+1
                        else:
                            if v4:
                                if reconfigure[0] == "" or reconfigure[0] != "" and (target in reconfigure or server in reconfigure):
                                    threads.append(Thread(target=self.execute, args=([clients,serverIP,basePort,target,server,privateServer,publicServer])))
                                execute,serverIP,basePort = True, serverIP+2, basePort+1
                            if v6:
                                if reconfigure[0] == "" or reconfigure[0] != "" and (target in reconfigure or server in reconfigure):
                                    threads.append(Thread(target=self.execute, args=([clients,serverIP,basePort,target,server,privateServer,publicServer,True])))
                                execute,serverIP,basePort = True, serverIP+2, basePort+1
                else:
                    if client in crossConnect: continue
                    print("direct-connectv4|v6™")
                    #Threading
                    if answer != "y":
                        if self.resolve[server]['v4'] and self.resolve[client]['v4']:
                            if reconfigure[0] == "" or reconfigure[0] != "" and (client in reconfigure or server in reconfigure):
                                self.execute(clients,serverIP,basePort,client,server,privateServer,publicServer)
                            execute,serverIP,basePort = True, serverIP+2, basePort+1
                        if self.resolve[server]['v6'] and self.resolve[client]['v6']:
                            if reconfigure[0] == "" or reconfigure[0] != "" and (client in reconfigure or server in reconfigure):
                                self.execute(clients,serverIP,basePort,client,server,privateServer,publicServer,True)
                            execute,serverIP,basePort = True, serverIP+2, basePort+1
                    else:
                        if self.resolve[server]['v4'] and self.resolve[client]['v4']:
                            if reconfigure[0] == "" or reconfigure[0] != "" and (client in reconfigure or server in reconfigure):
                                threads.append(Thread(target=self.execute, args=([clients,serverIP,basePort,client,server,privateServer,publicServer])))
                            execute,serverIP,basePort = True, serverIP+2, basePort+1
                        if self.resolve[server]['v6'] and self.resolve[client]['v6']:
                            if reconfigure[0] == "" or reconfigure[0] != "" and (client in reconfigure or server in reconfigure):
                                threads.append(Thread(target=self.execute, args=([clients,serverIP,basePort,client,server,privateServer,publicServer,True])))
                            execute,serverIP,basePort = True, serverIP+2, basePort+1
            #Check if target has any wg configuration
            if execute is False:
                print("Adding dummy for",server+suffix,"so vxlan works fine")
                if answer != "y":
                    self.execute(clients,serverIP,basePort,target,server+suffix,privateServer,publicServer,False,True)
                else:
                    threads.append(Thread(target=self.execute, args=([clients,serverIP,basePort,target,server+suffix,privateServer,publicServer,False,True])))
            if answer == "y":
                if rate == 0.2 and len(threads) > 4:
                    rate = len(threads) * 0.05
                    if rate > 2: rate = 2
                    print(server,"Updated rate",rate)
                self.lunchThreads(threads,rate)
