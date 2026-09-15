package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

type Device struct {
	ID          string `json:"id"`
	Type        string `json:"type"`
	Name        string `json:"name"`
	Host        string `json:"host"`
	Share       string `json:"share"`
	User        string `json:"user"`
	Password    string `json:"password"`
	HasPassword bool   `json:"hasPassword,omitempty"`
	MAC         string `json:"mac"`
}

type Transfer struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	SrcDevice   string   `json:"srcDevice"`
	SrcPath     string   `json:"srcPath"`
	SrcShare    string   `json:"srcShare"`
	SrcPaths    []string `json:"srcPaths"`
	DstDevice   string   `json:"dstDevice"`
	DstPath     string   `json:"dstPath"`
	DstShare    string   `json:"dstShare"`
	Mode        string   `json:"mode"`
	Fast        *bool    `json:"fast"`
	Auto        string   `json:"auto"`
	AutoTime    string   `json:"autoTime"`
	AutoWeekday string   `json:"autoWeekday"`
	Enabled     *bool    `json:"enabled"`
	LastRun     string   `json:"lastRun"`
}

type WakePlan struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	DeviceID    string   `json:"deviceId"`
	Direction   string   `json:"direction"`
	Wait        string   `json:"wait"`
	SrcPath     string   `json:"srcPath"`
	SrcShare    string   `json:"srcShare"`
	DstPath     string   `json:"dstPath"`
	DstShare    string   `json:"dstShare"`
	SrcPaths    []string `json:"srcPaths"`
	Auto        string   `json:"auto"`
	AutoTime    string   `json:"autoTime"`
	AutoWeekday string   `json:"autoWeekday"`
	LastRun     string   `json:"lastRun"`
	Enabled     bool     `json:"enabled"`
}

type Backup struct {
	SrcDevice     string `json:"srcDevice"`
	SrcPath       string `json:"srcPath"`
	SrcShare      string `json:"srcShare"`
	DstDevice     string `json:"dstDevice"`
	DstPath       string `json:"dstPath"`
	DstShare      string `json:"dstShare"`
	Keep          string `json:"keep"`
	Mode          string `json:"mode"`
	Fast          *bool  `json:"fast"`
	Auto          string `json:"auto"`
	AutoTime      string `json:"autoTime"`
	AutoWeekday   string `json:"autoWeekday"`
	Wait          string `json:"wait"`
	Enabled       *bool  `json:"enabled"`
	LastRun       string `json:"lastRun"`
	Password      string `json:"password"`
	HasPassword   bool   `json:"hasPassword,omitempty"`
	PasswordClear bool   `json:"passwordClear,omitempty"`
}

type State struct {
	Devices      []Device    `json:"devices"`
	Transfers    []Transfer  `json:"transfers"`
	WakePlans    []WakePlan  `json:"wakePlans"`
	Backup       *Backup     `json:"backup"`
	Logs         []string    `json:"logs"`
	ExtraFolders []folderRef `json:"extraFolders"`
}

type App struct {
	mu       sync.Mutex
	jobsMu   sync.Mutex
	cacheMu  sync.Mutex
	file     string
	data     State
	jobs     map[string]*Job
	building map[string]bool
}

func defaultState() State {
	return State{
		Devices: []Device{{
			ID:   "local",
			Type: "local",
			Name: "Dieses NAS",
		}},
		Transfers: []Transfer{},
		WakePlans: []WakePlan{},
		Logs:      []string{},
	}
}

func (a *App) load() {
	a.data = defaultState()
	b, err := os.ReadFile(a.file)
	if err != nil {
		return
	}
	_ = json.Unmarshal(b, &a.data)
	if a.data.Devices == nil {
		a.data.Devices = defaultState().Devices
	}
	if a.data.ExtraFolders == nil {
		a.data.ExtraFolders = []folderRef{}
	}
	normalizeWakePlans(a.data.WakePlans)
}

