package main

import (
	"errors"
	"io/fs"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

type Job struct {
	TransferID string `json:"transferId"`
	Name       string `json:"name"`
	Status     string `json:"status"`
	Percent    int    `json:"percent"`
	Detail     string `json:"detail"`
	DetailKey  string `json:"detailKey,omitempty"`
	DetailArg  string `json:"detailArg,omitempty"`
	BytesDone  int64  `json:"bytesDone"`
	BytesTotal int64  `json:"bytesTotal"`
	Updated    string `json:"updated"`
}

func (t Transfer) isEnabled() bool {
	return t.Enabled == nil || *t.Enabled
}

func (b Backup) isEnabled() bool {
	return b.Enabled == nil || *b.Enabled
}

func (b Backup) asTransfer() Transfer {
	return Transfer{
		ID:          "backup",
		Name:        "Backup",
		SrcDevice:   b.SrcDevice,
		SrcPath:     b.SrcPath,
		SrcShare:    b.SrcShare,
		DstDevice:   b.DstDevice,
		DstPath:     b.DstPath,
		DstShare:    b.DstShare,
		Mode:        "archive",
		Auto:        b.Auto,
		AutoTime:    b.AutoTime,
		AutoWeekday: b.AutoWeekday,
		Enabled:     b.Enabled,
		LastRun:     b.LastRun,
	}
}

func (a *App) backupCopy() *Backup {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.data.Backup == nil {
		return nil
	}
	b := *a.data.Backup
	return &b
}

func (a *App) mergeLastRun(next *State) {
	prev := map[string]Transfer{}
	for _, t := range a.data.Transfers {
		prev[t.ID] = t
	}
	for i, t := range next.Transfers {
		old, ok := prev[t.ID]
		if !ok {
			continue
		}
		if t.LastRun == "" || (old.LastRun != "" && old.LastRun > t.LastRun) {
			next.Transfers[i].LastRun = old.LastRun
		}
		if strings.TrimSpace(t.AutoTime) == "" && old.AutoTime != "" {
			next.Transfers[i].AutoTime = old.AutoTime
		}
	}
	prevW := map[string]WakePlan{}
	for _, p := range a.data.WakePlans {
		prevW[p.ID] = p
	}
	for i, p := range next.WakePlans {
		old, ok := prevW[p.ID]
		if !ok {
			continue
		}
		if p.LastRun == "" || (old.LastRun != "" && old.LastRun > p.LastRun) {
			next.WakePlans[i].LastRun = old.LastRun
		}
		if strings.TrimSpace(p.AutoTime) == "" && old.AutoTime != "" {
			next.WakePlans[i].AutoTime = old.AutoTime
		}
		if strings.TrimSpace(p.AutoWeekday) == "" && old.AutoWeekday != "" {
			next.WakePlans[i].AutoWeekday = old.AutoWeekday
		}
	}
	mergeDeviceSecrets(a.data.Devices, next.Devices, a.consentAllowsSecrets())
	normalizeWakePlans(next.WakePlans)
	if a.data.Backup != nil && next.Backup != nil {
		old := a.data.Backup
		if next.Backup.LastRun == "" || (old.LastRun != "" && old.LastRun > next.Backup.LastRun) {
			next.Backup.LastRun = old.LastRun
		}
		if strings.TrimSpace(next.Backup.AutoTime) == "" && old.AutoTime != "" {
			next.Backup.AutoTime = old.AutoTime
		}
		if strings.TrimSpace(next.Backup.AutoWeekday) == "" && old.AutoWeekday != "" {
			next.Backup.AutoWeekday = old.AutoWeekday
		}
		if next.Backup.PasswordClear {
			next.Backup.Password = ""
		} else if a.consentAllowsSecrets() && strings.TrimSpace(next.Backup.Password) == "" && old.Password != "" {
			next.Backup.Password = old.Password
		} else if !a.consentAllowsSecrets() {
			next.Backup.Password = ""
		}
		next.Backup.PasswordClear = false
		next.Backup.HasPassword = false
	}
}

func mergeDeviceSecrets(prev, next []Device, keepPass bool) {
	old := map[string]Device{}
	for _, d := range prev {
		old[d.ID] = d
	}
	for i, d := range next {
		o, ok := old[d.ID]
		if !ok {
			if !keepPass {
				next[i].Password = ""
			}
			continue
		}
		if keepPass && strings.TrimSpace(d.Password) == "" {
			next[i].Password = o.Password
		}
		if !keepPass {
			next[i].Password = ""
		}
		if strings.TrimSpace(d.MAC) == "" {
			next[i].MAC = o.MAC
		}
		if strings.TrimSpace(d.Host) == "" {
			next[i].Host = o.Host
		}
	}
}

func normalizeWakePlans(plans []WakePlan) {
	for i := range plans {
		switch plans[i].Auto {
		case "15", "30", "60":
			plans[i].Auto = "daily"
			if strings.TrimSpace(plans[i].AutoTime) == "" {
				plans[i].AutoTime = "22:00"
			}
		}
	}
}

func (a *App) jobsSnapshot() map[string]*Job {
	a.jobsMu.Lock()
	defer a.jobsMu.Unlock()
	out := make(map[string]*Job, len(a.jobs))
	for id, j := range a.jobs {
		cp := *j
		out[id] = &cp
	}
	return out
}

func (a *App) setJob(id string, mut func(*Job)) {
	a.jobsMu.Lock()
	defer a.jobsMu.Unlock()
	j := a.jobs[id]
	if j == nil {
		j = &Job{TransferID: id, Status: "idle"}
		a.jobs[id] = j
	}
	mut(j)
	j.Updated = time.Now().Format(time.RFC3339)
}

func parseChecksToken(name string) (cur, all int64, ok bool) {
	if !strings.HasPrefix(name, "checks:") {
		return 0, 0, false
	}
	p := strings.Split(strings.TrimPrefix(name, "checks:"), "/")
	if len(p) != 2 {
		return 0, 0, false
	}
	var err1, err2 error
	cur, err1 = strconv.ParseInt(p[0], 10, 64)
	all, err2 = strconv.ParseInt(p[1], 10, 64)
	return cur, all, err1 == nil && err2 == nil && all > 0
}

func (a *App) makeReporter(id string, total, done *int64) func(int64, string) {
	var lastUI time.Time
	var mu sync.Mutex
	return func(n int64, name string) {
		mu.Lock()
		defer mu.Unlock()
		if cur, all, ok := parseChecksToken(name); ok {
			if time.Since(lastUI) < 200*time.Millisecond {
				return
			}
			lastUI = time.Now()
			pct := int(cur * 100 / all)
			if pct > 100 {
				pct = 100
			}
			t := *total
			d := *done
			a.setJob(id, func(j *Job) {
				j.Status = "running"
				j.Percent = pct
				j.BytesDone = d
				j.BytesTotal = t
				j.msg("checking", strconv.FormatInt(cur, 10)+" / "+strconv.FormatInt(all, 10))
			})
			return
		}
		*done += n
		d, t := *done, *total
		if time.Since(lastUI) < 200*time.Millisecond && d < t {
			return
		}
		lastUI = time.Now()
		pct := 0
		if t > 0 {
			pct = int(d * 100 / t)
			if pct > 100 {
				pct = 100
			}
		}
		a.setJob(id, func(j *Job) {
			j.Status = "running"
			j.Percent = pct
			j.BytesDone = d
			j.BytesTotal = t
			j.progressName(name)
		})
	}
}

func (a *App) jobBusy(id string) bool {
	a.jobsMu.Lock()
	defer a.jobsMu.Unlock()
	j := a.jobs[id]
	return j != nil && (j.Status == "running" || j.Status == "waiting")
}

func (a *App) lookupTransfer(id string) (Transfer, []Device, error) {
	a.mu.Lock()
	defer a.mu.Unlock()
	devs := append([]Device(nil), a.data.Devices...)
	if id == "backup" {
		if a.data.Backup == nil {
			return Transfer{}, nil, locErr("noBackup")
		}
		b := *a.data.Backup
		mode := b.Mode
		if mode == "" {
			mode = "incr"
		}
		return Transfer{
			ID:        "backup",
			Name:      "Backup",
			SrcDevice: b.SrcDevice,
			SrcPath:   b.SrcPath,
			SrcShare:  b.SrcShare,
			DstDevice: b.DstDevice,
			DstPath:   b.DstPath,
			DstShare:  b.DstShare,
			Mode:      mode,
			Fast:      b.Fast,
		}, devs, nil
	}
	for _, t := range a.data.Transfers {
		if t.ID == id {
			return t, devs, nil
		}
	}
	return Transfer{}, nil, locErr("jobMissing")
}

func findDevice(devs []Device, id string) (Device, bool) {
	if id == "" || id == "local" {
		return Device{ID: "local", Type: "local", Name: "Dieses NAS"}, true
	}
	for _, d := range devs {
		if d.ID == id {
			return d, true
		}
	}
	return Device{}, false
}

func isLocalDevice(d Device) bool {
	return d.ID == "local" || d.Type == "local"
}

func deviceCanWake(d Device) bool {
	return !isLocalDevice(d) && strings.TrimSpace(d.MAC) != "" && strings.TrimSpace(d.Host) != ""
}

func hostReachable(host string) bool {
	host = strings.TrimSpace(host)
	if host == "" {
		return false
	}
	d := net.Dialer{Timeout: 2 * time.Second}
	for _, port := range []string{"445", "139"} {
		c, err := d.Dial("tcp4", net.JoinHostPort(host, port))
		if err == nil {
			_ = c.Close()
			return true
		}
	}
	return false
}

func (p WakePlan) asTransfer() Transfer {
	t := Transfer{
		ID:          p.ID,
		Name:        p.Name,
		SrcShare:    p.SrcShare,
		SrcPath:     p.SrcPath,
		SrcPaths:    append([]string(nil), p.SrcPaths...),
		DstShare:    p.DstShare,
		DstPath:     p.DstPath,
		Mode:        "sync",
		Auto:        p.Auto,
		AutoTime:    p.AutoTime,
		AutoWeekday: p.AutoWeekday,
		LastRun:     p.LastRun,
	}
	if p.Direction == "pull" {
		t.SrcDevice = p.DeviceID
		t.DstDevice = "local"
	} else {
		t.SrcDevice = "local"
		t.DstDevice = p.DeviceID
	}
	return t
}

func (a *App) lookupWake(id string) (WakePlan, []Device, error) {
	a.mu.Lock()
	defer a.mu.Unlock()
	devs := append([]Device(nil), a.data.Devices...)
	for _, p := range a.data.WakePlans {
		if p.ID == id {
			return p, devs, nil
		}
	}
	return WakePlan{}, nil, locErr("planMissing")
}

func (a *App) startJob(id, reason string) error {
	if a.jobBusy(id) {
		return nil
	}
	if id == "backup" {
		if _, _, err := a.backupSettings(); err != nil {
			return err
		}
		a.setJob(id, func(j *Job) {
			j.Name = "Backup"
			j.Status = "waiting"
			j.Percent = 0
			j.BytesDone = 0
			j.BytesTotal = 0
			j.msg("start")
		})
		go a.runArchiveBackup()
		return nil
	}
	if t, _, err := a.lookupTransfer(id); err == nil {
		a.setJob(id, func(j *Job) {
			j.Name = t.Name
			j.Status = "waiting"
			j.Percent = 0
			j.BytesDone = 0
			j.BytesTotal = 0
			j.msg("start")
		})
		go a.runJob(id, reason)
		return nil
	}
	if p, _, err := a.lookupWake(id); err == nil {
		a.setJob(id, func(j *Job) {
			j.Name = p.Name
			j.Status = "waiting"
			j.Percent = 0
			j.BytesDone = 0
			j.BytesTotal = 0
			j.msg("wake")
		})
		go a.runWake(id, reason)
		return nil
	}
	return locErr("jobMissing")
}

func (a *App) scheduleLoop() {
	tick := time.NewTicker(15 * time.Second)
	defer tick.Stop()
	for range tick.C {
		a.tickSchedules()
	}
}

func (a *App) tickSchedules() {
	a.mu.Lock()
	list := append([]Transfer(nil), a.data.Transfers...)
	wakes := append([]WakePlan(nil), a.data.WakePlans...)
	a.mu.Unlock()
	now := time.Now()
	for _, t := range list {
		if !t.isEnabled() || t.Auto == "" || a.jobBusy(t.ID) {
			continue
		}
		if !due(t, now) {
			continue
		}
		_ = a.startJob(t.ID, "schedule")
	}
	for _, p := range wakes {
		if !p.Enabled || p.Auto == "" || a.jobBusy(p.ID) {
			continue
		}
		if !due(p.asTransfer(), now) {
			continue
		}
		_ = a.startJob(p.ID, "schedule")
	}
	if b := a.backupCopy(); b != nil && b.isEnabled() && b.Auto != "" && !a.jobBusy("backup") {
		if due(b.asTransfer(), now) {
			_ = a.startJob("backup", "schedule")
		}
	}
}

func due(t Transfer, now time.Time) bool {
	last, _ := time.Parse(time.RFC3339, t.LastRun)
	switch t.Auto {
	case "daily":
		return dueAtClock(t.AutoTime, last, now)
	case "weekly":
		if now.Weekday() != wantedWeekday(t.AutoWeekday) {
			return false
		}
		return dueAtClock(t.AutoTime, last, now)
	case "biweekly":
		if now.Weekday() != wantedWeekday(t.AutoWeekday) {
			return false
		}
		if !last.IsZero() && now.Sub(last) < 13*24*time.Hour {
			return false
		}
		return dueAtClock(t.AutoTime, last, now)
	case "monthly":
		if now.Weekday() != wantedWeekday(t.AutoWeekday) {
			return false
		}
		if !last.IsZero() && last.Year() == now.Year() && last.Month() == now.Month() {
			return false
		}
		return dueAtClock(t.AutoTime, last, now)
	}
	mins, err := strconv.Atoi(t.Auto)
	if err != nil || mins <= 0 {
		return false
	}
	if last.IsZero() {
		return true
	}
	return now.Sub(last) >= time.Duration(mins)*time.Minute
}

const scheduleStartGrace = 20 * time.Minute

func dueAtClock(autoTime string, last, now time.Time) bool {
	hh, mm := 22, 0
	parts := strings.Split(strings.TrimSpace(autoTime), ":")
	if len(parts) >= 2 {
		if v, err := strconv.Atoi(parts[0]); err == nil {
			hh = v
		}
		if v, err := strconv.Atoi(parts[1]); err == nil {
			mm = v
		}
	}
	start := time.Date(now.Year(), now.Month(), now.Day(), hh, mm, 0, 0, now.Location())
	if now.Before(start) {
		return false
	}
	if now.Sub(start) > scheduleStartGrace {
		return false
	}
	if !last.IsZero() && !last.Before(start) {
		return false
	}
	return true
}

func wantedWeekday(s string) time.Weekday {
	n, err := strconv.Atoi(strings.TrimSpace(s))
	if err != nil || n < 1 || n > 7 {
		n = 1
	}
	if n == 7 {
		return time.Sunday
	}
	return time.Weekday(n)
}

func waitBudget(reason, auto string) time.Duration {
	if reason == "manual" {
		return 15 * time.Minute
	}
	switch auto {
	case "daily", "weekly", "biweekly", "monthly":
		return 12 * time.Hour
	}
	return 45 * time.Second
}

func (a *App) runJob(id, reason string) {
	t, devs, err := a.lookupTransfer(id)
	if err != nil {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.fromErr(err)
		})
		return
	}
	srcDev, ok := findDevice(devs, t.SrcDevice)
	if !ok {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("srcMissing")
		})
		return
	}
	dstDev, ok := findDevice(devs, t.DstDevice)
	if !ok {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("dstMissing")
		})
		return
	}
	sources := t.sourceList()
	if len(sources) == 0 || (strings.TrimSpace(t.DstPath) == "" && strings.TrimSpace(t.DstShare) == "") {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("needFolders")
		})
		return
	}

	deadline := time.Now().Add(waitBudget(reason, t.Auto))
	for {
		ready, wait, fail := sourceReady(srcDev, sources[0])
		if ready {
			break
		}
		if fail.Key != "" {
			a.setJob(id, func(j *Job) {
				j.Status = "error"
				j.msg(fail.Key, fail.Arg)
			})
			a.markLastRun(id)
			return
		}
		if time.Now().After(deadline) {
			a.setJob(id, func(j *Job) {
				j.Status = "error"
				j.msg("waitSourceGone")
			})
			a.markLastRun(id)
			return
		}
		a.setJob(id, func(j *Job) {
			j.Status = "waiting"
			if wait.Key != "" {
				j.msg(wait.Key, wait.Arg)
			} else {
				j.msg("waitSource")
			}
		})
		time.Sleep(15 * time.Second)
	}

	a.setJob(id, func(j *Job) {
		j.Status = "running"
		j.Percent = 0
		j.msg("counting")
	})
	mode := t.Mode
	if mode == "" {
		mode = "sync"
	}
	workers := t.workerCount()
	multi := len(sources) > 1
	var total int64
	for _, src := range sources {
		n, err := countSource(srcDev, src)
		if err != nil {
			a.setJob(id, func(j *Job) {
				j.Status = "error"
				k, arg := splitErr(err)
				if k == "raw" {
					j.msg("srcUnreadable", arg)
				} else {
					j.msg(k, arg)
				}
			})
			a.markLastRun(id)
			return
		}
		total += n
	}
	var done int64
	report := a.makeReporter(id, &total, &done)
	for _, src := range sources {
		if err := copyOne(srcDev, dstDev, src, t.DstShare, t.DstPath, mode, workers, multi, report); err != nil {
			a.setJob(id, func(j *Job) {
				j.Status = "error"
				j.fromErr(err)
				j.BytesDone = done
				j.BytesTotal = total
			})
			a.markLastRun(id)
			return
		}
	}
	doneKey := "xferDone"
	if total == 0 {
		doneKey = "xferEmpty"
	}
	a.setJob(id, func(j *Job) {
		j.Status = "ok"
		j.Percent = 100
		j.BytesDone = done
		j.BytesTotal = total
		j.msg(doneKey)
	})
	a.markLastRun(id)
}

