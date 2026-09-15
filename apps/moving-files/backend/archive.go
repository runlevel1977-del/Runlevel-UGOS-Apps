package main

import (
	"archive/tar"
	"compress/gzip"
	"errors"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const backupPrefix = "mf-backup-"
const backupSuffix = ".tar.gz"

func isBackupArchiveName(name string) bool {
	n := strings.ToLower(strings.TrimSpace(name))
	if !strings.HasPrefix(n, backupPrefix) {
		return false
	}
	return strings.HasSuffix(n, backupEncSuffix()) || strings.HasSuffix(n, backupSuffix)
}

func backupArchiveName(password string) string {
	name := backupPrefix + time.Now().Format("2006-01-02-150405") + backupSuffix
	if strings.TrimSpace(password) != "" {
		return name + ".enc"
	}
	return name
}

func backupStem(name string) string {
	n := strings.TrimSuffix(name, backupEncSuffix())
	n = strings.TrimSuffix(n, backupSuffix)
	n = strings.TrimPrefix(n, backupPrefix)
	if n == "" {
		n = "restore"
	}
	return n
}

func safeArchiveRel(name string) (string, bool) {
	name = strings.ReplaceAll(name, "\\", "/")
	name = strings.Trim(name, "/")
	if name == "" || name == "." {
		return "", false
	}
	for _, p := range strings.Split(name, "/") {
		if p == "" || p == "." || p == ".." {
			return "", false
		}
	}
	return name, true
}

func walkLocalFiles(root string, fn func(abs, relSlash string, fi os.FileInfo) error) error {
	rootAbs, err := filepath.Abs(root)
	if err != nil {
		return err
	}
	walk := func(base, relPrefix string) error {
		baseAbs, err := filepath.Abs(base)
		if err != nil {
			return err
		}
		return filepath.WalkDir(baseAbs, func(path string, d fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if d.IsDir() {
				if path != baseAbs && hiddenName(d.Name()) {
					return fs.SkipDir
				}
				return nil
			}
			if hiddenName(d.Name()) {
				return nil
			}
			fi, err := d.Info()
			if err != nil || !fi.Mode().IsRegular() {
				return nil
			}
			rel, err := filepath.Rel(baseAbs, path)
			if err != nil {
				return err
			}
			relSlash := filepath.ToSlash(rel)
			if relPrefix != "" {
				relSlash = strings.Trim(relPrefix+"/"+relSlash, "/")
			}
			return fn(path, relSlash, fi)
		})
	}
	if err := walk(rootAbs, ""); err != nil {
		return err
	}
	return forUnlistedTrees(rootAbs, func(extra, rel string) error {
		return walk(extra, rel)
	})
}

func archiveFolderName(srcDir string) string {
	abs, err := filepath.Abs(srcDir)
	if err != nil {
		abs = srcDir
	}
	name := filepath.Base(filepath.Clean(abs))
	if name == "" || name == "." || name == string(filepath.Separator) {
		return ""
	}
	return name
}

func writeTarGz(srcDir string, w io.Writer, report func(int64, string)) error {
	gw, err := gzip.NewWriterLevel(w, gzip.BestSpeed)
	if err != nil {
		return err
	}
	tw := tar.NewWriter(gw)
	wrap := archiveFolderName(srcDir)
	if wrap != "" {
		hdr := &tar.Header{
			Typeflag: tar.TypeDir,
			Name:     wrap + "/",
			Mode:     0o755,
			ModTime:  time.Now(),
			Format:   tar.FormatPAX,
		}
		if err := tw.WriteHeader(hdr); err != nil {
			_ = tw.Close()
			_ = gw.Close()
			return err
		}
	}
	err = walkLocalFiles(srcDir, func(abs, rel string, fi os.FileInfo) error {
		hdr, err := tar.FileInfoHeader(fi, "")
		if err != nil {
			return err
		}
		hdr.Name = rel
		if wrap != "" {
			hdr.Name = wrap + "/" + rel
		}
		hdr.Format = tar.FormatPAX
		if err := tw.WriteHeader(hdr); err != nil {
			return err
		}
		f, err := os.Open(abs)
		if err != nil {
			return err
		}
		n, copyErr := io.Copy(tw, f)
		_ = f.Close()
		if copyErr != nil {
			return copyErr
		}
		if report != nil {
			report(n, filepath.Base(abs))
		}
		return nil
	})
	closeErr := tw.Close()
	gzipErr := gw.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return gzipErr
}

func extractTarGz(r io.Reader, dest string, report func(int64, string)) (skipped []string, err error) {
	destAbs, err := filepath.Abs(dest)
	if err != nil {
		return nil, err
	}
	if err := assertWritableDir(destAbs); err != nil {
		return nil, err
	}
	gr, err := gzip.NewReader(r)
	if err != nil {
		return nil, err
	}
	defer gr.Close()
	tr := tar.NewReader(gr)
	pref := strings.TrimSuffix(destAbs, string(os.PathSeparator)) + string(os.PathSeparator)
	for {
		hdr, err := tr.Next()
		if errors.Is(err, io.EOF) {
			return skipped, nil
		}
		if err != nil {
			return skipped, err
		}
		rel, ok := safeArchiveRel(hdr.Name)
		if !ok {
			continue
		}
		target := filepath.Join(destAbs, filepath.FromSlash(rel))
		targetAbs, err := filepath.Abs(target)
		if err != nil {
			return skipped, err
		}
		if targetAbs != destAbs && !strings.HasPrefix(targetAbs, pref) {
			return skipped, locErr("badArchivePath")
		}
		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(targetAbs, 0o755); err != nil {
				skipped = append(skipped, rel+"/")
			}
		case tar.TypeReg, tar.TypeRegA:
			if err := os.MkdirAll(filepath.Dir(targetAbs), 0o755); err != nil {
				_, _ = io.Copy(io.Discard, tr)
				skipped = append(skipped, rel)
				continue
			}
			n, werr := writeExtractedFile(targetAbs, tr)
			if werr != nil {
				skipped = append(skipped, rel)
				if report != nil {
					report(0, filepath.Base(rel)+" (keine Schreibrechte)")
				}
				continue
			}
			if report != nil {
				report(n, filepath.Base(rel))
			}
		default:
			continue
		}
	}
}

func assertWritableDir(dir string) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return locErr("restoreDstHidden")
	}
	probe := filepath.Join(dir, ".mf-write-test")
	if err := os.WriteFile(probe, []byte("ok"), 0o644); err != nil {
		return locErr("dstNotWritable")
	}
	_ = os.Remove(probe)
	return nil
}

func writeExtractedFile(targetAbs string, r io.Reader) (int64, error) {
	out, err := os.OpenFile(targetAbs, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if err != nil {
		_ = os.Chmod(targetAbs, 0o644)
		_ = os.Remove(targetAbs)
		out, err = os.OpenFile(targetAbs, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
		if err != nil {
			_, _ = io.Copy(io.Discard, r)
			return 0, err
		}
	}
	n, copyErr := io.Copy(out, r)
	closeErr := out.Close()
	if copyErr != nil {
		return n, copyErr
	}
	return n, closeErr
}
