package main

import (
	"fmt"
	"net"
	"os"
	"strings"
	"syscall"
	"time"
)

type wolPath struct {
	src net.IP
	dst net.IP
	nic string
}

type localNet struct {
	nic  string
	ip   net.IP
	netw *net.IPNet
}

func parseFlexibleMAC(s string) (net.HardwareAddr, error) {
	s = strings.TrimSpace(s)
	s = strings.ReplaceAll(s, "-", ":")
	s = strings.ReplaceAll(s, ".", "")
	s = strings.ReplaceAll(s, " ", "")
	if !strings.Contains(s, ":") {
		s = strings.ToLower(s)
		if len(s) == 12 {
			parts := make([]string, 0, 6)
			for i := 0; i < 12; i += 2 {
				parts = append(parts, s[i:i+2])
			}
			s = strings.Join(parts, ":")
		}
	}
	hw, err := net.ParseMAC(s)
	if err != nil {
		return nil, locErr("badMac")
	}
	if len(hw) != 6 {
		return nil, locErr("badMac")
	}
	return hw, nil
}

func magicPacket(hw net.HardwareAddr) []byte {
	pkt := make([]byte, 6+16*6)
	for i := 0; i < 6; i++ {
		pkt[i] = 0xff
	}
	for i := 0; i < 16; i++ {
		copy(pkt[6+i*6:], hw)
	}
	return pkt
}

func hostIPv4(host string) net.IP {
	host = strings.TrimSpace(host)
	if host == "" {
		return nil
	}
	if i := strings.Index(host, ":"); i > 0 && net.ParseIP(host) == nil {
		host = host[:i]
	}
	if ip := net.ParseIP(host); ip != nil {
		return ip.To4()
	}
	ips, err := net.LookupIP(host)
	if err != nil {
		return nil
	}
	for _, ip := range ips {
		if v4 := ip.To4(); v4 != nil {
			return v4
		}
	}
	return nil
}

func ipv4Broadcast(ip net.IP, mask net.IPMask) net.IP {
	ip4 := ip.To4()
	if ip4 == nil || len(mask) < 4 {
		return nil
	}
	m := mask
	if len(m) == 16 {
		m = m[12:]
	}
	out := make(net.IP, 4)
	for i := 0; i < 4; i++ {
		out[i] = ip4[i] | ^m[i]
	}
	return out
}

func slash24Broadcast(ip net.IP) net.IP {
	ip4 := ip.To4()
	if ip4 == nil {
		return nil
	}
	return net.IPv4(ip4[0], ip4[1], ip4[2], 255).To4()
}

type lanIface struct {
	name    string
	index   int
	hw      net.HardwareAddr
	ip      net.IP
	netw    *net.IPNet
	up      bool
	running bool
}

func skipIfaceName(name string) bool {
	n := strings.ToLower(name)
	if n == "" || n == "lo" || strings.HasPrefix(n, "lo:") {
		return true
	}
	for _, p := range []string{"docker", "veth", "br-", "virbr", "cni", "flannel", "tun", "wg"} {
		if strings.Contains(n, p) {
			return true
		}
	}
	return false
}

func sysNetNames() []string {
	ents, err := os.ReadDir("/sys/class/net")
	if err != nil {
		return []string{"eth0", "eth1", "eth2", "enp1s0", "enp2s0"}
	}
	out := make([]string, 0, len(ents))
	for _, e := range ents {
		out = append(out, e.Name())
	}
	return out
}

func listLanIfaces() []lanIface {
	byName := map[string]*lanIface{}
	order := []string{}
	add := func(ifi net.Interface) {
		if ifi.Flags&net.FlagLoopback != 0 || skipIfaceName(ifi.Name) {
			return
		}
		cur, ok := byName[ifi.Name]
		if !ok {
			item := lanIface{
				name:    ifi.Name,
				index:   ifi.Index,
				hw:      ifi.HardwareAddr,
				up:      ifi.Flags&net.FlagUp != 0,
				running: ifi.Flags&net.FlagRunning != 0,
			}
			byName[ifi.Name] = &item
			order = append(order, ifi.Name)
			cur = byName[ifi.Name]
		} else {
			if ifi.Index != 0 {
				cur.index = ifi.Index
			}
			if len(ifi.HardwareAddr) > 0 {
				cur.hw = ifi.HardwareAddr
			}
			cur.up = cur.up || ifi.Flags&net.FlagUp != 0
			cur.running = cur.running || ifi.Flags&net.FlagRunning != 0
		}
		addrs, _ := ifi.Addrs()
		for _, a := range addrs {
			n, ok := a.(*net.IPNet)
			if !ok {
				continue
			}
			ip4 := n.IP.To4()
			if ip4 == nil {
				continue
			}
			if cur.ip == nil {
				cur.ip = ip4
				cur.netw = n
			}
		}
	}
	ifaces, _ := net.Interfaces()
	for _, ifi := range ifaces {
		add(ifi)
	}
	for _, name := range sysNetNames() {
		if skipIfaceName(name) {
			continue
		}
		ifi, err := net.InterfaceByName(name)
		if err != nil {
			continue
		}
		add(*ifi)
	}
	out := make([]lanIface, 0, len(order))
	for _, name := range order {
		if item := byName[name]; item != nil {
			out = append(out, *item)
		}
	}
	return out
}

