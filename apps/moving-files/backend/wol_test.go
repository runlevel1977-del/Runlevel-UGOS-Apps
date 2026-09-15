package main

import (
	"net"
	"testing"
)

func TestParseFlexibleMAC(t *testing.T) {
	cases := []string{
		"aa:bb:cc:dd:ee:ff",
		"AA-BB-CC-DD-EE-FF",
		"aabbccddeeff",
		"AABB.CCDD.EEFF",
	}
	for _, c := range cases {
		hw, err := parseFlexibleMAC(c)
		if err != nil {
			t.Fatalf("%s: %v", c, err)
		}
		if hw.String() != "aa:bb:cc:dd:ee:ff" {
			t.Fatalf("%s -> %s", c, hw)
		}
	}
	if _, err := parseFlexibleMAC("zz"); err == nil {
		t.Fatal("expected error")
	}
}

func TestSlash24Broadcast(t *testing.T) {
	ip := net.ParseIP("192.168.2.50").To4()
	got := slash24Broadcast(ip)
	if got.String() != "192.168.2.255" {
		t.Fatal(got)
	}
}

func TestSkipDockerIfaces(t *testing.T) {
	if !skipIfaceName("docker0") || !skipIfaceName("veth0") || !skipIfaceName("br-abc") {
		t.Fatal("docker ifaces should be skipped")
	}
	if skipIfaceName("eth1") || skipIfaceName("enp2s0") {
		t.Fatal("real nics must be used")
	}
}

func mustNet(nic, cidr string) localNet {
	ip, n, err := net.ParseCIDR(cidr)
	if err != nil {
		panic(err)
	}
	return localNet{nic: nic, ip: ip.To4(), netw: n}
}

func TestPickNetByDeviceIP(t *testing.T) {
	nets := []localNet{
		mustNet("eth0", "192.168.2.10/24"),
		mustNet("eth1", "10.0.0.2/24"),
	}
	got := pickNetsForTarget(net.ParseIP("192.168.2.200").To4(), nets)
	if len(got) != 1 || got[0].ip.String() != "192.168.2.10" {
		t.Fatalf("192er Gerät muss über 192er Karte: %v", got)
	}
	got = pickNetsForTarget(net.ParseIP("10.0.0.1").To4(), nets)
	if len(got) != 1 || got[0].ip.String() != "10.0.0.2" {
		t.Fatalf("10er Gerät muss über 10er Karte: %v", got)
	}
}

func TestPickNetByPrefixWhenMaskWrong(t *testing.T) {
	nets := []localNet{
		mustNet("eth0", "192.168.2.10/24"),
		mustNet("eth1", "10.0.0.2/32"),
	}
	got := pickNetsForTarget(net.ParseIP("10.0.0.1").To4(), nets)
	if len(got) != 1 || got[0].ip.String() != "10.0.0.2" {
		t.Fatalf("auch ohne /24-Maske die passendere Karte: %v", got)
	}
}

func TestPickRejectsOtherFirstOctet(t *testing.T) {
	nets := []localNet{
		mustNet("eth0", "192.168.2.10/24"),
		mustNet("eth1", "10.0.0.2/24"),
	}
	got := pickNetsForTarget(net.ParseIP("203.0.113.50").To4(), nets)
	if len(got) != 0 {
		t.Fatalf("fremdes Netz darf nicht gewählt werden: %v", got)
	}
}

func TestWolPathsUseEveryLanNic(t *testing.T) {
	nets := []localNet{
		mustNet("eth0", "192.168.2.168/24"),
		mustNet("eth1", "10.0.0.2/24"),
	}
	paths := wolPathsFromNets(net.ParseIP("192.168.2.45").To4(), nets)
	nics := map[string]bool{}
	eth1Bcast := false
	eth0Bcast := false
	for _, p := range paths {
		nics[p.nic] = true
		if p.nic == "eth1" && p.dst.String() == "10.0.0.255" {
			eth1Bcast = true
		}
		if p.nic == "eth0" && p.dst.String() == "192.168.2.255" {
			eth0Bcast = true
		}
	}
	if !nics["eth0"] || !nics["eth1"] {
		t.Fatalf("beide LAN-Karten: %v", paths)
	}
	if !eth0Bcast || !eth1Bcast {
		t.Fatalf("Broadcast pro Karte fehlt: %v", paths)
	}
}

func TestWolPathsNoIPSecondNic(t *testing.T) {
	nets := []localNet{
		mustNet("eth0", "192.168.2.168/24"),
		{nic: "eth1", ip: net.IPv4zero.To4()},
	}
	paths := wolPathsFromNets(net.ParseIP("10.0.0.1").To4(), nets)
	nics := map[string]bool{}
	for _, p := range paths {
		nics[p.nic] = true
	}
	if !nics["eth0"] || !nics["eth1"] {
		t.Fatalf("eth1 ohne IP muss trotzdem senden: %v", paths)
	}
}

func TestMagicPacketLen(t *testing.T) {
	hw, _ := parseFlexibleMAC("aa:bb:cc:dd:ee:ff")
	pkt := magicPacket(hw)
	if len(pkt) != 102 {
		t.Fatalf("len=%d", len(pkt))
	}
	for i := 0; i < 16; i++ {
		if string(pkt[6+i*6:12+i*6]) != string(hw) {
			t.Fatal("MAC missing in magic packet")
		}
	}
}
