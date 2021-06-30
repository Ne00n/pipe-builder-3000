# pipe-builder-3000

Sets up multiple point to point wireguard connections<br />
Make sure the Hostnames are present in /etc/hosts<br />
Wireguard needs to be already installed on all servers<br />

Its recommended to run this on clean servers.<br />
By default 10.0.x.x/8 is used.<br />
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
You can use * if you want to cross-connect to everything else<br />

If you updated pipe-builder you may run pipe.py clean since we renamed the Server files.<br />

**Examples**<br />

point-to-point<br />
```
{
 "Server1":{"id":1,"basePort":51194,"v6":false,"Targets":["Server3","Server2"]},
 "Server2":{"id":2,"basePort":51194,"v6":false,"Targets":["Server3"]}
}
```

cross-connect (mesh)<br />
Currently only mesh has IPv6 support<br />
```
{
 "Server1":{"id":1,"basePort":51194,"v6":true,"Targets":["*"]},
 "Server2":{"id":2,"basePort":51194,"v6":true,"Targets":["*"]},
 "Server3":{"id":3,"basePort":51194,"v6":false,"Targets":["*"]}
}
```

cross-connect + point-to-point<br />
```
{
 "Server1":{"id":1,"basePort":51194,"v6":false,"Targets":["*"]},
 "Server2":{"id":2,"basePort":51194,"v6":false,"Targets":["*","Server5"]},
 "Server3":{"id":3,"basePort":51194,"v6":false,"Targets":["*","Server4"]}
}
```

/etc/hosts<br />
```
bla.bla.bla.bla    Server1
bla:bla:piss::bla  Server1v6
bla.bla.bla.bla    Server2
bla:bla:beef::bla  Server2v6
bla.bla.bla.bla    Server3
bla:bla:bacon::bla Server3v6
```
Note: No need for dualstack, IPv6 only is supported</br >
However, if you use IPv6, you need IPv6 connectivity.

**Usage**<br />
Builds or Updates the network<br />
```
python3 pipe.py build
```
Shutdown of all Wireguard pipe* connections<br />
```
python3 pipe.py shutdown
```
Removes all Wireguard pipe* configuration files<br />
```
python3 pipe.py clean
```
