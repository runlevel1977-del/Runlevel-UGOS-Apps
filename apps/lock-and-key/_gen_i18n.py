# -*- coding: utf-8 -*-
"""Generate lock-and-key app/i18n.py with de/en/zh/fr/es/it/pl/ru/tr/hr."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "app" / "i18n.py"
STRINGS_JSON = ROOT / "_en_strings.json"
PUBLIC = Path(
    r"E:\APP PROJEKTE\NAS_Admin_Project\_runlevel_ugos_apps\apps\lock-and-key\app\i18n.py"
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

raw = json.loads(STRINGS_JSON.read_text(encoding="utf-8"))
en: dict[str, str] = raw["en"]
de: dict[str, str] = raw["de"]
EN_KEYS = list(en.keys())
assert set(en) == set(de), (set(en) - set(de), set(de) - set(en))


def L(**kwargs: str) -> dict[str, str]:
    return kwargs


# fmt: off
T: dict[str, dict[str, str]] = {
    "app.title": {k: "Lock & Key" for k in LANGS_EXTRA},
    "app.intro": L(
        fr="Chiffrez un dossier sur le NAS — déverrouillez uniquement avec le fichier clé du stick USB sur le NAS.",
        es="Cifre una carpeta en el NAS — desbloquee solo con el archivo de clave del USB en el NAS.",
        it="Cripta una cartella sul NAS — sblocca solo con il file chiave dallo stick USB sul NAS.",
        pl="Szyfruj folder na NAS — odblokuj tylko plikiem klucza z pendrive’a USB na NAS.",
        ru="Шифруйте папку на NAS — разблокировка только файлом ключа с USB-накопителя на NAS.",
        tr="NAS’ta bir klasörü şifreleyin — yalnızca NAS’taki USB bellek anahtar dosyasıyla açın.",
        hr="Šifrirajte mapu na NAS-u — otključajte samo datotekom ključa s USB sticka na NAS-u.",
        zh="在 NAS 上加密文件夹 — 仅能用 NAS 上 USB 棒中的密钥文件解锁。",
    ),
    "ui.language": L(fr="Langue", es="Idioma", it="Lingua", pl="Język", ru="Язык", tr="Dil", hr="Jezik", zh="语言"),
    "companion": L(
        fr="Companion bureau :", es="Companion de escritorio:", it="Companion desktop:",
        pl="Aplikacja desktopowa:", ru="Десктоп-компаньон:", tr="Masaüstü yardımcısı:",
        hr="Desktop pratilac:", zh="桌面配套应用：",
    ),
    "vaults.title": L(fr="Coffres", es="Cajas fuertes", it="Caveau", pl="Sejfy", ru="Хранилища", tr="Kasalar", hr="Sefovi", zh="保险库"),
    "vaults.empty": L(
        fr="Aucun coffre pour l’instant.", es="Aún no hay cajas fuertes.", it="Nessun caveau ancora.",
        pl="Brak sejfów.", ru="Хранилищ пока нет.", tr="Henüz kasa yok.", hr="Još nema sefova.", zh="尚无保险库。",
    ),
    "vaults.col_name": L(fr="Nom", es="Nombre", it="Nome", pl="Nazwa", ru="Имя", tr="Ad", hr="Naziv", zh="名称"),
    "vaults.col_path": L(fr="Dossier", es="Carpeta", it="Cartella", pl="Folder", ru="Папка", tr="Klasör", hr="Mapa", zh="文件夹"),
    "vaults.col_status": L(fr="État", es="Estado", it="Stato", pl="Status", ru="Статус", tr="Durum", hr="Status", zh="状态"),
    "vaults.col_usb": L(fr="Liaison USB", es="Enlace USB", it="Associazione USB", pl="Powiązanie USB", ru="Привязка USB", tr="USB bağlantısı", hr="USB povezivanje", zh="USB 绑定"),
    "vaults.col_files": L(fr="Fichiers", es="Archivos", it="File", pl="Pliki", ru="Файлы", tr="Dosyalar", hr="Datoteke", zh="文件"),
    "vaults.col_actions": L(fr="Action", es="Acción", it="Azione", pl="Akcja", ru="Действие", tr="İşlem", hr="Radnja", zh="操作"),
    "vaults.delete": L(fr="Supprimer", es="Eliminar", it="Elimina", pl="Usuń", ru="Удалить", tr="Sil", hr="Obriši", zh="删除"),
    "vaults.delete_confirm": L(
        fr="Retirer le coffre « {name} » de la liste ?",
        es="¿Quitar la caja fuerte “{name}” de la lista?",
        it="Rimuovere il caveau “{name}” dall’elenco?",
        pl="Usunąć sejf „{name}” z listy?",
        ru="Удалить хранилище «{name}» из списка?",
        tr="“{name}” kasasını listeden kaldırılsın mı?",
        hr="Ukloniti sef „{name}“ s popisa?",
        zh="从列表中移除保险库“{name}”？",
    ),
    "vaults.delete_locked_confirm": L(
        fr="Le coffre « {name} » est VERROUILLÉ. Seule l’entrée de liste est supprimée — les fichiers chiffrés restent sur le NAS. Gardez le fichier clé ! Continuer ?",
        es="La caja fuerte “{name}” está BLOQUEADA. Solo se quita la entrada de la lista — los cifrados siguen en el NAS. ¡Conserve el archivo de clave! ¿Continuar?",
        it="Il caveau “{name}” è BLOCCATO. Si rimuove solo la voce elenco — i file cifrati restano sul NAS. Conserva il file chiave! Continuare?",
        pl="Sejf „{name}” jest ZABLOKOWANY. Usuwany jest tylko wpis na liście — zaszyfrowane pliki zostają na NAS. Zachowaj plik klucza! Kontynuować?",
        ru="Хранилище «{name}» ЗАБЛОКИРОВАНО. Удаляется только запись в списке — шифрованные файлы остаются на NAS. Сохраните файл ключа! Продолжить?",
        tr="“{name}” kasası KİLİTLİ. Yalnızca liste girdisi silinir — şifreli dosyalar NAS’ta kalır. Anahtar dosyasını saklayın! Devam?",
        hr="Sef „{name}“ je ZAKLJUČAN. Briše se samo stavka popisa — šifrirane datoteke ostaju na NAS-u. Sačuvajte datoteku ključa! Nastaviti?",
        zh="保险库“{name}”已锁定。仅删除列表项 — 加密文件仍在 NAS 上。请保留密钥文件！继续？",
    ),
    "vaults.status_locked": L(fr="verrouillé", es="bloqueado", it="bloccato", pl="zablokowany", ru="заблокировано", tr="kilitli", hr="zaključano", zh="已锁定"),
    "vaults.status_unlocked": L(fr="ouvert", es="desbloqueado", it="sbloccato", pl="odblokowany", ru="разблокировано", tr="açık", hr="otključano", zh="已解锁"),
    "vaults.status_locking": L(fr="verrouillage …", es="bloqueando …", it="blocco in corso …", pl="blokowanie …", ru="блокировка …", tr="kilitleniyor …", hr="zaključavanje …", zh="正在锁定 …"),
    "vaults.bind_yes": L(fr="étiquette/série", es="etiqueta/serie", it="etichetta/serie", pl="etykieta/seria", ru="метка/серийный", tr="etiket/seri", hr="oznaka/serijski", zh="标签/序列号"),
    "vaults.bind_no": L(fr="fichier clé seul", es="solo archivo de clave", it="solo file chiave", pl="tylko plik klucza", ru="только файл ключа", tr="yalnızca anahtar dosyası", hr="samo datoteka ključa", zh="仅密钥文件"),
    "vaults.key_pw_yes": L(fr="protégé par mot de passe", es="protegido con contraseña", it="protetto da password", pl="chroniony hasłem", ru="с паролем", tr="parola korumalı", hr="zaštićeno lozinkom", zh="已设密码"),
    "vaults.key_pw_no": L(fr="sans mot de passe", es="sin contraseña", it="senza password", pl="bez hasła", ru="без пароля", tr="parolasız", hr="bez lozinke", zh="无密码"),
    "create.title": L(
        fr="Verrouiller un nouveau coffre", es="Sellar una nueva caja fuerte", it="Sigilla un nuovo caveau",
        pl="Zablokuj nowy sejf", ru="Запечатать новое хранилище", tr="Yeni kasa kilitle",
        hr="Zaključaj novi sef", zh="密封新保险库",
    ),
    "create.name": L(fr="Nom", es="Nombre", it="Nome", pl="Nazwa", ru="Имя", tr="Ad", hr="Naziv", zh="名称"),
    "create.volume": L(fr="Volume", es="Volumen", it="Volume", pl="Wolumen", ru="Том", tr="Birim", hr="Volumen", zh="卷"),
    "create.volume_hint": L(
        fr="Pour les dossiers de l’app Fichiers UGOS : choisissez Volume 1 ou 2 — pas « sélection UGOS ».",
        es="Para carpetas de la app Archivos UGOS: elija Volumen 1 o 2 — no “selección UGOS”.",
        it="Per le cartelle dell’app File UGOS: scegli Volume 1 o 2 — non “selezione UGOS”.",
        pl="Dla folderów aplikacji Pliki UGOS: wybierz Wolumen 1 lub 2 — nie „wybór UGOS”.",
        ru="Для папок в приложении «Файлы» UGOS: выберите Том 1 или 2 — не «выбор UGOS».",
        tr="UGOS Dosyalar uygulamasındaki klasörler için: Birim 1 veya 2 seçin — “UGOS seçimi” değil.",
        hr="Za mape u UGOS aplikaciji Datoteke: odaberite Volumen 1 ili 2 — ne „UGOS odabir“.",
        zh="UGOS 文件应用中的文件夹：请选卷 1 或卷 2 — 不要选“UGOS 选择”。",
    ),
    "create.files_ready": L(
        fr="{n} fichiers seront chiffrés (sous-dossiers inclus)",
        es="{n} archivos se cifrarán (incl. subcarpetas)",
        it="{n} file verranno cifrati (incl. sottocartelle)",
        pl="{n} plików zostanie zaszyfrowanych (w tym podfoldery)",
        ru="{n} файлов будет зашифровано (включая подпапки)",
        tr="{n} dosya şifrelenecek (alt klasörler dahil)",
        hr="{n} datoteka bit će šifrirano (uklj. podmape)",
        zh="将加密 {n} 个文件（含子文件夹）",
    ),
    "create.folder": L(fr="Dossier", es="Carpeta", it="Cartella", pl="Folder", ru="Папка", tr="Klasör", hr="Mapa", zh="文件夹"),
    "create.subfolder": L(fr="Ouvrir le sous-dossier", es="Abrir subcarpeta", it="Apri sottocartella", pl="Otwórz podfolder", ru="Открыть подпапку", tr="Alt klasörü aç", hr="Otvori podmapu", zh="打开子文件夹"),
    "create.browse_here": L(fr="Emplacement actuel", es="Ubicación actual", it="Posizione attuale", pl="Bieżąca lokalizacja", ru="Текущее расположение", tr="Geçerli konum", hr="Trenutna lokacija", zh="当前位置"),
    "create.browse_sealed": L(
        fr="déjà verrouillé — {enc} chiffrés, {open} ouverts",
        es="ya sellado — {enc} cifrados, {open} abiertos",
        it="già sigillato — {enc} cifrati, {open} aperti",
        pl="już zablokowany — {enc} zaszyfrowanych, {open} otwartych",
        ru="уже запечатано — {enc} шифр., {open} открытых",
        tr="zaten kilitli — {enc} şifreli, {open} açık",
        hr="već zaključano — {enc} šifrirano, {open} otvoreno",
        zh="已密封 — {enc} 已加密，{open} 未加密",
    ),
    "create.browse_open": L(
        fr="{open} fichiers ouverts, {enc} déjà .lkenc",
        es="{open} archivos abiertos, {enc} ya .lkenc",
        it="{open} file aperti, {enc} già .lkenc",
        pl="{open} otwartych plików, {enc} już .lkenc",
        ru="{open} открытых файлов, {enc} уже .lkenc",
        tr="{open} açık dosya, {enc} zaten .lkenc",
        hr="{open} otvorenih datoteka, {enc} već .lkenc",
        zh="{open} 个未加密文件，{enc} 个已是 .lkenc",
    ),
    "create.already_sealed": L(
        fr="Ce dossier est déjà verrouillé (coffre « {name} »). Déverrouillez-le d’abord ou choisissez un autre dossier.",
        es="Esta carpeta ya está sellada (caja “{name}”). Desbloquéela primero o elija otra carpeta.",
        it="Questa cartella è già sigillata (caveau “{name}”). Sbloccala prima o scegli un’altra cartella.",
        pl="Ten folder jest już zablokowany (sejf „{name}”). Najpierw odblokuj lub wybierz inny folder.",
        ru="Эта папка уже запечатана (хранилище «{name}»). Сначала разблокируйте или выберите другую папку.",
        tr="Bu klasör zaten kilitli (“{name}” kasası). Önce açın veya başka klasör seçin.",
        hr="Ova mapa je već zaključana (sef „{name}“). Prvo otključajte ili odaberite drugu mapu.",
        zh="此文件夹已密封（保险库“{name}”）。请先解锁或选择其他文件夹。",
    ),
    "create.selected": L(
        fr="Dossier coffre sélectionné", es="Carpeta de caja seleccionada", it="Cartella caveau selezionata",
        pl="Wybrany folder sejfu", ru="Выбранная папка хранилища", tr="Seçilen kasa klasörü",
        hr="Odabrana mapa sefa", zh="已选保险库文件夹",
    ),
    "create.select_folder": L(
        fr="Sélectionner ce dossier", es="Seleccionar esta carpeta", it="Seleziona questa cartella",
        pl="Wybierz ten folder", ru="Выбрать эту папку", tr="Bu klasörü seç",
        hr="Odaberi ovu mapu", zh="选择此文件夹",
    ),
    "create.not_selected": L(
        fr="Aucun dossier sélectionné — naviguez ici, puis « Sélectionner ce dossier ».",
        es="Ninguna carpeta seleccionada — navegue aquí y pulse “Seleccionar esta carpeta”.",
        it="Nessuna cartella selezionata — naviga qui, poi “Seleziona questa cartella”.",
        pl="Nie wybrano folderu — przejdź tutaj, potem „Wybierz ten folder”.",
        ru="Папка не выбрана — перейдите сюда, затем «Выбрать эту папку».",
        tr="Henüz klasör seçilmedi — buraya gidin, sonra “Bu klasörü seç”.",
        hr="Još nije odabrana mapa — dođite ovamo, zatim „Odaberi ovu mapu“.",
        zh="尚未选择文件夹 — 浏览到此处，然后点“选择此文件夹”。",
    ),
    "create.err_no_folder": L(
        fr="Veuillez d’abord sélectionner un dossier.", es="Seleccione primero una carpeta.",
        it="Seleziona prima una cartella.", pl="Najpierw wybierz folder.",
        ru="Сначала выберите папку.", tr="Lütfen önce bir klasör seçin.",
        hr="Prvo odaberite mapu.", zh="请先选择文件夹。",
    ),
    "create.bind_usb": L(
        fr="Écrire la clé sur stick USB (associer le stick)",
        es="Escribir clave en USB (vincular stick)",
        it="Scrivi chiave su USB (associa stick)",
        pl="Zapisz klucz na USB (powiąż pendrive)",
        ru="Записать ключ на USB (привязать накопитель)",
        tr="Anahtarı USB’ye yaz (belleği bağla)",
        hr="Zapiši ključ na USB (poveži stick)",
        zh="将密钥写入 USB 棒（绑定）",
    ),
    "create.bind_hint": L(
        fr="Après verrouillage réussi, le stick choisi est formaté — seul le fichier clé reste. Décoché : téléchargement de la clé seulement.",
        es="Tras un sellado correcto, el stick elegido se formatea — solo queda el archivo de clave. Sin marcar: solo descarga de clave.",
        it="Dopo un sigillo riuscito, lo stick scelto viene formattato — resta solo il file chiave. Non spuntato: solo download della chiave.",
        pl="Po udanym zablokowaniu wybrany pendrive jest formatowany — pozostaje tylko plik klucza. Odznaczone: tylko pobranie klucza.",
        ru="После успешной блокировки выбранный накопитель форматируется — остаётся только файл ключа. Без галочки: только скачивание ключа.",
        tr="Başarılı kilitlemeden sonra seçilen bellek biçimlendirilir — yalnızca anahtar dosyası kalır. İşaretsiz: yalnızca anahtar indirme.",
        hr="Nakon uspješnog zaključavanja odabrani stick se formatira — ostaje samo datoteka ključa. Neoznačeno: samo preuzimanje ključa.",
        zh="密封成功后，所选 USB 会被格式化 — 仅保留密钥文件。未勾选：仅下载密钥。",
    ),
    "create.seal": L(fr="Verrouiller le dossier", es="Sellar carpeta", it="Sigilla cartella", pl="Zablokuj folder", ru="Запечатать папку", tr="Klasörü kilitle", hr="Zaključaj mapu", zh="密封文件夹"),
    "create.key_password": L(
        fr="Protéger le fichier clé par mot de passe (optionnel)",
        es="Proteger el archivo de clave con contraseña (opcional)",
        it="Proteggi il file chiave con password (opzionale)",
        pl="Chroń plik klucza hasłem (opcjonalnie)",
        ru="Защитить файл ключа паролем (необязательно)",
        tr="Anahtar dosyasını parola ile koru (isteğe bağlı)",
        hr="Zaštiti datoteku ključa lozinkom (opcionalno)",
        zh="用密码保护密钥文件（可选）",
    ),
    "create.key_password_hint": L(
        fr="Au moins 8 caractères. Le NAS ne stocke pas le mot de passe — téléchargement et USB nécessitent le même mot de passe pour ouvrir.",
        es="Al menos 8 caracteres. El NAS no guarda la contraseña — descarga y USB necesitan la misma para desbloquear.",
        it="Almeno 8 caratteri. Il NAS non memorizza la password — download e USB richiedono la stessa per sbloccare.",
        pl="Co najmniej 8 znaków. NAS nie przechowuje hasła — pobieranie i USB wymagają tego samego hasła do odblokowania.",
        ru="Не менее 8 символов. NAS не хранит пароль — скачивание и USB требуют тот же пароль для разблокировки.",
        tr="En az 8 karakter. NAS parolayı saklamaz — indirme ve USB açmak için aynı parolayı gerektirir.",
        hr="Najmanje 8 znakova. NAS ne sprema lozinku — preuzimanje i USB trebaju istu lozinku za otključavanje.",
        zh="至少 8 个字符。NAS 不存储密码 — 下载与 USB 解锁需同一密码。",
    ),
    "create.key_password_field": L(
        fr="Mot de passe du fichier clé", es="Contraseña del archivo de clave", it="Password del file chiave",
        pl="Hasło pliku klucza", ru="Пароль файла ключа", tr="Anahtar dosyası parolası",
        hr="Lozinka datoteke ključa", zh="密钥文件密码",
    ),
    "create.key_password_confirm": L(
        fr="Confirmer le mot de passe", es="Confirmar contraseña", it="Conferma password",
        pl="Potwierdź hasło", ru="Подтвердите пароль", tr="Parolayı onayla",
        hr="Potvrdi lozinku", zh="确认密码",
    ),
    "create.err_password_short": L(
        fr="Mot de passe d’au moins 8 caractères.", es="La contraseña debe tener al menos 8 caracteres.",
        it="La password deve avere almeno 8 caratteri.", pl="Hasło musi mieć co najmniej 8 znaków.",
        ru="Пароль не менее 8 символов.", tr="Parola en az 8 karakter olmalı.",
        hr="Lozinka mora imati najmanje 8 znakova.", zh="密码至少 8 个字符。",
    ),
    "create.err_password_mismatch": L(
        fr="Les mots de passe ne correspondent pas.", es="Las contraseñas no coinciden.",
        it="Le password non corrispondono.", pl="Hasła nie są zgodne.",
        ru="Пароли не совпадают.", tr="Parolalar eşleşmiyor.",
        hr="Lozinke se ne podudaraju.", zh="两次密码不一致。",
    ),
    "create.pick": L(fr="Choisir un dossier …", es="Elegir carpeta …", it="Scegli cartella …", pl="Wybierz folder …", ru="Выбрать папку …", tr="Klasör seç …", hr="Odaberi mapu …", zh="选择文件夹 …"),
    "unlock.title": L(
        fr="Ouvrir / re-verrouiller", es="Abrir / volver a bloquear", it="Sblocca / riblocca",
        pl="Odblokuj / zablokuj ponownie", ru="Открыть / снова заблокировать", tr="Aç / yeniden kilitle",
        hr="Otključaj / ponovno zaključaj", zh="解锁 / 重新锁定",
    ),
    "unlock.pick": L(fr="Coffre", es="Caja fuerte", it="Caveau", pl="Sejf", ru="Хранилище", tr="Kasa", hr="Sef", zh="保险库"),
    "unlock.from_usb": L(
        fr="Ouvrir avec USB sur le NAS", es="Abrir con USB en el NAS", it="Sblocca con USB sul NAS",
        pl="Odblokuj USB na NAS", ru="Открыть USB на NAS", tr="NAS’taki USB ile aç",
        hr="Otključaj USB-om na NAS-u", zh="用 NAS 上的 USB 解锁",
    ),
    "unlock.upload_key": L(
        fr="Téléverser le fichier clé", es="Subir archivo de clave", it="Carica file chiave",
        pl="Prześlij plik klucza", ru="Загрузить файл ключа", tr="Anahtar dosyası yükle",
        hr="Prenesi datoteku ključa", zh="上传密钥文件",
    ),
    "unlock.key_password": L(
        fr="Mot de passe du fichier clé", es="Contraseña del archivo de clave", it="Password del file chiave",
        pl="Hasło pliku klucza", ru="Пароль файла ключа", tr="Anahtar dosyası parolası",
        hr="Lozinka datoteke ključa", zh="密钥文件密码",
    ),
    "unlock.key_password_hint": L(
        fr="Nécessaire seulement si un mot de passe a été défini au verrouillage.",
        es="Solo necesario si se estableció una contraseña al sellar.",
        it="Necessario solo se è stata impostata una password in fase di sigillo.",
        pl="Wymagane tylko, jeśli przy blokowaniu ustawiono hasło.",
        ru="Нужно только если при блокировке был задан пароль.",
        tr="Yalnızca kilitlemede parola ayarlandıysa gerekir.",
        hr="Potrebno samo ako je pri zaključavanju postavljena lozinka.",
        zh="仅在密封时设置了密码时需要。",
    ),
    "unlock.run": L(fr="Ouvrir", es="Abrir", it="Sblocca", pl="Odblokuj", ru="Открыть", tr="Aç", hr="Otključaj", zh="解锁"),
    "relock.run": L(fr="Re-verrouiller", es="Volver a bloquear", it="Riblocca", pl="Zablokuj ponownie", ru="Снова заблокировать", tr="Yeniden kilitle", hr="Ponovno zaključaj", zh="重新锁定"),
    "usb.title": L(fr="USB sur le NAS", es="USB en el NAS", it="USB sul NAS", pl="USB na NAS", ru="USB на NAS", tr="NAS’ta USB", hr="USB na NAS-u", zh="NAS 上的 USB"),
    "usb.empty": L(
        fr="Aucun stick USB monté.", es="No hay USB montado.", it="Nessuno stick USB montato.",
        pl="Brak podłączonego pendrive’a USB.", ru="USB-накопитель не подключён.", tr="Takılı USB bellek yok.",
        hr="Nema umetnutog USB sticka.", zh="未挂载 USB 棒。",
    ),
    "usb.write_key": L(
        fr="Formater le stick et écrire la clé", es="Formatear stick y escribir clave",
        it="Formatta stick e scrivi chiave", pl="Sformatuj pendrive i zapisz klucz",
        ru="Форматировать накопитель и записать ключ", tr="Belleği biçimlendir ve anahtarı yaz",
        hr="Formatiraj stick i zapiši ključ", zh="格式化棒并写入密钥",
    ),
    "usb.format_confirm": L(
        fr="Le stick USB sera entièrement effacé/formaté. Toutes les données seront perdues. Continuer ?",
        es="El USB se borrará/formateará por completo. Se perderán todos los datos. ¿Continuar?",
        it="Lo stick USB sarà cancellato/formattato completamente. Tutti i dati andranno persi. Continuare?",
        pl="Pendrive zostanie całkowicie wymazany/sformatowany. Wszystkie dane zostaną utracone. Kontynuować?",
        ru="USB-накопитель будет полностью стёрт/отформатирован. Все данные будут потеряны. Продолжить?",
        tr="USB bellek tamamen silinecek/biçimlendirilecek. Tüm veriler kaybolur. Devam?",
        hr="USB stick bit će potpuno obrisan/formatiran. Svi podaci bit će izgubljeni. Nastaviti?",
        zh="USB 棒将被完全擦除/格式化。所有数据将丢失。继续？",
    ),
    "usb.one_stick": L(
        fr="Un stick par coffre — les anciennes clés sont supprimées.",
        es="Un stick por caja — se eliminan las claves antiguas.",
        it="Uno stick per caveau — le vecchie chiavi vengono rimosse.",
        pl="Jeden pendrive na sejf — stare klucze są usuwane.",
        ru="Один накопитель на хранилище — старые ключи удаляются.",
        tr="Kasa başına bir bellek — eski anahtarlar kaldırılır.",
        hr="Jedan stick po sefu — stari ključevi se uklanjaju.",
        zh="每个保险库一根棒 — 旧密钥会被移除。",
    ),
    "usb.pick": L(fr="Stick USB", es="Stick USB", it="Stick USB", pl="Pendrive USB", ru="USB-накопитель", tr="USB bellek", hr="USB stick", zh="USB 棒"),
    "usb.pick_hint": L(
        fr="Si plusieurs sticks sont branchés, choisissez celui qui contient le fichier clé.",
        es="Si hay varios sticks, elija el que tiene el archivo de clave.",
        it="Se ci sono più stick, scegli quello con il file chiave.",
        pl="Przy kilku pendrive’ach wybierz ten z plikiem klucza.",
        ru="Если подключено несколько накопителей, выберите тот, где файл ключа.",
        tr="Birden fazla bellek varsa anahtar dosyasını taşıyanı seçin.",
        hr="Ako je umetnuto više stickova, odaberite onaj s datotekom ključa.",
        zh="若插了多根棒，请选择存有密钥文件的那根。",
    ),
    "usb.none": L(
        fr="Aucun stick monté", es="Ningún stick montado", it="Nessuno stick montato",
        pl="Brak podłączonego pendrive’a", ru="Накопитель не подключён", tr="Takılı bellek yok",
        hr="Nema umetnutog sticka", zh="未挂载棒",
    ),
    "usb.key_written": L(
        fr="Clé écrite sur le stick : {path} — ce stick est maintenant lié à ce coffre.",
        es="Clave escrita en el stick: {path} — este stick queda vinculado a esta caja.",
        it="Chiave scritta sullo stick: {path} — questo stick è ora associato a questo caveau.",
        pl="Klucz zapisany na pendrive: {path} — ten pendrive jest teraz powiązany z tym sejfem.",
        ru="Ключ записан на накопитель: {path} — он привязан к этому хранилищу.",
        tr="Anahtar belleğe yazıldı: {path} — bu bellek artık bu kasaya bağlı.",
        hr="Ključ zapisan na stick: {path} — ovaj stick je sada povezan s ovim sefom.",
        zh="密钥已写入棒：{path} — 此棒现已绑定到该保险库。",
    ),
    "usb.browser_alert_hint": L(
        fr="Note : la case « Empêcher les nouvelles invites » du navigateur ne bloque que les pop-ups — pas la protection du stick (série + formatage).",
        es="Nota: la casilla del navegador “evitar más avisos” solo bloquea ventanas emergentes — no la protección del stick (serie + formato).",
        it="Nota: la casella del browser “impedisci altri avvisi” blocca solo i popup — non la protezione dello stick (seriale + format).",
        pl="Uwaga: opcja przeglądarki „nie pokazuj więcej” blokuje tylko wyskakujące okna — nie ochronę pendrive’a (seria + formatowanie).",
        ru="Примечание: флажок браузера «больше не показывать» блокирует только всплывающие окна — не защиту накопителя (серийный номер + формат).",
        tr="Not: Tarayıcının “diğer uyarıları engelle” kutusu yalnızca pencereleri engeller — bellek korumasını değil (seri + biçimlendirme).",
        hr="Napomena: preglednikova opcija „spriječi daljnje upite“ blokira samo skočne prozore — ne zaštitu sticka (serijski + formatiranje).",
        zh="提示：浏览器的“禁止进一步提示”只阻止弹窗 — 不影响棒保护（序列号 + 格式化）。",
    ),
    "log.title": L(fr="Journal", es="Registro", it="Log", pl="Dziennik", ru="Журнал", tr="Günlük", hr="Zapisnik", zh="日志"),
    "job.running": L(fr="Tâche en cours …", es="Tarea en curso …", it="Operazione in corso …", pl="Zadanie trwa …", ru="Задача выполняется …", tr="Görev çalışıyor …", hr="Zadatak u tijeku …", zh="任务进行中 …"),
    "job.writing_key": L(
        fr="Écriture de la clé sur le stick USB …", es="Escribiendo la clave en el USB …",
        it="Scrittura della chiave sullo stick USB …", pl="Zapisywanie klucza na USB …",
        ru="Запись ключа на USB …", tr="Anahtar USB belleğe yazılıyor …",
        hr="Zapis ključa na USB stick …", zh="正在将密钥写入 USB 棒 …",
    ),
    "job.done": L(fr="Terminé", es="Listo", it="Fatto", pl="Gotowe", ru="Готово", tr="Bitti", hr="Gotovo", zh="完成"),
    "job.error": L(fr="Erreur", es="Error", it="Errore", pl="Błąd", ru="Ошибка", tr="Hata", hr="Greška", zh="错误"),
    "job.files_encrypted": L(fr="fichiers chiffrés", es="archivos cifrados", it="file cifrati", pl="plików zaszyfrowanych", ru="файлов зашифровано", tr="dosya şifrelendi", hr="datoteka šifrirano", zh="个文件已加密"),
    "job.files_decrypted": L(fr="fichiers déchiffrés", es="archivos descifrados", it="file decifrati", pl="plików odszyfrowanych", ru="файлов расшифровано", tr="dosya çözüldü", hr="datoteka dešifrirano", zh="个文件已解密"),
    "job.verify_ok": L(
        fr="contrôle d’intégrité OK ({n} fichiers)",
        es="comprobación de integridad OK ({n} archivos)",
        it="controllo integrità OK ({n} file)",
        pl="kontrola integralności OK ({n} plików)",
        ru="проверка целостности OK ({n} файлов)",
        tr="bütünlük kontrolü OK ({n} dosya)",
        hr="provjera cjelovitosti OK ({n} datoteka)",
        zh="完整性检查通过（{n} 个文件）",
    ),
    "job.verify_ok_legacy": L(
        fr="déchiffrement OK ({n} fichiers — ancien coffre sans manifeste)",
        es="descifrado OK ({n} archivos — caja antigua sin manifiesto)",
        it="decifratura OK ({n} file — caveau precedente senza manifesto)",
        pl="odszyfrowanie OK ({n} plików — starszy sejf bez manifestu)",
        ru="расшифровка OK ({n} файлов — старое хранилище без манифеста)",
        tr="şifre çözme OK ({n} dosya — manifesto’suz eski kasa)",
        hr="dešifriranje OK ({n} datoteka — stariji sef bez manifesta)",
        zh="解密成功（{n} 个文件 — 旧版保险库无校验清单）",
    ),
    "job.verify_fail": L(
        fr="échec du contrôle d’intégrité", es="fallo de comprobación de integridad",
        it="controllo integrità non riuscito", pl="kontrola integralności nie powiodła się",
        ru="проверка целостности не удалась", tr="bütünlük kontrolü başarısız",
        hr="provjera cjelovitosti nije uspjela", zh="完整性检查失败",
    ),
    "job.seal_failed_safe": L(
        fr="Verrouillage annulé — tous les fichiers originaux sont inchangés.",
        es="Sellado cancelado — todos los originales están intactos.",
        it="Sigillo annullato — tutti i file originali sono invariati.",
        pl="Blokowanie przerwane — wszystkie oryginalne pliki bez zmian.",
        ru="Блокировка отменена — все исходные файлы без изменений.",
        tr="Kilitleme iptal — tüm orijinal dosyalar değişmedi.",
        hr="Zaključavanje prekinuto — sve izvorne datoteke su nepromijenjene.",
        zh="密封已中止 — 所有原始文件未改动。",
    ),
    "job.unlock_failed_safe": L(
        fr="Déverrouillage annulé — tous les fichiers chiffrés sont inchangés.",
        es="Desbloqueo cancelado — todos los cifrados están intactos.",
        it="Sblocco annullato — tutti i file cifrati sono invariati.",
        pl="Odblokowanie przerwane — wszystkie zaszyfrowane pliki bez zmian.",
        ru="Разблокировка отменена — все шифрованные файлы без изменений.",
        tr="Açma iptal — tüm şifreli dosyalar değişmedi.",
        hr="Otključavanje prekinuto — sve šifrirane datoteke su nepromijenjene.",
        zh="解锁已中止 — 所有加密文件未改动。",
    ),
    "warn.seal_result": L(
        fr="Après verrouillage : les originaux disparaissent, remplacés par des .lkenc. Le dossier reste visible dans le gestionnaire de fichiers UGOS.",
        es="Tras sellar: los originales desaparecen y se sustituyen por .lkenc. La carpeta sigue visible en el administrador de archivos UGOS.",
        it="Dopo il sigillo: gli originali spariscono, sostituiti da .lkenc. La cartella resta visibile nel file manager UGOS.",
        pl="Po zablokowaniu: oryginały znikają, zastąpione przez .lkenc. Folder nadal widać w menedżerze plików UGOS.",
        ru="После блокировки: оригиналы исчезают, вместо них .lkenc. Папка остаётся видимой в файловом менеджере UGOS.",
        tr="Kilitlemeden sonra: orijinaller gider, yerini .lkenc alır. Klasör UGOS dosya yöneticisinde görünür kalır.",
        hr="Nakon zaključavanja: originali nestaju, zamijenjeni .lkenc. Mapa ostaje vidljiva u UGOS upravitelju datoteka.",
        zh="密封后：原文件消失，变为 .lkenc。文件夹仍在 UGOS 文件管理器中可见。",
    ),
    "warn.usb_remove": L(
        fr="Retirer l’USB ne masque pas le dossier — sans clé, les .lkenc sont seulement illisibles.",
        es="Quitar el USB no oculta la carpeta — sin clave, los .lkenc solo son ilegibles.",
        it="Rimuovere l’USB non nasconde la cartella — senza chiave i .lkenc sono solo illeggibili.",
        pl="Odłączenie USB nie ukrywa folderu — bez klucza pliki .lkenc są tylko nieczytelne.",
        ru="Извлечение USB не скрывает папку — без ключа .lkenc лишь нечитаемы.",
        tr="USB’yi çıkarmak klasörü gizlemez — anahtarsız .lkenc yalnızca okunamaz.",
        hr="Vadjenje USB-a ne skriva mapu — bez ključa .lkenc su samo nečitljivi.",
        zh="拔掉 USB 不会隐藏文件夹 — 没有密钥时 .lkenc 只是无法读取。",
    ),
    "warn.no_recovery": L(
        fr="Sans fichier clé, aucune récupération n’est possible.",
        es="Sin el archivo de clave no hay recuperación.",
        it="Senza il file chiave non c’è recupero.",
        pl="Bez pliku klucza nie ma odzyskania.",
        ru="Без файла ключа восстановление невозможно.",
        tr="Anahtar dosyası olmadan kurtarma yok.",
        hr="Bez datoteke ključa nema oporavka.",
        zh="没有密钥文件无法恢复。",
    ),
    "volume.1": L(fr="Volume 1", es="Volumen 1", it="Volume 1", pl="Wolumen 1", ru="Том 1", tr="Birim 1", hr="Volumen 1", zh="卷 1"),
    "volume.2": L(fr="Volume 2", es="Volumen 2", it="Volume 2", pl="Wolumen 2", ru="Том 2", tr="Birim 2", hr="Volumen 2", zh="卷 2"),
    "volume.ugos": L(
        fr="Sélection UGOS", es="Selección UGOS", it="Selezione UGOS",
        pl="Wybór UGOS", ru="Выбор UGOS", tr="UGOS seçimi", hr="UGOS odabir", zh="UGOS 选择",
    ),
    "volume.storage_fallback": L(fr="Stockage {id}", es="Almacenamiento {id}", it="Archiviazione {id}", pl="Pamięć {id}", ru="Хранилище {id}", tr="Depolama {id}", hr="Pohrana {id}", zh="存储 {id}"),
    "volume.usb_fmt": L(fr="USB : {name} ({size})", es="USB: {name} ({size})", it="USB: {name} ({size})", pl="USB: {name} ({size})", ru="USB: {name} ({size})", tr="USB: {name} ({size})", hr="USB: {name} ({size})", zh="USB：{name}（{size}）"),
    "volume.usb_name_fmt": L(fr="USB : {name}", es="USB: {name}", it="USB: {name}", pl="USB: {name}", ru="USB: {name}", tr="USB: {name}", hr="USB: {name}", zh="USB：{name}"),
    "err.no_storage": L(
        fr="Aucun stockage disponible", es="No hay almacenamiento disponible", it="Nessuno storage disponibile",
        pl="Brak dostępnej pamięci", ru="Нет доступного хранилища", tr="Kullanılabilir depolama yok",
        hr="Nema dostupne pohrane", zh="无可用存储",
    ),
    "err.usb_not_mounted": L(
        fr="USB {id} non monté", es="USB {id} no montado", it="USB {id} non montato",
        pl="USB {id} niezamontowany", ru="USB {id} не смонтирован", tr="USB {id} bağlı değil",
        hr="USB {id} nije montiran", zh="USB {id} 未挂载",
    ),
    "err.system_folder": L(
        fr="Les dossiers système (nom contenant @) ne peuvent pas être chiffrés.",
        es="Las carpetas del sistema (nombre con @) no se pueden cifrar.",
        it="Le cartelle di sistema (nome con @) non possono essere cifrate.",
        pl="Folderów systemowych (nazwa zawiera @) nie można szyfrować.",
        ru="Системные папки (имя содержит @) нельзя шифровать.",
        tr="Sistem klasörleri (adında @) şifrelenemez.",
        hr="Sistemske mape (ime sadrži @) ne mogu se šifrirati.",
        zh="系统文件夹（名称含 @）无法加密。",
    ),
    "err.no_usb": L(
        fr="Aucun stick USB monté.", es="No hay USB montado.", it="Nessuno stick USB montato.",
        pl="Brak podłączonego USB.", ru="USB не подключён.", tr="Takılı USB yok.",
        hr="Nema umetnutog USB-a.", zh="未挂载 USB。",
    ),
    "err.usb_selected_missing": L(
        fr="Le stick USB sélectionné n’est pas monté.", es="El USB seleccionado no está montado.",
        it="Lo stick USB selezionato non è montato.", pl="Wybrany USB nie jest zamontowany.",
        ru="Выбранный USB не смонтирован.", tr="Seçilen USB bağlı değil.",
        hr="Odabrani USB nije montiran.", zh="所选 USB 未挂载。",
    ),
    "err.select_usb": L(
        fr="Veuillez sélectionner un stick USB.", es="Seleccione un stick USB.",
        it="Seleziona uno stick USB.", pl="Wybierz pendrive USB.",
        ru="Выберите USB-накопитель.", tr="Bir USB bellek seçin.",
        hr="Odaberite USB stick.", zh="请选择 USB 棒。",
    ),
    "err.folder_not_found": L(
        fr="Dossier introuvable.", es="Carpeta no encontrada.", it="Cartella non trovata.",
        pl="Nie znaleziono folderu.", ru="Папка не найдена.", tr="Klasör bulunamadı.",
        hr="Mapa nije pronađena.", zh="未找到文件夹。",
    ),
    "err.folder_already_sealed": L(
        fr="Dossier déjà verrouillé (coffre « {name} ») — ouvrez d’abord ou choisissez un autre dossier.",
        es="Carpeta ya sellada (caja “{name}”) — desbloquee primero o elija otra.",
        it="Cartella già sigillata (caveau “{name}”) — sblocca prima o scegli un’altra.",
        pl="Folder już zablokowany (sejf „{name}”) — najpierw odblokuj lub wybierz inny.",
        ru="Папка уже запечатана (хранилище «{name}») — сначала разблокируйте или выберите другую.",
        tr="Klasör zaten kilitli (“{name}” kasası) — önce açın veya başka seçin.",
        hr="Mapa već zaključana (sef „{name}“) — prvo otključajte ili odaberite drugu.",
        zh="文件夹已密封（保险库“{name}”）— 请先解锁或另选文件夹。",
    ),
    "err.folder_partial": L(
        fr="Dossier partiellement verrouillé (mélange de fichiers ouverts et .lkenc) — ouvrez d’abord avec la clé ou supprimez les fichiers chiffrés orphelins.",
        es="Carpeta parcialmente sellada (mezcla de abiertos y .lkenc) — desbloquee con la clave o elimine cifrados huérfanos.",
        it="Cartella parzialmente sigillata (mix di aperti e .lkenc) — sblocca con la chiave o rimuovi i cifrati orfani.",
        pl="Folder częściowo zablokowany (mieszanka otwartych i .lkenc) — odblokuj kluczem lub usuń osierocone zaszyfrowane.",
        ru="Папка частично запечатана (смесь открытых и .lkenc) — разблокируйте ключом или удалите осиротевшие шифрованные файлы.",
        tr="Klasör kısmen kilitli (açık ve .lkenc karışımı) — önce anahtarla açın veya yetim şifreli dosyaları kaldırın.",
        hr="Mapa djelomično zaključana (mješavina otvorenih i .lkenc) — prvo otključajte ključem ili uklonite napuštene šifrirane datoteke.",
        zh="文件夹部分密封（未加密与 .lkenc 混杂）— 请先用密钥解锁或手动删除孤立的加密文件。",
    ),
    "err.no_encryptable": L(
        fr="Aucun fichier chiffrable dans {host} — utilisez Volume 1/2 pour les dossiers partagés, pas le raccourci UGOS.",
        es="No hay archivos cifrables en {host} — use Volumen 1/2 para carpetas compartidas, no el acceso UGOS.",
        it="Nessun file cifrabile in {host} — usa Volume 1/2 per le condivisioni, non il collegamento UGOS.",
        pl="Brak plików do zaszyfrowania w {host} — użyj Wolumenu 1/2 dla udziałów, nie skrótu UGOS.",
        ru="Нет файлов для шифрования в {host} — используйте Том 1/2 для общих папок, не ярлык UGOS.",
        tr="{host} içinde şifrelenecek dosya yok — paylaşımlar için Birim 1/2 kullanın, UGOS kısayolu değil.",
        hr="Nema datoteka za šifriranje u {host} — za dijeljene mape koristite Volumen 1/2, ne UGOS prečac.",
        zh="{host} 中无可加密文件 — 共享文件夹请用卷 1/2，不要用 UGOS 快捷方式。",
    ),
    "err.usb_bound_other": L(
        fr="Le stick USB est déjà associé au coffre « {name} ».",
        es="El USB ya está vinculado a la caja “{name}”.",
        it="Lo stick USB è già associato al caveau “{name}”.",
        pl="Pendrive jest już powiązany z sejfem „{name}”.",
        ru="USB уже привязан к хранилищу «{name}».",
        tr="USB zaten “{name}” kasasına bağlı.",
        hr="USB je već povezan sa sefom „{name}“.",
        zh="USB 已绑定到保险库“{name}”。",
    ),
    "err.usb_owned_other": L(
        fr="Le stick appartient encore au coffre « {name} » — choisissez un autre stick ou supprimez d’abord ce coffre.",
        es="El stick aún pertenece a la caja “{name}” — elija otro o elimine esa caja primero.",
        it="Lo stick appartiene ancora al caveau “{name}” — scegli un altro o elimina prima quel caveau.",
        pl="Pendrive należy jeszcze do sejfu „{name}” — wybierz inny lub najpierw usuń ten sejf.",
        ru="Накопитель ещё принадлежит хранилищу «{name}» — выберите другой или сначала удалите это хранилище.",
        tr="Bellek hâlâ “{name}” kasasına ait — başka seçin veya önce o kasayı silin.",
        hr="Stick još pripada sefu „{name}“ — odaberite drugi ili prvo obrišite taj sef.",
        zh="该棒仍属于保险库“{name}” — 请另选棒或先删除该保险库。",
    ),
    "err.encrypted_zero": L(
        fr="0 fichier chiffré dans {folder}.", es="0 archivos cifrados en {folder}.",
        it="0 file cifrati in {folder}.", pl="0 zaszyfrowanych plików w {folder}.",
        ru="0 файлов зашифровано в {folder}.", tr="{folder} içinde 0 dosya şifrelendi.",
        hr="0 šifriranih datoteka u {folder}.", zh="{folder} 中加密了 0 个文件。",
    ),
    "err.vault_not_found": L(
        fr="Coffre introuvable.", es="Caja fuerte no encontrada.", it="Caveau non trovato.",
        pl="Nie znaleziono sejfu.", ru="Хранилище не найдено.", tr="Kasa bulunamadı.",
        hr="Sef nije pronađen.", zh="未找到保险库。",
    ),
    "err.vault_not_locked": L(
        fr="Le coffre n’est pas verrouillé.", es="La caja no está bloqueada.", it="Il caveau non è bloccato.",
        pl="Sejf nie jest zablokowany.", ru="Хранилище не заблокировано.", tr="Kasa kilitli değil.",
        hr="Sef nije zaključan.", zh="保险库未锁定。",
    ),
    "err.vault_not_unlocked": L(
        fr="Le coffre n’est pas ouvert.", es="La caja no está desbloqueada.", it="Il caveau non è sbloccato.",
        pl="Sejf nie jest odblokowany.", ru="Хранилище не разблокировано.", tr="Kasa açık değil.",
        hr="Sef nije otključan.", zh="保险库未解锁。",
    ),
    "err.folder_already_sealed_simple": L(
        fr="Le dossier est déjà verrouillé.", es="La carpeta ya está sellada.", it="La cartella è già sigillata.",
        pl="Folder jest już zablokowany.", ru="Папка уже запечатана.", tr="Klasör zaten kilitli.",
        hr="Mapa je već zaključana.", zh="文件夹已密封。",
    ),
    "err.key_not_on_usb": L(
        fr="Fichier clé introuvable sur le stick USB.", es="Archivo de clave no encontrado en el USB.",
        it="File chiave non trovato sullo stick USB.", pl="Nie znaleziono pliku klucza na USB.",
        ru="Файл ключа не найден на USB.", tr="USB’de anahtar dosyası bulunamadı.",
        hr="Datoteka ključa nije pronađena na USB-u.", zh="USB 上未找到密钥文件。",
    ),
    "err.key_vault_mismatch": L(
        fr="Le fichier clé appartient à un autre coffre.", es="El archivo de clave pertenece a otra caja.",
        it="Il file chiave appartiene a un altro caveau.", pl="Plik klucza należy do innego sejfu.",
        ru="Файл ключа принадлежит другому хранилищу.", tr="Anahtar dosyası başka kasaya ait.",
        hr="Datoteka ključa pripada drugom sefu.", zh="密钥文件属于其他保险库。",
    ),
    "err.usb_binding_mismatch": L(
        fr="Liaison USB incorrecte (stick/numéro de série).", es="Enlace USB no coincide (stick/serie).",
        it="Associazione USB non corrispondente (stick/serie).", pl="Niezgodne powiązanie USB (pendrive/seria).",
        ru="Несовпадение привязки USB (накопитель/серийный номер).", tr="USB bağları uyuşmuyor (bellek/seri).",
        hr="USB povezivanje se ne podudara (stick/serijski).", zh="USB 绑定不匹配（棒/序列号）。",
    ),
    "err.vault_busy": L(
        fr="Le coffre est occupé.", es="La caja está ocupada.", it="Il caveau è occupato.",
        pl="Sejf jest zajęty.", ru="Хранилище занято.", tr="Kasa meşgul.",
        hr="Sef je zauzet.", zh="保险库正忙。",
    ),
    "err.vault_locked_delete": L(
        fr="Le coffre est verrouillé — confirmez la suppression pour retirer seulement l’entrée de liste.",
        es="La caja está bloqueada — confirme el borrado para quitar solo la entrada de lista.",
        it="Il caveau è bloccato — conferma l’eliminazione per rimuovere solo la voce elenco.",
        pl="Sejf jest zablokowany — potwierdź usunięcie, aby usunąć tylko wpis z listy.",
        ru="Хранилище заблокировано — подтвердите удаление, чтобы убрать только запись из списка.",
        tr="Kasa kilitli — yalnızca liste girdisini kaldırmak için silmeyi onaylayın.",
        hr="Sef je zaključan — potvrdite brisanje da uklonite samo stavku popisa.",
        zh="保险库已锁定 — 确认删除以仅移除列表项。",
    ),
    "err.not_directory": L(
        fr="Ce n’est pas un dossier.", es="No es una carpeta.", it="Non è una cartella.",
        pl="To nie jest folder.", ru="Это не папка.", tr="Klasör değil.",
        hr="Nije mapa.", zh="不是文件夹。",
    ),
    "err.invalid_path": L(
        fr="Chemin invalide.", es="Ruta no válida.", it="Percorso non valido.",
        pl="Nieprawidłowa ścieżka.", ru="Недопустимый путь.", tr="Geçersiz yol.",
        hr="Nevažeća putanja.", zh="无效路径。",
    ),
    "err.key_pw_short": L(
        fr="Mot de passe du fichier clé d’au moins 8 caractères.",
        es="La contraseña del archivo de clave debe tener al menos 8 caracteres.",
        it="La password del file chiave deve avere almeno 8 caratteri.",
        pl="Hasło pliku klucza musi mieć co najmniej 8 znaków.",
        ru="Пароль файла ключа не менее 8 символов.",
        tr="Anahtar dosyası parolası en az 8 karakter olmalı.",
        hr="Lozinka datoteke ključa mora imati najmanje 8 znakova.",
        zh="密钥文件密码至少 8 个字符。",
    ),
    "err.key_pw_required": L(
        fr="Mot de passe du fichier clé requis.", es="Se requiere contraseña del archivo de clave.",
        it="Password del file chiave richiesta.", pl="Wymagane hasło pliku klucza.",
        ru="Требуется пароль файла ключа.", tr="Anahtar dosyası parolası gerekli.",
        hr="Potrebna je lozinka datoteke ključa.", zh="需要密钥文件密码。",
    ),
    "err.not_pw_key": L(
        fr="Ce n’est pas un fichier clé protégé par mot de passe.",
        es="No es un archivo de clave protegido con contraseña.",
        it="Non è un file chiave protetto da password.",
        pl="To nie jest plik klucza chroniony hasłem.",
        ru="Это не файл ключа с паролем.",
        tr="Parola korumalı anahtar dosyası değil.",
        hr="Nije datoteka ključa zaštićena lozinkom.",
        zh="不是受密码保护的密钥文件。",
    ),
    "err.wrong_key_pw": L(
        fr="Mot de passe du fichier clé incorrect.", es="Contraseña del archivo de clave incorrecta.",
        it="Password del file chiave errata.", pl="Nieprawidłowe hasło pliku klucza.",
        ru="Неверный пароль файла ключа.", tr="Anahtar dosyası parolası yanlış.",
        hr="Pogrešna lozinka datoteke ključa.", zh="密钥文件密码错误。",
    ),
    "err.invalid_key_file": L(
        fr="Fichier clé invalide.", es="Archivo de clave no válido.", it="File chiave non valido.",
        pl="Nieprawidłowy plik klucza.", ru="Недопустимый файл ключа.", tr="Geçersiz anahtar dosyası.",
        hr="Nevažeća datoteka ključa.", zh="无效的密钥文件。",
    ),
    "err.no_encrypted_files": L(
        fr="Aucun fichier chiffré.", es="No hay archivos cifrados.", it="Nessun file cifrato.",
        pl="Brak zaszyfrowanych plików.", ru="Нет зашифрованных файлов.", tr="Şifreli dosya yok.",
        hr="Nema šifriranih datoteka.", zh="没有加密文件。",
    ),
    "err.no_files_to_seal": L(
        fr="Aucun fichier à verrouiller.", es="No hay archivos para sellar.", it="Nessun file da sigillare.",
        pl="Brak plików do zablokowania.", ru="Нет файлов для блокировки.", tr="Kilitlenecek dosya yok.",
        hr="Nema datoteka za zaključavanje.", zh="没有可密封的文件。",
    ),
    "err.verify_fail_detail": L(
        fr="Échec du contrôle d’intégrité : {detail}",
        es="Fallo de comprobación de integridad: {detail}",
        it="Controllo integrità non riuscito: {detail}",
        pl="Kontrola integralności nie powiodła się: {detail}",
        ru="Проверка целостности не удалась: {detail}",
        tr="Bütünlük kontrolü başarısız: {detail}",
        hr="Provjera cjelovitosti nije uspjela: {detail}",
        zh="完整性检查失败：{detail}",
    ),
    "err.usb_refuse_format": L(
        fr="Formatage refusé : ce n’est pas un périphérique USB.",
        es="Formato rechazado: no es un dispositivo USB.",
        it="Formattazione rifiutata: non è un dispositivo USB.",
        pl="Odmowa formatowania: to nie jest urządzenie USB.",
        ru="Форматирование отклонено: это не USB-устройство.",
        tr="Biçimlendirme reddedildi: USB aygıtı değil.",
        hr="Formatiranje odbijeno: nije USB uređaj.",
        zh="拒绝格式化：不是 USB 设备。",
    ),
    "err.usb_mount_missing": L(
        fr="Montage USB indisponible.", es="Montaje USB no disponible.", it="Mount USB non disponibile.",
        pl="Montowanie USB niedostępne.", ru="USB-монтирование недоступно.", tr="USB bağlama yok.",
        hr="USB mount nije dostupan.", zh="USB 挂载不可用。",
    ),
    "err.usb_clear_keys": L(
        fr="Impossible de supprimer les anciens fichiers clé du stick.",
        es="No se pudieron borrar los archivos de clave antiguos del stick.",
        it="Impossibile rimuovere i vecchi file chiave dallo stick.",
        pl="Nie udało się usunąć starych plików klucza z pendrive’a.",
        ru="Не удалось удалить старые файлы ключей с накопителя.",
        tr="Eski anahtar dosyaları bellekten silinemedi.",
        hr="Nije moguće obrisati stare datoteke ključa sa sticka.",
        zh="无法清除棒上的旧密钥文件。",
    ),
    "job.timeout": L(
        fr="Délai dépassé", es="Tiempo de espera agotado", it="Timeout",
        pl="Limit czasu", ru="Тайм-аут", tr="Zaman aşımı", hr="Istek vremena", zh="超时",
    ),
}
# fmt: on

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
    'LANG_COOKIE = "lk_lang"',
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
        '        del _thread_lang.value',
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
        "        set_thread_lang(c)",
        "        return c",
        '    q = normalize_lang(request.args.get("lang"))',
        "    if q:",
        "        set_thread_lang(q)",
        "        return q",
        '    al = (request.headers.get("Accept-Language") or "").lower()',
        '    for part in al.split(","):',
        '        token = part.split(";", 1)[0].strip()',
        "        picked = normalize_lang(token)",
        "        if picked:",
        "            set_thread_lang(picked)",
        "            return picked",
        "    lng = env_lang()",
        "    set_thread_lang(lng)",
        "    return lng",
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
        '    lng = normalize_lang(lang) or "en"',
        '    return dict(STRINGS.get(lng, STRINGS["en"]))',
        "",
        "",
        "def supported_langs() -> list[str]:",
        "    return list(LANG_LABELS.keys())",
        "",
        "",
        "class I18nError(ValueError):",
        '    """User-facing error with message key for UI language switching."""',
        "",
        "    def __init__(self, key: str, **params: Any):",
        "        self.key = key",
        "        self.params = params",
        "        super().__init__(t(key, **params))",
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

spec = importlib.util.spec_from_file_location("lock_and_key_i18n", SRC)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)

assert mod.LANG_COOKIE == "lk_lang"
assert mod.normalize_lang("fr-FR") == "fr"
assert mod.normalize_lang("hr") == "hr"
assert mod.normalize_lang("zh_CN") == "zh"
assert set(mod.LANG_LABELS) == set(ORDER)
for lang in ORDER:
    assert set(mod.STRINGS[lang]) == set(en), lang
assert len(mod.STRINGS["hr"]) == len(en)
assert hasattr(mod, "I18nError")
assert hasattr(mod, "supported_langs")
assert mod.supported_langs() == ORDER

print("OK wrote", SRC)
print("synced", public_msg)
print("langs", list(mod.LANG_LABELS))
print("keys", len(en))
