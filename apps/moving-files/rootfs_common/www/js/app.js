(function () {
  const API = "./../api";
  const KEY = "runlevel.native.v3";

  const defaultState = () => ({
    devices: [
      { id: "local", type: "local", name: "Dieses NAS", host: "", share: "", user: "", password: "", mac: "" }
    ],
    transfers: [],
    wakePlans: [],
    folderCaches: {},
    backup: null,
    logs: []
  });

  let state = defaultState();
  let jobs = {};
  let pollBackupStatus = "";
  let privacy = { decided: false, accepted: false };

  function typeLabel(type) {
    if (type === "local") return t("type.local");
    if (type === "nas") return t("type.nas");
    return t("type.pc");
  }

  function log(line) {
    const stamp = new Date().toLocaleString(fmtLocale());
    state.logs.unshift(stamp + "  " + line);
    state.logs = state.logs.slice(0, 80);
  }

  function stripSecrets(obj) {
    (obj.devices || []).forEach((d) => {
      if (d.password) d.hasPassword = true;
      d.password = "";
    });
    if (obj.backup) {
      if (obj.backup.password) obj.backup.hasPassword = true;
      obj.backup.password = "";
      obj.backup.passwordClear = false;
    }
  }

  function uid(prefix) {
    return prefix + "-" + Math.random().toString(36).slice(2, 8);
  }

  function deviceById(id) {
    return state.devices.find((d) => d.id === id);
  }

  function deviceName(id) {
    const d = deviceById(id);
    if (!d) return id;
    if (d.id === "local" || d.type === "local") return t("type.local");
    return d.name;
  }

  function locMsg(key, arg) {
    if (!key) return "";
    if (key === "raw" || key === "file") return arg || "";
    return t("job." + key, { n: arg || "" });
  }

  function locJob(j) {
    if (!j) return "";
    return locMsg(j.detailKey, j.detailArg) || j.detail || "";
  }

  function locErr(body) {
    if (!body) return t("err.generic");
    if (body.errorKey) return locMsg(body.errorKey, body.errorArg) || t("err.generic");
    return body.error || t("err.generic");
  }

  function locNote(body) {
    if (!body) return "";
    if (body.messageKey) return locMsg(body.messageKey, body.messageArg);
    return body.message || "";
  }

  function timedFetch(url, opts, ms) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms || 900);
    return fetch(url, Object.assign({ signal: ctrl.signal }, opts || {})).finally(() => clearTimeout(timer));
  }

  function folderLabel(share, path) {
    return [share, path].filter(Boolean).join("/") || t("folder.fallback");
  }

  function transferRoute(t) {
    const extra = (t.srcPaths || []).length ? " +" + t.srcPaths.length : "";
    return deviceName(t.srcDevice) + " " + folderLabel(t.srcShare, t.srcPath) + extra
      + " → " + deviceName(t.dstDevice) + " " + folderLabel(t.dstShare, t.dstPath);
  }

  let pick = { target: "", multi: false, deviceId: "", share: "", path: "", entries: [] };
  let picked = {
    transferSrc: [],
    transferDst: null,
    wakeSrc: [],
    wakeDst: null,
    backupSrc: null,
    backupDst: null,
    backupRestoreDst: null
  };

  function renderChips(id, items, single) {
    const box = document.getElementById(id);
    if (!box) return;
    const list = single ? (items ? [items] : []) : (items || []);
    if (!list.length) {
      box.innerHTML = `<span class="hint">${esc(t("chip.empty"))}</span>`;
      return;
    }
    box.innerHTML = list.map((it, i) =>
      `<span class="chip">${esc(folderLabel(it.share, it.path))}<button type="button" data-chip="${id}:${i}" aria-label="${esc(t("btn.remove"))}">×</button></span>`
    ).join("");
  }

  function refreshPicks() {
    renderChips("src-chips", picked.transferSrc, false);
    renderChips("dst-chips", picked.transferDst, true);
    renderChips("wake-src-chips", picked.wakeSrc, false);
    renderChips("wake-dst-chips", picked.wakeDst, true);
    renderChips("backup-src-chips", picked.backupSrc, true);
    renderChips("backup-dst-chips", picked.backupDst, true);
    renderChips("backup-restore-chips", picked.backupRestoreDst, true);
  }

  function openPickModal(open) {
    document.getElementById("modal-pick").classList.toggle("open", open);
  }

  function resetDeviceForm() {
    const f = document.getElementById("form-device");
    f.reset();
    f.deviceId.value = "";
    document.getElementById("device-form-title").textContent = t("devices.formAdd");
    document.getElementById("btn-save-device").textContent = t("btn.save");
    document.getElementById("device-msg").textContent = "";
  }

  function fillDeviceForm(d) {
    const f = document.getElementById("form-device");
    f.deviceId.value = d.id;
    f.type.value = d.type === "nas" ? "nas" : "pc";
    f.name.value = d.name || "";
    f.host.value = d.host || "";
    f.share.value = d.share || "";
    f.user.value = d.user || "";
    f.password.value = "";
    f.mac.value = d.mac || "";
    const ph = document.getElementById("device-pass-hint");
    if (ph) ph.textContent = d.hasPassword ? t("dev.passwordKeep") : "";
    document.getElementById("device-form-title").textContent = t("devices.formEdit");
    document.getElementById("btn-save-device").textContent = t("btn.saveChanges");
    document.getElementById("device-msg").textContent = "";
    show("devices");
    f.scrollIntoView({ block: "nearest" });
    setTimeout(() => f.name.focus(), 50);
  }

  function folderItemsFromJob(share, path, extras) {
    const out = [];
    if (share || path) out.push({ share: share || "", path: path || "" });
    (extras || []).forEach((raw) => {
      raw = String(raw || "").trim();
      if (!raw) return;
      const i = raw.indexOf("|");
      if (i >= 0) out.push({ share: raw.slice(0, i), path: raw.slice(i + 1) });
      else out.push({ share: share || "", path: raw });
    });
    return out;
  }

  function resetTransferForm() {
    const f = document.getElementById("form-transfer");
    f.reset();
    f.jobId.value = "";
    picked.transferSrc = [];
    picked.transferDst = null;
    document.getElementById("transfer-form-title").textContent = t("transfers.formAdd");
    document.getElementById("btn-save-transfer").textContent = t("btn.addJob");
    document.getElementById("transfer-msg").textContent = "";
    syncAutoTimeField();
    refreshPicks();
  }

  function fillTransferForm(job) {
    fillDeviceSelects();
    const f = document.getElementById("form-transfer");
    f.jobId.value = job.id;
    f.name.value = job.name || "";
    f.srcDevice.value = job.srcDevice || "local";
    f.dstDevice.value = job.dstDevice || "local";
    f.mode.value = job.mode || "sync";
    f.fast.value = isFast(job) ? "1" : "0";
    f.auto.value = job.auto || "";
    if (f.autoTime) f.autoTime.value = job.autoTime || "22:00";
    picked.transferSrc = folderItemsFromJob(job.srcShare, job.srcPath, job.srcPaths);
    picked.transferDst = { share: job.dstShare || "", path: job.dstPath || "" };
    document.getElementById("transfer-form-title").textContent = t("transfers.formEdit");
    document.getElementById("btn-save-transfer").textContent = t("btn.saveChanges");
    document.getElementById("transfer-msg").textContent = t("msg.keepSchedule");
    syncAutoTimeField();
    refreshPicks();
    show("transfers");
    f.scrollIntoView({ block: "nearest" });
    setTimeout(() => f.name.focus(), 50);
    renderTransfers();
  }

  function resetWakeForm() {
    const f = document.getElementById("form-wake");
    f.reset();
    f.planId.value = "";
    picked.wakeSrc = [];
    picked.wakeDst = null;
    document.getElementById("wake-form-title").textContent = t("wake.formAdd");
    document.getElementById("btn-save-wake").textContent = t("btn.addPlan");
    document.getElementById("wake-msg").textContent = "";
    syncAutoTimeField();
    refreshPicks();
  }

  function fillWakeForm(p) {
    fillDeviceSelects();
    const f = document.getElementById("form-wake");
    f.planId.value = p.id;
    f.name.value = p.name || "";
    if (p.deviceId && [...f.deviceId.options].some((o) => o.value === p.deviceId)) f.deviceId.value = p.deviceId;
    f.direction.value = p.direction === "pull" ? "pull" : "push";
    f.wait.value = String(p.wait || "20");
    f.auto.value = p.auto || "";
    if (f.autoTime) f.autoTime.value = p.autoTime || "22:00";
    if (f.autoWeekday) f.autoWeekday.value = p.autoWeekday || "1";
    picked.wakeSrc = folderItemsFromJob(p.srcShare, p.srcPath, p.srcPaths);
    picked.wakeDst = { share: p.dstShare || "", path: p.dstPath || "" };
    document.getElementById("wake-form-title").textContent = t("wake.formEdit");
    document.getElementById("btn-save-wake").textContent = t("btn.saveChanges");
    document.getElementById("wake-msg").textContent = t("msg.keepPlan");
    syncAutoTimeField();
    refreshPicks();
    show("wake");
    f.scrollIntoView({ block: "nearest" });
    setTimeout(() => f.name.focus(), 50);
    renderWake();
  }

  async function loadPickList() {
    const q = new URLSearchParams({
      device_id: pick.deviceId || "local",
      share: pick.share || "",
      path: pick.path || ""
    });
    const list = document.getElementById("pick-list");
    list.innerHTML = `<li><span class="name">${esc(t("pick.loading"))}</span></li>`;
    try {
      const res = await timedFetch("/api/browse?" + q.toString(), { cache: "no-store" }, 8000);
      const data = await res.json();
      if (!data.ok) {
        list.innerHTML = `<li><span class="name">${esc(locMsg(data.errorKey, data.errorArg) || data.error || t("err.generic"))}</span></li>`;
        document.getElementById("pick-hint").textContent = "";
        return;
      }
      pick.share = data.share || "";
      pick.path = data.path || "";
      pick.entries = data.entries || [];
      const crumb = [deviceName(pick.deviceId), pick.share, pick.path].filter(Boolean).join(" / ");
      document.getElementById("pick-crumb").textContent = crumb || t("pick.shares");
      let hint = data.hintKey ? t("hint." + data.hintKey) : (pick.multi ? t("pick.hintMulti") : t("pick.hintSingle"));
      if (data.cached && !data.hintKey) hint = t("hint.cached");
      document.getElementById("pick-hint").textContent = hint;
      document.getElementById("pick-checked").style.display = pick.multi ? "" : "none";
      if (!pick.entries.length) {
        list.innerHTML = `<li><span class="name">${esc(t("empty.pick"))}</span></li>`;
        return;
      }
      list.innerHTML = pick.entries.map((e, i) => `
        <li>
          ${pick.multi ? `<input type="checkbox" data-pick-idx="${i}" />` : ""}
          <span class="name">${e.kind === "share" ? "📁 " : "📂 "}${esc(e.name)}</span>
          <button type="button" class="link" data-pick-open="${i}">${esc(t("pick.open"))}</button>
          <button type="button" class="link" data-pick-sel="${i}">${esc(t("pick.choose"))}</button>
        </li>`).join("");
    } catch (err) {
      list.innerHTML = `<li><span class="name">${esc(t("empty.pickErr"))}</span></li>`;
    }
  }

  async function startPicker(target, multi, deviceId) {
    if (!deviceId) {
      alert(t("need.device"));
      return;
    }
    pick = { target, multi: !!multi, deviceId, share: "", path: "", entries: [] };
    document.getElementById("pick-title").textContent = multi ? t("pick.multi") : t("pick.folder");
    openPickModal(true);
    await loadPickList();
  }

  function applyPicked(entry, add) {
    const item = { share: entry.share || "", path: entry.path || "" };
    if (pick.target === "transferSrc") {
      if (add) picked.transferSrc.push(item);
      else picked.transferSrc = [item];
    } else if (pick.target === "transferDst") picked.transferDst = item;
    else if (pick.target === "wakeSrc") {
      if (add) picked.wakeSrc.push(item);
      else picked.wakeSrc = [item];
    }
    else if (pick.target === "wakeDst") picked.wakeDst = item;
    else if (pick.target === "backupSrc") picked.backupSrc = item;
    else if (pick.target === "backupDst") picked.backupDst = item;
    else if (pick.target === "backupRestoreDst") picked.backupRestoreDst = item;
    refreshPicks();
    openPickModal(false);
  }

  async function load() {
    try {
      const res = await timedFetch("/api/state", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        state = Object.assign(defaultState(), data);
        if (!Array.isArray(state.transfers)) state.transfers = [];
        if (!Array.isArray(state.wakePlans)) state.wakePlans = [];
        state.wakePlans.forEach(normalizeWakePlan);
        if (!state.folderCaches || typeof state.folderCaches !== "object") state.folderCaches = {};
        if (!Array.isArray(state.devices)) state.devices = defaultState().devices;
        if (!state.devices.some((d) => d.id === "local")) {
          state.devices.unshift(defaultState().devices[0]);
        }
        return;
      }
    } catch (err) {}
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        state = Object.assign(defaultState(), JSON.parse(raw));
        if (!Array.isArray(state.transfers)) state.transfers = [];
        if (!Array.isArray(state.wakePlans)) state.wakePlans = [];
        state.wakePlans.forEach(normalizeWakePlan);
      }
    } catch (err) {}
  }

  async function save() {
    const toStore = JSON.parse(JSON.stringify(state));
    stripSecrets(toStore);
    localStorage.setItem(KEY, JSON.stringify(toStore));
    try {
      await timedFetch("/api/state", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state)
      });
    } catch (err) {}
    stripSecrets(state);
  }

  function refreshFormLabels() {
    const df = document.getElementById("form-device");
    const editingDev = !!(df && df.deviceId.value);
    const dTitle = document.getElementById("device-form-title");
    const dBtn = document.getElementById("btn-save-device");
    if (dTitle) dTitle.textContent = t(editingDev ? "devices.formEdit" : "devices.formAdd");
    if (dBtn) dBtn.textContent = t(editingDev ? "btn.saveChanges" : "btn.save");
    const ph = document.getElementById("device-pass-hint");
    if (ph) {
      const d = editingDev ? deviceById(df.deviceId.value) : null;
      ph.textContent = d && d.hasPassword ? t("dev.passwordKeep") : "";
    }
    const banner = document.getElementById("consent-banner");
    if (banner && !banner.hidden) banner.textContent = t("privacy.bannerDecline");
    const tf = document.getElementById("form-transfer");
    const editingJob = !!(tf && tf.jobId.value);
    const tTitle = document.getElementById("transfer-form-title");
    const tBtn = document.getElementById("btn-save-transfer");
    if (tTitle) tTitle.textContent = t(editingJob ? "transfers.formEdit" : "transfers.formAdd");
    if (tBtn) tBtn.textContent = t(editingJob ? "btn.saveChanges" : "btn.addJob");
    const wf = document.getElementById("form-wake");
    const editingWake = !!(wf && wf.planId.value);
    const wTitle = document.getElementById("wake-form-title");
    const wBtn = document.getElementById("btn-save-wake");
    if (wTitle) wTitle.textContent = t(editingWake ? "wake.formEdit" : "wake.formAdd");
    if (wBtn) wBtn.textContent = t(editingWake ? "btn.saveChanges" : "btn.addPlan");
  }

  function show(id) {
    document.querySelectorAll(".nav button[data-view]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.view === id);
    });
    document.querySelectorAll(".view").forEach((view) => {
      view.classList.toggle("active", view.id === "view-" + id);
    });
    if (id === "backup") loadBackups();
  }

  function fillDeviceSelects() {
    const html = state.devices
      .map((d) => {
        const name = deviceName(d.id);
        const typ = typeLabel(d.type);
        const label = name === typ ? name : name + " (" + typ + ")";
        return `<option value="${d.id}">${esc(label)}</option>`;
      })
      .join("");
    document.querySelectorAll("select[name='srcDevice'], select[name='dstDevice']").forEach((el) => {
      const prev = el.value;
      el.innerHTML = html;
      if ([...el.options].some((o) => o.value === prev)) el.value = prev;
    });
    const remote = state.devices.filter((d) => d.id !== "local");
    const wakeSel = document.querySelector("#form-wake select[name='deviceId']");
    const prevWake = wakeSel.value;
    wakeSel.innerHTML = remote.length
      ? remote.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("")
      : `<option value="">${esc(t("need.deviceConn"))}</option>`;
    if ([...wakeSel.options].some((o) => o.value === prevWake)) wakeSel.value = prevWake;
    backupWakeHint();
  }

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function formatBytes(n) {
    n = Number(n) || 0;
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
    if (n < 1073741824) return (n / 1048576).toFixed(1) + " MB";
    return (n / 1073741824).toFixed(2) + " GB";
  }

  function weekdayName(v) {
    return t("day." + String(v)) || t("day.1");
  }

  function weekdayOptions(selected) {
    const cur = String(selected || "1");
    return ["1", "2", "3", "4", "5", "6", "7"].map((v) => {
      return `<option value="${v}"${v === cur ? " selected" : ""}>${esc(t("day." + v))}</option>`;
    }).join("");
  }

  function wakeNeedsClock(auto) {
    return auto === "daily" || auto === "weekly" || auto === "biweekly" || auto === "monthly";
  }

  function wakeNeedsWeekday(auto) {
    return auto === "weekly" || auto === "biweekly" || auto === "monthly";
  }

  function normalizeWakePlan(p) {
    if (!p) return p;
    if (p.auto === "15" || p.auto === "30" || p.auto === "60") p.auto = "daily";
    if (wakeNeedsClock(p.auto) && !p.autoTime) p.autoTime = "22:00";
    if (wakeNeedsWeekday(p.auto) && !p.autoWeekday) p.autoWeekday = "1";
    return p;
  }

  function autoHint(auto, forBackup) {
    if (forBackup) {
      if (wakeNeedsClock(auto)) return t("autoHint.backupClock");
      return t("autoHint.backupManual");
    }
    if (auto === "daily") return t("autoHint.daily");
    if (auto === "weekly") return t("autoHint.weekly");
    if (auto === "biweekly") return t("autoHint.biweekly");
    if (auto === "monthly") return t("autoHint.monthly");
    if (auto === "15" || auto === "30" || auto === "60") return t("autoHint.interval");
    return t("autoHint.manual");
  }

  function syncAutoTimeField() {
    syncAutoWrap("transfer-auto", "wrap-auto-time", "auto-hint");
    const auto = document.getElementById("wake-auto");
    const wrap = document.getElementById("wrap-wake-auto-time");
    const dayWrap = document.getElementById("wrap-wake-weekday");
    const hint = document.getElementById("wake-auto-hint");
    if (auto && wrap) wrap.hidden = !wakeNeedsClock(auto.value);
    if (dayWrap) dayWrap.hidden = !wakeNeedsWeekday(auto.value);
    if (hint && auto) hint.textContent = autoHint(auto.value);
    const bAuto = document.getElementById("backup-auto");
    const bWrap = document.getElementById("wrap-backup-auto-time");
    const bDay = document.getElementById("wrap-backup-weekday");
    const bHint = document.getElementById("backup-auto-hint");
    if (bAuto && bWrap) bWrap.hidden = !wakeNeedsClock(bAuto.value);
    if (bDay) bDay.hidden = !wakeNeedsWeekday(bAuto.value);
    if (bHint && bAuto) bHint.textContent = autoHint(bAuto.value, true);
    backupWakeHint();
  }

  function backupWakeHint() {
    const f = document.getElementById("form-backup");
    const el = document.getElementById("backup-wake-hint");
    if (!f || !el || !f.dstDevice) return;
    const d = deviceById(f.dstDevice.value);
    if (!d || d.id === "local" || d.type === "local") {
      el.textContent = "";
      return;
    }
    if (String(d.mac || "").trim()) {
      el.textContent = t("mac.yes");
    } else {
      el.textContent = t("mac.no");
    }
  }

  function backupJobOpts() {
    const b = state.backup || {};
    return {
      id: "backup",
      auto: b.auto,
      autoTime: b.autoTime,
      autoWeekday: b.autoWeekday,
      enabled: b.enabled !== false,
      lastRun: b.lastRun
    };
  }

  function syncAutoWrap(selectId, wrapId, hintId) {
    const auto = document.getElementById(selectId);
    const wrap = document.getElementById(wrapId);
    const hint = document.getElementById(hintId);
    if (!auto || !wrap) return;
    wrap.hidden = auto.value !== "daily";
    if (hint) hint.textContent = autoHint(auto.value);
  }

  function autoLabel(job) {
    if (!job.auto) return t("label.manual");
    const time = job.autoTime || "22:00";
    const day = weekdayName(job.autoWeekday);
    if (job.auto === "daily") return t("label.dailyAt", { t: time });
    if (job.auto === "weekly") return t("label.weeklyAt", { d: day, t: time });
    if (job.auto === "biweekly") return t("label.biweeklyAt", { d: day, t: time });
    if (job.auto === "monthly") return t("label.monthlyAt", { d: day, t: time });
    if (job.auto === "60") return t("label.hourly");
    return t("label.everyMin", { n: job.auto });
  }

  function modeLabel(mode) {
    if (mode === "incr" || mode === "sync") return t("mode.incr");
    if (mode === "copy") return t("mode.copyShort");
    if (mode === "move") return t("mode.moveShort");
    if (mode === "full") return t("mode.full");
    return mode || "";
  }

  function isFast(t) {
    return !t || t.fast !== false;
  }

  function nextRunText(job) {
    const running = jobs[job.id];
    if (running && (running.status === "running" || running.status === "waiting")) return "";
    if (!job.auto || job.enabled === false) return "";
    if (job.auto === "daily") {
      const parts = String(job.autoTime || "22:00").split(":");
      const d = new Date();
      d.setHours(Number(parts[0]) || 22, Number(parts[1]) || 0, 0, 0);
      if (d.getTime() <= Date.now()) d.setDate(d.getDate() + 1);
      return t("next.start", { t: d.toLocaleTimeString(fmtLocale(), { hour: "2-digit", minute: "2-digit" }) });
    }
    if (wakeNeedsWeekday(job.auto)) {
      const parts = String(job.autoTime || "22:00").split(":");
      const hh = Number(parts[0]) || 22;
      const mm = Number(parts[1]) || 0;
      const want = Number(job.autoWeekday) || 1;
      const jsWant = want === 7 ? 0 : want;
      const d = new Date();
      d.setSeconds(0, 0);
      d.setHours(hh, mm, 0, 0);
      let guard = 0;
      while (d.getDay() !== jsWant || d.getTime() <= Date.now()) {
        d.setDate(d.getDate() + 1);
        d.setHours(hh, mm, 0, 0);
        if (++guard > 400) break;
      }
      if (job.auto === "biweekly" && job.lastRun) {
        const minNext = new Date(job.lastRun);
        if (!isNaN(minNext.getTime())) {
          minNext.setDate(minNext.getDate() + 13);
          while (d.getTime() < minNext.getTime()) d.setDate(d.getDate() + 7);
        }
      }
      if (job.auto === "monthly" && job.lastRun) {
        const last = new Date(job.lastRun);
        if (!isNaN(last.getTime())) {
          while (d.getFullYear() === last.getFullYear() && d.getMonth() === last.getMonth()) {
            d.setDate(d.getDate() + 7);
          }
        }
      }
      return t("next.start", { t: d.toLocaleString(fmtLocale(), { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) });
    }
    const mins = Number(job.auto) || 30;
    if (job.lastRun) {
      const next = new Date(job.lastRun);
      if (!isNaN(next.getTime())) {
        next.setMinutes(next.getMinutes() + mins);
        if (next.getTime() > Date.now()) {
          return t("next.try", { t: next.toLocaleTimeString(fmtLocale(), { hour: "2-digit", minute: "2-digit" }) });
        }
      }
    }
    return t("next.tryIn", { n: mins });
  }

  function progressHTML(job) {
    const j = jobs[job.id];
    if (!j || !j.status || j.status === "idle") {
      const nxt = nextRunText(job);
      return `<div class="progress"><p class="progress-label">${esc(nxt || t("prog.idle"))}</p></div>`;
    }
    const running = j.status === "running" || j.status === "waiting";
    const pct = Math.max(0, Math.min(100, Number(j.percent) || 0));
    let cls = "progress-fill";
    if (j.status === "waiting" || (j.status === "running" && !pct && j.detailKey !== "checking")) cls += " indeterminate";
    if (j.status === "ok") cls += " ok";
    if (j.status === "error") cls += " error";
    let label = locJob(j);
    if (j.status === "running" && j.bytesTotal) {
      label = (pct || 0) + " % · " + t("prog.of", { a: formatBytes(j.bytesDone), b: formatBytes(j.bytesTotal) });
      const extra = locJob(j);
      if (extra) label += " · " + extra;
    } else if (j.status === "running") {
      label = locJob(j) || t("job.rcloneSmb");
    } else if (j.status === "waiting") {
      label = locJob(j) || t("prog.wait");
    } else if (j.status === "ok") {
      label = t("prog.done") + (j.bytesDone ? " · " + formatBytes(j.bytesDone) : "");
      const extra = locJob(j);
      if (extra) label += " · " + extra;
    } else if (j.status === "error") {
      label = locJob(j) || t("prog.err");
    }
    return `<div class="progress">
      <div class="progress-track"><div class="${cls}" style="width:${running && !pct ? 38 : pct}%"></div></div>
      <p class="progress-label">${esc(label)}</p>
    </div>`;
  }

  function renderSummary() {
    const remote = state.devices.filter((d) => d.id !== "local");
    const auto = state.transfers.filter((t) => t.auto).length;
    const wakeOn = state.wakePlans.filter((p) => p.enabled).length;
    document.getElementById("summary-cards").innerHTML = `
      <article class="card">
        <h3>${esc(t("sum.devices"))}</h3>
        <p class="meta">${remote.length ? remote.map((d) => d.name).join(", ") : t("sum.onlyLocal")}</p>
        <span class="dot ${remote.length ? "ok" : ""}">${t("sum.connected", { n: remote.length })}</span>
      </article>
      <article class="card">
        <h3>${esc(t("sum.transfers"))}</h3>
        <p class="meta">${t("sum.tasks", { n: state.transfers.length, a: auto })}</p>
        <span class="dot ${Object.values(jobs).some((j) => j.status === "running" || j.status === "waiting") ? "ok" : state.transfers.length ? "ok" : ""}">${
          Object.values(jobs).some((j) => j.status === "running")
            ? t("sum.running")
            : Object.values(jobs).some((j) => j.status === "waiting")
              ? t("sum.waiting")
              : state.transfers.length
                ? t("sum.ready")
                : t("sum.none")
        }</span>
      </article>
      <article class="card">
        <h3>${esc(t("sum.wake"))}</h3>
        <p class="meta">${t("sum.plansN", { n: state.wakePlans.length })}</p>
        <span class="dot ${wakeOn ? "ok" : ""}">${wakeOn ? t("sum.activeN", { n: wakeOn }) : t("sum.noPlan")}</span>
      </article>
      <article class="card">
        <h3>${esc(t("nav.backup"))}</h3>
        <p class="meta">${state.backup ? (state.backup.auto ? autoLabel(state.backup) + " · " : "") + (state.backup.srcPath || "") + " → " + (state.backup.dstPath || "") : t("sum.backupUnset")}</p>
        <span class="dot ${state.backup ? "ok" : ""}">${state.backup ? (state.backup.auto && state.backup.enabled !== false ? autoLabel(state.backup) : t("sum.saved")) : t("sum.offline")}</span>
      </article>`;
  }

  function renderDevices() {
    const box = document.getElementById("device-list");
    box.innerHTML = state.devices.map((d) => {
      const fc = (state.folderCaches && state.folderCaches[d.id]) || {};
      let cacheLine = "";
      if (d.id !== "local") {
        if (fc.building) cacheLine = t("dev.cacheBuilding");
        else if (fc.ready) {
          cacheLine = t("dev.cacheReady") + (fc.partial ? t("dev.cachePartial") : "") + (fc.cachedAt ? " · " + new Date(fc.cachedAt).toLocaleString(fmtLocale()) : "");
        } else cacheLine = t("dev.cacheNone");
      }
      const extra = d.type === "local"
        ? t("dev.localVol")
        : (d.host || t("dev.noIp")) + (d.share ? " · " + d.share : "") + (d.mac ? " · MAC " + d.mac : " · " + t("dev.noMac"))
          + (cacheLine ? " · " + cacheLine : "");
      const tools = d.id === "local" ? "" : `
        <div class="tools">
          <button class="btn ok" data-wol="${d.id}">${esc(t("btn.wake"))}</button>
          <button class="btn" data-cache-device="${d.id}" ${fc.building ? "disabled" : ""}>${esc(t("btn.cache"))}</button>
          <button class="btn" data-edit-device="${d.id}">${esc(t("btn.edit"))}</button>
          <button class="btn danger" data-del-device="${d.id}">${esc(t("btn.remove"))}</button>
        </div>`;
      return `<article class="device"><div><h3>${esc(deviceName(d.id))}</h3><p class="meta">${esc(typeLabel(d.type))}<br>${esc(extra)}</p>
        <span class="dot ${d.id === "local" || d.host ? "ok" : ""}">${d.id === "local" ? t("dot.local") : "SMB"}</span></div>${tools}</article>`;
    }).join("");
  }

  function renderTransfers() {
    const n = state.transfers.length;
    const count = document.getElementById("transfer-count");
    if (count) count.textContent = n ? t("transfers.jobs") + " (" + n + ")" : t("transfers.jobs");
    const box = document.getElementById("transfer-list");
    if (!n) {
      box.innerHTML = `<p class="empty">${esc(t("empty.jobs"))}</p>`;
      return;
    }
    box.innerHTML = state.transfers.map((job, i) => {
      const j = jobs[job.id];
      const busy = j && (j.status === "running" || j.status === "waiting");
      const timeField = job.auto === "daily"
        ? `<input class="job-time" type="time" data-time-transfer="${job.id}" value="${esc(job.autoTime || "22:00")}" title="${esc(t("title.dailyTime"))}" />`
        : "";
      const editing = (document.querySelector("#form-transfer [name=jobId]") || {}).value === job.id;
      return `
      <article class="job${editing ? " editing" : ""}" data-job="${job.id}">
        <div>
          <h3>${i + 1}. ${esc(job.name)}</h3>
          <p class="meta">${esc(transferRoute(job))}<br>
          ${esc(modeLabel(job.mode))} · ${isFast(job) ? t("speed.fullShort") : t("speed.slowShort")} · ${esc(autoLabel(job))}<span data-run-flag${busy ? "" : " hidden"}> · ${esc(t("running"))}</span></p>
          ${timeField}
          <select class="job-speed" data-fast-transfer="${job.id}">
            <option value="1"${isFast(job) ? " selected" : ""}>${esc(t("speed.full"))}</option>
            <option value="0"${isFast(job) ? "" : " selected"}>${esc(t("speed.slow"))}</option>
          </select>
        </div>
        <div class="tools">
          <button class="toggle ${job.enabled === false ? "" : "on"}" data-toggle-transfer="${job.id}" type="button"><i></i></button>
          <button class="btn" data-run-transfer="${job.id}" ${busy ? "disabled" : ""}>${esc(t("btn.now"))}</button>
          <button class="btn" data-edit-transfer="${job.id}">${esc(t("btn.edit"))}</button>
          <button class="btn" data-copy-transfer="${job.id}">${esc(t("btn.copy"))}</button>
          <button class="btn danger" data-del-transfer="${job.id}">${esc(t("btn.delete"))}</button>
        </div>
        ${progressHTML(job)}
      </article>`;
    }).join("");
  }

  function extraFolderLabels(share, path, extras) {
    const list = [folderLabel(share, path)];
    (extras || []).forEach((raw) => {
      const i = String(raw).indexOf("|");
      if (i >= 0) list.push(folderLabel(raw.slice(0, i), raw.slice(i + 1)));
      else list.push(folderLabel(share, raw));
    });
    return list;
  }

  function renderWake() {
    const n = state.wakePlans.length;
    const count = document.getElementById("wake-count");
    if (count) count.textContent = n ? t("wake.plans") + " (" + n + ")" : t("wake.plans");
    const box = document.getElementById("wake-list");
    if (!n) {
      box.innerHTML = `<p class="empty">${esc(t("empty.plans"))}</p>`;
      return;
    }
    box.innerHTML = state.wakePlans.map((p, i) => {
      const srcs = extraFolderLabels(p.srcShare, p.srcPath, p.srcPaths);
      const extra = srcs.length > 1 ? " · " + t("wake.nFolders", { n: srcs.length }) : "";
      const j = jobs[p.id];
      const busy = j && (j.status === "running" || j.status === "waiting");
      const clock = wakeNeedsClock(p.auto);
      const timeField = clock
        ? `<input class="job-time" type="time" data-time-wake="${p.id}" value="${esc(p.autoTime || "22:00")}" title="${esc(t("title.startTime"))}" />`
        : "";
      const dayField = wakeNeedsWeekday(p.auto)
        ? `<select class="job-speed" data-weekday-wake="${p.id}" title="${esc(t("title.weekday"))}">${weekdayOptions(p.autoWeekday)}</select>`
        : "";
      const editing = (document.querySelector("#form-wake [name=planId]") || {}).value === p.id;
      return `
      <article class="job${editing ? " editing" : ""}" data-job="${p.id}">
        <div>
          <h3>${i + 1}. ${esc(p.name)}</h3>
          <p class="meta">${esc(deviceName(p.deviceId))} · ${p.direction === "pull" ? t("wake.pullShort") : t("wake.pushShort")} · ${t("wake.waitMin", { n: p.wait })}${extra} · ${esc(autoLabel(p))}<br>
          ${esc(srcs.join(", "))} → ${esc(folderLabel(p.dstShare, p.dstPath))}</p>
          ${dayField}
          ${timeField}
          <select class="job-speed" data-auto-wake="${p.id}" title="${esc(t("title.schedule"))}">
            <option value=""${!p.auto ? " selected" : ""}>${esc(t("auto.manual"))}</option>
            <option value="daily"${p.auto === "daily" ? " selected" : ""}>${esc(t("auto.daily"))}</option>
            <option value="weekly"${p.auto === "weekly" ? " selected" : ""}>${esc(t("auto.weekly"))}</option>
            <option value="biweekly"${p.auto === "biweekly" ? " selected" : ""}>${esc(t("auto.biweekly"))}</option>
            <option value="monthly"${p.auto === "monthly" ? " selected" : ""}>${esc(t("auto.monthly"))}</option>
          </select>
        </div>
        <div class="tools">
          <button class="toggle ${p.enabled ? "on" : ""}" data-toggle-wake="${p.id}" type="button" title="${esc(t("title.active"))}"><i></i></button>
          <button class="btn" data-run-wake="${p.id}" ${busy ? "disabled" : ""}>${esc(t("btn.now"))}</button>
          <button class="btn" data-edit-wake="${p.id}">${esc(t("btn.edit"))}</button>
          <button class="btn" data-copy-wake="${p.id}">${esc(t("btn.copy"))}</button>
          <button class="btn danger" data-del-wake="${p.id}">${esc(t("btn.delete"))}</button>
        </div>
        ${progressHTML({ id: p.id, auto: p.auto, autoTime: p.autoTime, autoWeekday: p.autoWeekday, enabled: p.enabled !== false, lastRun: p.lastRun })}
      </article>`;
    }).join("");
  }

  function renderSchedules() {
    const items = [];
    state.transfers.filter((job) => job.auto).forEach((job) => {
      const extra = job.auto === "daily"
        ? t("sched.xferDaily", { t: job.autoTime || "22:00" })
        : t("sched.xferInterval", { label: autoLabel(job) });
      items.push({
        title: job.name,
        detail: t("sched.xfer", { extra }),
        on: job.enabled !== false,
        kind: "transfer",
        id: job.id
      });
    });
    state.wakePlans.filter((p) => p.auto).forEach((p) => {
      const extra = t("sched.wakeWait", { label: autoLabel(p), n: p.wait });
      items.push({
        title: p.name,
        detail: t("sched.wake", { extra }),
        on: !!p.enabled,
        kind: "wake",
        id: p.id
      });
    });
    if (state.backup && state.backup.auto) {
      const wait = state.backup.wait || "20";
      items.push({
        title: t("backup.title"),
        detail: t("sched.backup", { label: autoLabel(state.backup), n: wait }),
        on: state.backup.enabled !== false,
        kind: "backup",
        id: "backup"
      });
    }
    const box = document.getElementById("schedule-list");
    if (!items.length) {
      box.innerHTML = `<p class="empty">${esc(t("empty.sched"))}</p>`;
      return;
    }
    box.innerHTML = items.map((it) => `
      <article class="job">
        <div><h3>${esc(it.title)}</h3><p class="meta">${esc(it.detail)}</p></div>
        <button class="toggle ${it.on ? "on" : ""}" data-sched="${it.kind}:${it.id}" type="button"><i></i></button>
      </article>`).join("");
  }

  function renderLog() {
    document.getElementById("log-box").textContent = state.logs.join("\n") || t("empty.log");
  }

  function renderAll() {
    fillDeviceSelects();
    renderSummary();
    renderDevices();
    renderTransfers();
    renderWake();
    renderSchedules();
    renderLog();
    if (state.backup) {
      const f = document.getElementById("form-backup");
      if (f.srcDevice) f.srcDevice.value = state.backup.srcDevice || "local";
      if (f.dstDevice) f.dstDevice.value = state.backup.dstDevice || "local";
      if (f.keep && state.backup.keep) f.keep.value = state.backup.keep;
      if (f.auto) f.auto.value = state.backup.auto || "";
      if (f.autoTime) f.autoTime.value = state.backup.autoTime || "22:00";
      if (f.autoWeekday) f.autoWeekday.value = state.backup.autoWeekday || "1";
      if (f.wait) f.wait.value = String(state.backup.wait || "20");
      const protect = document.getElementById("backup-protect");
      const wrapPass = document.getElementById("wrap-backup-pass");
      const passHint = document.getElementById("backup-pass-hint");
      if (protect) protect.checked = !!state.backup.hasPassword;
      if (wrapPass) wrapPass.hidden = !protect || !protect.checked;
      const p1 = document.getElementById("backup-pass");
      const p2 = document.getElementById("backup-pass2");
      if (p1) p1.value = "";
      if (p2) p2.value = "";
      if (passHint) {
        passHint.textContent = state.backup.hasPassword ? t("pass.on") : t("pass.off");
      }
      picked.backupSrc = { share: state.backup.srcShare || "", path: state.backup.srcPath || "" };
      picked.backupDst = { share: state.backup.dstShare || "", path: state.backup.dstPath || "" };
      syncAutoTimeField();
    }
    refreshPicks();
    const backupProg = document.getElementById("backup-progress");
    if (backupProg) {
      backupProg.innerHTML = state.backup ? progressHTML(backupJobOpts()) : "";
    }
    const restoreProg = document.getElementById("restore-progress");
    if (restoreProg) {
      restoreProg.innerHTML = jobs["backup-restore"] ? progressHTML({ id: "backup-restore" }) : "";
    }
    syncAutoTimeField();
    refreshFormLabels();
  }

  async function sendWol(deviceId) {
    const d = deviceById(deviceId);
    if (!d || d.id === "local") {
      alert(t("err.needRemote"));
      return;
    }
    const note = (msg) => {
      const el = document.getElementById("wake-msg") || document.getElementById("device-msg");
      if (el) el.textContent = msg;
      const dm = document.getElementById("device-msg");
      if (dm && dm !== el) dm.textContent = msg;
    };
    try {
      const res = await timedFetch("/api/wol", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deviceId: d.id, mac: d.mac || "", host: d.host || "" })
      }, 8000);
      let body = {};
      try { body = await res.json(); } catch (err) {}
      if (res.ok) {
        const noteMsg = locNote(body) || t("msg.wolSent");
        log(t("log.wol", { m: noteMsg }));
        note(noteMsg);
        return;
      }
      const err = locErr(body);
      log(t("log.wolFail", { m: err }));
      alert(err);
    } catch (err) {
      log(t("log.wolOffline"));
      alert(t("err.wolOffline"));
    }
  }

  async function saveFolderCache(deviceId) {
    const d = deviceById(deviceId);
    try {
      const res = await timedFetch("/api/folder-cache", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: deviceId })
      }, 8000);
      if (!res.ok) {
        alert(t("err.cache"));
        return;
      }
      log(t("log.cache", { n: d ? d.name : deviceId }));
      if (!state.folderCaches) state.folderCaches = {};
      state.folderCaches[deviceId] = Object.assign({}, state.folderCaches[deviceId], { building: true });
      renderDevices();
    } catch (err) {
      alert(t("err.offline"));
    }
  }

  async function startNasJob(id, name) {
    try {
      const res = await timedFetch("/api/jobs/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        log(t("log.xferStart", { n: name || id }));
        await pollJobs();
        return true;
      }
      log(t("log.xferFail", { n: name || id }));
    } catch (err) {
      log(t("log.xferOffline"));
    }
    return false;
  }

  document.querySelectorAll(".nav button[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => show(btn.dataset.view));
  });
  document.querySelector("[data-view='devices'].btn, .section-head [data-view='devices']")?.addEventListener("click", () => show("devices"));
  document.querySelector(".section-head .btn.ghost")?.addEventListener("click", () => show("devices"));

  document.getElementById("btn-add-device").addEventListener("click", () => {
    resetDeviceForm();
    document.getElementById("form-device").scrollIntoView({ block: "nearest" });
    document.querySelector("#form-device [name=name]").focus();
  });
  document.getElementById("btn-cancel-device").addEventListener("click", () => resetDeviceForm());

  document.getElementById("form-device").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const data = Object.fromEntries(new FormData(ev.target).entries());
    if (!data.name || !data.host) {
      document.getElementById("device-msg").textContent = t("err.nameIp");
      return;
    }
    if ((data.password || "") && !privacy.accepted) {
      document.getElementById("device-msg").textContent = t("err.consentPass");
      document.getElementById("modal-privacy").classList.add("open");
      return;
    }
    const rec = {
      type: data.type === "nas" ? "nas" : "pc",
      name: data.name,
      host: data.host.trim(),
      share: (data.share || "").trim(),
      user: data.user || "",
      password: data.password || "",
      mac: (data.mac || "").trim()
    };
    if (rec.password) rec.hasPassword = true;
    const id = (data.deviceId || "").trim();
    if (id && id !== "local") {
      const d = state.devices.find((x) => x.id === id);
      if (!d) {
        document.getElementById("device-msg").textContent = t("err.notFound");
        return;
      }
      if (!rec.mac) rec.mac = d.mac || "";
      Object.assign(d, rec);
      if (!rec.password) d.hasPassword = !!d.hasPassword;
      log(rec.name + " (" + rec.host + ")");
      document.getElementById("device-msg").textContent = t("msg.saved");
    } else {
      state.devices.push(Object.assign({ id: uid("dev") }, rec));
      log(rec.name + " (" + rec.host + ")");
      document.getElementById("device-msg").textContent = t("msg.deviceAdded", { n: rec.name });
    }
    await save();
    resetDeviceForm();
    renderAll();
    show("devices");
  });

  document.getElementById("btn-cancel-transfer").addEventListener("click", () => {
    resetTransferForm();
    renderTransfers();
  });
  document.getElementById("btn-cancel-wake").addEventListener("click", () => {
    resetWakeForm();
    renderWake();
  });

  document.getElementById("form-transfer").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const data = Object.fromEntries(new FormData(ev.target).entries());
    const srcs = picked.transferSrc.slice();
    const dst = picked.transferDst;
    if (!data.name || !srcs.length || !dst) {
      document.getElementById("transfer-msg").textContent = t("err.nameFolders");
      return;
    }
    const first = srcs[0];
    const extra = srcs.slice(1).map((s) => s.share + "|" + (s.path || ""));
    if (data.auto === "daily" && !data.autoTime) data.autoTime = "22:00";
    const rec = {
      name: data.name,
      srcDevice: data.srcDevice,
      srcShare: first.share,
      srcPath: first.path,
      srcPaths: extra,
      dstDevice: data.dstDevice,
      dstShare: dst.share,
      dstPath: dst.path,
      mode: data.mode,
      fast: data.fast !== "0",
      auto: data.auto,
      autoTime: data.autoTime || ""
    };
    const id = (data.jobId || "").trim();
    let msg = "";
    if (id) {
      const job = state.transfers.find((x) => x.id === id);
      if (!job) {
        document.getElementById("transfer-msg").textContent = t("err.jobNotFound");
        return;
      }
      Object.assign(job, rec);
      log(t("log.jobChanged", { n: rec.name }));
      msg = t("msg.jobSaved", { n: rec.name });
    } else {
      state.transfers.push(Object.assign({ id: uid("tr"), enabled: true, lastRun: "" }, rec));
      log(t("log.jobAdded", { n: data.name, c: state.transfers.length }));
      msg = t("msg.jobAdded", { n: data.name, c: state.transfers.length });
    }
    resetTransferForm();
    document.getElementById("transfer-msg").textContent = msg;
    await save();
    renderAll();
  });

  document.getElementById("form-wake").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const data = Object.fromEntries(new FormData(ev.target).entries());
    if (!data.deviceId) {
      document.getElementById("wake-msg").textContent = t("err.needRemote");
      return;
    }
    if (!data.name || !picked.wakeSrc.length || !picked.wakeDst) {
      document.getElementById("wake-msg").textContent = t("err.nameFolders");
      return;
    }
    const srcs = picked.wakeSrc.slice();
    const first = srcs[0];
    const extra = srcs.slice(1).map((s) => s.share + "|" + (s.path || ""));
    if (wakeNeedsClock(data.auto) && !data.autoTime) data.autoTime = "22:00";
    if (wakeNeedsWeekday(data.auto) && !data.autoWeekday) data.autoWeekday = "1";
    const rec = {
      name: data.name,
      deviceId: data.deviceId,
      direction: data.direction,
      wait: data.wait,
      srcShare: first.share,
      srcPath: first.path,
      srcPaths: extra,
      dstShare: picked.wakeDst.share,
      dstPath: picked.wakeDst.path,
      auto: data.auto || "",
      autoTime: data.autoTime || "",
      autoWeekday: data.autoWeekday || ""
    };
    const id = (data.planId || "").trim();
    let msg = "";
    if (id) {
      const plan = state.wakePlans.find((x) => x.id === id);
      if (!plan) {
        document.getElementById("wake-msg").textContent = t("err.planNotFound");
        return;
      }
      Object.assign(plan, rec);
      log(t("log.planChanged", { n: rec.name }));
      msg = t("msg.planSaved", { n: rec.name });
    } else {
      state.wakePlans.push(Object.assign({ id: uid("wk"), enabled: true, lastRun: "" }, rec));
      log(t("log.planAdded", { n: data.name, c: srcs.length }));
      msg = t("msg.planAdded", { n: data.name, c: srcs.length });
      if (data.auto) {
        msg += t("msg.planLater");
      }
    }
    resetWakeForm();
    document.getElementById("wake-msg").textContent = msg;
    await save();
    renderAll();
  });

  document.getElementById("btn-wol").addEventListener("click", () => {
    const id = document.querySelector("#form-wake select[name='deviceId']").value;
    if (id) sendWol(id);
  });

  document.getElementById("form-backup").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (await saveBackupFromForm()) {
      let msg = t("msg.backupSaved");
      if (state.backup && state.backup.auto) {
        msg += t("msg.backupLater");
      }
      document.getElementById("backup-msg").textContent = msg;
      renderAll();
    }
  });

  async function saveBackupFromForm() {
    const f = document.getElementById("form-backup");
    const data = Object.fromEntries(new FormData(f).entries());
    if (!picked.backupSrc || !picked.backupDst) {
      document.getElementById("backup-msg").textContent = t("err.needPick");
      return false;
    }
    const protect = document.getElementById("backup-protect");
    const wrapPass = document.getElementById("wrap-backup-pass");
    const p1 = document.getElementById("backup-pass");
    const p2 = document.getElementById("backup-pass2");
    const usePass = !!(protect && protect.checked);
    if (usePass && !privacy.accepted) {
      document.getElementById("backup-msg").textContent = t("err.consentPass");
      document.getElementById("modal-privacy").classList.add("open");
      return false;
    }
    if (wrapPass) wrapPass.hidden = !usePass;
    const prev = state.backup || {};
    if (wakeNeedsClock(data.auto) && !data.autoTime) data.autoTime = "22:00";
    if (wakeNeedsWeekday(data.auto) && !data.autoWeekday) data.autoWeekday = "1";
    let password = "";
    let passwordClear = false;
    if (!usePass) {
      passwordClear = true;
    } else {
      const a = (p1 && p1.value) || "";
      const b = (p2 && p2.value) || "";
      if (a || b) {
        if (a !== b) {
          document.getElementById("backup-msg").textContent = t("err.passMismatch");
          return false;
        }
        if (a.length < 4) {
          document.getElementById("backup-msg").textContent = t("err.passShort");
          return false;
        }
        password = a;
      } else if (!prev.hasPassword) {
        document.getElementById("backup-msg").textContent = t("err.passNeed");
        return false;
      }
    }
    state.backup = {
      srcDevice: data.srcDevice,
      srcShare: picked.backupSrc.share,
      srcPath: picked.backupSrc.path,
      dstDevice: data.dstDevice,
      dstShare: picked.backupDst.share,
      dstPath: picked.backupDst.path,
      keep: data.keep,
      mode: "archive",
      auto: data.auto || "",
      autoTime: data.autoTime || "22:00",
      autoWeekday: data.autoWeekday || "1",
      wait: data.wait || "20",
      lastRun: prev.lastRun || "",
      enabled: prev.enabled !== false,
      password,
      passwordClear,
      hasPassword: usePass
    };
    log(t("log.backupSaved", {
      a: folderLabel(picked.backupSrc.share, picked.backupSrc.path),
      b: folderLabel(picked.backupDst.share, picked.backupDst.path)
    }));
    await save();
    loadBackups();
    return true;
  }

  document.getElementById("btn-run-backup").addEventListener("click", async () => {
    if (!(await saveBackupFromForm())) return;
    document.getElementById("backup-msg").textContent = t("msg.backupStart");
    await startNasJob("backup", t("backup.title"));
    renderAll();
    loadBackups();
  });

  document.getElementById("btn-pick-backup-restore").addEventListener("click", () => {
    startPicker("backupRestoreDst", false, "local");
  });
  document.getElementById("btn-restore-backup").addEventListener("click", async () => {
    const names = [...document.querySelectorAll("#backup-archive-list [data-archive]:checked")].map((el) => el.dataset.archive);
    const msg = document.getElementById("restore-msg");
    if (!names.length) {
      msg.textContent = t("err.needArchive");
      return;
    }
    if (!picked.backupRestoreDst) {
      msg.textContent = t("err.needRestore");
      return;
    }
    msg.textContent = t("msg.restoreStart");
    try {
      const res = await timedFetch("/api/backup/restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          names,
          destShare: picked.backupRestoreDst.share,
          destPath: picked.backupRestoreDst.path || "",
          password: (document.getElementById("restore-pass") || {}).value || ""
        })
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        msg.textContent = locErr(body) || t("err.restoreStart");
        return;
      }
      log(t("log.restoreStart", { n: names.join(", ") }));
      await pollJobs();
    } catch (err) {
      msg.textContent = t("err.offline");
    }
  });

  async function loadBackups() {
    const box = document.getElementById("backup-archive-list");
    if (!box) return;
    if (!state.backup) {
      box.innerHTML = `<p class="empty">${esc(t("empty.backupNeed"))}</p>`;
      return;
    }
    try {
      const res = await timedFetch("/api/backups", { cache: "no-store" }, 20000);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        box.innerHTML = `<p class="empty">${esc(locMsg(data.errorKey, data.errorArg) || data.error || t("empty.archivesErr"))}</p>`;
        return;
      }
      const list = data.archives || [];
      if (!list.length) {
        box.innerHTML = `<p class="empty">${esc(t("empty.archives"))}</p>`;
        return;
      }
      box.innerHTML = list.map((a) => {
        const when = a.time ? new Date(a.time).toLocaleString(fmtLocale()) : "";
        const lock = a.encrypted ? t("lock.yes") : "";
        return `<article class="job">
          <label class="archive-pick">
            <input type="checkbox" data-archive="${esc(a.name)}" />
            <div><h3>${esc(a.name)}</h3><p class="meta">${esc(formatBytes(a.size))}${when ? " · " + when : ""}${lock}</p></div>
          </label>
        </article>`;
      }).join("");
    } catch (err) {
      box.innerHTML = `<p class="empty">${esc(t("err.offline"))}</p>`;
    }
  }

  document.getElementById("btn-pick-src").addEventListener("click", () => {
    startPicker("transferSrc", true, document.querySelector("#form-transfer [name=srcDevice]").value);
  });
  document.getElementById("btn-pick-dst").addEventListener("click", () => {
    startPicker("transferDst", false, document.querySelector("#form-transfer [name=dstDevice]").value);
  });
  document.getElementById("btn-pick-wake-src").addEventListener("click", () => {
    const dir = document.querySelector("#form-wake [name=direction]").value;
    const remote = document.querySelector("#form-wake [name=deviceId]").value;
    startPicker("wakeSrc", true, dir === "pull" ? remote : "local");
  });
  document.getElementById("btn-pick-wake-dst").addEventListener("click", () => {
    const dir = document.querySelector("#form-wake [name=direction]").value;
    const remote = document.querySelector("#form-wake [name=deviceId]").value;
    startPicker("wakeDst", false, dir === "push" ? remote : "local");
  });
  document.getElementById("btn-pick-backup-src").addEventListener("click", () => {
    startPicker("backupSrc", false, document.querySelector("#form-backup [name=srcDevice]").value);
  });
  document.getElementById("btn-pick-backup-dst").addEventListener("click", () => {
    startPicker("backupDst", false, document.querySelector("#form-backup [name=dstDevice]").value);
  });
  document.getElementById("pick-cancel").addEventListener("click", () => openPickModal(false));
  document.getElementById("modal-pick").addEventListener("click", (ev) => {
    if (ev.target.id === "modal-pick") openPickModal(false);
  });
  document.getElementById("pick-up").addEventListener("click", () => {
    if (pick.path) pick.path = pick.path.split("/").slice(0, -1).join("/");
    else pick.share = "";
    loadPickList();
  });
  document.getElementById("pick-here").addEventListener("click", () => {
    if (!pick.share) {
      alert(t("err.needShare"));
      return;
    }
    applyPicked({ share: pick.share, path: pick.path }, false);
  });
  document.getElementById("pick-checked").addEventListener("click", () => {
    const boxes = [...document.querySelectorAll("#pick-list [data-pick-idx]:checked")];
    if (!boxes.length) {
      alert(t("err.needCheck"));
      return;
    }
    boxes.forEach((box) => {
      const e = pick.entries[Number(box.dataset.pickIdx)];
      if (e) applyPicked(e, true);
    });
    openPickModal(false);
    refreshPicks();
  });
  document.getElementById("pick-list").addEventListener("click", (ev) => {
    const openBtn = ev.target.closest("[data-pick-open]");
    const selBtn = ev.target.closest("[data-pick-sel]");
    if (openBtn) {
      const e = pick.entries[Number(openBtn.dataset.pickOpen)];
      if (!e) return;
      if (e.kind === "share") { pick.share = e.share; pick.path = ""; }
      else { pick.share = e.share; pick.path = e.path; }
      loadPickList();
    } else if (selBtn) {
      const e = pick.entries[Number(selBtn.dataset.pickSel)];
      if (e) applyPicked(e, pick.multi);
    }
  });
  document.body.addEventListener("click", (ev) => {
    const chip = ev.target.closest("[data-chip]");
    if (!chip) return;
    const [id, idx] = chip.dataset.chip.split(":");
    const i = Number(idx);
    if (id === "src-chips") picked.transferSrc.splice(i, 1);
    else if (id === "dst-chips") picked.transferDst = null;
    else if (id === "wake-src-chips") picked.wakeSrc.splice(i, 1);
    else if (id === "wake-dst-chips") picked.wakeDst = null;
    else if (id === "backup-src-chips") picked.backupSrc = null;
    else if (id === "backup-dst-chips") picked.backupDst = null;
    else if (id === "backup-restore-chips") picked.backupRestoreDst = null;
    refreshPicks();
  });

  document.getElementById("btn-clear-log").addEventListener("click", async () => {
    state.logs = [];
    await save();
    renderAll();
  });

  document.body.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("[data-del-device],[data-edit-device],[data-wol],[data-cache-device],[data-del-transfer],[data-edit-transfer],[data-run-transfer],[data-copy-transfer],[data-toggle-transfer],[data-del-wake],[data-edit-wake],[data-run-wake],[data-copy-wake],[data-toggle-wake],[data-sched]");
    if (!btn) return;
    if (btn.dataset.delDevice) {
      const delId = btn.dataset.delDevice;
      state.devices = state.devices.filter((d) => d.id !== delId);
      const f = document.getElementById("form-device");
      if (f.deviceId.value === delId) resetDeviceForm();
      log(t("log.deviceRemoved"));
    } else if (btn.dataset.editDevice) {
      const d = state.devices.find((x) => x.id === btn.dataset.editDevice);
      if (d) fillDeviceForm(d);
      return;
    } else if (btn.dataset.wol) {
      await sendWol(btn.dataset.wol);
      return;
    } else if (btn.dataset.cacheDevice) {
      await saveFolderCache(btn.dataset.cacheDevice);
      return;
    } else if (btn.dataset.delTransfer) {
      const delId = btn.dataset.delTransfer;
      state.transfers = state.transfers.filter((x) => x.id !== delId);
      const f = document.getElementById("form-transfer");
      if (f.jobId.value === delId) resetTransferForm();
    } else if (btn.dataset.editTransfer) {
      const job = state.transfers.find((x) => x.id === btn.dataset.editTransfer);
      if (job) fillTransferForm(job);
      return;
    } else if (btn.dataset.copyTransfer) {
      const job = state.transfers.find((x) => x.id === btn.dataset.copyTransfer);
      if (job) {
        state.transfers.push(Object.assign({}, job, { id: uid("tr"), name: t("name.copy", { n: job.name }), lastRun: "" }));
        log(t("log.jobCopied", { n: job.name }));
      }
    } else if (btn.dataset.toggleTransfer) {
      const job = state.transfers.find((x) => x.id === btn.dataset.toggleTransfer);
      if (job) job.enabled = job.enabled === false;
    } else if (btn.dataset.runTransfer) {
      const job = state.transfers.find((x) => x.id === btn.dataset.runTransfer);
      await startNasJob(btn.dataset.runTransfer, job ? job.name : btn.dataset.runTransfer);
      await save();
      renderAll();
      return;
    } else if (btn.dataset.delWake) {
      const delId = btn.dataset.delWake;
      state.wakePlans = state.wakePlans.filter((x) => x.id !== delId);
      const f = document.getElementById("form-wake");
      if (f.planId.value === delId) resetWakeForm();
    } else if (btn.dataset.editWake) {
      const p = state.wakePlans.find((x) => x.id === btn.dataset.editWake);
      if (p) fillWakeForm(p);
      return;
    } else if (btn.dataset.copyWake) {
      const p = state.wakePlans.find((x) => x.id === btn.dataset.copyWake);
      if (p) {
        state.wakePlans.push(Object.assign({}, p, { id: uid("wk"), name: t("name.copy", { n: p.name }), enabled: true, lastRun: "" }));
        log(t("log.planCopied", { n: p.name }));
      }
    } else if (btn.dataset.runWake) {
      const p = state.wakePlans.find((x) => x.id === btn.dataset.runWake);
      if (p) {
        log(t("log.wakeStart", { n: p.name }));
        await startNasJob(p.id, p.name);
      }
    } else if (btn.dataset.toggleWake) {
      const p = state.wakePlans.find((x) => x.id === btn.dataset.toggleWake);
      if (p) p.enabled = !p.enabled;
    } else if (btn.dataset.sched) {
      const [kind, id] = btn.dataset.sched.split(":");
      if (kind === "wake") {
        const p = state.wakePlans.find((x) => x.id === id);
        if (p) p.enabled = !p.enabled;
      } else if (kind === "transfer") {
        const job = state.transfers.find((x) => x.id === id);
        if (job) job.enabled = job.enabled === false;
      } else if (kind === "backup" && state.backup) {
        state.backup.enabled = state.backup.enabled !== false ? false : true;
      }
    }
    await save();
    renderAll();
  });

  document.body.addEventListener("change", async (ev) => {
    const timeEl = ev.target.closest("[data-time-transfer]");
    if (timeEl) {
      const job = state.transfers.find((x) => x.id === timeEl.dataset.timeTransfer);
      if (job) {
        job.autoTime = timeEl.value || "22:00";
        log(t("log.startTime", { n: job.name, t: job.autoTime }));
        await save();
        renderSchedules();
      }
      return;
    }
    const wakeTime = ev.target.closest("[data-time-wake]");
    if (wakeTime) {
      const p = state.wakePlans.find((x) => x.id === wakeTime.dataset.timeWake);
      if (p) {
        p.autoTime = wakeTime.value || "22:00";
        log(t("log.startTime", { n: p.name, t: p.autoTime }));
        await save();
        renderSchedules();
      }
      return;
    }
    const wakeAuto = ev.target.closest("[data-auto-wake]");
    if (wakeAuto) {
      const p = state.wakePlans.find((x) => x.id === wakeAuto.dataset.autoWake);
      if (p) {
        p.auto = wakeAuto.value || "";
        if (wakeNeedsClock(p.auto) && !p.autoTime) p.autoTime = "22:00";
        if (wakeNeedsWeekday(p.auto) && !p.autoWeekday) p.autoWeekday = "1";
        log(t("log.schedule", { n: p.name, s: autoLabel(p) }));
        await save();
        renderAll();
      }
      return;
    }
    const wakeDay = ev.target.closest("[data-weekday-wake]");
    if (wakeDay) {
      const p = state.wakePlans.find((x) => x.id === wakeDay.dataset.weekdayWake);
      if (p) {
        p.autoWeekday = wakeDay.value || "1";
        log(t("log.weekday", { n: p.name, d: weekdayName(p.autoWeekday) }));
        await save();
        renderAll();
      }
      return;
    }
    const fastEl = ev.target.closest("[data-fast-transfer]");
    if (fastEl) {
      const job = state.transfers.find((x) => x.id === fastEl.dataset.fastTransfer);
      if (job) {
        job.fast = fastEl.value !== "0";
        log(t("log.speed", { n: job.name, s: job.fast ? t("speed.fullShort") : t("speed.slowShort") }));
        await save();
      }
    }
  });

  document.getElementById("transfer-auto").addEventListener("change", syncAutoTimeField);
  document.getElementById("wake-auto").addEventListener("change", syncAutoTimeField);
  document.getElementById("backup-auto").addEventListener("change", syncAutoTimeField);
  document.getElementById("backup-protect").addEventListener("change", () => {
    const wrap = document.getElementById("wrap-backup-pass");
    const protect = document.getElementById("backup-protect");
    const passHint = document.getElementById("backup-pass-hint");
    if (wrap && protect) wrap.hidden = !protect.checked;
    if (passHint && protect) passHint.textContent = protect.checked ? t("pass.on") : t("pass.off");
  });
  document.querySelector("#form-backup select[name='dstDevice']").addEventListener("change", backupWakeHint);

  function jobIsBusy(id) {
    const j = jobs[id];
    return !!(j && (j.status === "running" || j.status === "waiting"));
  }

  function cacheSig(c) {
    if (!c || typeof c !== "object") return "";
    return Object.keys(c).sort().map((k) => {
      const x = c[k] || {};
      return k + ":" + (x.building ? "1" : "0") + (x.ready ? "1" : "0") + (x.partial ? "1" : "0") + ":" + (x.cachedAt || "");
    }).join("|");
  }

  function patchJobList(box, items) {
    if (!box) return false;
    if (!items.length) return !box.querySelector("article[data-job]");
    const cards = [...box.querySelectorAll("article[data-job]")];
    if (cards.length !== items.length) return false;
    for (let i = 0; i < items.length; i++) {
      if (cards[i].getAttribute("data-job") !== items[i].id) return false;
    }
    items.forEach((item) => {
      const art = box.querySelector('article[data-job="' + item.id + '"]');
      if (!art) return;
      const prog = art.querySelector(".progress");
      if (prog) prog.outerHTML = progressHTML(item);
      const busy = jobIsBusy(item.id);
      const runBtn = art.querySelector("[data-run-transfer], [data-run-wake]");
      if (runBtn) runBtn.disabled = busy;
      const flag = art.querySelector("[data-run-flag]");
      if (flag) flag.hidden = !busy;
    });
    return true;
  }

  let lastCacheSig = "";

  async function pollJobs() {
    try {
      const res = await timedFetch("/api/jobs", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      jobs = data && typeof data === "object" ? data : {};
      const tBox = document.getElementById("transfer-list");
      if (!patchJobList(tBox, state.transfers)) renderTransfers();
      const wBox = document.getElementById("wake-list");
      if (!patchJobList(wBox, state.wakePlans)) renderWake();
      renderSummary();
      const backupProg = document.getElementById("backup-progress");
      if (backupProg && state.backup) backupProg.innerHTML = progressHTML(backupJobOpts());
      const restoreProg = document.getElementById("restore-progress");
      if (restoreProg) restoreProg.innerHTML = jobs["backup-restore"] ? progressHTML({ id: "backup-restore" }) : "";
      const bJob = jobs.backup;
      const rJob = jobs["backup-restore"];
      if (bJob && (bJob.status === "ok" || bJob.status === "error") && bJob.status !== pollBackupStatus) {
        loadBackups();
        const el = document.getElementById("backup-msg");
        if (el && (bJob.detailKey || bJob.detail)) el.textContent = locJob(bJob);
      }
      pollBackupStatus = bJob ? bJob.status : "";
      if (rJob && rJob.status === "ok") {
        const el = document.getElementById("restore-msg");
        if (el) el.textContent = locJob(rJob) || t("msg.restoreOk");
      }
      if (rJob && rJob.status === "error") {
        const el = document.getElementById("restore-msg");
        if (el) el.textContent = locJob(rJob) || t("msg.restoreFail");
      }
      try {
        const cr = await timedFetch("/api/folder-cache", { cache: "no-store" }, 4000);
        if (cr.ok) {
          const caches = await cr.json();
          if (caches && typeof caches === "object") {
            const sig = cacheSig(caches);
            if (sig !== lastCacheSig) {
              lastCacheSig = sig;
              state.folderCaches = caches;
              renderDevices();
            }
          }
        }
      } catch (e) {}
    } catch (err) {}
  }

  async function loadPrivacy() {
    try {
      const res = await timedFetch("/api/privacy", { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        privacy.decided = !!data.decided;
        privacy.accepted = !!data.accepted;
        if (data.privacyUrl) {
          const a = document.getElementById("privacy-link");
          const f = document.getElementById("foot-privacy");
          if (a) a.href = data.privacyUrl;
          if (f) f.href = data.privacyUrl;
        }
        if (data.helpUrl) {
          const h = document.getElementById("foot-help");
          if (h) h.href = data.helpUrl;
        }
        if (data.issuesUrl) {
          const i = document.getElementById("foot-issues");
          if (i) i.href = data.issuesUrl;
        }
      }
    } catch (err) {}
    const modal = document.getElementById("modal-privacy");
    if (modal) modal.classList.toggle("open", !privacy.decided);
    const banner = document.getElementById("consent-banner");
    if (banner) {
      banner.hidden = !(privacy.decided && !privacy.accepted);
      banner.textContent = t("privacy.bannerDecline");
    }
    const protect = document.getElementById("backup-protect");
    if (protect) protect.disabled = privacy.decided && !privacy.accepted;
  }

  async function postConsent(accepted) {
    try {
      await timedFetch("/api/privacy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accepted: !!accepted })
      });
    } catch (err) {}
    privacy.decided = true;
    privacy.accepted = !!accepted;
    document.getElementById("modal-privacy").classList.remove("open");
    await loadPrivacy();
    renderAll();
  }

  syncAutoTimeField();
  applyI18n();
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      setLang(btn.getAttribute("data-lang"));
      renderAll();
    });
  });
  document.getElementById("privacy-agree").addEventListener("click", () => postConsent(true));
  document.getElementById("privacy-decline").addEventListener("click", () => postConsent(false));
  loadPrivacy().then(() => load()).then(async () => {
    stripSecrets(state);
    renderAll();
    await pollJobs();
    setInterval(pollJobs, 800);
  });
})();