func ifaceInventory(ifaces []lanIface) string {
	if len(ifaces) == 0 {
		return "keine LAN-Karte sichtbar"
	}
	parts := []string{}
	for _, n := range ifaces {
		ip := "ohne IPv4"
		if n.ip != nil {
			ip = n.ip.String()
		}
		st := "down"
		if n.up && n.running {
			st = "up"
		} else if n.up {
			st = "up/kein-Link"
		}
		parts = append(parts, n.name+"="+ip+" ("+st+")")
	}
	return strings.Join(parts, ", ")
}

func localNetsFromIfaces(ifaces []lanIface) []localNet {
	out := []localNet{}
	for _, n := range ifaces {
		ip := n.ip
		if ip == nil {
			ip = net.IPv4zero.To4()
		}
		out = append(out, localNet{nic: n.name, ip: ip, netw: n.netw})
	}
	return out
}

func localIPv4Nets() []localNet {
	return localNetsFromIfaces(listLanIfaces())
}

func commonPrefixBits(a, b net.IP) int {
	a4, b4 := a.To4(), b.To4()
	if a4 == nil || b4 == nil {
		return 0
	}
	bits := 0
	for i := 0; i < 4; i++ {
		x := a4[i] ^ b4[i]
		for bit := 7; bit >= 0; bit-- {
			if x&(1<<uint(bit)) != 0 {
				return bits
			}
			bits++
		}
	}
	return 32
}

func ifaceScore(n localNet, tip net.IP) int {
	if tip == nil || n.ip == nil {
		return -1
	}
	score := commonPrefixBits(n.ip, tip)
	if n.netw != nil && n.netw.Contains(tip) {
		ones, _ := n.netw.Mask.Size()
		if ones < 0 {
			ones = 0
		}
		if ones > score {
			score = ones
		}
		score += 100
	}
	return score
}

func pickNetsForTarget(tip net.IP, nets []localNet) []localNet {
	if tip == nil {
		return nets
	}
	bestScore := -1
	var best []localNet
	for _, n := range nets {
		score := ifaceScore(n, tip)
		if score < 8 {
			continue
		}
		if score > bestScore {
			bestScore = score
			best = []localNet{n}
		} else if score == bestScore {
			best = append(best, n)
		}
	}
	return best
}

func wolPathsFromNets(tip net.IP, nets []localNet) []wolPath {
	seen := map[string]bool{}
	paths := []wolPath{}
	add := func(nic string, src, dst net.IP) {
		if src == nil || dst == nil {
			return
		}
		key := nic + " " + src.String() + "->" + dst.String()
		if seen[key] {
			return
		}
		seen[key] = true
		paths = append(paths, wolPath{src: src, dst: dst, nic: nic})
	}
	limited := net.IPv4(255, 255, 255, 255).To4()
	for _, n := range nets {
		if tip != nil {
			add(n.nic, n.ip, tip)
			add(n.nic, n.ip, slash24Broadcast(tip))
		}
		if n.netw != nil {
			if bc := ipv4Broadcast(n.ip, n.netw.Mask); bc != nil {
				add(n.nic, n.ip, bc)
			}
		}
		add(n.nic, n.ip, limited)
	}
	return paths
}

func wolPaths(host string) ([]wolPath, error) {
	tip := hostIPv4(host)
	nets := localIPv4Nets()
	if len(nets) == 0 {
		return nil, locErr("wolNoNic")
	}
	paths := wolPathsFromNets(tip, nets)
	if len(paths) == 0 {
		return nil, locErr("wolSend")
	}
	return paths, nil
}

