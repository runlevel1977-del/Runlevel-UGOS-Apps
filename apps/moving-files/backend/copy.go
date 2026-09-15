package main

import (
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

func isIncremental(mode string) bool {
	return mode == "sync" || mode == "incr"
}

const copyBufSize = 4 << 20

func workerCount(fast *bool) int {
	if fast != nil && !*fast {
		return 1
	}
	return 8
}

func (t Transfer) workerCount() int {
	return workerCount(t.Fast)
}

func sameFile(dst string, src os.FileInfo) bool {
	st, err := os.Stat(dst)
	if err != nil {
		return false
	}
	return sameMeta(st.Size(), st.ModTime(), src.Size(), src.ModTime())
}

func sameMeta(dstSize int64, dstTime time.Time, srcSize int64, srcTime time.Time) bool {
	if dstSize != srcSize {
		return false
	}
	return !dstTime.Before(srcTime.Add(-2 * time.Second))
}

func alwaysNest(mode string, multi bool, baseName string) bool {
	if multi || strings.TrimSpace(baseName) == "" {
		return true
	}
	return mode == "copy" || mode == "move"
}

func nestInto(destDir, baseName, mode string, multi bool) bool {
	if alwaysNest(mode, multi, baseName) {
		return true
	}
	nested := filepath.Join(destDir, baseName)
	st, err := os.Stat(nested)
	if err != nil || !st.IsDir() {
		return false
	}
	entries, err := os.ReadDir(destDir)
	if err != nil {
		return true
	}
	for _, e := range entries {
		name := e.Name()
		if name == baseName || strings.HasPrefix(name, ".") {
			continue
		}
		return false
	}
	return true
}

type copyJob struct {
	src string
	dst string
	fi  os.FileInfo
}

func copyTree(src, dst, mode string, workers int, report func(int64, string)) error {
	srcAbs, err := filepath.Abs(src)
	if err != nil {
		return err
	}
	info, err := os.Stat(srcAbs)
	if err != nil {
		return err
	}
	if workers < 1 {
		workers = 1
	}
	if !info.IsDir() {
		dstAbs := dst
		if st, err := os.Stat(dst); err == nil && st.IsDir() {
			dstAbs = filepath.Join(dst, filepath.Base(srcAbs))
		}
		return copyFile(srcAbs, dstAbs, info, mode, report)
	}
	jobs := []copyJob{}
	err = filepath.WalkDir(srcAbs, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(srcAbs, path)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if d.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		fi, err := d.Info()
		if err != nil || !fi.Mode().IsRegular() {
			return nil
		}
		jobs = append(jobs, copyJob{src: path, dst: target, fi: fi})
		return nil
	})
	if err != nil {
		return err
	}
	if workers == 1 || len(jobs) < 2 {
		for _, j := range jobs {
			if err := copyFile(j.src, j.dst, j.fi, mode, report); err != nil {
				return err
			}
		}
	} else {
		ch := make(chan copyJob)
		var wg sync.WaitGroup
		var mu sync.Mutex
		var firstErr error
		for i := 0; i < workers; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for j := range ch {
					mu.Lock()
					failed := firstErr != nil
					mu.Unlock()
					if failed {
						continue
					}
					if err := copyFile(j.src, j.dst, j.fi, mode, report); err != nil {
						mu.Lock()
						if firstErr == nil {
							firstErr = err
						}
						mu.Unlock()
					}
				}
			}()
		}
		for _, j := range jobs {
			mu.Lock()
			failed := firstErr != nil
			mu.Unlock()
			if failed {
				break
			}
			ch <- j
		}
		close(ch)
		wg.Wait()
		if firstErr != nil {
			return firstErr
		}
	}
	return forUnlistedTrees(srcAbs, func(extra, rel string) error {
		return copyTree(extra, filepath.Join(dst, filepath.FromSlash(rel)), mode, workers, report)
	})
}

func copyFile(src, dst string, fi os.FileInfo, mode string, report func(int64, string)) error {
	if isIncremental(mode) && sameFile(dst, fi) {
		if report != nil {
			report(fi.Size(), filepath.Base(src)+" (unverändert)")
		}
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	tmp := dst + ".partial"
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, fi.Mode().Perm())
	if err != nil {
		return err
	}
	n, copyErr := io.CopyBuffer(out, in, make([]byte, copyBufSize))
	closeErr := out.Close()
	if copyErr != nil {
		_ = os.Remove(tmp)
		return copyErr
	}
	if closeErr != nil {
		_ = os.Remove(tmp)
		return closeErr
	}
	_ = os.Chtimes(tmp, fi.ModTime(), fi.ModTime())
	if err := os.Rename(tmp, dst); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	if report != nil {
		report(n, filepath.Base(src))
	}
	if mode == "move" {
		return os.Remove(src)
	}
	return nil
}
