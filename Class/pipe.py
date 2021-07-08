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
            p = subprocess.run(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode != 0:
                print("Warning got returncode",p.returncode,"on",server)
                print("Error:",p.stderr.decode('utf-8'))
            if p.returncode != 255: break
            print("Retrying",cmd,"on",server)
            time.sleep(random.randint(5, 15))
        return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]

    def checkResolve(self,server):
        ip = subprocess.check_output(['dig','ANY','+short',server]).decode("utf-8")
        if not ip: return False
        return True

    def prepare(self,server,Filter=True,delete=False):
        print("---",server,"Preparing","---")
        #Check if v6 only
        serverSuffix = ""
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
                print("Stopping",client.replace("Serv",""),"on",server)
                self.cmd(server+serverSuffix,'systemctl stop wg-quick@'+client+' && systemctl disable wg-quick@'+client)
                if delete == True:
                    self.cmd(server+serverSuffix,'rm -f /etc/wireguard/'+client+".conf")
                #Stop Client
                v6 = 'v6' if client.endswith("v6Serv") else ''
                client = client.replace("Serv","").replace(self.targets['prefix'],"").replace("v6","")
                if self.checkResolve(client) is False and self.checkResolve(client+"v6") is True:
                    print("Switching",client,"to v6 only")
                    suffix ="v6"
                else:
                    suffix = ""
                print("Stopping",self.targets['prefix']+server+v6,"on",client+suffix)
                self.cmd(client+suffix,'systemctl stop wg-quick@'+self.targets['prefix']+server+v6+' && systemctl disable wg-quick@'+self.targets['prefix']+server+v6)
                if delete == True:
                    self.cmd(client+suffix,'rm -f /etc/wireguard/'+self.targets['prefix']+server+v6+".conf")

    def clean(self):
        threads = []
        answer = input("Use Threading? (y/n): ")
        for server,data in self.targets['servers'].items():
            if answer != "y":
                self.prepare(server,False,True)
            else:
                threads.append(Thread(target=self.prepare, args=([server,False,True])))
        if answer == "y": self.lunchThreads(threads)

    def shutdown(self):
        threads = []
        answer = input("Use Threading? (y/n): ")
        for server,data in self.targets['servers'].items():
            if answer != "y":
                self.prepare(server,False)
            else:
                threads.append(Thread(target=self.prepare, args=([server,False])))
        if answer == "y": self.lunchThreads(threads)

    def lunchThreads(self,threads):
        for thread in threads:
            thread.start()
            time.sleep(0.1)
        for thread in threads:
            thread.join()

    def isClient(self,client):
        return False if client.replace("v6","") in self.targets['servers'] else True

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
        start = 4
        crossConnect,clients,threads = [],[],[]
        answer = input("Use Threading? (y/n): ")
        print("Launching")
        time.sleep(3)
        for server,data in self.targets['servers'].items():
            #Prepare
            if data['basePort'] == "random":
                self.targets['servers'][server]['basePort'] = port = random.randint(1500, 55000)
            else:
                port = data['basePort']
            self.prepare(server)
            print("---",server,"Deploying","---")
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
                    print("cross-connect™")
                    for target in self.targets['servers']:
                        #Prevent v4 connections to v6 only hosts
                        if self.checkResolve(target) is False and self.checkResolve(target+"v6") is True: continue
                        if self.checkResolve(server) is False and self.checkResolve(server+"v6") is True: continue
                        #Prevent double connections
                        if target not in crossConnect:
                            if answer != "y":
                                self.execute(clients,data,start,port,target,server,privateServer,publicServer)
                            else:
                                threads.append(Thread(target=self.execute, args=([clients,data,start,port,target,server,privateServer,publicServer])))
                            execute = True
                            start +=2
                            port +=1
                    if data['v6'] == True:
                        print("cross-connectv6™")
                        for target,row in self.targets['servers'].items():
                            #Prevent double connections & v4 peers
                            if target not in crossConnect and row['v6'] == True:
                                if answer != "y":
                                    self.execute(clients,data,start,port,target+"v6",server+"v6",privateServer,publicServer,True)
                                else:
                                    threads.append(Thread(target=self.execute, args=([clients,data,start,port,target+"v6",server+"v6",privateServer,publicServer,True])))
                                execute = True
                                start +=2
                                port +=1
                else:
                    print("direct-connect™")
                    if answer != "y":
                        self.execute(clients,data,start,port,client,server,privateServer,publicServer)
                    else:
                        threads.append(Thread(target=self.execute, args=([clients,data,start,port,client,server,privateServer,publicServer])))
                    execute = True
                    start +=2
                    port +=1
            #Check if target has any wg configuration
            if execute is False:
                print("Adding dummy for",server+suffix,"so vxlan works fine")
                port = 51194
                if answer != "y":
                    self.execute(clients,data,start,port,server+suffix,server+suffix,privateServer,publicServer,False,True)
                else:
                    threads.append(Thread(target=self.execute, args=([clients,data,start,port,server+suffix,server+suffix,privateServer,publicServer,False,True])))
            if answer == "y": self.lunchThreads(threads)
            #Reset stuff
            threads,start = [],4
