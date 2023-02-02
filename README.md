# pipe-builder-3000
**Not longer updated**<br>
Use wg-mesh instead.<br>

Sets up multiple point to point wireguard connections<br />
Make sure the Hostnames are present in /etc/hosts<br />
Wireguard needs to be already installed on all servers<br />

Its recommended to run this on clean servers.<br />
By default 10.0.x.x/16 is used. Can be changed to 172.16.0.0/12 or 192.168.0.0/16.<br />
10.0.id.1 Node /30<br />
10.0.id.4-255 peers /31<br />
10.0.250.1-255 clients /32<br />
10.0.251.1-255 vxlan /32 <br />
10.0.252.1-255 source based routing<br />

This script configures only the wireguard connections, to make everything reachable (mesh) there is an addon:<br />
https://github.com/Ne00n/bird-spawner-3000

Which uses bird2 that dynamically creates routes and reroutes traffic if a node goes down.<br />

**ToDo**<br />
- nothing

**Dependencies**<br />
wireguard, python3

**Debian 10**<br />
```
sh -c "echo 'deb http://deb.debian.org/debian buster-backports main contrib non-free' > /etc/apt/sources.list.d/buster-backports.list"
apt-get update && apt-get install wireguard python3 -y
```

**Prepare**<br />
Rename hosts.example.json to hosts.json and fill it up<br />
You can use * or geo if you want to cross-connect to everything else<br />
Geo uses a latency cap for setting up links, its a bit slower than *<br />

**Examples**<br />

point-to-point<br />
```
"Server1":{"id":1,"basePort":51194,"type":"native","Targets":["Server3","Server2"]},
"Server2":{"id":2,"basePort":51194,"type":"native","Targets":["Server3"]}
```

cross-connect (mesh)<br />
```
"Server1":{"id":1,"basePort":51194,"type":"native","Targets":["*"]},
"Server2":{"id":2,"basePort":"random","type":"native","Targets":["geo"]},
"Server3":{"id":3,"basePort":51194,"type":"native","Targets":["*"]}
```

cross-connect + point-to-point<br />
```
"Server1":{"id":1,"basePort":51194,"type":"native","Targets":["*"]},
"Server2":{"id":2,"basePort":51194,"type":"native","Targets":["*","Server5"]},
"Server3":{"id":3,"basePort":"random","type":"native","Targets":["*","Server4"]}
```

Names should not contain: dummy<br />

/etc/hosts<br />
```
bla.bla.bla.bla    Server1
bla:bla:piss::bla  Server1v6
bla.bla.bla.bla    Server2
bla:bla:beef::bla  Server2v6
bla.bla.bla.bla    Server3
bla:bla:bacon::bla Server3v6
```
Note: No need for dualstack, IPv4 or IPv6 only is supported</br >

**Usage**<br />
Builds or Updates the network<br />
```
python3 pipe.py build
```
- Threading can be enabled, to make stuff run faster, however harder to debug<br />
- Reconfigure can be used to update a server IP or just randomize the wg ports of that server, without impacting the entire network<br />
Don't use that function to enable IPv6 afterwards<br />
- You can ignore and remove old servers while doing a build, remove them from the .json before you use it<br />

Shutdown of all Wireguard prefix* connections<br />
```
python3 pipe.py shutdown
```
Removes all Wireguard prefix* configuration files<br />
```
python3 pipe.py clean
```
- Same as above, you can ignore servers, which are offline, to make things faster
