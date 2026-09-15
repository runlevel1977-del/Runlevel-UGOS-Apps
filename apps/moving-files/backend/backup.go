package main

import (
	"io"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

func keepCount(s string) int {
	n, err := strconv.Atoi(strings.TrimSpace(s))
	if err != nil || n < 1 {
		return 7
	}
	if n > 50 {
		return 50
	}
	return n
}

func (a *App) backupSettings() (Backup, []Device, error) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.data.Backup == nil {
		return Backup{}, nil, locErr("noBackup")
	}
	return *a.data.Backup, append([]Device(nil), a.data.Devices...), nil
}

func (a *App) listBackupArchives() ([]backupArchive, error) {
	b, devs, err := a.backupSettings()
	if err != nil {
		return nil, err
	}
	dst, ok := findDevice(devs, b.DstDevice)
	if !ok {
		return nil, locErr("dstMissing")
	}
	list, err := listBackupArchives(dst, b.DstShare, b.DstPath)
	if err != nil {
		return nil, err
	}
	sort.Slice(list, func(i, j int) bool { return list[i].Name > list[j].Name })
	return list, nil
}

func listBackupArchives(d Device, share, rel string) ([]backupArchive, error) {
	if isLocalDevice(d) {
		abs, err := resolveLocalPath(share, rel)
		if err != nil {
			return nil, err
		}
		items, err := os.ReadDir(abs)
		if err != nil {
			if os.IsNotExist(err) {
				return []backupArchive{}, nil
			}
			return nil, err
		}
		out := []backupArchive{}
		for _, it := range items {
			if it.IsDir() || hiddenName(it.Name()) || !isBackupArchiveName(it.Name()) {
				continue
			}
			info, err := it.Info()
			if err != nil {
				continue
			}
			out = append(out, backupArchive{
				Name:      it.Name(),
				Size:      info.Size(),
				Time:      info.ModTime().Format(time.RFC3339),
				Encrypted: isBackupEncryptedName(it.Name()),
			})
		}
		return out, nil
	}
	return smbListBackupArchives(d, share, rel)
}

func pruneBackupArchives(d Device, share, rel string, keep int) error {
	list, err := listBackupArchives(d, share, rel)
	if err != nil {
		return err
	}
	sort.Slice(list, func(i, j int) bool { return list[i].Name > list[j].Name })
	if len(list) <= keep {
		return nil
	}
	for _, item := range list[keep:] {
		destRel := joinRel(rel, item.Name)
		if isLocalDevice(d) {
			abs, err := resolveLocalPath(share, destRel)
			if err != nil {
				continue
			}
			_ = os.Remove(abs)
			continue
		}
		_ = smbRemoveFile(d, share, destRel)
	}
	return nil
}

func (a *App) failBackup(key string, arg ...string) {
	a.setJob("backup", func(j *Job) {
		j.Status = "error"
		j.msg(key, arg...)
	})
	a.markLastRun("backup")
}

func (a *App) failBackupErr(err error) {
	k, arg := splitErr(err)
	a.failBackup(k, arg)
}