// wakeIfOffline sends WoL only when the destination has a MAC. Any device with a MAC
// can be woken (QNAP, PC, …). Without MAC, an offline target just fails.
func (a *App) wakeIfOffline(id string, dest Device, waitMins int, action string) (ready, mark bool) {
	if isLocalDevice(dest) {
		return true, false
	}
	if hostReachable(dest.Host) {
		return true, false
	}
	if !deviceCanWake(dest) {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("dstUnreachable")
		})
		return false, true
	}
	return a.waitForDevice(id, dest, waitMins, action)
}

// waitForDevice wakes a device if SMB is down. ready=false means the job should stop.
// mark is true after a timeout so schedules do not retry every 15s.
func (a *App) waitForDevice(id string, dev Device, waitMins int, action string) (ready, mark bool) {
	label := strings.TrimSpace(dev.Name)
	if label == "" {
		label = dev.Host
	}
	if hostReachable(dev.Host) {
		a.setJob(id, func(j *Job) {
			j.Status = "waiting"
			j.msg("alreadyAwake", label)
		})
		return true, false
	}
	if strings.TrimSpace(dev.MAC) == "" {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("noMac", label)
		})
		return false, false
	}
	a.setJob(id, func(j *Job) {
		j.msg("wolTo", label)
	})
	if _, err := sendMagicPacket(dev.MAC, dev.Host); err != nil {
		a.setJob(id, func(j *Job) {
			j.msg("wolWait", label)
		})
	} else {
		a.setJob(id, func(j *Job) {
			j.msg("wolSent")
		})
	}
	if waitMins < 1 {
		waitMins = 20
	}
	deadline := time.Now().Add(time.Duration(waitMins) * time.Minute)
	for !hostReachable(dev.Host) {
		if time.Now().After(deadline) {
			a.setJob(id, func(j *Job) {
				j.Status = "error"
				j.msg("wakeGone", label)
			})
			return false, true
		}
		a.setJob(id, func(j *Job) {
			j.Status = "waiting"
			j.msg("waitDevice", label)
		})
		time.Sleep(15 * time.Second)
	}
	a.setJob(id, func(j *Job) {
		j.Status = "waiting"
		j.msg("nowAwake", label)
	})
	return true, false
}

