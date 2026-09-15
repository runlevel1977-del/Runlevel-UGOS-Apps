package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCacheKey(t *testing.T) {
	if cacheKey("Public", "filme/2024") != "Public/filme/2024" {
		t.Fatal(cacheKey("Public", "filme/2024"))
	}
	if cacheKey("Public", "") != "Public" {
		t.Fatal(cacheKey("Public", ""))
	}
}

func TestFolderCacheRoundTrip(t *testing.T) {
	dir := t.TempDir()
	a := &App{file: filepath.Join(dir, "state.json"), building: map[string]bool{}}
	entries := []browseEntry{
		{Name: "Public", Share: "Public", Kind: "share"},
		{Name: "backup", Share: "backup", Kind: "share"},
	}
	a.rememberBrowse("qnap", "", "", entries)
	res, ok := a.browseFromCache("qnap", "", "")
	if !ok || !res.Cached || len(res.Entries) != 2 {
		t.Fatalf("shares cache: ok=%v cached=%v n=%d", ok, res.Cached, len(res.Entries))
	}
	a.rememberBrowse("qnap", "Public", "", []browseEntry{
		{Name: "filme", Share: "Public", Path: "filme", Kind: "dir"},
	})
	res, ok = a.browseFromCache("qnap", "Public", "")
	if !ok || len(res.Entries) != 1 || res.Entries[0].Path != "filme" {
		t.Fatalf("dirs: %#v", res.Entries)
	}
	if _, ok := a.browseFromCache("qnap", "Public", "missing"); ok {
		t.Fatal("unknown path must not hit cache")
	}
}

func TestPruneFolderCaches(t *testing.T) {
	dir := t.TempDir()
	a := &App{file: filepath.Join(dir, "state.json"), building: map[string]bool{}}
	a.rememberBrowse("gone", "", "", []browseEntry{{Name: "x", Kind: "share"}})
	if _, err := os.Stat(a.cachePath("gone")); err != nil {
		t.Fatal(err)
	}
	a.pruneFolderCaches([]Device{{ID: "keep"}})
	if _, err := os.Stat(a.cachePath("gone")); !os.IsNotExist(err) {
		t.Fatal("stale cache should be removed")
	}
}
