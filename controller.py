from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from datetime import datetime

LOG_FILE = "port_log.txt"

class PortMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(PortMonitor, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.port_status = {}
        self.logger.info("Port Monitor Controller started")

    # writes event to log file and prints it
    def log_event(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp}  |  {msg}"
        print(line)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")

    # runs when switch connects, installs default rule to send packets to controller
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        self.logger.info("Switch %s connected", datapath.id)

    # installs a flow rule on the switch
    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    # runs when a port goes up or down
    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofproto = dp.ofproto
        reason = msg.reason
        port = msg.desc
        port_no = port.port_no
        dpid = dp.id

        reason_map = {
            ofproto.OFPPR_ADD: "ADDED",
            ofproto.OFPPR_DELETE: "DELETED",
            ofproto.OFPPR_MODIFY: "MODIFIED"
        }
        reason_str = reason_map.get(reason, "UNKNOWN")

        if port.state & ofproto.OFPPS_LINK_DOWN:
            status = "DOWN"
        else:
            status = "UP"

        self.port_status[(dpid, port_no)] = status

        log_msg = f"Switch: s{dpid}  |  Port: {port_no}  |  Event: {reason_str}  |  Status: {status}"
        self.log_event(log_msg)

        if status == "DOWN":
            print(f"\n[ALERT] Port {port_no} on Switch s{dpid} is DOWN!\n")
        else:
            print(f"\n[INFO]  Port {port_no} on Switch s{dpid} is UP.\n")

        self.display_status()

    # prints current status of all ports
    def display_status(self):
        print("=" * 40)
        print("  Current Port Status")
        print("=" * 40)
        if not self.port_status:
            print("  No port events recorded yet.")
        for (dpid, port_no), status in self.port_status.items():
            print(f"  Switch s{dpid} - Port {port_no}: {status}")
        print("=" * 40)

    # handles incoming packets and learns MAC addresses
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofproto = dp.ofproto
        parser = dp.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        dst = eth.dst
        src = eth.src
        dpid = dp.id

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self.add_flow(dp, 1, match, actions)

        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        dp.send_msg(out)
