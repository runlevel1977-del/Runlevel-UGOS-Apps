package main

import (
	"fmt"
	"testing"
)

func TestJobMsgKeys(t *testing.T) {
	j := &Job{}
	j.msg("start")
	if j.DetailKey != "start" || j.Detail != "" {
		t.Fatalf("start: %+v", j)
	}
	j.progressName("photo.jpg")
	if j.DetailKey != "file" || j.DetailArg != "photo.jpg" {
		t.Fatalf("file: %+v", j)
	}
	j.progressName("notes.txt (unverändert)")
	if j.DetailKey != "unchanged" || j.DetailArg != "notes.txt" {
		t.Fatalf("unchanged: %+v", j)
	}
	j.progressName("2026/09/15 INFO : 12 MiB/s, ETA 2m")
	if j.DetailKey != "raw" {
		t.Fatalf("stats line: %+v", j)
	}
	j.fromErr(locErr("jobMissing"))
	if j.DetailKey != "jobMissing" {
		t.Fatalf("fromErr: %+v", j)
	}
}

func TestApiErr(t *testing.T) {
	m := apiKey("deviceMissing")
	if m["errorKey"] != "deviceMissing" {
		t.Fatalf("%v", m)
	}
	m = apiErr(locErr("noBackup"))
	if m["errorKey"] != "noBackup" {
		t.Fatalf("%v", m)
	}
}

func TestSplitErrKeys(t *testing.T) {
	k, _ := splitErr(locErr("badMac"))
	if k != "badMac" {
		t.Fatalf("locErr: %s", k)
	}
	k, _ = splitErr(fmt.Errorf("ungültige MAC-Adresse"))
	if k != "badMac" {
		t.Fatalf("german mac: %s", k)
	}
	k, _ = splitErr(fmt.Errorf("rclone fehlt"))
	if k != "rcloneMissing" {
		t.Fatalf("rclone: %s", k)
	}
}
