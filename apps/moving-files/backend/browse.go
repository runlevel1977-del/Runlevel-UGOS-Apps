package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type browseEntry struct {
	Name  string `json:"name"`
	Share string `json:"share"`
	Path  string `json:"path"`
	Kind  string `json:"kind"`
	Label string `json:"label"`
}

type browseResult struct {
	OK       bool          `json:"ok"`
	Error    string        `json:"error,omitempty"`
	Hint     string        `json:"hint,omitempty"`
	HintKey  string        `json:"hintKey,omitempty"`
	ErrorKey string        `json:"errorKey,omitempty"`
	ErrorArg string        `json:"errorArg,omitempty"`
	Share    string        `json:"share"`
	Path     string        `json:"path"`
	Parent   string        `json:"parent"`
	Entries  []browseEntry `json:"entries"`
	Cached   bool          `json:"cached,omitempty"`
}

func configuredFolderPaths() []string {
	out := []string{}
	seen := map[string]bool{}
	add := func(p string) {
		p = strings.TrimSpace(strings.Trim(p, `"'`))
		if p == "" || seen[p] {
			return
		}
		seen[p] = true
		out = append(out, p)
	}
	for _, key := range []string{"NAS_FOLDER", "NAS_FOLDERS", "HDD_FOLDER", "VOLUME2", "VOLUME2_FOLDER", "ACCESS_PATH"} {
		for _, part := range splitEnvPaths(os.Getenv(key)) {
			add(part)
		}
	}
	for _, kv := range os.Environ() {
		i := strings.IndexByte(kv, '=')
		if i <= 0 {
			continue
		}
		k, v := kv[:i], kv[i+1:]
		if strings.HasPrefix(k, "NAS_FOLDER") || strings.HasPrefix(k, "HDD_FOLDER") || strings.HasPrefix(k, "UGAPP_ACCESS") {
			for _, part := range splitEnvPaths(v) {
				add(part)
			}
		}
	}
	return out
}

func splitEnvPaths(v string) []string {
	v = strings.TrimSpace(v)
	if v == "" {
		return nil
	}
	if strings.HasPrefix(v, "[") {
		var arr []string
		if json.Unmarshal([]byte(v), &arr) == nil {
			return arr
		}
	}
	v = strings.ReplaceAll(v, "\n", ",")
	v = strings.ReplaceAll(v, ";", ",")
	parts := strings.Split(v, ",")
	out := []string{}
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}

func sharedDir() string {
	if v := strings.TrimSpace(os.Getenv("UGAPP_SHARED_DIR")); v != "" {
		return v
	}
	if v := strings.TrimSpace(os.Getenv("UGAPP_INSTALL_DIR")); v != "" {
		return filepath.Join(v, "shared")
	}
	return ""
}

func hiddenName(name string) bool {
	n := strings.ToLower(strings.TrimSpace(name))
	if n == "" || n == "." || n == ".." {
		return true
	}
	if strings.HasPrefix(n, ".") || strings.HasPrefix(n, "@") {
		return true
	}
	if n == "#recycle" || n == "recycle" || n == "$recycle.bin" {
		return true
	}
	return false
}

func parentRel(path string) string {
	p := strings.Trim(strings.ReplaceAll(path, "\\", "/"), "/")
	if p == "" {
		return ""
	}
	i := strings.LastIndex(p, "/")
	if i < 0 {
		return ""
	}
	return p[:i]
}

func joinRel(parts ...string) string {
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		p = strings.Trim(strings.ReplaceAll(p, "\\", "/"), "/")
		if p != "" {
			out = append(out, p)
		}
	}
	return strings.Join(out, "/")
}

func cleanRel(p string) (string, bool) {
	p = strings.Trim(strings.ReplaceAll(p, "\\", "/"), "/")
	if p == "" {
		return "", true
	}
	for _, part := range strings.Split(p, "/") {
		if part == "" || part == "." || part == ".." {
			return "", false
		}
	}
	return p, true
}