func enableBroadcast(c *net.UDPConn) {
	rc, err := c.SyscallConn()
	if err != nil {
		return
	}
	_ = rc.Control(func(fd uintptr) {
		_ = syscall.SetsockoptInt(int(fd), syscall.SOL_SOCKET, syscall.SO_BROADCAST, 1)
	})
}

func bindToDevice(c *net.UDPConn, nic string) error {
	if nic == "" {
		return nil
	}
	rc, err := c.SyscallConn()
	if err != nil {
		return err
	}
	var bindErr error
	if err := rc.Control(func(fd uintptr) {
		bindErr = syscall.SetsockoptString(int(fd), syscall.SOL_SOCKET, syscall.SO_BINDTODEVICE, nic)
	}); err != nil {
		return err
	}
	return bindErr
}

func sendFrom(nic string, src net.IP, dests []net.IP, pkt []byte) (int, error) {
	noIP := src == nil || src.IsUnspecified()
	bindIP := src
	if noIP {
		bindIP = net.IPv4zero
	} else {
		bindIP = bindIP.To4()
	}
	conn, err := net.ListenUDP("udp4", &net.UDPAddr{IP: bindIP, Port: 0})
	if err != nil {
		return 0, err
	}
	defer conn.Close()
	enableBroadcast(conn)
	if err := bindToDevice(conn, nic); err != nil {
		if noIP {
			return 0, fmt.Errorf("%s: keine IP, Bind an die Karte nicht erlaubt (%v)", nic, err)
		}
	}
	ok := 0
	var last error
	for _, ip := range dests {
		for _, port := range []int{9, 7} {
			if _, err := conn.WriteToUDP(pkt, &net.UDPAddr{IP: ip, Port: port}); err != nil {
				last = err
				continue
			}
			ok++
		}
	}
	if ok == 0 {
		return 0, last
	}
	return ok, nil
}

func sendMagicPacket(mac, host string) (string, error) {
	hw, err := parseFlexibleMAC(mac)
	if err != nil {
		return "", err
	}
	ifaces := listLanIfaces()
	inv := ifaceInventory(ifaces)
	paths := wolPathsFromNets(hostIPv4(host), localNetsFromIfaces(ifaces))
	if len(paths) == 0 && len(ifaces) == 0 {
		return "", locErr("wolNoNic")
	}
	pkt := magicPacket(hw)
	type grp struct {
		nic   string
		src   net.IP
		dests []net.IP
	}
	var groups []grp
	idx := map[string]int{}
	for _, p := range paths {
		key := p.nic + "/" + p.src.String()
		if i, ok := idx[key]; ok {
			groups[i].dests = append(groups[i].dests, p.dst)
			continue
		}
		idx[key] = len(groups)
		groups = append(groups, grp{nic: p.nic, src: p.src, dests: []net.IP{p.dst}})
	}
	ok := 0
	labels := []string{}
	notes := []string{}
	for round := 0; round < 3; round++ {
		for _, g := range groups {
			n, err := sendFrom(g.nic, g.src, g.dests, pkt)
			if err != nil {
				if round == 0 {
					notes = append(notes, err.Error())
				}
				continue
			}
			ok += n
			if round == 0 {
				ds := []string{}
				for _, d := range g.dests {
					ds = append(ds, d.String())
				}
				srcLabel := g.src.String()
				if g.src == nil || g.src.IsUnspecified() {
					srcLabel = "ohne-IP"
				}
				labels = append(labels, g.nic+" "+srcLabel+" → "+strings.Join(ds, ", ")+" (Magic-MAC "+hw.String()+")")
			}
		}
		if round < 2 {
			time.Sleep(120 * time.Millisecond)
		}
	}
	if ok == 0 {
		return "", locErr("wolSend")
	}
	parts := []string{
		fmt.Sprintf("%d UDP-Pakete mit Magic-MAC %s", ok, hw.String()),
	}
	if len(labels) > 0 {
		parts = append(parts, strings.Join(labels, " | "))
	}
	if len(notes) > 0 {
		parts = append(parts, strings.Join(notes, " | "))
	}
	parts = append(parts, "Karten: "+inv)
	noLink := []string{}
	for _, ifi := range ifaces {
		if ifi.up && !ifi.running {
			noLink = append(noLink, ifi.name)
		}
	}
	if len(noLink) > 0 {
		parts = append(parts, strings.Join(noLink, ", ")+" ohne Kabel-Link: QNAP-LAN muss im Ruhezustand Strom behalten, sonst kommt über das Direktkabel nichts raus")
	}
	return strings.Join(parts, ". "), nil
}
