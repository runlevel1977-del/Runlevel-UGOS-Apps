package main

import (
	"testing"
	"time"
)

func TestDueDaily(t *testing.T) {
	job := Transfer{Auto: "daily", AutoTime: "22:00"}
	before := time.Date(2026, 9, 13, 21, 59, 0, 0, time.Local)
	if due(job, before) {
		t.Fatal("should not run before 22:00")
	}
	after := time.Date(2026, 9, 13, 22, 0, 1, 0, time.Local)
	if !due(job, after) {
		t.Fatal("should run after 22:00")
	}
	job.LastRun = after.Format(time.RFC3339)
	if due(job, after.Add(time.Hour)) {
		t.Fatal("should not run twice the same evening")
	}
	nextDay := time.Date(2026, 9, 14, 22, 0, 1, 0, time.Local)
	if !due(job, nextDay) {
		t.Fatal("should run the next day")
	}
	missed := Transfer{Auto: "daily", AutoTime: "11:00"}
	afternoon := time.Date(2026, 9, 13, 15, 6, 0, 0, time.Local)
	if due(missed, afternoon) {
		t.Fatal("missed morning slot must wait until tomorrow")
	}
}

func TestDueMissedWeeklySlot(t *testing.T) {
	job := Transfer{Auto: "biweekly", AutoTime: "11:00", AutoWeekday: "7"}
	sundayAfternoon := time.Date(2026, 9, 13, 15, 6, 0, 0, time.Local)
	if sundayAfternoon.Weekday() != time.Sunday {
		t.Fatal("fixture must be a Sunday")
	}
	if due(job, sundayAfternoon) {
		t.Fatal("creating a Sunday 11:00 plan at 15:00 must not start immediately")
	}
	nextSunday := time.Date(2026, 9, 20, 11, 0, 30, 0, time.Local)
	if !due(job, nextSunday) {
		t.Fatal("should run the next Sunday at 11:00")
	}
}

func TestWakePlanMultipleSources(t *testing.T) {
	p := WakePlan{
		DeviceID:  "qnap",
		Direction: "push",
		SrcShare:  "vol1",
		SrcPath:   "fotos",
		SrcPaths:  []string{"vol1|filme", "hdd|musik"},
		DstShare:  "qnap",
		DstPath:   "backup",
	}
	srcs := p.asTransfer().sourceList()
	if len(srcs) != 3 {
		t.Fatalf("got %d sources: %#v", len(srcs), srcs)
	}
	if srcs[2].Share != "hdd" || srcs[2].Path != "musik" {
		t.Fatalf("third source: %#v", srcs[2])
	}
	if p.asTransfer().DstDevice != "qnap" || p.asTransfer().SrcDevice != "local" {
		t.Fatal("push should send from this NAS to the device")
	}
}

func TestDueInterval(t *testing.T) {
	job := Transfer{Auto: "30"}
	now := time.Date(2026, 9, 13, 12, 0, 0, 0, time.Local)
	if !due(job, now) {
		t.Fatal("first interval run should be due")
	}
	job.LastRun = now.Format(time.RFC3339)
	if due(job, now.Add(10*time.Minute)) {
		t.Fatal("should wait the interval")
	}
	if !due(job, now.Add(30*time.Minute)) {
		t.Fatal("should run after 30 min")
	}
}

func TestWantedWeekday(t *testing.T) {
	if wantedWeekday("1") != time.Monday {
		t.Fatal("1 should be Monday")
	}
	if wantedWeekday("7") != time.Sunday {
		t.Fatal("7 should be Sunday")
	}
	if wantedWeekday("") != time.Monday {
		t.Fatal("empty should default to Monday")
	}
}

