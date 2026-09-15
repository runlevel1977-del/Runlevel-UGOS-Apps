package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestBrowseLocalRoots(t *testing.T) {
	dir := t.TempDir()
	if err := os.Mkdir(filepath.Join(dir, "HierLandetAlles"), 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("UGAPP_SHARED_DIR", dir)
	t.Setenv("NAS_FOLDER", "")
	t.Setenv("HDD_FOLDER", "")
	res := browseLocal("", "", nil)
	if !res.OK {
		t.Fatal(res.Error)
	}
	if len(res.Entries) == 0 {
		t.Fatal("expected authorized folder")
	}
	found := false
	for _, e := range res.Entries {
		if e.Name == "HierLandetAlles" && e.Kind == "share" {
			found = true
		}
	}
	if !found {
		t.Fatalf("entries=%v", res.Entries)
	}
}

func TestBrowseConfiguredEnvFolder(t *testing.T) {
	dir := t.TempDir()
	folder := filepath.Join(dir, "HierLandetAlles")
	if err := os.Mkdir(folder, 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("UGAPP_SHARED_DIR", "")
	t.Setenv("NAS_FOLDER", folder)
	t.Setenv("HDD_FOLDER", "")
	res := browseLocal("", "", nil)
	if !res.OK {
		t.Fatal(res.Error)
	}
	found := false
	for _, e := range res.Entries {
		if e.Name == "HierLandetAlles" {
			found = true
		}
	}
	if !found {
		t.Fatalf("entries=%v", res.Entries)
	}
}

func TestBrowseHDDFolderAndExtra(t *testing.T) {
	dir := t.TempDir()
	vol1 := filepath.Join(dir, "HierLandetAlles")
	hdd := filepath.Join(dir, "Papa Sicherung")
	if err := os.Mkdir(vol1, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(hdd, 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("UGAPP_SHARED_DIR", "")
	t.Setenv("NAS_FOLDER", vol1)
	t.Setenv("HDD_FOLDER", hdd)
	res := browseLocal("", "", nil)
	if !res.OK {
		t.Fatal(res.Error)
	}
	names := map[string]bool{}
	for _, e := range res.Entries {
		names[e.Name] = true
	}
	if !names["HierLandetAlles"] || !names["Papa Sicherung"] {
		t.Fatalf("expected both folders, got %v", res.Entries)
	}
	extraDir := filepath.Join(dir, "extra")
	if err := os.Mkdir(extraDir, 0o755); err != nil {
		t.Fatal(err)
	}
	res = browseLocal("", "", []folderRef{{Share: extraDir, Path: ""}})
	foundExtra := false
	for _, e := range res.Entries {
		if e.Share == extraDir || e.Name == "extra" {
			foundExtra = true
		}
	}
	if !foundExtra {
		t.Fatalf("extra folder missing: %v", res.Entries)
	}
}

func TestShareKeyAndDisplayName(t *testing.T) {
	if shareKey("/volume2/Papa Sicherung") != "/volume2/Papa Sicherung" {
		t.Fatal(shareKey("/volume2/Papa Sicherung"))
	}
	if displayName("/volume2/Papa Sicherung") != "Papa Sicherung (Volume 2)" {
		t.Fatal(displayName("/volume2/Papa Sicherung"))
	}
	if displayName("/volume2") != "Volume 2" {
		t.Fatal(displayName("/volume2"))
	}
	if !isVolumeRoot("/volume1") || !isVolumeRoot("/volume2") || isVolumeRoot("/volume2/Papa") {
		t.Fatal("volume root detection")
	}
}

func TestFlattenVolumeWrappers(t *testing.T) {
	root := t.TempDir()
	v1 := filepath.Join(root, "volume1")
	v2 := filepath.Join(root, "volume2")
	if err := os.MkdirAll(filepath.Join(v1, "HierLandetAlles"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(v2, "Papa Sicherung"), 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("UGAPP_SHARED_DIR", root)
	t.Setenv("NAS_FOLDER", "")
	t.Setenv("HDD_FOLDER", "")
	res := browseLocal("", "", nil)
	if !res.OK {
		t.Fatal(res.Error)
	}
	names := []string{}
	for _, e := range res.Entries {
		names = append(names, e.Name)
		if e.Name == "volume1" || e.Name == "volume2" || e.Share == "volume1" || e.Share == "volume2" {
			t.Fatalf("volume wrapper leaked: %+v", e)
		}
	}
	found1, found2 := false, false
	for _, e := range res.Entries {
		if strings.Contains(e.Name, "HierLandetAlles") {
			found1 = true
		}
		if strings.Contains(e.Name, "Papa Sicherung") {
			found2 = true
		}
	}
	if !found1 || !found2 {
		t.Fatalf("expected real folders, got %v", names)
	}
}

func TestVolumeWrapperUsesConfiguredName(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "volume1"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(filepath.Join(root, "volume2"), 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("UGAPP_SHARED_DIR", root)
	t.Setenv("NAS_FOLDER", "/volume1/APP PROJEKTE")
	t.Setenv("HDD_FOLDER", "/volume2/Papa Sicherung")
	res := browseLocal("", "", nil)
	if !res.OK {
		t.Fatal(res.Error)
	}
	for _, e := range res.Entries {
		if e.Name == "volume1" || e.Name == "volume2" {
			t.Fatalf("raw volume name shown: %+v", e)
		}
	}
	labels := map[string]string{}
	for _, e := range res.Entries {
		labels[e.Share] = e.Name
	}
	if !strings.Contains(labels["volume1"], "APP PROJEKTE") {
		t.Fatalf("volume1 label=%v entries=%v", labels["volume1"], res.Entries)
	}
	if !strings.Contains(labels["volume2"], "Papa Sicherung") {
		t.Fatalf("volume2 label=%v entries=%v", labels["volume2"], res.Entries)
	}
}

func TestResolveVolumeShare(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("NAS_FOLDER", dir)
	t.Setenv("HDD_FOLDER", "")
	t.Setenv("UGAPP_SHARED_DIR", "")
	got, err := resolveLocalPath(dir, "")
	if err != nil {
		t.Fatal(err)
	}
	if got != dir && filepath.Clean(got) != filepath.Clean(dir) {
		t.Fatalf("got %s want %s", got, dir)
	}
}
