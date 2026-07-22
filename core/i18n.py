"""Bilingual (RU/EN) dictionary + tiny observer for live language switching."""
from __future__ import annotations

from typing import Callable

STRINGS: dict[str, dict[str, str]] = {
    # Common ---------------------------------------------------------------
    "app.title":            {"ru": "Prizma Studio",                    "en": "Prizma Studio"},
    "app.tagline":          {"ru": "PDF + PSD в одном окне",            "en": "PDF + PSD in a single window"},
    "tab.pdf":              {"ru": "PDF Tools",                         "en": "PDF Tools"},
    "tab.psd":              {"ru": "PSD Tools",                         "en": "PSD Tools"},
    "tab.settings":         {"ru": "Настройки",                         "en": "Settings"},
    "tab.about":            {"ru": "О программе",                       "en": "About"},
    "lang.label":           {"ru": "Язык:",                             "en": "Language:"},
    "lang.ru":              {"ru": "Русский",                           "en": "Russian"},
    "lang.en":              {"ru": "Английский",                        "en": "English"},
    "status.ready":         {"ru": "Готово",                            "en": "Ready"},
    "log.title":            {"ru": "Журнал",                            "en": "Log"},
    "log.clear":            {"ru": "Очистить",                          "en": "Clear"},
    "common.browse":        {"ru": "Обзор…",                            "en": "Browse…"},
    "common.apply":         {"ru": "Применить",                         "en": "Apply"},
    "common.cancel":        {"ru": "Отмена",                            "en": "Cancel"},
    "common.ok":            {"ru": "ОК",                                "en": "OK"},
    "common.save":          {"ru": "Сохранить",                         "en": "Save"},
    "common.open":          {"ru": "Открыть",                           "en": "Open"},

    # PDF tab --------------------------------------------------------------
    "pdf.open":             {"ru": "Открыть PDF",                       "en": "Open PDF"},
    "pdf.save":             {"ru": "Сохранить как…",                    "en": "Save as…"},
    "pdf.close":            {"ru": "Закрыть",                           "en": "Close"},
    "pdf.merge":            {"ru": "Слить PDF-файлы…",                  "en": "Merge PDFs…"},
    "pdf.page":             {"ru": "Страница",                          "en": "Page"},
    "pdf.of":               {"ru": "из",                                "en": "of"},
    "pdf.zoom.in":          {"ru": "Приблизить",                        "en": "Zoom in"},
    "pdf.zoom.out":         {"ru": "Отдалить",                          "en": "Zoom out"},
    "pdf.zoom.fit":         {"ru": "По ширине",                         "en": "Fit width"},
    "pdf.prev":             {"ru": "◀ Пред.",                           "en": "◀ Prev"},
    "pdf.next":             {"ru": "След. ▶",                           "en": "Next ▶"},
    "pdf.rotate.left":      {"ru": "Повернуть влево",                   "en": "Rotate left"},
    "pdf.rotate.right":     {"ru": "Повернуть вправо",                  "en": "Rotate right"},
    "pdf.delete.page":      {"ru": "Удалить страницу",                  "en": "Delete page"},
    "pdf.move.up":          {"ru": "Переместить ↑",                     "en": "Move ↑"},
    "pdf.move.down":        {"ru": "Переместить ↓",                     "en": "Move ↓"},
    "pdf.insert.text":      {"ru": "Вставить текст",                    "en": "Insert text"},
    "pdf.insert.image":     {"ru": "Вставить изображение",              "en": "Insert image"},
    "pdf.edit.text":        {"ru": "Редактировать текст",               "en": "Edit text"},
    "pdf.section.file":     {"ru": "Файл",                              "en": "File"},
    "pdf.section.pages":    {"ru": "Страницы",                          "en": "Pages"},
    "pdf.section.edit":     {"ru": "Правка",                            "en": "Edit"},
    "pdf.section.view":     {"ru": "Вид",                               "en": "View"},
    "pdf.dialog.text":      {"ru": "Текст для вставки:",                "en": "Text to insert:"},
    "pdf.dialog.oldtext":   {"ru": "Заменить текст:",                   "en": "Replace text:"},
    "pdf.dialog.newtext":   {"ru": "На:",                               "en": "With:"},
    "pdf.no.document":      {"ru": "Документ не открыт",                "en": "No document open"},
    "pdf.saved":            {"ru": "Сохранено:",                        "en": "Saved:"},
    "pdf.opened":           {"ru": "Открыт:",                           "en": "Opened:"},
    "pdf.merge.title":      {"ru": "Выберите PDF-файлы для слияния",    "en": "Select PDF files to merge"},

    # PSD tab --------------------------------------------------------------
    "psd.open":             {"ru": "Открыть PSD/PSB",                   "en": "Open PSD/PSB"},
    "psd.scan":             {"ru": "Сканировать слои",                  "en": "Scan layers"},
    "psd.unlock":           {"ru": "Разблокировать все слои",           "en": "Unlock all layers"},
    "psd.replace":          {"ru": "Заменить фото в Smart Object",      "en": "Replace photo in Smart Object"},
    "psd.batch":            {"ru": "Пакетная замена по папке",          "en": "Batch replace by folder"},
    "psd.in.folder":        {"ru": "Папка исходников",                  "en": "Source folder"},
    "psd.out.folder":       {"ru": "Папка вывода",                      "en": "Output folder"},
    "psd.mode":             {"ru": "Режим",                             "en": "Mode"},
    "psd.mode.fit":         {"ru": "Fit (вписать)",                     "en": "Fit"},
    "psd.mode.fill":        {"ru": "Fill (заполнить)",                  "en": "Fill"},
    "psd.mode.original":    {"ru": "Original (сохранить формат)",       "en": "Original (keep format)"},
    "psd.mode.hint":        {"ru": "Fit — вписать с полями · Fill — заполнить с обрезкой · Original — сохранить пропорции нового фото (без обрезки и искажений)",
                             "en": "Fit — inside with margins · Fill — crop to fill · Original — preserve new photo aspect (no crop, no distortion)"},
    "psd.no_upscale":       {"ru": "Не увеличивать (сохранить резкость)",
                             "en": "No upscaling (keep sharpness)"},
    "psd.crop_bbox":        {"ru": "Обрезать по рамке слоя",
                             "en": "Crop to layer bbox"},
    "psd.quality.hint":     {"ru": "«Не увеличивать» — если новое фото меньше рамки, оно не растягивается (иначе Photoshop дорисовывает пиксели → мыло). «Обрезать по рамке» — новое фото не вылезет за оригинальный размер слоя. Ресемплинг: Bicubic Sharper.",
                             "en": "“No upscaling” — if the new photo is smaller than the frame, it will not be enlarged (upscaling forces Photoshop to invent pixels → blur). “Crop to bbox” — the new photo cannot bleed past the original layer frame. Resampling: Bicubic Sharper."},
    "psd.depth":            {"ru": "Глубина Smart Object",              "en": "Smart Object depth"},
    "psd.section.file":     {"ru": "Файл",                              "en": "File"},
    "psd.section.layers":   {"ru": "Слои",                              "en": "Layers"},
    "psd.section.actions":  {"ru": "Действия",                          "en": "Actions"},
    "psd.section.batch":    {"ru": "Пакетная обработка",                "en": "Batch"},
    "psd.no.photoshop":     {"ru": "Photoshop не найден. PSD-функции недоступны.",
                             "en": "Photoshop not found. PSD features unavailable."},
    "psd.no.file":          {"ru": "Файл PSD не открыт",                "en": "No PSD file open"},
    "psd.select.layer":     {"ru": "Выберите Smart Object в списке",    "en": "Select a Smart Object from the list"},
    "psd.done":             {"ru": "Готово",                            "en": "Done"},
    "psd.processing":       {"ru": "Обработка…",                        "en": "Processing…"},

    # Settings tab ---------------------------------------------------------
    "settings.language":    {"ru": "Язык интерфейса",                   "en": "Interface language"},
    "settings.theme":       {"ru": "Тема оформления",                   "en": "Theme"},
    "settings.theme.system":{"ru": "Системная",                         "en": "System"},
    "settings.theme.light": {"ru": "Светлая",                           "en": "Light"},
    "settings.theme.dark":  {"ru": "Тёмная",                            "en": "Dark"},
    "settings.paths":       {"ru": "Пути по умолчанию",                 "en": "Default paths"},
    "settings.pdf_dir":     {"ru": "PDF – рабочая папка",               "en": "PDF – working folder"},
    "settings.psd_in":      {"ru": "PSD – папка исходников",            "en": "PSD – source folder"},
    "settings.psd_out":     {"ru": "PSD – папка вывода",                "en": "PSD – output folder"},
    "settings.depth":       {"ru": "Глубина Smart Object",              "en": "Smart Object depth"},
    "settings.restart":     {"ru": "Изменение языка применяется мгновенно.",
                             "en": "Language change is applied instantly."},

    # About tab ------------------------------------------------------------
    "about.name":           {"ru": "Prizma Studio",                     "en": "Prizma Studio"},
    "about.version":        {"ru": "Версия",                            "en": "Version"},
    "about.author":         {"ru": "Автор",                             "en": "Author"},
    "about.description":    {
        "ru": "Единое приложение для работы с PDF и PSD-шаблонами.\n"
              "PDF Tools — просмотр, редактирование, слияние, вставка текста и изображений.\n"
              "PSD Tools — разблокировка слоёв, замена фото в Smart Objects, пакетная обработка.",
        "en": "All-in-one desktop toolkit for PDF and PSD templates.\n"
              "PDF Tools — view, edit, merge, insert text and images.\n"
              "PSD Tools — unlock layers, replace photos in Smart Objects, batch processing.",
    },
    "about.tech":           {"ru": "Технологии",                        "en": "Technologies"},

    # Errors ---------------------------------------------------------------
    "error.title":          {"ru": "Ошибка",                            "en": "Error"},
    "info.title":           {"ru": "Информация",                        "en": "Information"},
}


class I18N:
    """Simple translator with an observer pattern for live re-translation."""

    def __init__(self, language: str = "ru") -> None:
        self._lang = language if language in ("ru", "en") else "ru"
        self._subscribers: list[Callable[[], None]] = []

    @property
    def language(self) -> str:
        return self._lang

    def set_language(self, lang: str) -> None:
        if lang not in ("ru", "en") or lang == self._lang:
            return
        self._lang = lang
        for cb in list(self._subscribers):
            try:
                cb()
            except Exception:
                pass

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback) if callback in self._subscribers else None

    def t(self, key: str) -> str:
        entry = STRINGS.get(key)
        if not entry:
            return key
        return entry.get(self._lang) or entry.get("ru") or key


# Singleton translator.
i18n = I18N()