func (a *App) runWake(id, reason string) {
	p, devs, err := a.lookupWake(id)
	if err != nil {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.fromErr(err)
		})
		return
	}
	dev, ok := findDevice(devs, p.DeviceID)
	if !ok {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("dstMissingCheck")
		})
		return
	}
	waitMins, _ := strconv.Atoi(strings.TrimSpace(p.Wait))
	ready, mark := a.waitForDevice(id, dev, waitMins, "starte Übertragung.")
	if !ready {
		if mark {
			a.markLastRun(id)
		}
		return
	}
	t := p.asTransfer()
	srcDev, ok := findDevice(devs, t.SrcDevice)
	if !ok {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("srcMissing")
		})
		return
	}
	dstDev, ok := findDevice(devs, t.DstDevice)
	if !ok {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("dstMissing")
		})
		return
	}
	sources := t.sourceList()
	if len(sources) == 0 {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("noSrcFolders")
		})
		return
	}
	a.setJob(id, func(j *Job) {
		j.Status = "running"
		j.Percent = 0
		j.msg("counting")
	})
	workers := t.workerCount()
	multi := len(sources) > 1
	var total int64
	for _, src := range sources {
		n, err := countSource(srcDev, src)
		if err != nil {
			a.setJob(id, func(j *Job) {
				j.Status = "error"
				k, arg := splitErr(err)
				if k == "raw" {
					j.msg("srcUnreadable", arg)
				} else {
					j.msg(k, arg)
				}
			})
			a.markLastRun(id)
			return
		}
		total += n
	}
	var done int64
	report := a.makeReporter(id, &total, &done)
	for _, src := range sources {
		if err := copyOne(srcDev, dstDev, src, t.DstShare, t.DstPath, "sync", workers, multi, report); err != nil {
			a.setJob(id, func(j *Job) {
				j.Status = "error"
				j.fromErr(err)
				j.BytesDone = done
				j.BytesTotal = total
			})
			a.markLastRun(id)
			return
		}
	}
	doneKey := "xferDone"
	if total == 0 {
		doneKey = "xferEmpty"
	}
	a.setJob(id, func(j *Job) {
		j.Status = "ok"
		j.Percent = 100
		j.BytesDone = done
		j.BytesTotal = total
		j.msg(doneKey)
	})
	a.markLastRun(id)
}

