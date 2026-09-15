package main

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

var errCacheDevice = errors.New("kein SMB-Gerät")

const (
	cacheMaxDepth   = 4
	cacheMaxNodes   = 400
	cacheMaxSeconds = 90
)

type smbFolderCache struct {
	CachedAt string              `json:"cachedAt"`
	Partial  bool                `json:"partial"`
	Shares   []string            `json:"shares"`
	Dirs     map[string][]string `json:"dirs"`
}

type folderCacheInfo struct {
	Ready    bool   `json:"ready"`
	CachedAt string `json:"cachedAt"`
	Shares   int    `json:"shares"`
	Dirs     int    `json:"dirs"`
	Building bool   `json:"building"`
	Partial  bool   `json:"partial"`
}

func cacheKey(share, rel string) string {
	share = strings.TrimSpace(share)
	rel = strings.Trim(strings.ReplaceAll(rel, "\\", "/"), "/")
	if rel == "" {
		return share
	}
	return share + "/" + rel
}

func (a *App) cacheDir() string {
	return filepath.Join(filepath.Dir(a.file), "smb_cache")
}

func (a *App) cachePath(id string) string {
	safe := strings.Map(func(r rune) rune {
		if r == '.' || r == '-' || r == '_' || (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') {
			return r
		}
		return '_'
	}, id)
	if safe == "" {
		safe = "device"
	}
	return filepath.Join(a.cacheDir(), safe+".json")
}

func (a *App) loadFolderCache(id string) *smbFolderCache {
	b, err := os.ReadFile(a.cachePath(id))
	if err != nil {
		return nil
	}
	var c smbFolderCache
	if json.Unmarshal(b, &c) != nil {
		return nil
	}
	if c.Dirs == nil {
		c.Dirs = map[string][]string{}
	}
	return &c
}

func (a *App) saveFolderCache(id string, c *smbFolderCache) {
	if c == nil || id == "" || id == "local" {
		return
	}
	_ = os.MkdirAll(a.cacheDir(), 0o700)
	c.CachedAt = time.Now().Format(time.RFC3339)
	b, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return
	}
	_ = os.WriteFile(a.cachePath(id), b, 0o600)
}

func (a *App) deleteFolderCache(id string) {
	_ = os.Remove(a.cachePath(id))
	a.cacheMu.Lock()
	delete(a.building, id)
	a.cacheMu.Unlock()
}

func (a *App) pruneFolderCaches(keep []Device) {
	keepIDs := map[string]bool{}
	for _, d := range keep {
		keepIDs[d.ID] = true
	}
	ents, err := os.ReadDir(a.cacheDir())
	if err != nil {
		return
	}
	for _, e := range ents {
		name := strings.TrimSuffix(e.Name(), ".json")
		if !keepIDs[name] {
			_ = os.Remove(filepath.Join(a.cacheDir(), e.Name()))
		}
	}
}

func (a *App) rememberBrowse(id, share, rel string, entries []browseEntry) {
	if id == "" || id == "local" {
		return
	}
	a.cacheMu.Lock()
	defer a.cacheMu.Unlock()
	c := a.loadFolderCache(id)
	if c == nil {
		c = &smbFolderCache{Dirs: map[string][]string{}}
	}
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		if e.Name != "" {
			names = append(names, e.Name)
		}
	}
	sort.Strings(names)
	if share == "" {
		c.Shares = names
	} else {
		if c.Dirs == nil {
			c.Dirs = map[string][]string{}
		}
		c.Dirs[cacheKey(share, rel)] = names
	}
	a.saveFolderCache(id, c)
}