func (a *App) runArchiveBackup() {
	id := "backup"
	b, devs, err := a.backupSettings()
	if err != nil {
		a.failBackupErr(err)
		return
	}
	srcDev, ok := findDevice(devs, b.SrcDevice)
	if !ok {
		a.failBackup("srcMissing")
		return
	}
	dstDev, ok := findDevice(devs, b.DstDevice)
	if !ok {
		a.failBackup("dstMissing")
		return
	}
	src := folderRef{Share: b.SrcShare, Path: b.SrcPath}
	if !isLocalDevice(srcDev) {
		a.failBackup("backupNeedLocal")
		return
	}
	if strings.TrimSpace(src.Share) == "" && strings.TrimSpace(src.Path) == "" {
		a.failBackup("backupNoSrc")
		return
	}
	if strings.TrimSpace(b.DstShare) == "" && strings.TrimSpace(b.DstPath) == "" {
		a.failBackup("backupNoDst")
		return
	}
	ready, wait, fail := sourceReady(srcDev, src)
	if !ready {
		m := fail
		if m.Key == "" {
			m = wait
		}
		if m.Key == "" {
			m = locMsg{Key: "srcOffline"}
		}
		a.failBackup(m.Key, m.Arg)
		return
	}
	waitMins, _ := strconv.Atoi(strings.TrimSpace(b.Wait))
	ok, mark := a.wakeIfOffline(id, dstDev, waitMins, "starte Backup.")
	if !ok {
		if mark {
			a.markLastRun(id)
		}
		return
	}
	a.setJob(id, func(j *Job) {
		j.Status = "running"
		j.Percent = 0
		j.msg("counting")
	})
	total, err := countSource(srcDev, src)
	if err != nil {
		a.failBackup("srcUnreadable", err.Error())
		return
	}
	from, err := resolveLocalPath(src.Share, src.Path)
	if err != nil {
		a.failBackup("srcNotVisible")
		return
	}
	name := backupArchiveName(b.Password)
	var done int64
	lastUI := time.Now()
	var reportMu sync.Mutex
	report := func(n int64, file string) {
		reportMu.Lock()
		defer reportMu.Unlock()
		done += n
		if time.Since(lastUI) < 200*time.Millisecond && done < total {
			return
		}
		lastUI = time.Now()
		pct := 0
		if total > 0 {
			pct = int(done * 100 / total)
			if pct > 100 {
				pct = 100
			}
		}
		a.setJob(id, func(j *Job) {
			j.Status = "running"
			j.Percent = pct
			j.BytesDone = done
			j.BytesTotal = total
			j.progressName(file)
		})
	}
	a.setJob(id, func(j *Job) {
		j.msg("archiveWrite")
		j.BytesTotal = total
	})
	destRel := joinRel(b.DstPath, name)
	writeErr := writeBackupArchive(dstDev, b.DstShare, destRel, from, b.Password, report)
	if writeErr != nil {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.fromErr(writeErr)
			j.BytesDone = done
			j.BytesTotal = total
		})
		a.markLastRun(id)
		return
	}
	_ = pruneBackupArchives(dstDev, b.DstShare, b.DstPath, keepCount(b.Keep))
	a.setJob(id, func(j *Job) {
		j.Status = "ok"
		j.Percent = 100
		j.BytesDone = done
		j.BytesTotal = total
		j.msg("archiveSaved", name)
	})
	a.markLastRun(id)
}

func writeBackupArchive(dst Device, share, rel, srcDir, password string, report func(int64, string)) error {
	rel = strings.Trim(strings.ReplaceAll(rel, "\\", "/"), "/")
	if rel == "" {
		return locErr("archiveName")
	}
	writeBody := func(w io.Writer) error {
		out, closeEnc, err := wrapArchiveWriter(w, password)
		if err != nil {
			return err
		}
		err = writeTarGz(srcDir, out, report)
		closeErr := closeEnc()
		if err != nil {
			return err
		}
		return closeErr
	}
	if isLocalDevice(dst) {
		dirRel := path.Dir(rel)
		if dirRel == "." {
			dirRel = ""
		}
		dirAbs, err := resolveLocalPath(share, dirRel)
		if err != nil {
			return locErr("backupDstHidden")
		}
		abs := filepath.Join(dirAbs, filepath.Base(rel))
		if err := os.MkdirAll(filepath.Dir(abs), 0o755); err != nil {
			return err
		}
		out, err := os.Create(abs)
		if err != nil {
			return err
		}
		err = writeBody(out)
		closeErr := out.Close()
		if err != nil {
			_ = os.Remove(abs)
			return err
		}
		return closeErr
	}
	return smbWriteFile(dst, share, rel, writeBody)
}

func (a *App) startRestore(names []string, destShare, destPath, password string) error {
	id := "backup-restore"
	if a.jobBusy(id) || a.jobBusy("backup") {
		return locErr("backupBusy")
	}
	clean := []string{}
	needPass := false
	for _, n := range names {
		n = path.Base(strings.TrimSpace(n))
		if isBackupArchiveName(n) {
			if isBackupEncryptedName(n) {
				needPass = true
			}
			clean = append(clean, n)
		}
	}
	if len(clean) == 0 {
		return locErr("noArchive")
	}
	if needPass && strings.TrimSpace(password) == "" {
		return locErr("needArchivePass")
	}
	if strings.TrimSpace(destShare) == "" && strings.TrimSpace(destPath) == "" {
		return locErr("needRestoreFolder")
	}
	a.setJob(id, func(j *Job) {
		j.Name = "Restore"
		j.Status = "waiting"
		j.Percent = 0
		j.BytesDone = 0
		j.BytesTotal = 0
		j.msg("start")
	})
	go a.runRestore(clean, destShare, destPath, password)
	return nil
}

