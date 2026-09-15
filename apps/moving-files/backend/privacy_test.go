package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPublicStateRedactsPasswords(t *testing.T) {
	s := State{
		Devices: []Device{{ID: "dev-1", Password: "secret-smb", Name: "PC"}},
		Backup:  &Backup{Password: "archive-pw", SrcPath: "/a"},
	}
	out := publicState(s)
	if out.Devices[0].Password != "" {
		t.Fatalf("device password leaked: %q", out.Devices[0].Password)
	}
	if !out.Devices[0].HasPassword {
		t.Fatal("want hasPassword on device")
	}
	if out.Backup.Password != "" {
		t.Fatalf("backup password leaked: %q", out.Backup.Password)
	}
	if !out.Backup.HasPassword {
		t.Fatal("want hasPassword on backup")
	}
	if s.Devices[0].Password != "secret-smb" {
		t.Fatal("publicState must not mutate stored secrets")
	}
	if s.Backup.Password != "archive-pw" {
		t.Fatal("publicState must not mutate stored backup password")
	}
}

func TestConsentRoundTrip(t *testing.T) {
	dir := t.TempDir()
	a := &App{file: filepath.Join(dir, "state.json")}
	if a.consentAllowsSecrets() {
		t.Fatal("no file: secrets not allowed")
	}
	if _, err := a.saveConsent(true); err != nil {
		t.Fatal(err)
	}
	if !a.consentAllowsSecrets() {
		t.Fatal("accepted should allow secrets")
	}
	if _, err := a.saveConsent(false); err != nil {
		t.Fatal(err)
	}
	if a.consentAllowsSecrets() {
		t.Fatal("declined should block secrets")
	}
	b, err := os.ReadFile(a.consentPath())
	if err != nil || len(b) == 0 {
		t.Fatalf("consent file: %v", err)
	}
}
