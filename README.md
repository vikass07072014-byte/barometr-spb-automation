# Barometr SPB Automation

Автоматизация карточек для Instagram-профиля `@barometr.spb`.

## Что уже работает

- генерация ежедневной карточки `1080 × 1350`, формат `4:5`;
- прогноз на завтра и компактный блок текущего дня;
- тайм-лайн осадков, давление, ветер, влажность, восход и закат;
- выбор заведения и позиции меню из проверяемой базы;
- крупное изображение блюда или напитка на переднем плане;
- проверка размера и формата перед публикацией;
- GitHub Actions: ручной запуск и расписание на `07:50 МСК`;
- публикация в `08:00 МСК` через Buffer API;
- сохранение `buffer_post_id` и времени постановки в очередь.

Автопубликация по умолчанию **выключена**. Тестовые данные не отправляются в Instagram.

## Локальная проверка

```bash
python -m pip install -r requirements.txt
python src/render_card.py --weather data/weather.example.json --output docs/latest.jpg
python src/validate_card.py docs/latest.jpg --manifest docs/latest-manifest.json --allow-warnings
python src/build_caption.py --weather data/weather.example.json --manifest docs/latest-manifest.json --output docs/latest-caption.txt
```

## Настройка GitHub

1. Включить GitHub Pages: `Settings → Pages → Deploy from a branch → main / docs`.
2. Создать Buffer Free, подключить Creator-аккаунт Instagram напрямую через Instagram Login.
3. Добавить Repository secrets:
   - `BUFFER_API_KEY`
   - `BUFFER_CHANNEL_ID`
4. Добавить Repository variables:
   - `AUTOMATION_ENABLED=true` — включает запуск по расписанию;
   - `AUTO_PUBLISH=true` — включает публикацию без утверждения;
5. Сначала запустить `Actions → Daily Barometr SPB → Run workflow` с `publish=false`.
6. Проверить `docs/latest.jpg`; только после этого разрешать публикацию.

## Защитные правила

- секреты никогда не записываются в репозиторий;
- без `AUTO_PUBLISH=true` отправка в Instagram блокируется;
- для публикации создаётся JPEG 1080 × 1350;
- карточка не публикуется без валидного прогноза и готового заведения;
- алкогольные позиции маркируются `18+` и не получают рекламных призывов;
- URL, Buffer post ID и запланированное время сохраняются в receipt-файле;
- бесплатный лимит Buffer — до 10 одновременно запланированных публикаций.

## Статус контента

В `data/venues.json` сейчас находятся первые позиции. Для полной недельной ротации необходимо добавить проверенные заведения и отдельные изображения блюд/напитков на прозрачном фоне. До этого безопаснее использовать ручное утверждение.

## Погода

Прогноз загружается из бесплатного `MET Norway Locationforecast 2.0` без API-ключа. Данные разрешены для коммерческого использования по CC BY 4.0 при обязательной атрибуции. Скрипт отправляет идентифицирующий `User-Agent`, делает два запроса в сутки (прогноз и восход/закат), а источник указывается на карточке и в подписи.