type folderRef struct {
	Share string
	Path  string
}

func (t Transfer) sourceList() []folderRef {
	out := []folderRef{}
	if strings.TrimSpace(t.SrcShare) != "" || strings.TrimSpace(t.SrcPath) != "" {
		out = append(out, folderRef{Share: t.SrcShare, Path: t.SrcPath})
	}
	for _, p := range t.SrcPaths {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		share, rel := t.SrcShare, p
		if i := strings.Index(p, "|"); i >= 0 {
			share, rel = p[:i], p[i+1:]
		}
		out = append(out, folderRef{Share: share, Path: rel})
	}
	return out
}

func sourceReady(d Device, src folderRef) (ready bool, wait, fail locMsg) {
	if isLocalDevice(d) {
		abs, err := resolveLocalPath(src.Share, src.Path)
		if err != nil {
			if strings.TrimSpace(src.Share) == "" && strings.Contains(src.Path, `:\`) {
				return false, locMsg{}, locMsg{Key: "winPath"}
			}
			return false, locMsg{}, locMsg{Key: "shareHidden", Arg: src.Share}
		}
		if _, err := os.Stat(abs); err != nil {
			return false, locMsg{}, locMsg{Key: "srcNotFound", Arg: abs}
		}
		return true, locMsg{}, locMsg{}
	}
	if !hostReachable(d.Host) {
		arg := strings.TrimSpace(d.Name)
		if arg == "" {
			arg = d.Host
		} else if d.Host != "" {
			arg = arg + " (" + d.Host + ")"
		}
		return false, locMsg{Key: "waitHost", Arg: arg}, locMsg{}
	}
	if err := smbStatOK(d, src.Share, src.Path); err != nil {
		return false, locMsg{Key: "waitShare", Arg: src.Share}, locMsg{}
	}
	return true, locMsg{}, locMsg{}
}

func countSource(d Device, src folderRef) (int64, error) {
	if isLocalDevice(d) {
		abs, err := resolveLocalPath(src.Share, src.Path)
		if err != nil {
			return 0, err
		}
		n, err := countBytes(abs)
		if err != nil {
			return 0, err
		}
		if err := forUnlistedTrees(abs, func(extra, _ string) error {
			n2, e := countBytes(extra)
			n += n2
			return e
		}); err != nil {
			return n, err
		}
		return n, nil
	}
	sess, conn, err := smbDial(d)
	if err != nil {
		return 0, err
	}
	defer func() {
		_ = sess.Logoff()
		_ = conn.Close()
	}()
	fsys, err := sess.Mount(src.Share)
	if err != nil {
		return 0, err
	}
	defer fsys.Umount()
	return smbWalkBytes(fsys, src.Path)
}

func copyOne(srcDev, dstDev Device, src folderRef, dstShare, dstPath, mode string, workers int, multi bool, report func(int64, string)) error {
	if err := tryRcloneCopy(srcDev, dstDev, src, dstShare, dstPath, mode, workers, multi, report); err == nil {
		return nil
	} else if !errors.Is(err, errRcloneSkip) {
		return err
	}
	baseName := src.Path
	if i := strings.LastIndex(strings.ReplaceAll(baseName, "\\", "/"), "/"); i >= 0 {
		baseName = baseName[i+1:]
	}
	if baseName == "" {
		baseName = src.Share
	}
	switch {
	case isLocalDevice(srcDev) && isLocalDevice(dstDev):
		from, err := resolveLocalPath(src.Share, src.Path)
		if err != nil {
			return err
		}
		to, err := resolveLocalPath(dstShare, dstPath)
		if err != nil {
			return err
		}
		if nestInto(to, baseName, mode, multi) {
			to = filepath.Join(to, baseName)
		}
		if err := pathsSafe(from, to); err != nil {
			return err
		}
		return copyTree(from, to, mode, workers, report)
	case !isLocalDevice(srcDev) && isLocalDevice(dstDev):
		to, err := resolveLocalPath(dstShare, dstPath)
		if err != nil {
			return locErr("dstHidden")
		}
		if nestInto(to, baseName, mode, multi) {
			to = filepath.Join(to, baseName)
		}
		return copySMBToLocal(srcDev, src.Share, src.Path, to, mode, workers, report)
	case isLocalDevice(srcDev) && !isLocalDevice(dstDev):
		from, err := resolveLocalPath(src.Share, src.Path)
		if err != nil {
			return err
		}
		dstRel := dstPath
		if alwaysNest(mode, multi, baseName) {
			dstRel = joinRel(dstPath, baseName)
		}
		if err := copyLocalToSMB(dstDev, from, dstShare, dstRel, mode, workers, report); err != nil {
			return err
		}
		return forUnlistedTrees(from, func(extra, rel string) error {
			return copyLocalToSMB(dstDev, extra, dstShare, joinRel(dstRel, rel), mode, workers, report)
		})
	default:
		tmp, err := os.MkdirTemp("", "rl-xfer-*")
		if err != nil {
			return err
		}
		defer os.RemoveAll(tmp)
		tmpDir := tmp
		if err := copySMBToLocal(srcDev, src.Share, src.Path, tmpDir, "copy", workers, report); err != nil {
			return err
		}
		dstRel := dstPath
		if alwaysNest(mode, multi, baseName) {
			dstRel = joinRel(dstPath, baseName)
		}
		return copyLocalToSMB(dstDev, tmpDir, dstShare, dstRel, mode, workers, nil)
	}
}

func (a *App) markLastRun(id string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	now := time.Now().Format(time.RFC3339)
	for i, t := range a.data.Transfers {
		if t.ID == id {
			a.data.Transfers[i].LastRun = now
			_ = a.saveLocked()
			return
		}
	}
	for i, p := range a.data.WakePlans {
		if p.ID == id {
			a.data.WakePlans[i].LastRun = now
			_ = a.saveLocked()
			return
		}
	}
	if id == "backup" && a.data.Backup != nil {
		a.data.Backup.LastRun = now
		_ = a.saveLocked()
	}
}

func pathsSafe(src, dst string) error {
	absSrc, err := filepath.Abs(src)
	if err != nil {
		return err
	}
	absDst, err := filepath.Abs(dst)
	if err != nil {
		return err
	}
	if absDst == absSrc {
		return locErr("samePath")
	}
	rel, err := filepath.Rel(absSrc, absDst)
	if err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
		return locErr("dstInsideSrc")
	}
	return nil
}

func countBytes(root string) (int64, error) {
	var total int64
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		info, err := d.Info()
		if err != nil {
			return nil
		}
		if !info.Mode().IsRegular() {
			return nil
		}
		total += info.Size()
		return nil
	})
	return total, err
}
