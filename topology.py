from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.link import TCLink

class PortMonitorTopo(Topo):
    def build(self):
        s1 = self.addSwitch('s1')
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)

def run():
    topo = PortMonitorTopo()
    net = Mininet(
        topo=topo,
        controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6633),
        link=TCLink,
        autoSetMacs=True
    )
    net.start()
    print("Network started. Ryu controller expected at 127.0.0.1:6633")
    print("Try: h1 ping h2")
    print("Bring port down: sh ifconfig s1-eth1 down")
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
