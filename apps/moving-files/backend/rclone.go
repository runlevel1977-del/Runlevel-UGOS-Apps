package main

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

var errRcloneSkip = errors.New("rclone skip")

func rcloneBin() string {
	exe, err := os.Executable()
	if err == nil {
		cand := filepath.Join(filepath.Dir(exe), "rclone")
		if st, err := os.Stat(cand); err == nil && !st.IsDir() {
			return cand
		}
	}
	return ""
}

func rcloneAvailable() bool {
	return rcloneBin() != ""
}

func rcloneQuote(v string) string {
	if strings.ContainsAny(v, " ,='") {
		return "'" + strings.ReplaceAll(v, "'", `\'`) + "'"
	}
	return v
}

func rcloneObscure(bin, password string) string {
	if password == "" {
		return ""
	}
	cmd := exec.Command(bin, "obscure", password)
	out, err := cmd.Output()
	if err != nil {
		return password
	}
	return strings.TrimSpace(string(out))
}

func rcloneSMBURL(d Device, share, rel string) string {
	host := rcloneQuote(strings.TrimSpace(d.Host))
	user := strings.TrimSpace(d.User)
	domain := "WORKGROUP"
	if i := strings.IndexAny(user, `/\`); i >= 0 {
		domain, user = user[:i], user[i+1:]
	}
	if user == "" {
		user = "Guest"
	}
	bin := rcloneBin()
	pass := rcloneObscure(bin, d.Password)
	sub := strings.ReplaceAll(strings.Trim(rel, `/\`), `\`, "/")
	remote := strings.TrimSpace(share)
	if sub != "" {
		remote = remote + "/" + sub
	}
	return fmt.Sprintf(
		":smb,host=%s,user=%s,pass=%s,domain=%s,case_insensitive=true,idle_timeout=0:%s",
		host, rcloneQuote(user), pass, rcloneQuote(domain), remote,
	)
}

func rcloneCopyArgs(src, dst string, performance bool) []string {
	transfers := "2"
	args := []string{
		"copy", src, dst,
		"-v", "--stats", "1s", "--stats-one-line",
		"--checkers", "4",
		"--timeout", "12h", "--contimeout", "5m",
		"--retries", "10", "--low-level-retries", "20", "--retries-sleep", "30s",
		"--exclude", ".DS_Store", "--exclude", "Thumbs.db",
	}
	if performance {
		transfers = "4"
		args = append(args, "--buffer-size", "64M")
	} else {
		args = append(args, "--disable", "OpenWriterAt,OpenChunkWriter")
	}
	args = append(args, "--transfers", transfers)
	return args
}

func runRcloneCopy(src, dst string, performance bool, report func(int64, string)) error {
	bin := rcloneBin()
	if bin == "" {
		return locErr("rcloneMissing")
	}
	modes := []bool{false}
	if performance {
		modes = []bool{true, false}
	}
	var last error
	for i, perf := range modes {
		if i > 0 && report != nil {
			report(0, "rclone Performance fehlgeschlagen — stabiler SMB-Modus…")
		}
		err := execRclone(bin, rcloneCopyArgs(src, dst, perf), report)
		if err == nil {
			return nil
		}
		last = err
	}
	return last
}

func execRclone(bin string, args []string, report func(int64, string)) error {
	ctx, cancel := context.WithTimeout(context.Background(), 13*time.Hour)
	defer cancel()
	cmd := exec.CommandContext(ctx, bin, args...)
	cmd.Env = append(os.Environ(), "RCLONE_CONFIG=/dev/null")
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return err
	}
	if err := cmd.Start(); err != nil {
		return err
	}
	gotBytes := make(chan struct{}, 1)
	wrapped := report
	if report != nil {
		wrapped = func(n int64, name string) {
			if n > 0 {
				select {
				case gotBytes <- struct{}{}:
				default:
				}
			}
			report(n, name)
		}
	}
	done := make(chan struct{})
	go func() {
		scanRcloneStats(stderr, wrapped)
		close(done)
	}()
	go func() {
		select {
		case <-gotBytes:
		case <-time.After(20 * time.Second):
			cancel()
		case <-ctx.Done():
		}
	}()
	waitErr := cmd.Wait()
	<-done
	if ctx.Err() != nil && waitErr != nil {
		return errRcloneSkip
	}
	return waitErr
}

func splitRcloneLine(data []byte, atEOF bool) (advance int, token []byte, err error) {
	if len(data) == 0 && atEOF {
		return 0, nil, nil
	}
	for i := 0; i < len(data); i++ {
		if data[i] != '\n' && data[i] != '\r' {
			continue
		}
		adv := i + 1
		if data[i] == '\r' && i+1 < len(data) && data[i+1] == '\n' {
			adv++
		}
		return adv, data[:i], nil
	}
	if atEOF {
		return len(data), data, nil
	}
	return 0, nil, nil
}

func scanRcloneStats(r io.Reader, report func(int64, string)) {
	sc := bufio.NewScanner(r)
	sc.Split(splitRcloneLine)
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	var lastBytes int64
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || report == nil {
			continue
		}
		if n, ok := parseRcloneTransferred(line); ok {
			delta := n - lastBytes
			if delta < 0 {
				delta = 0
			}
			lastBytes = n
			report(delta, line)
			continue
		}
		if strings.Contains(line, "Transferred:") || strings.Contains(line, "/s") {
			report(0, line)
		}
	}
}

func parseRcloneTransferred(line string) (int64, bool) {
	if i := strings.Index(line, "Transferred:"); i >= 0 {
		return parseRcloneSize(strings.TrimSpace(line[i+len("Transferred:"):]))
	}
	i := strings.Index(line, " / ")
	if i <= 0 {
		return 0, false
	}
	left := strings.Fields(strings.TrimSpace(line[:i]))
	if len(left) < 2 {
		return 0, false
	}
	return parseRcloneSize(left[len(left)-2] + " " + left[len(left)-1])
}

func parseRcloneSize(rest string) (int64, bool) {
	fields := strings.Fields(rest)
	if len(fields) < 2 {
		return 0, false
	}
	n, err := strconv.ParseFloat(strings.ReplaceAll(fields[0], ",", ""), 64)
	if err != nil {
		return 0, false
	}
	unit := strings.Trim(fields[1], ",/")
	mult := rcloneUnitBytes(unit)
	if mult == 0 {
		return 0, false
	}
	return int64(n * float64(mult)), true
}

func rcloneUnitBytes(unit string) int64 {
	switch strings.TrimSpace(unit) {
	case "B":
		return 1
	case "KiB", "KB":
		return 1024
	case "MiB", "MB":
		return 1024 * 1024
	case "GiB", "GB":
		return 1024 * 1024 * 1024
	case "TiB", "TB":
		return 1024 * 1024 * 1024 * 1024
	default:
		return 0
	}
}

func tryRcloneCopy(srcDev, dstDev Device, src folderRef, dstShare, dstPath, mode string, workers int, multi bool, report func(int64, string)) error {
	if mode == "move" || !rcloneAvailable() {
		return errRcloneSkip
	}
	if isLocalDevice(srcDev) && isLocalDevice(dstDev) {
		return errRcloneSkip
	}
	fast := workers >= 4
	baseName := src.Path
	if i := strings.LastIndex(strings.ReplaceAll(baseName, "\\", "/"), "/"); i >= 0 {
		baseName = baseName[i+1:]
	}
	if baseName == "" {
		baseName = src.Share
	}
	if report != nil {
		report(0, "rclone SMB…")
	}
	switch {
	case isLocalDevice(srcDev) && !isLocalDevice(dstDev):
		from, e := resolveLocalPath(src.Share, src.Path)
		if e != nil {
			return errRcloneSkip
		}
		dstRel := dstPath
		if alwaysNest(mode, multi, baseName) {
			dstRel = joinRel(dstPath, baseName)
		}
		if err := runRcloneCopy(from, rcloneSMBURL(dstDev, dstShare, dstRel), fast, report); err != nil {
			return err
		}
		return forUnlistedTrees(from, func(extra, rel string) error {
			if report != nil {
				report(0, "rclone versteckter Ordner: "+filepath.Base(extra))
			}
			return runRcloneCopy(extra, rcloneSMBURL(dstDev, dstShare, joinRel(dstRel, rel)), fast, report)
		})
	case !isLocalDevice(srcDev) && isLocalDevice(dstDev):
		to, e := resolveLocalPath(dstShare, dstPath)
		if e != nil {
			return errRcloneSkip
		}
		if nestInto(to, baseName, mode, multi) {
			to = filepath.Join(to, baseName)
		}
		if e := os.MkdirAll(to, 0o755); e != nil {
			return e
		}
		return runRcloneCopy(rcloneSMBURL(srcDev, src.Share, src.Path), to, fast, report)
	case !isLocalDevice(srcDev) && !isLocalDevice(dstDev):
		dstRel := dstPath
		if alwaysNest(mode, multi, baseName) {
			dstRel = joinRel(dstPath, baseName)
		}
		return runRcloneCopy(
			rcloneSMBURL(srcDev, src.Share, src.Path),
			rcloneSMBURL(dstDev, dstShare, dstRel),
			fast,
			report,
		)
	default:
		return errRcloneSkip
	}
}
