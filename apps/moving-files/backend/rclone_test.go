package main

import (
	"strings"
	"testing"
)

func TestParseRcloneTransferred(t *testing.T) {
	n, ok := parseRcloneTransferred("Transferred:   	    1.234 GiB / 10.000 GiB, 12%, 55.123 MiB/s, ETA 2m30s")
	if !ok {
		t.Fatal("should parse stats line")
	}
	f := 1.234
	want := int64(f * 1024 * 1024 * 1024)
	if n < want-1024*1024 || n > want+1024*1024 {
		t.Fatalf("got %d want ~%d", n, want)
	}
	if _, ok := parseRcloneTransferred("INFO : folder/sub/file.bin"); ok {
		t.Fatal("path must not look like stats")
	}
	n, ok = parseRcloneTransferred("2026/09/15 18:20:44 INFO  : 1.5 GiB / 10 GiB, 15%, 12 MiB/s, ETA 2m")
	if !ok || n < 1024*1024*1024 {
		t.Fatalf("one-line stats: %d %v", n, ok)
	}
}

func TestScanRcloneStatsCR(t *testing.T) {
	in := "2026/09/15 18:20:44 INFO  : 0 B / 0 B, -, 0 B/s, ETA -\r" +
		"2026/09/15 18:20:45 INFO  : 1.5 GiB / 10 GiB, 15%, 12 MiB/s, ETA 2m\n"
	var ns []int64
	scanRcloneStats(strings.NewReader(in), func(n int64, _ string) {
		ns = append(ns, n)
	})
	if len(ns) < 2 || ns[len(ns)-1] < 1024*1024*1024 {
		t.Fatalf("cr stats: %v", ns)
	}
}

func TestRcloneSMBURLSpaceShare(t *testing.T) {
	d := Device{Host: "192.168.2.1", User: "nas", Password: ""}
	u := rcloneSMBURL(d, "APP PROJEKTE", "")
	if strings.Contains(u, "'APP PROJEKTE'") {
		t.Fatalf("space in share must not be quoted: %s", u)
	}
	if !strings.Contains(u, ":APP PROJEKTE") {
		t.Fatalf("share missing: %s", u)
	}
}

func TestRcloneQuote(t *testing.T) {
	if rcloneQuote("nas") != "nas" {
		t.Fatal("plain value")
	}
	got := rcloneQuote("a,b")
	if got != "'a,b'" {
		t.Fatalf("quoted: %s", got)
	}
	if rcloneQuote("iPhone 17 Pro") != "'iPhone 17 Pro'" {
		t.Fatalf("space: %s", rcloneQuote("iPhone 17 Pro"))
	}
}