func (a *App) browseFromCache(id, share, rel string) (browseResult, bool) {
	c := a.loadFolderCache(id)
	if c == nil {
		return browseResult{}, false
	}
	if share == "" {
		if c.Shares == nil {
			return browseResult{}, false
		}
		entries := make([]browseEntry, 0, len(c.Shares))
		for _, name := range c.Shares {
			entries = append(entries, browseEntry{Name: name, Share: name, Path: "", Kind: "share", Label: name})
		}
		return browseResult{OK: true, HintKey: "cached", Entries: entries, Cached: true}, true
	}
	key := cacheKey(share, rel)
	names, ok := c.Dirs[key]
	if !ok {
		return browseResult{}, false
	}
	entries := make([]browseEntry, 0, len(names))
	for _, name := range names {
		entries = append(entries, browseEntry{
			Name: name, Share: share, Path: joinRel(rel, name), Kind: "dir", Label: name,
		})
	}
	hintKey := "cached"
	if len(entries) == 0 {
		hintKey = "cachedEmpty"
	}
	return browseResult{
		OK: true, Share: share, Path: rel, Parent: parentRel(rel),
		HintKey: hintKey, Entries: entries, Cached: true,
	}, true
}

func (a *App) folderCacheSummaries() map[string]folderCacheInfo {
	a.mu.Lock()
	devs := append([]Device(nil), a.data.Devices...)
	a.mu.Unlock()
	return a.folderCacheSummariesFor(devs)
}

func (a *App) folderCacheSummariesFor(devs []Device) map[string]folderCacheInfo {
	out := map[string]folderCacheInfo{}
	a.cacheMu.Lock()
	building := map[string]bool{}
	for k, v := range a.building {
		building[k] = v
	}
	a.cacheMu.Unlock()
	for _, d := range devs {
		if d.ID == "local" {
			continue
		}
		info := folderCacheInfo{Building: building[d.ID]}
		if c := a.loadFolderCache(d.ID); c != nil {
			info.Ready = len(c.Shares) > 0 || len(c.Dirs) > 0
			info.CachedAt = c.CachedAt
			info.Shares = len(c.Shares)
			info.Dirs = len(c.Dirs)
			info.Partial = c.Partial
		}
		out[d.ID] = info
	}
	return out
}

func (a *App) startFolderCacheBuild(id string) error {
	a.mu.Lock()
	dev, ok := findDevice(a.data.Devices, id)
	a.mu.Unlock()
	if !ok || isLocalDevice(dev) {
		return errCacheDevice
	}
	a.cacheMu.Lock()
	if a.building[id] {
		a.cacheMu.Unlock()
		return nil
	}
	if a.building == nil {
		a.building = map[string]bool{}
	}
	a.building[id] = true
	a.cacheMu.Unlock()
	go a.buildFolderCache(dev)
	return nil
}

func (a *App) buildFolderCache(dev Device) {
	defer func() {
		a.cacheMu.Lock()
		delete(a.building, dev.ID)
		a.cacheMu.Unlock()
	}()
	started := time.Now()
	live := browseSMB(dev, "", "")
	if !live.OK {
		return
	}
	c := &smbFolderCache{Dirs: map[string][]string{}, Shares: nil}
	for _, e := range live.Entries {
		c.Shares = append(c.Shares, e.Name)
	}
	nodes := 0
	timedOut := false
	var walk func(share, rel string, depth int)
	walk = func(share, rel string, depth int) {
		if timedOut || nodes >= cacheMaxNodes || depth > cacheMaxDepth {
			return
		}
		if time.Since(started) > cacheMaxSeconds*time.Second {
			timedOut = true
			return
		}
		res := browseSMB(dev, share, rel)
		if !res.OK {
			return
		}
		names := make([]string, 0, len(res.Entries))
		for _, e := range res.Entries {
			names = append(names, e.Name)
		}
		c.Dirs[cacheKey(share, rel)] = names
		nodes++
		for _, e := range res.Entries {
			if timedOut {
				return
			}
			walk(share, e.Path, depth+1)
		}
	}
	for _, share := range c.Shares {
		if timedOut {
			break
		}
		walk(share, "", 0)
	}
	c.Partial = timedOut || nodes >= cacheMaxNodes
	a.cacheMu.Lock()
	a.saveFolderCache(dev.ID, c)
	a.cacheMu.Unlock()
}
