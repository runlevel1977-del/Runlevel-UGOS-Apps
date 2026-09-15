package main

import (
	"io"
	"io/fs"
	"net"
	"os"
	"path"
	"strings"
	"sync"
	"time"

	"github.com/hirochachacha/go-smb2"
)

func smbDial(d Device) (*smb2.Session, net.Conn, error) {
	host := strings.TrimSpace(d.Host)
	if host == "" {
		return nil, nil, locErr("noHost")
	}
	conn, err := net.DialTimeout("tcp4", net.JoinHostPort(host, "445"), 6*time.Second)
	if err != nil {
		return nil, nil, err
	}
	if tcp, ok := conn.(*net.TCPConn); ok {
		_ = tcp.SetNoDelay(true)
		_ = tcp.SetReadBuffer(copyBufSize)
		_ = tcp.SetWriteBuffer(copyBufSize)
	}
	user := strings.TrimSpace(d.User)
	pass := d.Password
	domain := ""
	if i := strings.IndexAny(user, `/\`); i >= 0 {
		domain, user = user[:i], user[i+1:]
	}
	if user == "" {
		user = "Guest"
	}
	dialer := &smb2.Dialer{Initiator: &smb2.NTLMInitiator{User: user, Password: pass, Domain: domain}}
	sess, err := dialer.Dial(conn)
	if err != nil {
		_ = conn.Close()
		return nil, nil, err
	}
	return sess, conn, nil
}

func browseSMB(d Device, share, rel string) browseResult {
	sess, conn, err := smbDial(d)
	if err != nil {
		if !hostReachable(d.Host) {
			return browseFail("hostDown")
		}
		return browseFail("smbAuth")
	}
	defer func() {
		_ = sess.Logoff()
		_ = conn.Close()
	}()
	if share == "" {
		names, err := sess.ListSharenames()
		if err != nil {
			return browseFail("sharesRead", err.Error())
		}
		entries := []browseEntry{}
		for _, name := range names {
			if hiddenName(name) || strings.HasSuffix(name, "$") {
				continue
			}
			entries = append(entries, browseEntry{Name: name, Share: name, Path: "", Kind: "share", Label: name})
		}
		if d.Share != "" {
			found := false
			for _, e := range entries {
				if strings.EqualFold(e.Name, d.Share) {
					found = true
					break
				}
			}
			if !found {
				entries = append([]browseEntry{{Name: d.Share, Share: d.Share, Path: "", Kind: "share", Label: d.Share}}, entries...)
			}
		}
		hintKey := ""
		if len(entries) == 0 {
			hintKey = "noShares"
		}
		return browseResult{OK: true, HintKey: hintKey, Entries: entries}
	}
	fsys, err := sess.Mount(share)
	if err != nil {
		return browseFail("shareUnreachable", share)
	}
	defer fsys.Umount()
	dir := strings.ReplaceAll(rel, "\\", "/")
	items, err := fsys.ReadDir(dir)
	if err != nil {
		return browseFail("folderUnreadable", err.Error())
	}
	entries := []browseEntry{}
	for _, it := range items {
		if hiddenName(it.Name()) || !it.IsDir() {
			continue
		}
		p := joinRel(rel, it.Name())
		entries = append(entries, browseEntry{Name: it.Name(), Share: share, Path: p, Kind: "dir", Label: it.Name()})
	}
	return browseResult{OK: true, Share: share, Path: rel, Parent: parentRel(rel), Entries: entries}
}

func smbStatOK(d Device, share, rel string) error {
	sess, conn, err := smbDial(d)
	if err != nil {
		return err
	}
	defer func() {
		_ = sess.Logoff()
		_ = conn.Close()
	}()
	if share == "" {
		return locErr("noShare")
	}
	fsys, err := sess.Mount(share)
	if err != nil {
		return err
	}
	defer fsys.Umount()
	p := strings.ReplaceAll(rel, "\\", "/")
	if p == "" {
		return nil
	}
	st, err := fsys.Stat(p)
	if err != nil {
		return err
	}
	if !st.IsDir() && !st.Mode().IsRegular() {
		return locErr("noFile")
	}
	return nil
}

func smbWalkBytes(fsys *smb2.Share, rel string) (int64, error) {
	var total int64
	err := walkSMB(fsys, rel, func(p string, st fs.FileInfo) error {
		if st.Mode().IsRegular() {
			total += st.Size()
		}
		return nil
	})
	return total, err
}

func walkSMB(fsys *smb2.Share, rel string, fn func(string, fs.FileInfo) error) error {
	p := strings.ReplaceAll(rel, "\\", "/")
	st, err := fsys.Stat(p)
	if err != nil {
		if p == "" {
			st = fakeDir{}
		} else {
			return err
		}
	}
	if !st.IsDir() {
		return fn(p, st)
	}
	items, err := fsys.ReadDir(p)
	if err != nil {
		return err
	}
	for _, it := range items {
		if hiddenName(it.Name()) {
			continue
		}
		child := it.Name()
		if p != "" {
			child = path.Join(p, it.Name())
		}
		if it.IsDir() {
			if err := walkSMB(fsys, child, fn); err != nil {
				return err
			}
			continue
		}
		if it.Mode().IsRegular() {
			if err := fn(child, it); err != nil {
				return err
			}
		}
	}
	return nil
}

type fakeDir struct{}

func (fakeDir) Name() string       { return "" }
func (fakeDir) Size() int64        { return 0 }
func (fakeDir) Mode() fs.FileMode  { return fs.ModeDir }
func (fakeDir) ModTime() time.Time { return time.Time{} }
func (fakeDir) IsDir() bool        { return true }
func (fakeDir) Sys() any           { return nil }

func copySMBToLocal(d Device, share, rel, dst, mode string, workers int, report func(int64, string)) error {
	if workers < 1 {
		workers = 1
	}
	sess, conn, err := smbDial(d)
	if err != nil {
		return err
	}
	fsys, err := sess.Mount(share)
	if err != nil {
		_ = sess.Logoff()
		_ = conn.Close()
		return err
	}
	base := strings.ReplaceAll(rel, "\\", "/")
	type pullJob struct {
		smbPath string
		target  string
		st      fs.FileInfo
	}
	jobs := []pullJob{}
	err = walkSMB(fsys, base, func(p string, st fs.FileInfo) error {
		if !st.Mode().IsRegular() {
			return nil
		}
		relOut := p
		if base != "" {
			relOut = strings.TrimPrefix(p, base)
			relOut = strings.TrimPrefix(relOut, "/")
		}
		if relOut == "" {
			relOut = path.Base(p)
		}
		jobs = append(jobs, pullJob{smbPath: p, target: filepathJoin(dst, relOut), st: st})
		return nil
	})
	if err != nil {
		_ = fsys.Umount()
		_ = sess.Logoff()
		_ = conn.Close()
		return err
	}
	copyOne := func(fsys *smb2.Share, j pullJob) error {
		if isIncremental(mode) && sameFile(j.target, j.st) {
			if report != nil {
				report(j.st.Size(), path.Base(j.smbPath)+" (unverändert)")
			}
			return nil
		}
		if err := os.MkdirAll(dirOf(j.target), 0o755); err != nil {
			return err
		}
		in, err := fsys.Open(j.smbPath)
		if err != nil {
			return err
		}
		defer in.Close()
		out, err := os.OpenFile(j.target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
		if err != nil {
			return err
		}
		n, copyErr := io.CopyBuffer(out, in, make([]byte, copyBufSize))
		closeErr := out.Close()
		if copyErr != nil {
			return copyErr
		}
		if closeErr != nil {
			return closeErr
		}
		_ = os.Chtimes(j.target, j.st.ModTime(), j.st.ModTime())
		if report != nil {
			report(n, path.Base(j.smbPath))
		}
		return nil
	}
	if workers == 1 || len(jobs) < 2 {
		defer func() {
			_ = fsys.Umount()
			_ = sess.Logoff()
			_ = conn.Close()
		}()
		for _, j := range jobs {
			if err := copyOne(fsys, j); err != nil {
				return err
			}
		}
		return nil
	}
	_ = fsys.Umount()
	_ = sess.Logoff()
	_ = conn.Close()
	return runSMBWorkers(workers, len(jobs), func(ch chan int, setErr func(error)) {
		sess, conn, err := smbDial(d)
		if err != nil {
			setErr(err)
			for range ch {
			}
			return
		}
		fsys, err := sess.Mount(share)
		if err != nil {
			_ = sess.Logoff()
			_ = conn.Close()
			setErr(err)
			for range ch {
			}
			return
		}
		defer func() {
			_ = fsys.Umount()
			_ = sess.Logoff()
			_ = conn.Close()
		}()
		for i := range ch {
			if err := copyOne(fsys, jobs[i]); err != nil {
				setErr(err)
			}
		}
	})
}

func copyLocalToSMB(d Device, src, share, rel, mode string, workers int, report func(int64, string)) error {
	if workers < 1 {
		workers = 1
	}
	srcAbs, err := os.Stat(src)
	if err != nil {
		return err
	}
	baseName := path.Base(strings.ReplaceAll(src, "\\", "/"))
	type pushJob struct {
		local string
		dest  string
		info  os.FileInfo
	}
	jobs := []pushJob{}
	err = filepathWalkCopy(src, srcAbs.IsDir(), func(relFile string, info os.FileInfo, r io.Reader) error {
		if closer, ok := r.(io.Closer); ok {
			_ = closer.Close()
		}
		dest := strings.ReplaceAll(joinRel(rel, relFile), "\\", "/")
		if relFile == "" && !srcAbs.IsDir() {
			dest = strings.ReplaceAll(joinRel(rel, baseName), "\\", "/")
		}
		local := src
		if srcAbs.IsDir() && relFile != "" && relFile != "." {
			local = filepathJoin(src, relFile)
		}
		jobs = append(jobs, pushJob{local: local, dest: dest, info: info})
		return nil
	})
	if err != nil {
		return err
	}
	copyOne := func(fsys *smb2.Share, j pushJob) error {
		if isIncremental(mode) {
			if st, err := fsys.Stat(j.dest); err == nil && sameMeta(st.Size(), st.ModTime(), j.info.Size(), j.info.ModTime()) {
				if report != nil {
					report(j.info.Size(), path.Base(j.dest)+" (unverändert)")
				}
				return nil
			}
		}
		if dir := path.Dir(j.dest); dir != "." && dir != "" {
			_ = smbMkdirAll(fsys, dir)
		}
		in, err := os.Open(j.local)
		if err != nil {
			return err
		}
		defer in.Close()
		out, err := fsys.Create(j.dest)
		if err != nil {
			return err
		}
		n, copyErr := io.CopyBuffer(out, in, make([]byte, copyBufSize))
		closeErr := out.Close()
		if copyErr != nil {
			return copyErr
		}
		if closeErr != nil {
			return closeErr
		}
		if report != nil {
			report(n, path.Base(j.dest))
		}
		return nil
	}
	sess, conn, err := smbDial(d)
	if err != nil {
		return err
	}
	fsys, err := sess.Mount(share)
	if err != nil {
		_ = sess.Logoff()
		_ = conn.Close()
		return err
	}
	if workers == 1 || len(jobs) < 2 {
		defer func() {
			_ = fsys.Umount()
			_ = sess.Logoff()
			_ = conn.Close()
		}()
		for _, j := range jobs {
			if err := copyOne(fsys, j); err != nil {
				return err
			}
		}
		return nil
	}
	_ = fsys.Umount()
	_ = sess.Logoff()
	_ = conn.Close()
	return runSMBWorkers(workers, len(jobs), func(ch chan int, setErr func(error)) {
		sess, conn, err := smbDial(d)
		if err != nil {
			setErr(err)
			for range ch {
			}
			return
		}
		fsys, err := sess.Mount(share)
		if err != nil {
			_ = sess.Logoff()
			_ = conn.Close()
			setErr(err)
			for range ch {
			}
			return
		}
		defer func() {
			_ = fsys.Umount()
			_ = sess.Logoff()
			_ = conn.Close()
		}()
		for i := range ch {
			if err := copyOne(fsys, jobs[i]); err != nil {
				setErr(err)
			}
		}
	})
}

func runSMBWorkers(workers, n int, body func(chan int, func(error))) error {
	ch := make(chan int)
	var mu sync.Mutex
	var first error
	setErr := func(err error) {
		if err == nil {
			return
		}
		mu.Lock()
		if first == nil {
			first = err
		}
		mu.Unlock()
	}
	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			body(ch, setErr)
		}()
	}
	for i := 0; i < n; i++ {
		mu.Lock()
		fail := first != nil
		mu.Unlock()
		if fail {
			break
		}
		ch <- i
	}
	close(ch)
	wg.Wait()
	return first
}

func smbMkdirAll(fsys *smb2.Share, dir string) error {
	dir = strings.ReplaceAll(dir, "\\", "/")
	acc := ""
	for _, part := range strings.Split(dir, "/") {
		if part == "" || part == "." {
			continue
		}
		if acc == "" {
			acc = part
		} else {
			acc = acc + "/" + part
		}
		if _, err := fsys.Stat(acc); err == nil {
			continue
		}
		if err := fsys.Mkdir(acc, 0o755); err != nil {
			if _, stErr := fsys.Stat(acc); stErr == nil {
				continue
			}
			return err
		}
	}
	return nil
}

func filepathJoin(base, rel string) string {
	rel = strings.ReplaceAll(rel, "\\", "/")
	return strings.TrimSuffix(base, string(os.PathSeparator)) + string(os.PathSeparator) + filepathFromSlash(rel)
}

func dirOf(p string) string {
	i := strings.LastIndexAny(p, `/\`)
	if i < 0 {
		return "."
	}
	return p[:i]
}

func filepathFromSlash(p string) string {
	return strings.ReplaceAll(p, "/", string(os.PathSeparator))
}

func filepathWalkCopy(src string, isDir bool, fn func(rel string, info os.FileInfo, r io.Reader) error) error {
	if !isDir {
		info, err := os.Stat(src)
		if err != nil {
			return err
		}
		f, err := os.Open(src)
		if err != nil {
			return err
		}
		defer f.Close()
		return fn("", info, f)
	}
	return fs.WalkDir(os.DirFS(src), ".", func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() || hiddenName(d.Name()) {
			return nil
		}
		info, err := d.Info()
		if err != nil || !info.Mode().IsRegular() {
			return nil
		}
		f, err := os.Open(filepathJoin(src, p))
		if err != nil {
			return err
		}
		defer f.Close()
		return fn(p, info, f)
	})
}

type backupArchive struct {
	Name      string `json:"name"`
	Size      int64  `json:"size"`
	Time      string `json:"time"`
	Encrypted bool   `json:"encrypted"`
}

func withSMBShare(d Device, share string, fn func(*smb2.Share) error) error {
	sess, conn, err := smbDial(d)
	if err != nil {
		return err
	}
	defer func() {
		_ = sess.Logoff()
		_ = conn.Close()
	}()
	fsys, err := sess.Mount(share)
	if err != nil {
		return err
	}
	defer fsys.Umount()
	return fn(fsys)
}

func smbWriteFile(d Device, share, rel string, write func(io.Writer) error) error {
	rel = strings.ReplaceAll(strings.Trim(rel, `/\`), `\`, "/")
	if rel == "" {
		return locErr("archiveName")
	}
	return withSMBShare(d, share, func(fsys *smb2.Share) error {
		if dir := path.Dir(rel); dir != "." && dir != "" {
			if err := smbMkdirAll(fsys, dir); err != nil {
				return err
			}
		}
		out, err := fsys.Create(rel)
		if err != nil {
			return err
		}
		err = write(out)
		closeErr := out.Close()
		if err != nil {
			_ = fsys.Remove(rel)
			return err
		}
		return closeErr
	})
}

func smbReadFile(d Device, share, rel string, read func(io.Reader) error) error {
	rel = strings.ReplaceAll(strings.Trim(rel, `/\`), `\`, "/")
	if rel == "" {
		return locErr("archiveName")
	}
	return withSMBShare(d, share, func(fsys *smb2.Share) error {
		in, err := fsys.Open(rel)
		if err != nil {
			return err
		}
		defer in.Close()
		return read(in)
	})
}

func smbRemoveFile(d Device, share, rel string) error {
	rel = strings.ReplaceAll(strings.Trim(rel, `/\`), `\`, "/")
	if rel == "" {
		return locErr("archiveName")
	}
	return withSMBShare(d, share, func(fsys *smb2.Share) error {
		return fsys.Remove(rel)
	})
}

func smbListBackupArchives(d Device, share, rel string) ([]backupArchive, error) {
	rel = strings.ReplaceAll(strings.Trim(rel, `/\`), `\`, "/")
	var out []backupArchive
	err := withSMBShare(d, share, func(fsys *smb2.Share) error {
		items, err := fsys.ReadDir(rel)
		if err != nil {
			return err
		}
		for _, it := range items {
			if it.IsDir() || hiddenName(it.Name()) || !isBackupArchiveName(it.Name()) {
				continue
			}
			out = append(out, backupArchive{
				Name:      it.Name(),
				Size:      it.Size(),
				Time:      it.ModTime().Format(time.RFC3339),
				Encrypted: isBackupEncryptedName(it.Name()),
			})
		}
		return nil
	})
	return out, err
}
