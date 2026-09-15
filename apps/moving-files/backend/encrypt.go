package main

import (
	"bufio"
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"errors"
	"hash"
	"io"
	"strings"

	"golang.org/x/crypto/pbkdf2"
)

const (
	encMagic     = "MFENC1"
	encSaltSize  = 16
	encIVSize    = 16
	encHMACSize  = 32
	encPBKDF2N   = 100000
	encKeySize   = 64
	encHeaderLen = 6 + encSaltSize + encIVSize
)

func backupEncSuffix() string { return backupSuffix + ".enc" }

func isBackupEncryptedName(name string) bool {
	n := strings.ToLower(strings.TrimSpace(name))
	return strings.HasPrefix(n, backupPrefix) && strings.HasSuffix(n, backupEncSuffix())
}

func deriveEncKeys(password string, salt []byte) (aesKey, macKey []byte) {
	key := pbkdf2.Key([]byte(password), salt, encPBKDF2N, encKeySize, sha256.New)
	return key[:32], key[32:]
}

type encWriter struct {
	w      io.Writer
	stream cipher.Stream
	mac    hash.Hash
}

func newEncWriter(w io.Writer, password string) (*encWriter, error) {
	salt := make([]byte, encSaltSize)
	iv := make([]byte, encIVSize)
	if _, err := io.ReadFull(rand.Reader, salt); err != nil {
		return nil, err
	}
	if _, err := io.ReadFull(rand.Reader, iv); err != nil {
		return nil, err
	}
	aesKey, macKey := deriveEncKeys(password, salt)
	block, err := aes.NewCipher(aesKey)
	if err != nil {
		return nil, err
	}
	hdr := make([]byte, 0, encHeaderLen)
	hdr = append(hdr, encMagic...)
	hdr = append(hdr, salt...)
	hdr = append(hdr, iv...)
	if _, err := w.Write(hdr); err != nil {
		return nil, err
	}
	return &encWriter{
		w:      w,
		stream: cipher.NewCTR(block, iv),
		mac:    hmac.New(sha256.New, macKey),
	}, nil
}

func (e *encWriter) Write(p []byte) (int, error) {
	if len(p) == 0 {
		return 0, nil
	}
	buf := make([]byte, len(p))
	e.stream.XORKeyStream(buf, p)
	e.mac.Write(buf)
	if _, err := e.w.Write(buf); err != nil {
		return 0, err
	}
	return len(p), nil
}

func (e *encWriter) Close() error {
	_, err := e.w.Write(e.mac.Sum(nil))
	return err
}

type decReader struct {
	r      io.Reader
	stream cipher.Stream
	mac    hash.Hash
	hold   []byte
	err    error
}

func newDecReader(r io.Reader, password string) (io.Reader, error) {
	hdr := make([]byte, encHeaderLen)
	if _, err := io.ReadFull(r, hdr); err != nil {
		return nil, locErr("archiveIncomplete")
	}
	if string(hdr[:6]) != encMagic {
		return nil, locErr("notEncrypted")
	}
	salt := hdr[6 : 6+encSaltSize]
	iv := hdr[6+encSaltSize:]
	aesKey, macKey := deriveEncKeys(password, salt)
	block, err := aes.NewCipher(aesKey)
	if err != nil {
		return nil, err
	}
	return &decReader{
		r:      r,
		stream: cipher.NewCTR(block, iv),
		mac:    hmac.New(sha256.New, macKey),
	}, nil
}

func (d *decReader) Read(p []byte) (int, error) {
	for {
		if len(d.hold) > encHMACSize {
			n := len(d.hold) - encHMACSize
			if n > len(p) {
				n = len(p)
			}
			chunk := d.hold[:n]
			d.mac.Write(chunk)
			d.stream.XORKeyStream(p[:n], chunk)
			d.hold = append([]byte(nil), d.hold[n:]...)
			return n, nil
		}
		if d.err != nil {
			if errors.Is(d.err, io.EOF) {
				if len(d.hold) != encHMACSize {
					return 0, locErr("archiveIncomplete")
				}
				if !hmac.Equal(d.mac.Sum(nil), d.hold) {
					return 0, locErr("badPass")
				}
				d.hold = nil
				d.err = io.ErrUnexpectedEOF
				return 0, io.EOF
			}
			return 0, d.err
		}
		buf := make([]byte, 8192)
		n, err := d.r.Read(buf)
		if n > 0 {
			d.hold = append(d.hold, buf[:n]...)
		}
		d.err = err
	}
}

func wrapArchiveWriter(w io.Writer, password string) (io.Writer, func() error, error) {
	if strings.TrimSpace(password) == "" {
		return w, func() error { return nil }, nil
	}
	enc, err := newEncWriter(w, password)
	if err != nil {
		return nil, nil, err
	}
	return enc, enc.Close, nil
}

func wrapArchiveReader(r io.Reader, name, password string) (io.Reader, error) {
	br := bufio.NewReader(r)
	peek, _ := br.Peek(len(encMagic))
	encrypted := isBackupEncryptedName(name) || string(peek) == encMagic
	if !encrypted {
		return br, nil
	}
	if strings.TrimSpace(password) == "" {
		return nil, locErr("needArchivePass")
	}
	return newDecReader(br, password)
}