func (a *App) saveLocked() error {
	if err := os.MkdirAll(filepath.Dir(a.file), 0o700); err != nil {
		return err
	}
	b, err := json.MarshalIndent(a.data, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(a.file, b, 0o600)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func main() {
	fs := flag.NewFlagSet("movingfiles_serv", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	port := fs.Int("port", 21010, "listen port")
	_ = fs.Parse(os.Args[1:])

	fmt.Fprintf(os.Stderr, "movingfiles_serv start args=%v port=%d\n", os.Args, *port)

	dataDir := os.Getenv("DATA_DIR")
	if dataDir == "" {
		if cwd, err := os.Getwd(); err == nil {
			dataDir = filepath.Join(cwd, "data")
		} else {
			dataDir = "/tmp/com.runlevel.movingfiles"
		}
	}
	_ = os.MkdirAll(dataDir, 0o700)
	app := &App{file: filepath.Join(dataDir, "state.json"), jobs: map[string]*Job{}, building: map[string]bool{}}
	app.load()
	go app.scheduleLoop()

	mux := http.NewServeMux()
	heartbeat := func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{
			"status":    "healthy",
			"timestamp": time.Now().Format(time.DateTime),
		})
	}
	mux.HandleFunc("/heartbeat", heartbeat)
	mux.HandleFunc("/api/heartbeat", heartbeat)
	mux.HandleFunc("/api/state", func(w http.ResponseWriter, r *http.Request) {
		app.mu.Lock()
		defer app.mu.Unlock()
		switch r.Method {
		case http.MethodGet:
			type view struct {
				State
				FolderCaches map[string]folderCacheInfo `json:"folderCaches"`
			}
			writeJSON(w, http.StatusOK, view{State: publicState(app.data), FolderCaches: app.folderCacheSummariesFor(app.data.Devices)})
		case http.MethodPut:
			body, err := io.ReadAll(io.LimitReader(r.Body, 2<<20))
			if err != nil {
				http.Error(w, "read", http.StatusBadRequest)
				return
			}
			var next State
			if err := json.Unmarshal(body, &next); err != nil {
				http.Error(w, "json", http.StatusBadRequest)
				return
			}
			if next.Devices == nil {
				next.Devices = defaultState().Devices
			}
			app.mergeLastRun(&next)
			if !app.consentAllowsSecrets() {
				for i := range next.Devices {
					next.Devices[i].Password = ""
					next.Devices[i].HasPassword = false
				}
				if next.Backup != nil {
					next.Backup.Password = ""
					next.Backup.PasswordClear = false
					next.Backup.HasPassword = false
				}
			}
			if next.ExtraFolders == nil {
				next.ExtraFolders = []folderRef{}
			}
			app.data = next
			app.pruneFolderCaches(next.Devices)
			if err := app.saveLocked(); err != nil {
				http.Error(w, "save", http.StatusInternalServerError)
				return
			}
			writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
		default:
			http.Error(w, "method", http.StatusMethodNotAllowed)
		}
	})
	mux.HandleFunc("/api/wol", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			DeviceID string `json:"deviceId"`
			MAC      string `json:"mac"`
			Host     string `json:"host"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "json", http.StatusBadRequest)
			return
		}
		name := ""
		if strings.TrimSpace(req.DeviceID) != "" {
			app.mu.Lock()
			d, ok := findDevice(app.data.Devices, req.DeviceID)
			app.mu.Unlock()
			if !ok {
				writeJSON(w, http.StatusBadRequest, apiKey("deviceMissing"))
				return
			}
			name = d.Name
			if strings.TrimSpace(d.MAC) != "" {
				req.MAC = d.MAC
			}
			if strings.TrimSpace(d.Host) != "" {
				req.Host = d.Host
			}
		}
		label := strings.TrimSpace(name)
		if label == "" {
			label = strings.TrimSpace(req.Host)
		}
		if label == "" {
			label = "device"
		}
		if hostReachable(req.Host) {
			writeJSON(w, http.StatusOK, map[string]string{
				"ok":         "true",
				"awake":      "true",
				"messageKey": "alreadyAwake",
				"messageArg": label,
			})
			return
		}
		if strings.TrimSpace(req.MAC) == "" {
			writeJSON(w, http.StatusBadRequest, apiKey("noMac", label))
			return
		}
		_, err := sendMagicPacket(req.MAC, req.Host)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, apiErr(err))
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"ok": "true", "messageKey": "wolSent"})
	})
	mux.HandleFunc("/api/jobs", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method", http.StatusMethodNotAllowed)
			return
		}
		writeJSON(w, http.StatusOK, app.jobsSnapshot())
	})
	mux.HandleFunc("/api/jobs/run", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			ID string `json:"id"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.ID == "" {
			http.Error(w, "json", http.StatusBadRequest)
			return
		}
		if err := app.startJob(req.ID, "manual"); err != nil {
			writeJSON(w, http.StatusBadRequest, apiErr(err))
			return
		}
		writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
	})
	mux.HandleFunc("/api/backups", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method", http.StatusMethodNotAllowed)
			return
		}
		list, err := app.listBackupArchives()
		if err != nil {
			writeJSON(w, http.StatusBadRequest, apiErr(err))
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "archives": list})
	})
	mux.HandleFunc("/api/backup/restore", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			Names     []string `json:"names"`
			DestShare string   `json:"destShare"`
			DestPath  string   `json:"destPath"`
			Password  string   `json:"password"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "json", http.StatusBadRequest)
			return
		}
		if err := app.startRestore(req.Names, req.DestShare, req.DestPath, req.Password); err != nil {
			writeJSON(w, http.StatusBadRequest, apiErr(err))
			return
		}
		writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
	})
	mux.HandleFunc("/api/browse", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "method", http.StatusMethodNotAllowed)
			return
		}
		q := r.URL.Query()
		writeJSON(w, http.StatusOK, app.browse(q.Get("device_id"), q.Get("share"), q.Get("path")))
	})
	mux.HandleFunc("/api/folder-cache", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			writeJSON(w, http.StatusOK, app.folderCacheSummaries())
		case http.MethodPost:
			var req struct {
				ID string `json:"id"`
			}
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.ID == "" {
				http.Error(w, "json", http.StatusBadRequest)
				return
			}
			if err := app.startFolderCacheBuild(req.ID); err != nil {
				writeJSON(w, http.StatusBadRequest, apiKey("notSmb"))
				return
			}
			writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
		default:
			http.Error(w, "method", http.StatusMethodNotAllowed)
		}
	})

	mux.HandleFunc("/api/privacy", func(w http.ResponseWriter, r *http.Request) {
		const privacyURL = "https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/privacy/movingfiles.md"
		const helpURL = "https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/blob/main/docs/help/movingfiles.md"
		const issuesURL = "https://github.com/runlevel1977-del/Runlevel-UGOS-Apps/issues"
		switch r.Method {
		case http.MethodGet:
			row := app.loadConsent()
			writeJSON(w, http.StatusOK, map[string]any{
				"decided":    row.Decided,
				"accepted":   row.Accepted,
				"privacyUrl": privacyURL,
				"helpUrl":    helpURL,
				"issuesUrl":  issuesURL,
			})
		case http.MethodPost:
			var req struct {
				Accepted bool `json:"accepted"`
			}
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
				http.Error(w, "json", http.StatusBadRequest)
				return
			}
			app.mu.Lock()
			row, err := app.saveConsent(req.Accepted)
			if err == nil && !req.Accepted {
				app.stripSecretsLocked()
				err = app.saveLocked()
			}
			app.mu.Unlock()
			if err != nil {
				http.Error(w, "save", http.StatusInternalServerError)
				return
			}
			writeJSON(w, http.StatusOK, map[string]any{"ok": true, "decided": row.Decided, "accepted": row.Accepted})
		default:
			http.Error(w, "method", http.StatusMethodNotAllowed)
		}
	})

	www := os.Getenv("WWW_DIR")
	if www == "" && os.Getenv("UGAPP_INSTALL_DIR") != "" {
		www = filepath.Join(os.Getenv("UGAPP_INSTALL_DIR"), "www")
	}
	if www != "" {
		if st, err := os.Stat(www); err == nil && st.IsDir() {
			mux.Handle("/", http.FileServer(http.Dir(www)))
		}
	}

	addr := fmt.Sprintf("0.0.0.0:%d", *port)
	ln, err := net.Listen("tcp4", addr)
	if err != nil {
		fmt.Fprintln(os.Stderr, "listen", err)
		os.Exit(1)
	}
	fmt.Fprintf(os.Stderr, "Runlevel native listening on %s\n", addr)
	if err := http.Serve(ln, mux); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