func (a *App) lookupDevice(id string) (Device, bool) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if id == "" || id == "local" {
		return Device{ID: "local", Type: "local", Name: "Dieses NAS"}, true
	}
	for _, d := range a.data.Devices {
		if d.ID == id {
			return d, true
		}
	}
	return Device{}, false
}

func (a *App) browse(deviceID, share, path string) browseResult {
	dev, ok := a.lookupDevice(deviceID)
	if !ok {
		return browseFail("deviceMissing")
	}
	share = strings.TrimSpace(share)
	rel, good := cleanRel(path)
	if !good {
		return browseFail("badPath")
	}
	if isLocalDevice(dev) {
		return browseLocal(share, rel, a.extraRefs())
	}
	live := browseSMB(dev, share, rel)
	if live.OK {
		a.rememberBrowse(dev.ID, share, rel, live.Entries)
		return live
	}
	if cached, ok := a.browseFromCache(dev.ID, share, rel); ok {
		return cached
	}
	if !hostReachable(dev.Host) {
		if a.loadFolderCache(dev.ID) != nil {
			return browseFail("notInCache")
		}
		return browseFail("noCache")
	}
	return live
}

func (a *App) extraRefs() []folderRef {
	a.mu.Lock()
	defer a.mu.Unlock()
	return append([]folderRef(nil), a.data.ExtraFolders...)
}

func volumeRoots() []string {
	out := []string{}
	for i := 1; i <= 8; i++ {
		p := "/volume" + strconv.Itoa(i)
		if st, err := os.Stat(p); err == nil && st.IsDir() {
			out = append(out, p)
		}
	}
	return out
}

func shareKey(abs string) string {
	p := filepath.ToSlash(filepath.Clean(abs))
	if root := sharedDir(); root != "" {
		r := strings.TrimSuffix(filepath.ToSlash(filepath.Clean(root)), "/")
		if p == r {
			return filepath.Base(abs)
		}
		if strings.HasPrefix(p, r+"/") {
			return strings.TrimPrefix(p, r+"/")
		}
	}
	if strings.HasPrefix(p, "/volume") {
		return p
	}
	return filepath.Base(abs)
}

func displayName(abs string) string {
	p := filepath.ToSlash(abs)
	base := filepath.Base(abs)
	if isVolumeWrapperName(base) {
		return prettyVolumeName(base)
	}
	for i := 1; i <= 8; i++ {
		n := strconv.Itoa(i)
		token := "/volume" + n
		if p == token || strings.Contains(p, token+"/") || strings.HasSuffix(p, token) {
			return base + " (Volume " + n + ")"
		}
	}
	return base
}

func prettyVolumeName(name string) string {
	n := strings.ToLower(strings.TrimSpace(name))
	return "Volume " + strings.TrimPrefix(n, "volume")
}

