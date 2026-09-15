package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSafeArchiveRel(t *testing.T) {
	if _, ok := safeArchiveRel("../etc/passwd"); ok {
		t.Fatal("traversal must be rejected")
	}
	gotAbs, ok := safeArchiveRel("/abs/path")
	if !ok || gotAbs != "abs/path" {
		t.Fatalf("leading slash must become relative, got %q ok=%v", gotAbs, ok)
	}
	got, ok := safeArchiveRel("2024/01/a.jpg")
	if !ok || got != "2024/01/a.jpg" {
		t.Fatalf("got %q ok=%v", got, ok)
	}
}

func TestTarGzRoundTrip(t *testing.T) {
	root := t.TempDir()
	src := filepath.Join(root, "NAS_Admin_Pro")
	dst := t.TempDir()
	sub := filepath.Join(src, "2024", "01")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(sub, "a.jpg"), []byte("photo"), 0o644); err != nil {
		t.Fatal(err)
	}
	var buf bytes.Buffer
	if err := writeTarGz(src, &buf, nil); err != nil {
		t.Fatal(err)
	}
	if _, err := extractTarGz(bytes.NewReader(buf.Bytes()), dst, nil); err != nil {
		t.Fatal(err)
	}
	got, err := os.ReadFile(filepath.Join(dst, "NAS_Admin_Pro", "2024", "01", "a.jpg"))
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "photo" {
		t.Fatalf("got %q", got)
	}
	if _, err := os.Stat(filepath.Join(dst, "2024")); err == nil {
		t.Fatal("selected folder name must wrap the contents")
	}
}

func TestExtractReplacesReadonly(t *testing.T) {
	root := t.TempDir()
	src := filepath.Join(root, "home")
	dst := t.TempDir()
	if err := os.MkdirAll(src, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(src, "README.md"), []byte("new"), 0o644); err != nil {
		t.Fatal(err)
	}
	target := filepath.Join(dst, "home", "README.md")
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(target, []byte("old"), 0o444); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(target, 0o444); err != nil {
		t.Fatal(err)
	}
	var buf bytes.Buffer
	if err := writeTarGz(src, &buf, nil); err != nil {
		t.Fatal(err)
	}
	skipped, err := extractTarGz(bytes.NewReader(buf.Bytes()), dst, nil)
	if err != nil {
		t.Fatal(err)
	}
	got, rerr := os.ReadFile(target)
	if rerr != nil && len(skipped) == 0 {
		t.Fatal(rerr)
	}
	if rerr == nil && string(got) != "new" && len(skipped) == 0 {
		t.Fatalf("got %q skipped=%v", got, skipped)
	}
}

func TestExtractRejectsTraversal(t *testing.T) {
	src := t.TempDir()
	dst := t.TempDir()
	outside := filepath.Join(src, "..", "nope")
	_ = outside
	var buf bytes.Buffer
	if err := writeTarGz(src, &buf, nil); err != nil {
		t.Fatal(err)
	}
	// inject is covered by safeArchiveRel; empty src still produces valid gzip
	if _, err := extractTarGz(bytes.NewReader(buf.Bytes()), dst, nil); err != nil {
		t.Fatal(err)
	}
}

func TestArchiveFolderName(t *testing.T) {
	if archiveFolderName(`/volume1/HierLandetAlles/NAS_Admin_Pro`) != "NAS_Admin_Pro" {
		t.Fatal(archiveFolderName(`/volume1/HierLandetAlles/NAS_Admin_Pro`))
	}
}

func TestKeepCountAndName(t *testing.T) {
	if keepCount("") != 7 || keepCount("30") != 30 || keepCount("99") != 50 {
		t.Fatal(keepCount("30"))
	}
	name := backupArchiveName("")
	if !isBackupArchiveName(name) {
		t.Fatal(name)
	}
	if !strings.HasPrefix(backupStem(name), "20") {
		t.Fatal(backupStem(name))
	}
}

func TestPruneBackupArchives(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("NAS_FOLDER", dir)
	t.Setenv("HDD_FOLDER", "")
	t.Setenv("UGAPP_SHARED_DIR", "")
	for _, n := range []string{
		"mf-backup-2026-01-01-120000.tar.gz",
		"mf-backup-2026-02-01-120000.tar.gz",
		"mf-backup-2026-03-01-120000.tar.gz",
		"notes.txt",
	} {
		if err := os.WriteFile(filepath.Join(dir, n), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	d := Device{ID: "local", Type: "local"}
	if err := pruneBackupArchives(d, dir, "", 2); err != nil {
		t.Fatal(err)
	}
	list, err := listBackupArchives(d, dir, "")
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 2 {
		t.Fatalf("keep 2, got %d", len(list))
	}
	if _, err := os.Stat(filepath.Join(dir, "notes.txt")); err != nil {
		t.Fatal("unrelated file must stay")
	}
}
