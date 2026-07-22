# Acceptance checklist — PSD Tools patch

Ручные сценарии для проверки на Windows-машине с установленным Adobe Photoshop.

## Настройка
1. Установить зависимости: `pip install pywin32 pillow pymupdf`
2. Запустить Photoshop хотя бы один раз (чтобы COM зарегистрировался).
3. Standalone-запуск вкладки: `python -m modules.psd_tools_tab`

## Сценарии

### 1. JPG → Smart Object
- [ ] Открыть PSD с SO-слоем «placeholder»
- [ ] Выбрать JPG (sRGB) как замену
- [ ] Режим «Smart Object» → «Заменить в выбранных»
- [ ] Ожидание: SO обновлён, диалогов Camera Raw/Missing Profile нет, PS не «завис»

### 2. PNG → Smart Object
- [ ] Тот же PSD, PNG с прозрачностью → Smart Object
- [ ] Ожидание: замена без диалогов, альфа сохранена

### 3. JPG → растровый слой
- [ ] PSD с обычным Layer «bg»
- [ ] JPG → режим «Растровый слой»
- [ ] Ожидание: пиксели слоя заменены Merge Down'ом

### 4. 5 замен подряд без перезапуска PS
- [ ] Загрузить 5 разных изображений подряд в один и тот же SO
- [ ] Ожидание: ни одно из RETRYLATER не приводит к падению, retry-обёртка их «съедает»

### 5. Разные цветовые профили
- [ ] sRGB JPG
- [ ] AdobeRGB JPG
- [ ] CMYK TIFF
- [ ] Ожидание: во всех случаях диалог профиля НЕ появляется (Pillow-нормализация в PNG без ICC)

### 6. PSB внутри SO (крупный файл)
- [ ] PSD, где SO содержит PSB > 500 MB
- [ ] Ожидание: возможны задержки, но благодаря retry+wait_ready операция завершается без -2147417846

## Что проверять при ошибке
- В stderr должен быть `[psd_tools_tab] COM error hresult=<число>` — приложить в баг-репорт
- Логи PS: `Edit → Preferences → History Log`
