# -*- coding: utf-8 -*-
"""Generate security-hub app/i18n.py with de/en/zh/fr/es/it/pl/ru/tr/hr."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "app" / "i18n.py"
STRINGS_JSON = ROOT / "_en_strings.json"
PUBLIC = Path(
    r"E:\APP PROJEKTE\NAS_Admin_Project\_runlevel_ugos_apps\apps\security-hub\app\i18n.py"
)

_PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
LANGS_EXTRA = ("fr", "es", "it", "pl", "ru", "tr", "hr", "zh")
ORDER = ["de", "en", "zh", "fr", "es", "it", "pl", "ru", "tr", "hr"]
LABELS = {
    "de": "DE",
    "en": "EN",
    "zh": "中文",
    "fr": "FR",
    "es": "ES",
    "it": "IT",
    "pl": "PL",
    "ru": "RU",
    "tr": "TR",
    "hr": "HR",
}

if STRINGS_JSON.is_file():
    raw = json.loads(STRINGS_JSON.read_text(encoding="utf-8"))
    en: dict[str, str] = raw["en"]
    de: dict[str, str] = raw["de"]
else:
    _ns: dict = {}
    _partial = SRC.read_text(encoding="utf-8").split("def env_lang", 1)[0]
    exec(compile(_partial, "i18n_partial.py", "exec"), _ns)
    en = _ns["STRINGS"]["en"]
    de = _ns["STRINGS"]["de"]

EN_KEYS = list(en.keys())
assert set(en) == set(de), (set(en) - set(de), set(de) - set(en))

T: dict[str, dict[str, str]] = {
    "app.title": {k: "Security Hub" for k in LANGS_EXTRA},
    "app.intro": {
        "fr": "Historique d’accès et surveillance en direct sur le NAS — SSH, SMB, app/web UGOS et connexions actives. Lecture seule, sans blocage.",
        "es": "Historial de acceso y supervisión en vivo en el NAS: SSH, SMB, app/web UGOS y conexiones activas. Solo lectura, sin bloqueo.",
        "it": "Cronologia accessi e monitoraggio live sul NAS — SSH, SMB, app/web UGOS e connessioni attive. Solo lettura, senza blocco.",
        "pl": "Historia dostępu i monitoring na żywo na NAS — SSH, SMB, aplikacja/web UGOS oraz aktywne połączenia. Tylko odczyt, bez blokowania.",
        "ru": "История доступа и живой мониторинг на NAS — SSH, SMB, приложение/веб UGOS и активные соединения. Только чтение, без блокировки.",
        "tr": "NAS üzerinde erişim geçmişi ve canlı izleme — SSH, SMB, UGOS uygulama/web ve aktif bağlantılar. Salt okunur, engelleme yok.",
        "hr": "Povijest pristupa i živi nadzor na NAS-u — SSH, SMB, UGOS app/web i aktivne veze. Samo za čitanje, bez blokiranja.",
        "zh": "NAS 上的访问历史与实时监控 — SSH、SMB、UGOS 应用/网页及活动连接。只读，不封锁。",
    },
    "app.mount_hint": {
        "fr": "Lit les journaux hôte sous /var/log et /var/ugreen/log. Trier, filtrer, exporter — visibilité complète.",
        "es": "Lee los registros del host en /var/log y /var/ugreen/log. Ordenar, filtrar, exportar — visibilidad total.",
        "it": "Legge i log host in /var/log e /var/ugreen/log. Ordina, filtra, esporta — piena visibilità.",
        "pl": "Odczytuje logi hosta z /var/log i /var/ugreen/log. Sortuj, filtruj, eksportuj — pełna widoczność.",
        "ru": "Читает системные журналы в /var/log и /var/ugreen/log. Сортировка, фильтр, экспорт — полная видимость.",
        "tr": "Ana makine günlüklerini /var/log ve /var/ugreen/log altında okur. Sırala, filtrele, dışa aktar — tam görünürlük.",
        "hr": "Čita host zapise pod /var/log i /var/ugreen/log. Sortiraj, filtriraj, izvezi — potpuna vidljivost.",
        "zh": "读取主机日志（/var/log 与 /var/ugreen/log）。排序、筛选、导出 — 完整可见。",
    },
    "app.readonly_note": {
        "fr": "Pas de blocage IP dans cette app : UGOS block_ip_list ne bloque pas fiablement SSH ni SMB sur DXP4800. Utilisez le pare-feu UGOS pour un vrai contrôle d’accès ; blocage IP optionnel dans Ugreen NAS Admin (bureau).",
        "es": "Sin bloqueo de IP en esta app: UGOS block_ip_list no bloquea de forma fiable SSH ni SMB en DXP4800. Use el firewall UGOS para un control de acceso real; bloqueo IP opcional en Ugreen NAS Admin (escritorio).",
        "it": "Nessun blocco IP in questa app: UGOS block_ip_list non blocca in modo affidabile SSH o SMB su DXP4800. Usa il firewall UGOS per un vero controllo accessi; blocco IP opzionale in Ugreen NAS Admin (desktop).",
        "pl": "Brak blokady IP w tej aplikacji: UGOS block_ip_list nie blokuje niezawodnie SSH ani SMB na DXP4800. Użyj zapory UGOS do realnej kontroli dostępu; opcjonalna blokada IP w Ugreen NAS Admin (desktop).",
        "ru": "В этом приложении нет блокировки IP: UGOS block_ip_list на DXP4800 ненадёжно блокирует SSH и SMB. Для реального контроля доступа используйте брандмауэр UGOS; опциональная блокировка IP в Ugreen NAS Admin (десктоп).",
        "tr": "Bu uygulamada IP engelleme yok: UGOS block_ip_list DXP4800’de SSH veya SMB’yi güvenilir şekilde engellemez. Gerçek erişim denetimi için UGOS güvenlik duvarını kullanın; isteğe bağlı IP engeli Ugreen NAS Admin’de (masaüstü).",
        "hr": "Nema IP blokade u ovoj aplikaciji: UGOS block_ip_list na DXP4800 ne pouzdano blokira SSH ni SMB. Za stvarnu kontrolu pristupa koristite UGOS vatrozid; opcionalna IP blokada u Ugreen NAS Admin (desktop).",
        "zh": "本应用不含 IP 封锁：在 DXP4800 上 UGOS block_ip_list 无法可靠封锁 SSH 或 SMB。请用 UGOS 防火墙做真正的访问控制；可选 IP 封锁见 Ugreen NAS Admin（桌面版）。",
    },
    "ui.language": {
        "fr": "Langue",
        "es": "Idioma",
        "it": "Lingua",
        "pl": "Język",
        "ru": "Язык",
        "tr": "Dil",
        "hr": "Jezik",
        "zh": "语言",
    },
    "companion": {
        "fr": "Companion bureau (Login Track + blocage IP) :",
        "es": "Companion de escritorio (Login Track + bloqueo IP):",
        "it": "Companion desktop (Login Track + blocco IP):",
        "pl": "Aplikacja desktopowa (Login Track + blokada IP):",
        "ru": "Десктоп-компаньон (Login Track + блокировка IP):",
        "tr": "Masaüstü yardımcısı (Login Track + IP engeli):",
        "hr": "Desktop pratilac (Login Track + IP blokada):",
        "zh": "桌面配套应用（Login Track + IP 封锁）：",
    },
    "btn.refresh": {
        "fr": "Actualiser",
        "es": "Actualizar",
        "it": "Aggiorna",
        "pl": "Odśwież",
        "ru": "Обновить",
        "tr": "Yenile",
        "hr": "Osvježi",
        "zh": "刷新",
    },
    "btn.export": {
        "fr": "Exporter",
        "es": "Exportar",
        "it": "Esporta",
        "pl": "Eksport",
        "ru": "Экспорт",
        "tr": "Dışa aktar",
        "hr": "Izvoz",
        "zh": "导出",
    },
    "live.enable": {
        "fr": "Temps réel (depuis l’ouverture de l’onglet uniquement)",
        "es": "En vivo (solo desde el inicio de la pestaña)",
        "it": "Live (solo dall’apertura della scheda)",
        "pl": "Na żywo (tylko od otwarcia karty)",
        "ru": "Вживую (только с момента открытия вкладки)",
        "tr": "Canlı (yalnızca sekme başlangıcından beri)",
        "hr": "Uživo (samo od otvaranja kartice)",
        "zh": "实时（仅自标签页打开起）",
    },
    "live.hint": {
        "fr": "Temps réel activé : nouveaux accès uniquement. Désactivé : charger l’historique.",
        "es": "En vivo activado: solo inicios nuevos. Desactivado: cargar historial.",
        "it": "Live attivo: solo nuovi accessi. Disattivo: carica la cronologia.",
        "pl": "Na żywo włączone: tylko nowe logowania. Wyłączone: wczytaj historię.",
        "ru": "Вживую вкл.: только новые входы. Выкл.: загрузить историю.",
        "tr": "Canlı açık: yalnızca yeni oturumlar. Kapalı: geçmişi yükle.",
        "hr": "Uživo uključeno: samo nove prijave. Isključeno: učitaj povijest.",
        "zh": "实时开：仅新登录。实时关：加载历史。",
    },
    "filter.hide_pings": {
        "fr": "Masquer les pings de session d’app",
        "es": "Ocultar pings de sesión de app",
        "it": "Nascondi ping di sessione app",
        "pl": "Ukryj pingi sesji aplikacji",
        "ru": "Скрыть пинги сессии приложения",
        "tr": "Uygulama oturum pinglerini gizle",
        "hr": "Sakrij pingove app sesije",
        "zh": "隐藏应用会话心跳",
    },
    "sort.label": {
        "fr": "Trier",
        "es": "Ordenar",
        "it": "Ordina",
        "pl": "Sortuj",
        "ru": "Сортировка",
        "tr": "Sırala",
        "hr": "Sortiraj",
        "zh": "排序",
    },
    "sort.time": {
        "fr": "Date / heure",
        "es": "Fecha / hora",
        "it": "Data / ora",
        "pl": "Data / godzina",
        "ru": "Дата / время",
        "tr": "Tarih / saat",
        "hr": "Datum / vrijeme",
        "zh": "日期 / 时间",
    },
    "sort.ip": {
        "fr": "Adresse IP",
        "es": "Dirección IP",
        "it": "Indirizzo IP",
        "pl": "Adres IP",
        "ru": "IP-адрес",
        "tr": "IP adresi",
        "hr": "IP adresa",
        "zh": "IP 地址",
    },
    "sort.user": {
        "fr": "Utilisateur",
        "es": "Usuario",
        "it": "Utente",
        "pl": "Użytkownik",
        "ru": "Пользователь",
        "tr": "Kullanıcı",
        "hr": "Korisnik",
        "zh": "用户",
    },
    "sort.source": {
        "fr": "Source",
        "es": "Origen",
        "it": "Origine",
        "pl": "Źródło",
        "ru": "Источник",
        "tr": "Kaynak",
        "hr": "Izvor",
        "zh": "来源",
    },
    "sort.outcome": {
        "fr": "Résultat",
        "es": "Resultado",
        "it": "Esito",
        "pl": "Wynik",
        "ru": "Результат",
        "tr": "Sonuç",
        "hr": "Ishod",
        "zh": "结果",
    },
    "sort.desc": {
        "fr": "Décroissant",
        "es": "Descendente",
        "it": "Decrescente",
        "pl": "Malejąco",
        "ru": "По убыванию",
        "tr": "Azalan",
        "hr": "Silazno",
        "zh": "降序",
    },
    "sort.asc": {
        "fr": "Croissant",
        "es": "Ascendente",
        "it": "Crescente",
        "pl": "Rosnąco",
        "ru": "По возрастанию",
        "tr": "Artan",
        "hr": "Uzlazno",
        "zh": "升序",
    },
    "days.label": {
        "fr": "Historique (jours)",
        "es": "Historial (días)",
        "it": "Cronologia (giorni)",
        "pl": "Historia (dni)",
        "ru": "История (дни)",
        "tr": "Geçmiş (gün)",
        "hr": "Povijest (dani)",
        "zh": "历史（天）",
    },
    "col.time": {
        "fr": "Heure",
        "es": "Hora",
        "it": "Ora",
        "pl": "Czas",
        "ru": "Время",
        "tr": "Zaman",
        "hr": "Vrijeme",
        "zh": "时间",
    },
    "col.ip": {k: "IP" for k in LANGS_EXTRA},
    "col.source": {
        "fr": "Source",
        "es": "Origen",
        "it": "Origine",
        "pl": "Źródło",
        "ru": "Источник",
        "tr": "Kaynak",
        "hr": "Izvor",
        "zh": "来源",
    },
    "col.outcome": {
        "fr": "Résultat",
        "es": "Resultado",
        "it": "Esito",
        "pl": "Wynik",
        "ru": "Результат",
        "tr": "Sonuç",
        "hr": "Ishod",
        "zh": "结果",
    },
    "col.user": {
        "fr": "Utilisateur",
        "es": "Usuario",
        "it": "Utente",
        "pl": "Użytkownik",
        "ru": "Пользователь",
        "tr": "Kullanıcı",
        "hr": "Korisnik",
        "zh": "用户",
    },
    "col.access": {
        "fr": "Accès / cible",
        "es": "Acceso / destino",
        "it": "Accesso / destinazione",
        "pl": "Dostęp / cel",
        "ru": "Доступ / цель",
        "tr": "Erişim / hedef",
        "hr": "Pristup / cilj",
        "zh": "访问 / 目标",
    },
    "col.detail": {
        "fr": "Détail (journal brut)",
        "es": "Detalle (log en bruto)",
        "it": "Dettaglio (log grezzo)",
        "pl": "Szczegóły (surowy log)",
        "ru": "Детали (сырой лог)",
        "tr": "Ayrıntı (ham günlük)",
        "hr": "Detalj (sirovi zapis)",
        "zh": "详情（原始日志）",
    },
    "access.hint": {
        "fr": "Dossiers SMB et chemins API issus de l’audit UGOS/Samba ; SSH affiche connexion/session.",
        "es": "Carpetas SMB y rutas API del audit UGOS/Samba; SSH muestra inicio de sesión/sesión.",
        "it": "Cartelle SMB e percorsi API dall’audit UGOS/Samba; SSH mostra login/sessione.",
        "pl": "Foldery SMB i ścieżki API z audytu UGOS/Samba; SSH pokazuje logowanie/sesję.",
        "ru": "Папки SMB и пути API из аудита UGOS/Samba; SSH показывает вход/сессию.",
        "tr": "UGOS/Samba denetiminden SMB klasörleri ve API yolları; SSH oturum açmayı/oturumu gösterir.",
        "hr": "SMB mape i API putanje iz UGOS/Samba audita; SSH prikazuje prijavu/sesiju.",
        "zh": "SMB 文件夹与 API 路径来自 UGOS/Samba 审计；SSH 显示登录/会话。",
    },
    "status.loading": {
        "fr": "Chargement des journaux …",
        "es": "Cargando datos de registro …",
        "it": "Caricamento dati di log …",
        "pl": "Ładowanie danych logów …",
        "ru": "Загрузка журналов …",
        "tr": "Günlük verileri yükleniyor …",
        "hr": "Učitavanje podataka zapisa …",
        "zh": "正在加载日志数据 …",
    },
    "status.live_waiting": {
        "fr": "Temps réel actif — en attente de nouveaux accès …",
        "es": "En vivo activo — esperando nuevos inicios de sesión …",
        "it": "Live attivo — in attesa di nuovi accessi …",
        "pl": "Na żywo aktywne — czekam na nowe logowania …",
        "ru": "Живой режим активен — ожидание новых входов …",
        "tr": "Canlı etkin — yeni oturumlar bekleniyor …",
        "hr": "Uživo aktivno — čekam nove prijave …",
        "zh": "实时已启用 — 等待新登录 …",
    },
    "status.busy": {
        "fr": "Requête en cours …",
        "es": "Consulta en curso …",
        "it": "Query in corso …",
        "pl": "Trwa zapytanie …",
        "ru": "Выполняется запрос …",
        "tr": "Sorgu devam ediyor …",
        "hr": "Upit u tijeku …",
        "zh": "查询进行中 …",
    },
    "status.entries": {
        "fr": "{count} entrées affichées",
        "es": "{count} entradas mostradas",
        "it": "{count} voci visualizzate",
        "pl": "{count} wpisów wyświetlonych",
        "ru": "Показано записей: {count}",
        "tr": "{count} kayıt gösteriliyor",
        "hr": "Prikazano unosa: {count}",
        "zh": "已显示 {count} 条",
    },
    "status.collect_empty": {
        "fr": "Aucune entrée de journal — vérifiez les montages et chemins de logs (diagnostics ci-dessous).",
        "es": "No se encontraron entradas de registro — compruebe montajes y rutas de logs (diagnóstico abajo).",
        "it": "Nessuna voce di log trovata — controlla mount e percorsi log (diagnostica sotto).",
        "pl": "Brak wpisów w logach — sprawdź montowania i ścieżki logów (diagnostyka poniżej).",
        "ru": "Записи журнала не найдены — проверьте монтирования и пути логов (диагностика ниже).",
        "tr": "Günlük kaydı bulunamadı — bağlama noktalarını ve günlük yollarını kontrol edin (aşağıdaki tanı).",
        "hr": "Nema unosa u zapisima — provjerite točke montiranja i putanje zapisa (dijagnostika ispod).",
        "zh": "未找到日志条目 — 请检查挂载与日志路径（见下方诊断）。",
    },
    "empty": {
        "fr": "Aucune entrée pour l’instant. Temps réel désactivé → Actualiser charge l’historique. Activé → attendre de nouveaux accès.",
        "es": "Aún no hay entradas. En vivo desactivado → Actualizar carga el historial. Activado → espere nuevos inicios.",
        "it": "Ancora nessuna voce. Live disattivo → Aggiorna carica la cronologia. Attivo → attendi nuovi accessi.",
        "pl": "Brak wpisów. Na żywo wyłączone → Odśwież wczytuje historię. Włączone → czekaj na nowe logowania.",
        "ru": "Пока нет записей. Вживую выкл. → Обновить загружает историю. Вкл. → ждите новых входов.",
        "tr": "Henüz kayıt yok. Canlı kapalı → Yenile geçmişi yükler. Açık → yeni oturumları bekleyin.",
        "hr": "Još nema unosa. Uživo isključeno → Osvježi učitava povijest. Uključeno → čekajte nove prijave.",
        "zh": "暂无条目。实时关 → 刷新加载历史。实时开 → 等待新登录。",
    },
    "diag.title": {
        "fr": "Diagnostics",
        "es": "Diagnóstico",
        "it": "Diagnostica",
        "pl": "Diagnostyka",
        "ru": "Диагностика",
        "tr": "Tanılama",
        "hr": "Dijagnostika",
        "zh": "诊断",
    },
    "log.title": {
        "fr": "Journal de l’app",
        "es": "Registro de la app",
        "it": "Log dell’app",
        "pl": "Log aplikacji",
        "ru": "Журнал приложения",
        "tr": "Uygulama günlüğü",
        "hr": "Zapis aplikacije",
        "zh": "应用日志",
    },
    "export.empty": {
        "fr": "Rien à exporter.",
        "es": "Nada que exportar.",
        "it": "Niente da esportare.",
        "pl": "Brak danych do eksportu.",
        "ru": "Нечего экспортировать.",
        "tr": "Dışa aktarılacak bir şey yok.",
        "hr": "Nema podataka za izvoz.",
        "zh": "无可导出内容。",
    },
}

missing = []
for key in EN_KEYS:
    if key not in T:
        missing.append(key)
        continue
    en_ph = set(_PLACEHOLDER_RE.findall(en[key]))
    for lang in LANGS_EXTRA:
        if lang not in T[key]:
            missing.append(f"{key}:{lang}")
            continue
        got_ph = set(_PLACEHOLDER_RE.findall(T[key][lang]))
        if got_ph != en_ph:
            raise SystemExit(f"{key}/{lang} placeholders {got_ph} != {en_ph}")
if missing:
    raise SystemExit(f"missing translations: {missing[:40]}")


def esc(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


out: dict[str, dict[str, str]] = {"de": de, "en": en}
for lang in LANGS_EXTRA:
    out[lang] = {k: T[k][lang] for k in EN_KEYS}

lines: list[str] = [
    "# -*- coding: utf-8 -*-",
    "from __future__ import annotations",
    "",
    "import os",
    "import threading",
    "from typing import Any",
    "",
    'LANG_COOKIE = "security_hub_lang"',
    "_thread_lang = threading.local()",
    "",
    "LANG_LABELS: dict[str, str] = {",
]
for code in ORDER:
    lines.append(f'    "{code}": "{LABELS[code]}",')
lines.append("}")
lines.append("")
lines.append("STRINGS: dict[str, dict[str, str]] = {")
for code in ORDER:
    lines.append(f'    "{code}": {{')
    for key in EN_KEYS:
        lines.append(f'        "{key}": "{esc(out[code][key])}",')
    lines.append("    },")
lines.append("}")
lines.extend(
    [
        "",
        "",
        "def env_lang() -> str:",
        '    loc = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()',
        '    for code in ("de", "fr", "es", "it", "pl", "ru", "tr", "hr", "zh"):',
        "        if code in loc:",
        "            return code",
        '    return "en"',
        "",
        "",
        "def normalize_lang(raw: str | None) -> str | None:",
        "    if not raw:",
        "        return None",
        '    v = str(raw).strip().lower().replace("_", "-")',
        "    if v in STRINGS:",
        "        return v",
        '    primary = v.split("-", 1)[0][:2]',
        "    return primary if primary in STRINGS else None",
        "",
        "",
        "def set_thread_lang(lang: str | None) -> None:",
        "    if lang:",
        "        _thread_lang.value = lang",
        "    elif hasattr(_thread_lang, \"value\"):",
        "        del _thread_lang.value",
        "",
        "",
        "def get_lang() -> str:",
        '    tl = getattr(_thread_lang, "value", None)',
        "    if tl:",
        "        return tl",
        "    try:",
        "        from flask import g",
        "",
        '        return getattr(g, "lang", "en")',
        "    except RuntimeError:",
        "        return env_lang()",
        "",
        "",
        "def lang_from_request(request) -> str:",
        "    c = normalize_lang(request.cookies.get(LANG_COOKIE))",
        "    if c:",
        "        return c",
        '    q = normalize_lang(request.args.get("lang"))',
        "    if q:",
        "        return q",
        '    al = (request.headers.get("Accept-Language") or "").lower()',
        '    for part in al.split(","):',
        '        token = part.split(";", 1)[0].strip()',
        "        picked = normalize_lang(token)",
        "        if picked:",
        "            return picked",
        "    return env_lang()",
        "",
        "",
        "def t(key: str, lang: str | None = None, **fmt: Any) -> str:",
        "    lng = lang or get_lang()",
        '    s = STRINGS.get(lng, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)',
        "    if fmt:",
        "        try:",
        "            return s.format(**fmt)",
        "        except (KeyError, ValueError):",
        "            return s",
        "    return s",
        "",
        "",
        "def bundle(lang: str) -> dict[str, str]:",
        '    return dict(STRINGS.get(lang, STRINGS["en"]))',
        "",
        "",
        "def supported_langs() -> list[str]:",
        "    return list(LANG_LABELS.keys())",
        "",
    ]
)

content = "\n".join(lines) + "\n"
SRC.write_text(content, encoding="utf-8")
if PUBLIC.parent.exists() or PUBLIC.parent.parent.exists():
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.write_text(content, encoding="utf-8")
    public_msg = str(PUBLIC)
else:
    public_msg = "(skipped — tree missing)"

spec = importlib.util.spec_from_file_location("security_hub_i18n", SRC)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

assert mod.LANG_COOKIE == "security_hub_lang"
assert mod.normalize_lang("fr-FR") == "fr"
assert mod.normalize_lang("hr") == "hr"
assert mod.normalize_lang("zh_CN") == "zh"
assert set(mod.LANG_LABELS) == set(ORDER)
for lang in ORDER:
    assert set(mod.STRINGS[lang]) == set(en), lang
assert len(mod.STRINGS["hr"]) == len(en)
assert hasattr(mod, "set_thread_lang")
assert hasattr(mod, "supported_langs")
assert mod.supported_langs() == ORDER

print("OK wrote", SRC)
print("synced", public_msg)
print("langs", list(mod.LANG_LABELS))
print("keys", len(en))