func (a *App) runRestore(names []string, destShare, destPath, password string) {
	id := "backup-restore"
	b, devs, err := a.backupSettings()
	if err != nil {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.fromErr(err)
		})
		return
	}
	srcDev, ok := findDevice(devs, b.DstDevice)
	if !ok {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("backupDstMissing")
		})
		return
	}
	to, err := resolveLocalPath(destShare, destPath)
	if err != nil {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("restoreDstHidden")
		})
		return
	}
	if !isLocalDevice(srcDev) && !hostReachable(srcDev.Host) {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("archiveOffline")
		})
		return
	}
	list, err := listBackupArchives(srcDev, b.DstShare, b.DstPath)
	if err != nil {
		a.setJob(id, func(j *Job) {
			j.Status = "error"
			j.msg("archivesRead", err.Error())
		})
		return
	}
	sizeByName := map[string]int64{}
	for _, item := range list {
		sizeByName[item.Name] = item.Size
	}
	var total int64
	for _, n := range names {
		total += sizeByName[n]
	}
	var done int64
	lastUI := time.Now()
	var reportMu sync.Mutex
	report := func(n int64, file string) {
		reportMu.Lock()
		defer reportMu.Unlock()
		done += n
		if time.Since(lastUI) < 200*time.Millisecond {
			return
		}
		lastUI = time.Now()
		pct := 0
		if total > 0 {
			pct = int(done * 100 / total)
			if pct > 100 {
				pct = 100
			}
		}
		a.setJob(id, func(j *Job) {
			j.Status = "running"
			j.Percent = pct
			j.BytesDone = done
			j.BytesTotal = total
			j.progressName(file)
		})
	}
	var skippedAll []string
	a.setJob(id, func(j *Job) {
		j.Status = "running"
		j.BytesTotal = total
		j.msg("unpack")
	})
	for _, name := range names {
		rel := joinRel(b.DstPath, name)
		a.setJob(id, func(j *Job) {
			j.msg("unpackFile", name)
		})
		skipped, err := extractBackupArchive(srcDev, b.DstShare, rel, name, to, password, report)
		if err != nil {
			a.setJob(id, func(j *Job) {
				j.Status = "error"
				j.msg("unpackErr", name+": "+err.Error())
			})
			return
		}
		skippedAll = append(skippedAll, skipped...)
	}
	doneKey := "restoreOk"
	arg := filepath.Base(to)
	if n := len(skippedAll); n > 0 {
		show := skippedAll[0]
		if n > 1 {
			show += " +" + strconv.Itoa(n-1)
		}
		doneKey = "restoreSkip"
		arg = show
	}
	a.setJob(id, func(j *Job) {
		j.Status = "ok"
		j.Percent = 100
		j.BytesDone = done
		j.BytesTotal = total
		j.msg(doneKey, arg)
	})
}

func extractBackupArchive(src Device, share, rel, name, dest, password string, report func(int64, string)) ([]string, error) {
	if isLocalDevice(src) {
		abs, err := resolveLocalPath(share, rel)
		if err != nil {
			return nil, err
		}
		f, err := os.Open(abs)
		if err != nil {
			return nil, err
		}
		defer f.Close()
		plain, err := wrapArchiveReader(f, name, password)
		if err != nil {
			return nil, err
		}
		return extractTarGz(plain, dest, report)
	}
	var skipped []string
	err := smbReadFile(src, share, rel, func(r io.Reader) error {
		plain, e := wrapArchiveReader(r, name, password)
		if e != nil {
			return e
		}
		skipped, e = extractTarGz(plain, dest, report)
		return e
	})
	return skipped, err
}
