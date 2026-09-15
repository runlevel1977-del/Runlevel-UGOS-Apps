package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestUnescapeMount(t *testing.T) {
	got := unescapeMount(`/home/papa/Photos/MobileBackup/iPhone\04017\040Pro`)
	if got != "/home/papa/Photos/MobileBackup/iPhone 17 Pro" {
		t.Fatalf("got %q", got)
	}
}

func TestParseMountPointsSpace(t *testing.T) {
	data := "36 35 98:0 / /home/papa/Photos/MobileBackup/iPhone\\04017\\040Pro rw - ext4 /dev/sda1 rw\n"
	pts := parseMountPoints(data)
	if len(pts) != 1 || pts[0] != "/home/papa/Photos/MobileBackup/iPhone 17 Pro" {
		t.Fatalf("pts=%v", pts)
	}
}

func TestOverlayChildFromGrantedPath(t *testing.T) {
	root := t.TempDir()
	parent := filepath.Join(root, "MobileBackup")
	child := filepath.Join(parent, "iPhone 17 Pro")
	if err := os.MkdirAll(child, 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("NAS_FOLDER", child)
	t.Setenv("HDD_FOLDER", "")
	t.Setenv("UGAPP_SHARED_DIR", "")
	names := overlayChildNames(parent)
	found := false
	for _, n := range names {
		if n == "iPhone 17 Pro" {
			found = true
		}
	}
	if !found {
		t.Fatalf("missing iPhone child, names=%v", names)
	}
	entries, err := listLocalDirs(parent, "home", "papa/Photos/MobileBackup")
	if err != nil {
		t.Fatal(err)
	}
	count := 0
	for _, e := range entries {
		if e.Name == "iPhone 17 Pro" {
			count++
			if e.Path != "papa/Photos/MobileBackup/iPhone 17 Pro" {
				t.Fatalf("path=%s", e.Path)
			}
		}
	}
	if count != 1 {
		t.Fatalf("want 1 iPhone entry, got %d in %#v", count, entries)
	}
}

func TestCountIncludesUnlistedGrantedChild(t *testing.T) {
	root := t.TempDir()
	parent := filepath.Join(root, "Photos")
	hiddenParent := filepath.Join(parent, "MobileBackup")
	child := filepath.Join(hiddenParent, "iPhone 17 Pro")
	if err := os.MkdirAll(child, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(child, "a.jpg"), []byte("photo"), 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv("NAS_FOLDER", child)
	t.Setenv("HDD_FOLDER", "")
	t.Setenv("UGAPP_SHARED_DIR", "")
	if err := os.Chmod(hiddenParent, 0o111); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chmod(hiddenParent, 0o755) })
	items, err := os.ReadDir(hiddenParent)
	if err == nil && len(items) > 0 {
		t.Skip("parent still lists children on this OS")
	}
	n, err := countBytes(parent)
	if err != nil {
		n = 0
	}
	var extra int64
	unlisted := unlistedTreesUnder(parent)
	if len(unlisted) == 0 {
		t.Fatal("expected unlisted iPhone tree")
	}
	if err := forUnlistedTrees(parent, func(abs, _ string) error {
		n2, e := countBytes(abs)
		extra += n2
		return e
	}); err != nil {
		t.Fatal(err)
	}
	if n+extra != 5 {
		t.Fatalf("bytes parent=%d extra=%d want 5 unlisted=%v", n, extra, unlisted)
	}
}