func isVolumeWrapperName(name string) bool {
	n := strings.ToLower(strings.TrimSpace(name))
	if !strings.HasPrefix(n, "volume") {
		return false
	}
	rest := n[len("volume"):]
	if rest == "" {
		return false
	}
	for _, c := range rest {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

func configuredLabelForVolume(wrapper string) string {
	vol := strings.ToLower(strings.TrimSpace(wrapper))
	if !isVolumeWrapperName(vol) {
		return ""
	}
	for _, p := range configuredFolderPaths() {
		s := filepath.ToSlash(p)
		if strings.Contains(s, "/"+vol+"/") || strings.HasSuffix(s, "/"+vol) {
			return displayName(p)
		}
	}
	n := strings.TrimPrefix(vol, "volume")
	if n == "1" {
		parts := splitEnvPaths(os.Getenv("NAS_FOLDER"))
		if len(parts) > 0 {
			return displayName(parts[0])
		}
	}
	if n == "2" {
		parts := splitEnvPaths(os.Getenv("HDD_FOLDER"))
		if len(parts) > 0 {
			return displayName(parts[0])
		}
		parts = splitEnvPaths(os.Getenv("NAS_FOLDER"))
		if len(parts) > 1 {
			return displayName(parts[1])
		}
	}
	return ""
}

func browseLocal(share, rel string, extra []folderRef) browseResult {
	root := sharedDir()
	if share == "" {
		entries := listAuthorizedRoots(root, extra)
		hintKey := ""
		if len(entries) == 0 {
			hintKey = "noLocal"
		}
		return browseResult{OK: true, HintKey: hintKey, Entries: entries}
	}
	abs, err := resolveLocalPath(share, rel)
	if err != nil {
		if os.IsNotExist(err) {
			return browseFail("srcNotFound", share)
		}
		return browseFail("badPath")
	}
	entries, err := listLocalDirs(abs, share, rel)
	if err != nil {
		return browseFail("folderUnreadable", err.Error())
	}
	return browseResult{
		OK:      true,
		Share:   share,
		Path:    rel,
		Parent:  parentRel(rel),
		Entries: entries,
	}
}

func isVolumeRoot(abs string) bool {
	p := filepath.ToSlash(filepath.Clean(abs))
	for i := 1; i <= 8; i++ {
		if p == "/volume"+strconv.Itoa(i) {
			return true
		}
	}
	return false
}

func readableDir(p string) bool {
	if p == "" {
		return false
	}
	st, err := os.Stat(p)
	return err == nil && st.IsDir()
}

func listAuthorizedRoots(root string, extra []folderRef) []browseEntry {
	out := []browseEntry{}
	seen := map[string]bool{}
	addAbs := func(abs string, kind string) {
		abs = filepath.Clean(abs)
		if abs == "" || abs == "." || isVolumeRoot(abs) {
			return
		}
		if !readableDir(abs) {
			return
		}
		if real, err := filepath.EvalSymlinks(abs); err == nil && real != "" {
			abs = real
		}
		if isVolumeRoot(abs) {
			return
		}
		key := shareKey(abs)
		if seen[key] {
			return
		}
		name := displayName(abs)
		if hiddenName(filepath.Base(abs)) || isVolumeWrapperName(filepath.Base(abs)) {
			return
		}
		seen[key] = true
		out = append(out, browseEntry{Name: name, Share: key, Path: "", Kind: kind, Label: name})
	}
	addSharedTree := func(dir string) {
		if dir == "" {
			return
		}
		items, err := os.ReadDir(dir)
		if err != nil {
			return
		}
		for _, it := range items {
			child := filepath.Join(dir, it.Name())
			if isVolumeWrapperName(it.Name()) {
				kids, err := os.ReadDir(child)
				listed := 0
				if err == nil {
					for _, k := range kids {
						if hiddenName(k.Name()) || isVolumeWrapperName(k.Name()) {
							continue
						}
						addAbs(filepath.Join(child, k.Name()), "share")
						listed++
					}
				}
				if listed == 0 {
					label := configuredLabelForVolume(it.Name())
					if label == "" {
						continue
					}
					key := it.Name()
					if seen[key] {
						continue
					}
					seen[key] = true
					out = append(out, browseEntry{Name: label, Share: key, Path: "", Kind: "share", Label: label})
				}
				continue
			}
			addAbs(child, "share")
		}
	}
	addSharedTree(root)
	for _, p := range configuredFolderPaths() {
		if readableDir(p) {
			addAbs(p, "share")
			continue
		}
		if root != "" {
			base := filepath.Base(p)
			addAbs(filepath.Join(root, base), "share")
			slash := filepath.ToSlash(p)
			if i := strings.Index(slash, "/volume"); i >= 0 {
				addAbs(filepath.Join(root, filepath.FromSlash(slash[i+1:])), "share")
			}
		}
	}
	for _, f := range extra {
		abs, err := resolveLocalPath(f.Share, f.Path)
		if err != nil {
			label := strings.Trim(f.Share+"/"+f.Path, "/")
			if label == "" {
				continue
			}
			key := f.Share
			if seen[key+"|"+f.Path] {
				continue
			}
			seen[key+"|"+f.Path] = true
			out = append(out, browseEntry{Name: label, Share: f.Share, Path: f.Path, Kind: "share", Label: label + " (nicht lesbar)"})
			continue
		}
		addAbs(abs, "share")
	}
	return out
}

func resolveLocalPath(share, rel string) (string, error) {
	share = strings.TrimSpace(share)
	rel, good := cleanRel(rel)
	if !good {
		return "", os.ErrInvalid
	}
	if share == "" {
		if strings.HasPrefix(rel, "/volume") {
			return rel, nil
		}
		return "", os.ErrNotExist
	}
	try := func(p string) string {
		if readableDir(p) {
			return p
		}
		return ""
	}
	root := sharedDir()
	slash := filepath.ToSlash(share)
	base := ""
	if root != "" && !strings.HasPrefix(slash, "/") && strings.Contains(slash, "/") {
		base = try(filepath.Join(root, filepath.FromSlash(slash)))
	}
	if base == "" && strings.HasPrefix(slash, "/volume") {
		base = try(filepath.FromSlash(share))
		if base == "" && root != "" {
			base = try(filepath.Join(root, filepath.FromSlash(strings.TrimPrefix(slash, "/"))))
		}
	}
	if base == "" && root != "" {
		base = try(filepath.Join(root, share))
	}
	if base == "" && root != "" {
		for i := 1; i <= 8; i++ {
			base = try(filepath.Join(root, "volume"+strconv.Itoa(i), share))
			if base != "" {
				break
			}
		}
	}
	if base == "" {
		for _, p := range configuredFolderPaths() {
			if filepath.Base(p) == share || filepath.ToSlash(p) == slash || p == share {
				base = try(p)
				if base != "" {
					break
				}
				if root != "" {
					base = try(filepath.Join(root, filepath.Base(p)))
					if base == "" {
						s := filepath.ToSlash(p)
						if i := strings.Index(s, "/volume"); i >= 0 {
							base = try(filepath.Join(root, filepath.FromSlash(s[i+1:])))
						}
					}
					if base != "" {
						break
					}
				}
			}
		}
	}
	if base == "" {
		for _, vol := range volumeRoots() {
			base = try(filepath.Join(vol, share))
			if base != "" {
				break
			}
		}
	}
	if base == "" {
		return "", os.ErrNotExist
	}
	if isVolumeRoot(base) && rel == "" {
		return "", os.ErrNotExist
	}
	if rel == "" {
		return base, nil
	}
	full := filepath.Join(base, filepath.FromSlash(rel))
	realBase, err := filepath.Abs(base)
	if err != nil {
		return "", err
	}
	realFull, err := filepath.Abs(full)
	if err != nil {
		return "", err
	}
	pref := strings.TrimSuffix(realBase, string(os.PathSeparator)) + string(os.PathSeparator)
	if realFull != realBase && !strings.HasPrefix(realFull, pref) {
		return "", os.ErrPermission
	}
	return realFull, nil
}

func listLocalDirs(abs, share, rel string) ([]browseEntry, error) {
	items, err := os.ReadDir(abs)
	if err != nil {
		return nil, err
	}
	out := []browseEntry{}
	seen := map[string]bool{}
	add := func(name string) {
		if hiddenName(name) || seen[name] {
			return
		}
		if !readableDir(filepath.Join(abs, name)) {
			return
		}
		seen[name] = true
		out = append(out, browseEntry{
			Name:  name,
			Share: share,
			Path:  joinRel(rel, name),
			Kind:  "dir",
			Label: name,
		})
	}
	for _, it := range items {
		if dirEntryIsDir(abs, it) {
			add(it.Name())
		}
	}
	for _, name := range overlayChildNames(abs) {
		add(name)
	}
	return out, nil
}