func TestDueWeekly(t *testing.T) {
	job := Transfer{Auto: "weekly", AutoTime: "22:00", AutoWeekday: "7"}
	sundayBefore := time.Date(2026, 9, 13, 21, 59, 0, 0, time.Local)
	if sundayBefore.Weekday() != time.Sunday {
		t.Fatal("fixture must be a Sunday")
	}
	if due(job, sundayBefore) {
		t.Fatal("should not run before 22:00")
	}
	sundayAfter := time.Date(2026, 9, 13, 22, 0, 1, 0, time.Local)
	if !due(job, sundayAfter) {
		t.Fatal("should run Sunday after 22:00")
	}
	monday := time.Date(2026, 9, 14, 22, 0, 1, 0, time.Local)
	if due(job, monday) {
		t.Fatal("weekly Sunday plan should not run on Monday")
	}
	job.LastRun = sundayAfter.Format(time.RFC3339)
	nextSunday := time.Date(2026, 9, 20, 22, 0, 1, 0, time.Local)
	if !due(job, nextSunday) {
		t.Fatal("should run again the next Sunday")
	}
}

func TestDueBiweekly(t *testing.T) {
	job := Transfer{Auto: "biweekly", AutoTime: "22:00", AutoWeekday: "1"}
	monday := time.Date(2026, 9, 14, 22, 0, 1, 0, time.Local)
	if monday.Weekday() != time.Monday {
		t.Fatal("fixture must be a Monday")
	}
	if !due(job, monday) {
		t.Fatal("first biweekly run should be due")
	}
	job.LastRun = monday.Format(time.RFC3339)
	nextMonday := time.Date(2026, 9, 21, 22, 0, 1, 0, time.Local)
	if due(job, nextMonday) {
		t.Fatal("should skip the Monday one week later")
	}
	twoWeeks := time.Date(2026, 9, 28, 22, 0, 1, 0, time.Local)
	if !due(job, twoWeeks) {
		t.Fatal("should run two weeks later")
	}
}

func TestDueMonthly(t *testing.T) {
	job := Transfer{Auto: "monthly", AutoTime: "22:00", AutoWeekday: "1"}
	monday := time.Date(2026, 9, 14, 22, 0, 1, 0, time.Local)
	if !due(job, monday) {
		t.Fatal("first monthly run should be due")
	}
	job.LastRun = monday.Format(time.RFC3339)
	laterSameMonth := time.Date(2026, 9, 21, 22, 0, 1, 0, time.Local)
	if due(job, laterSameMonth) {
		t.Fatal("should not run twice in the same month")
	}
	nextMonth := time.Date(2026, 10, 5, 22, 0, 1, 0, time.Local)
	if nextMonth.Weekday() != time.Monday {
		t.Fatal("5 Oct 2026 should be Monday")
	}
	if !due(job, nextMonth) {
		t.Fatal("should run the first matching weekday of the next month")
	}
}

func TestDeviceCanWake(t *testing.T) {
	if deviceCanWake(Device{ID: "local", Type: "local", MAC: "AA:BB:CC:DD:EE:FF"}) {
		t.Fatal("this NAS must not be woken")
	}
	if deviceCanWake(Device{ID: "pc", Type: "pc", Host: "10.0.0.9"}) {
		t.Fatal("no MAC means no wake")
	}
	if !deviceCanWake(Device{ID: "qnap", Type: "nas", Host: "10.0.0.1", MAC: "24:5E:BE:17:C0:53"}) {
		t.Fatal("remote with MAC can wake")
	}
	if !deviceCanWake(Device{ID: "pc", Type: "pc", Host: "192.168.2.10", MAC: "11:22:33:44:55:66"}) {
		t.Fatal("any destination with MAC can wake")
	}
}

func TestBackupScheduleDue(t *testing.T) {
	b := Backup{Auto: "weekly", AutoTime: "22:00", AutoWeekday: "1"}
	monday := time.Date(2026, 9, 14, 22, 0, 1, 0, time.Local)
	if !due(b.asTransfer(), monday) {
		t.Fatal("backup weekly should use the same clock as transfers")
	}
}

func TestIsLocalDeviceEmptyHost(t *testing.T) {
	qnap := Device{ID: "qnap", Type: "nas", Name: "Qnap", Host: ""}
	if isLocalDevice(qnap) {
		t.Fatal("NAS without host must not be treated as this NAS")
	}
	d, ok := findDevice([]Device{qnap}, "missing")
	if ok {
		t.Fatalf("missing device should not resolve: %#v", d)
	}
}
