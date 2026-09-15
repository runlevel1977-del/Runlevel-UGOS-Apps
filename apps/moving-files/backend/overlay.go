package main

import (
	"os"
	"path/filepath"
	"sort"
	"strings"
)

var mountinfoFile = "/proc/self/mountinfo"

func unescapeMount(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	for i := 0; i < len(s); i++ {
		if s[i] == '\\' && i+3 < len(s) {
			n := 0
			ok := true
			for _, c := range s[i+1 : i+4] {
				if c < '0' || c > '7' {
					ok = false
					break
				}
				n = n*8 + int(c-'0')
			}
			if ok {
				b.WriteByte(byte(n))
				i += 3
				continue
			}
		}
		b.WriteByte(s[i])
	}
	return b.String()
}

func parseMountPoints(data string) []string {
	out := []string{}
	for _, line := range strings.Split(data, "\n") {
		fields := strings.Fields(line)
		if len(fields) < 5 {
			continue
		}
		p := unescapeMount(fields[4])
		if p != "" {
			out = append(out, filepath.Clean(p))
		}
	}
	return out
}

func mountPointsUnder(root string) []string {
	root = filepath.Clean(root)
	if root == "" || root == "." {
		return nil
	}
	b, err := os.ReadFile(mountinfoFile)
	if err != nil {
		return nil
	}
	pref := strings.TrimSuffix(root, string(os.PathSeparator)) + string(os.PathSeparator)
	out := []string{}
	seen := map[string]bool{}
	for _, p := range parseMountPoints(string(b)) {
		if p == root || !strings.HasPrefix(p, pref) {
			continue
		}
		if seen[p] {
			continue
		}
		seen[p] = true
		out = append(out, p)
	}
	return out
}

func grantedReadableAbs() []string {
	out := []string{}
	seen := map[string]bool{}
	add := func(p string) {
		p = strings.TrimSpace(p)
		if p == "" {
			return
		}
		p = filepath.Clean(p)
		if !readableDir(p) || seen[p] {
			return
		}
		seen[p] = true
		out = append(out, p)
	}
	root := sharedDir()
	for _, p := range configuredFolderPaths() {
		add(p)
		if root == "" {
			continue
		}
		add(filepath.Join(root, filepath.Base(p)))
		slash := filepath.ToSlash(p)
		add(filepath.Join(root, filepath.FromSlash(strings.TrimPrefix(slash, "/"))))
		if i := strings.Index(slash, "/volume"); i >= 0 {
			add(filepath.Join(root, filepath.FromSlash(slash[i+1:])))
		}
	}
	return out
}

func overlayCandidatesUnder(root string) []string {
	root = filepath.Clean(root)
	pref := strings.TrimSuffix(root, string(os.PathSeparator)) + string(os.PathSeparator)
	seen := map[string]bool{}
	out := []string{}
	add := func(p string) {
		p = filepath.Clean(p)
		if p == root || !strings.HasPrefix(p, pref) || !readableDir(p) || seen[p] {
			return
		}
		seen[p] = true
		out = append(out, p)
	}
	for _, p := range grantedReadableAbs() {
		add(p)
	}
	for _, p := range mountPointsUnder(root) {
		add(p)
	}
	sort.Strings(out)
	return out
}

func listedInParent(child string) bool {
	parent := filepath.Dir(child)
	name := filepath.Base(child)
	items, err := os.ReadDir(parent)
	if err != nil {
		return false
	}
	for _, it := range items {
		if it.Name() == name {
			return true
		}
	}
	return false
}

func unlistedTreesUnder(root string) []string {
	root = filepath.Clean(root)
	out := []string{}
	for _, p := range overlayCandidatesUnder(root) {
		if !listedInParent(p) {
			out = append(out, p)
		}
	}
	return out
}

func overlayChildNames(abs string) []string {
	abs = filepath.Clean(abs)
	pref := strings.TrimSuffix(abs, string(os.PathSeparator)) + string(os.PathSeparator)
	seen := map[string]bool{}
	names := []string{}
	add := func(childAbs string) {
		childAbs = filepath.Clean(childAbs)
		if childAbs == abs || !strings.HasPrefix(childAbs, pref) {
			return
		}
		rest := strings.TrimPrefix(childAbs, pref)
		name := rest
		if i := strings.IndexAny(rest, `/\`); i >= 0 {
			name = rest[:i]
		}
		if name == "" || hiddenName(name) || seen[name] {
			return
		}
		if !readableDir(filepath.Join(abs, name)) && !readableDir(childAbs) {
			return
		}
		seen[name] = true
		names = append(names, name)
	}
	for _, p := range overlayCandidatesUnder(abs) {
		add(p)
	}
	sort.Strings(names)
	return names
}

func dirEntryIsDir(abs string, it os.DirEntry) bool {
	if it.IsDir() {
		return true
	}
	st, err := os.Stat(filepath.Join(abs, it.Name()))
	return err == nil && st.IsDir()
}

func forUnlistedTrees(root string, fn func(abs, relSlash string) error) error {
	for _, extra := range unlistedTreesUnder(root) {
		rel, err := filepath.Rel(root, extra)
		if err != nil {
			return err
		}
		rel = filepath.ToSlash(rel)
		if rel == "" || rel == "." {
			continue
		}
		if err := fn(extra, rel); err != nil {
			return err
		}
	}
	return nil
}
