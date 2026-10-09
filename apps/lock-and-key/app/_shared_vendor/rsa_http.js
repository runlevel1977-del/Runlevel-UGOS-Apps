/* RSA encrypt for HTTP (no crypto.subtle). OAEP when available, else PKCS#1 v1.5. */
(function (global) {
  function b64ToBytes(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function bytesToB64(bytes) {
    let s = "";
    for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return btoa(s);
  }
  function pemToDer(pem) {
    const b64 = String(pem || "")
      .replace(/-----BEGIN PUBLIC KEY-----/g, "")
      .replace(/-----END PUBLIC KEY-----/g, "")
      .replace(/\s+/g, "");
    return b64ToBytes(b64);
  }
  function readLen(buf, i) {
    let len = buf[i++];
    if ((len & 0x80) === 0) return { len: len, i: i };
    const n = len & 0x7f;
    len = 0;
    for (let k = 0; k < n; k++) len = (len << 8) + buf[i++];
    return { len: len, i: i };
  }
  function readTag(buf, i, tag) {
    if (buf[i] !== tag) throw new Error("bad public key");
    return readLen(buf, i + 1);
  }
  function bytesToBigInt(bytes) {
    let hex = "";
    for (let i = 0; i < bytes.length; i++) hex += bytes[i].toString(16).padStart(2, "0");
    return BigInt("0x" + hex);
  }
  function readInt(buf, i) {
    const r = readTag(buf, i, 0x02);
    const end = r.i + r.len;
    let s = r.i;
    while (s < end - 1 && buf[s] === 0) s++;
    return { n: bytesToBigInt(buf.subarray(s, end)), i: end };
  }
  function parseSpki(pem) {
    const der = pemToDer(pem);
    let i = 0;
    const seq = readTag(der, i, 0x30);
    i = seq.i;
    const alg = readTag(der, i, 0x30);
    i = alg.i + alg.len;
    const bits = readTag(der, i, 0x03);
    i = bits.i;
    if (der[i] !== 0x00) throw new Error("bad bitstring");
    i += 1;
    const inner = readTag(der, i, 0x30);
    i = inner.i;
    const n = readInt(der, i);
    const e = readInt(der, n.i);
    const hexLen = n.n.toString(16).length;
    const k = Math.ceil(hexLen / 2);
    return { n: n.n, e: e.n, k: k };
  }
  function modPow(base, exp, mod) {
    let r = 1n;
    base %= mod;
    while (exp > 0n) {
      if (exp & 1n) r = (r * base) % mod;
      base = (base * base) % mod;
      exp >>= 1n;
    }
    return r;
  }
  function randomNonZero(len) {
    const out = new Uint8Array(len);
    if (global.crypto && typeof crypto.getRandomValues === "function") {
      crypto.getRandomValues(out);
      for (let i = 0; i < len; i++) {
        if (out[i] === 0) out[i] = (i % 255) + 1;
      }
    } else {
      for (let i = 0; i < len; i++) out[i] = (Math.floor(Math.random() * 255) + 1);
    }
    return out;
  }
  function encryptPkcs1Bytes(pem, bytes) {
    const key = parseSpki(pem);
    const msg = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes || []);
    if (msg.length > key.k - 11) throw new Error("password too long");
    const padded = new Uint8Array(key.k);
    padded[0] = 0x00;
    padded[1] = 0x02;
    const ps = randomNonZero(key.k - 3 - msg.length);
    padded.set(ps, 2);
    padded[2 + ps.length] = 0x00;
    padded.set(msg, 3 + ps.length);
    const m = bytesToBigInt(padded);
    const c = modPow(m, key.e, key.n);
    let hex = c.toString(16);
    if (hex.length % 2) hex = "0" + hex;
    const out = new Uint8Array(key.k);
    const raw = new Uint8Array(hex.length / 2);
    for (let i = 0; i < raw.length; i++) raw[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    out.set(raw, key.k - raw.length);
    return bytesToB64(out);
  }
  function encryptPkcs1(pem, plain) {
    return encryptPkcs1Bytes(pem, new TextEncoder().encode(String(plain || "")));
  }
  async function encryptOaepBytes(pem, bytes) {
    if (!global.crypto || !crypto.subtle) return null;
    const der = pemToDer(pem);
    const key = await crypto.subtle.importKey(
      "spki",
      der,
      { name: "RSA-OAEP", hash: "SHA-256" },
      false,
      ["encrypt"]
    );
    const msg = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes || []);
    const enc = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, key, msg);
    return bytesToB64(new Uint8Array(enc));
  }
  async function encryptOaep(pem, plain) {
    return encryptOaepBytes(pem, new TextEncoder().encode(String(plain || "")));
  }
  async function encryptOneBlock(pem, bytes, secure) {
    if (secure) {
      try {
        const oaep = await encryptOaepBytes(pem, bytes);
        if (oaep) return oaep;
      } catch (e) {
        /* fall through to PKCS#1 */
      }
    }
    return encryptPkcs1Bytes(pem, bytes);
  }
  async function loadPublicPem() {
    const r = await fetch("/api/crypto/public-key", { headers: { Accept: "application/json" } });
    const j = await r.json();
    if (!j || !j.pem) throw new Error("no public key");
    return j.pem;
  }
  global.rlEncryptSecret = async function (plain) {
    const pem = await loadPublicPem();
    const secure = typeof global.isSecureContext === "boolean" ? global.isSecureContext : false;
    return encryptOneBlock(pem, new TextEncoder().encode(String(plain || "")), secure);
  };
  global.rlEncryptPayload = async function (plain) {
    const pem = await loadPublicPem();
    const key = parseSpki(pem);
    const secure = typeof global.isSecureContext === "boolean" ? global.isSecureContext : false;
    const bytes = typeof plain === "string"
      ? new TextEncoder().encode(plain)
      : (plain instanceof Uint8Array ? plain : new Uint8Array(plain || []));
    const max = Math.max(1, secure ? key.k - 66 : key.k - 11);
    const chunks = [];
    for (let i = 0; i < bytes.length; i += max) {
      chunks.push(await encryptOneBlock(pem, bytes.subarray(i, i + max), secure));
    }
    if (!chunks.length) chunks.push(await encryptOneBlock(pem, new Uint8Array(0), secure));
    return "c1:" + chunks.length + ":" + chunks.join(":");
  };
})(window);
