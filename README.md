# pipe-builder-3000

Sets up multiple point to point wireguard connections<br />
Make sure the Hostnames are present in /etc/hosts<br />
Wireguard needs to be already installed on all servers<br />

Its recommended to run this on clean servers.<br />
By default 10.0.x.x/8 is used.

**Dependencies**<br />
apt-get install wireguard

Debian 10:<br />
```
sh -c "echo 'deb http://deb.debian.org/debian buster-backports main contrib non-free' > /etc/apt/sources.list.d/buster-backports.list"</br>
apt-get update </br>
apt-get install wireguard -y</br>
```

**Prepare**<br />
Rename hosts.example.json to hosts.json and fill it up<br />
You can use * if you want to cross-connect to everything else

Examples:<br />

point-to-point<br />
```
{
 "Server1":{"Targets":["Server3","Server2"]},
 "Server2":{"Targets":["Server3"]}
}
```

cross-connect (mesh)<br />
```
{
 "Server1":{"Targets":["*"]},
 "Server2":{"Targets":["*"]},
 "Server3":{"Targets":["*"]}
}
```

cross-connect + point-to-point<br />
```
{
 "Server1":{"Targets":["*"]},
 "Server2":{"Targets":["*","Server5"]},
 "Server3":{"Targets":["*","Server4"]}
}
```

**Usage**<br />
python3 pipe.py
