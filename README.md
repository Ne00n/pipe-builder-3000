# pipe-builder-3000

Sets up multiple point to point wireguard connections<br />
Make sure the Hostnames are present in /etc/hosts<br />
Wireguard needs to be already installed on all servers<br />

Its recommended to run this on clean servers.

**Dependencies**<br />
apt-get install wireguard

**Prepare**<br />
Rename hosts.example.json to hosts.json and fill it up

**Usage**<br />
python3 pipe.py
