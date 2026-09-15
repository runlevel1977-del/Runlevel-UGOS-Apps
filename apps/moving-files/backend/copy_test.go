package main

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestSameMeta(t *testing.T) {
	now := time.Date(2026, 9, 13, 12, 0, 0, 0, time.UTC)
	if !sameMeta(10, now, 10, now) {
		t.Fatal("identical files should match")
	}
	if !sameMeta(10, now.Add(-time.Second), 10, now) {
		t.Fatal("1s NAS timestamp drift should still skip")
	}
	if sameMeta(10, now.Add(-3*time.Second), 10, now) {
		t.Fatal("older dest must be copied again")
	}
	if sameMeta(11, now, 10, now) {
		t.Fatal("size mismatch must copy")
	}
}

func TestNestInto(t *testing.T) {
	dir := t.TempDir()
	if nestInto(dir, "proj", "incr", false) {
		t.Fatal("incremental should merge into the chosen dest folder")
	}
	if nestInto(dir, "proj", "sync", false) {
		t.Fatal("sync should merge into the chosen dest folder")
	}
	if !nestInto(dir, "proj", "copy", false) {
		t.Fatal("copy should create a subfolder")
	}
	if !nestInto(dir, "proj", "incr", true) {
		t.Fatal("multiple sources should nest")
	}
	if err := os.Mkdir(filepath.Join(dir, "proj"), 0o755); err != nil {
		t.Fatal(err)
	}
	if !nestInto(dir, "proj", "incr", false) {
		t.Fatal("existing nested backup folder should be reused")
	}
	if err := os.WriteFile(filepath.Join(dir, "readme.txt"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	if nestInto(dir, "proj", "incr", false) {
		t.Fatal("populated dest is the backup itself; merge, do not nest")
	}
}

func TestCopyTreeSkipsUnchanged(t *testing.T) {
	src := t.TempDir()
	dst := t.TempDir()
	srcFile := filepath.Join(src, "a.txt")
	dstFile := filepath.Join(dst, "a.txt")
	if err := os.WriteFile(srcFile, []byte("AAAA"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := copyTree(src, dst, "incr", 2, nil); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(srcFile, []byte("BBBB"), 0o644); err != nil {
		t.Fatal(err)
	}
	future := time.Now().Add(time.Hour)
	if err := os.Chtimes(dstFile, future, future); err != nil {
		t.Fatal(err)
	}
	if err := copyTree(src, dst, "incr", 2, nil); err != nil {
		t.Fatal(err)
	}
	got, err := os.ReadFile(dstFile)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "AAAA" {
		t.Fatalf("unchanged dest was overwritten: %q", got)
	}

	past := time.Now().Add(-time.Hour)
	if err := os.Chtimes(dstFile, past, past); err != nil {
		t.Fatal(err)
	}
	if err := copyTree(src, dst, "incr", 2, nil); err != nil {
		t.Fatal(err)
	}
	got, err = os.ReadFile(dstFile)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "BBBB" {
		t.Fatalf("changed source was not copied: %q", got)
	}
}

func TestWorkerCount(t *testing.T) {
	if workerCount(nil) != 8 {
		t.Fatal("missing switch should be full speed")
	}
	on, off := true, false
	if workerCount(&on) != 8 || workerCount(&off) != 1 {
		t.Fatal("speed switch mapping")
	}
}
