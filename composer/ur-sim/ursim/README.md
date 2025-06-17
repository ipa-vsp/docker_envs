## URSim Net Configuration

```bash
sudo ip link add macvlan0 link wlp2s0 type macvlan mode bridge
sudo ip addr add 192.168.50.100/24 dev macvlan0
sudo ip link set macvlan0 up
```