package main

import (
	"bytes"
	"io"
	"strings"
	"testing"
)

func TestBackupEncryptedName(t *testing.T) {
	plain := backupPrefix + "2026-01-01-120000" + backupSuffix
	enc := plain + ".enc"
	if !isBackupArchiveName(plain) || isBackupEncryptedName(plain) {
		t.Fatal(plain)
	}
	if !isBackupArchiveName(enc) || !isBackupEncryptedName(enc) {
		t.Fatal(enc)
	}
}

func TestEncRoundTrip(t *testing.T) {
	var buf bytes.Buffer
	w, closeEnc, err := wrapArchiveWriter(&buf, "secret-pass")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := io.WriteString(w, "hello-archive"); err != nil {
		t.Fatal(err)
	}
	if err := closeEnc(); err != nil {
		t.Fatal(err)
	}
	plain, err := wrapArchiveReader(bytes.NewReader(buf.Bytes()), "mf-backup-x.tar.gz.enc", "secret-pass")
	if err != nil {
		t.Fatal(err)
	}
	got, err := io.ReadAll(plain)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "hello-archive" {
		t.Fatalf("got %q", got)
	}
}

func TestEncWrongPassword(t *testing.T) {
	var buf bytes.Buffer
	w, closeEnc, err := wrapArchiveWriter(&buf, "right")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := io.WriteString(w, "payload"); err != nil {
		t.Fatal(err)
	}
	if err := closeEnc(); err != nil {
		t.Fatal(err)
	}
	plain, err := wrapArchiveReader(bytes.NewReader(buf.Bytes()), "mf-backup-x.tar.gz.enc", "wrong")
	if err != nil {
		t.Fatal(err)
	}
	_, err = io.ReadAll(plain)
	if err == nil {
		t.Fatal("want wrong-password error")
	}
	k, _ := splitErr(err)
	if k != "badPass" {
		t.Fatalf("want wrong-password error, got %v", err)
	}
}

func TestWrapArchiveReaderPlain(t *testing.T) {
	plain, err := wrapArchiveReader(strings.NewReader("plain-bytes"), "mf-backup-x.tar.gz", "")
	if err != nil {
		t.Fatal(err)
	}
	got, err := io.ReadAll(plain)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "plain-bytes" {
		t.Fatalf("got %q", got)
	}
}
