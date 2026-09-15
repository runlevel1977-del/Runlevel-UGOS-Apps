package main

import (
	"errors"
	"strings"
)

type locError struct {
	Key string
	Arg string
}

func (e locError) Error() string {
	if e.Arg != "" {
		return e.Key + ": " + e.Arg
	}
	return e.Key
}

func locErr(key string, arg ...string) error {
	e := locError{Key: key}
	if len(arg) > 0 {
		e.Arg = arg[0]
	}
	return e
}

type locMsg struct {
	Key string
	Arg string
}

func (j *Job) msg(key string, arg ...string) {
	j.DetailKey = key
	j.DetailArg = ""
	if len(arg) > 0 {
		j.DetailArg = arg[0]
	}
	if key == "raw" || key == "file" {
		j.Detail = j.DetailArg
	} else {
		j.Detail = ""
	}
}

func (j *Job) fromErr(err error) {
	k, a := splitErr(err)
	j.msg(k, a)
}

func (j *Job) progressName(name string) {
	switch {
	case name == "rclone SMB…":
		j.msg("rcloneSmb")
	case name == "rclone Performance fehlgeschlagen — stabiler SMB-Modus…":
		j.msg("rcloneFallback")
	case strings.HasPrefix(name, "rclone versteckter Ordner: "):
		j.msg("rcloneHidden", strings.TrimPrefix(name, "rclone versteckter Ordner: "))
	case strings.HasSuffix(name, " (unverändert)"):
		j.msg("unchanged", strings.TrimSuffix(name, " (unverändert)"))
	case strings.HasSuffix(name, " (keine Schreibrechte)"):
		j.msg("noWrite", strings.TrimSuffix(name, " (keine Schreibrechte)"))
	default:
		if strings.Contains(name, "Transferred:") || strings.Contains(name, "/s") {
			j.msg("raw", name)
		} else {
			j.msg("file", name)
		}
	}
}

func splitErr(err error) (key, arg string) {
	if err == nil {
		return "raw", ""
	}
	var le locError
	if errors.As(err, &le) {
		return le.Key, le.Arg
	}
	s := err.Error()
	switch {
	case strings.Contains(s, "Passwort falsch"):
		return "badPass", ""
	case strings.Contains(s, "passwortgeschützt"):
		return "needArchivePass", ""
	case s == "rclone fehlt":
		return "rcloneMissing", ""
	case strings.Contains(s, "keine LAN-Karte"):
		return "wolNoNic", ""
	case strings.Contains(s, "Wake-Paket konnte nicht"):
		return "wolSend", ""
	case strings.Contains(s, "ungültige MAC"):
		return "badMac", ""
	case strings.Contains(s, "Archiv unvollständig"):
		return "archiveIncomplete", ""
	case strings.Contains(s, "keine IP/Hostname"):
		return "noHost", ""
	case strings.Contains(s, "keine Freigabe"):
		return "noShare", ""
	case strings.Contains(s, "Dateiname fehlt"):
		return "archiveName", ""
	default:
		return "raw", s
	}
}

func apiErr(err error) map[string]string {
	k, a := splitErr(err)
	return apiKey(k, a)
}

func apiKey(key string, arg ...string) map[string]string {
	m := map[string]string{"errorKey": key}
	if len(arg) > 0 && arg[0] != "" {
		m["errorArg"] = arg[0]
		if key == "raw" {
			m["error"] = arg[0]
		}
	}
	return m
}

func browseFail(key string, arg ...string) browseResult {
	r := browseResult{OK: false, ErrorKey: key}
	if len(arg) > 0 && arg[0] != "" {
		r.ErrorArg = arg[0]
		if key == "raw" {
			r.Error = arg[0]
		}
	}
	return r
}
