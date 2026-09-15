package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const privacyConsentVersion = 1

type privacyConsent struct {
	Accepted bool   `json:"accepted"`
	Decided  bool   `json:"decided"`
	At       string `json:"at"`
	Version  int    `json:"version"`
}

func (a *App) consentPath() string {
	return filepath.Join(filepath.Dir(a.file), "privacy_consent.json")
}

func (a *App) loadConsent() privacyConsent {
	b, err := os.ReadFile(a.consentPath())
	if err != nil {
		return privacyConsent{}
	}
	var row privacyConsent
	if json.Unmarshal(b, &row) != nil {
		return privacyConsent{}
	}
	return row
}

func (a *App) saveConsent(accepted bool) (privacyConsent, error) {
	row := privacyConsent{
		Accepted: accepted,
		Decided:  true,
		At:       time.Now().UTC().Format(time.RFC3339),
		Version:  privacyConsentVersion,
	}
	if err := os.MkdirAll(filepath.Dir(a.consentPath()), 0o700); err != nil {
		return row, err
	}
	b, err := json.MarshalIndent(row, "", "  ")
	if err != nil {
		return row, err
	}
	return row, os.WriteFile(a.consentPath(), b, 0o600)
}

func (a *App) consentAllowsSecrets() bool {
	row := a.loadConsent()
	return row.Decided && row.Accepted
}

func (a *App) stripSecretsLocked() {
	for i := range a.data.Devices {
		a.data.Devices[i].Password = ""
	}
	if a.data.Backup != nil {
		a.data.Backup.Password = ""
		a.data.Backup.PasswordClear = false
		a.data.Backup.HasPassword = false
	}
}

func publicState(s State) State {
	devs := make([]Device, len(s.Devices))
	copy(devs, s.Devices)
	for i := range devs {
		if strings.TrimSpace(devs[i].Password) != "" {
			devs[i].HasPassword = true
		} else {
			devs[i].HasPassword = false
		}
		devs[i].Password = ""
	}
	s.Devices = devs
	if s.Backup != nil {
		b := *s.Backup
		b.HasPassword = strings.TrimSpace(b.Password) != ""
		b.Password = ""
		b.PasswordClear = false
		s.Backup = &b
	}
	return s
}
