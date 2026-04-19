# Russia Mobile VPN Aggregator

Автоматический агрегатор VPN-конфигов, оптимизированных для мобильного использования в России.
Собирает, тестирует и отбирает лучшие 100 конфигураций с минимальным пингом.

## 🚀 Быстрый старт

### 1. Установка и настройка

```bash
# Клонируйте репозиторий
git clone https://github.com/ВАШНИК/russia-mobile-vpn-aggregator.git
cd russia-mobile-vpn-aggregator

# Настройте окружение (один раз)
python setup_env.py

# Запустите агрегатор
python main.py
```

### 2. Настройка GitHub Actions (для автообновления)

1. Загрузите репозиторий на GitHub
2. Добавьте `GITHUB_TOKEN` в Settings → Secrets and variables → Actions
3. Actions будут запускаться автоматически каждый час

## 📋 Описание работы

### Источники конфигов

- **igarek**: VLESS Reality, VLESS Black, White Lists, CIDR, SNI
- **goida**: VPN-конфиги с зеркала
- **itdog**: Shadowsocks серверы
- **Дополнительные**: Другие популярные репозитории

### Процесс работы

1. **Сбор** — скачивание конфигов из всех источников
2. **Парсинг** — извлечение vless://, trojan://, vmess://, ss://
3. **Дедупликация** — удаление повторяющихся конфигов
4. **Тестирование** — проверка через sing-box (параллельно, 20 воркеров)
5. **Геолокация** — определение страны сервера
6. **Отбор** — топ-100 по пингу, максимум 5 серверов из РФ
7. **Генерация** — итоговый файл с profile-title

<!-- STATS_START -->
## 📊 Статистика (автообновление)

- **Последнее обновление:** 2026-04-20 00:51:10 UTC
- **Всего протестировано:** 564
- **Рабочих конфигов:** 500
- **В топ-100:** 100
- **Средний пинг:** 38.7ms

### Распределение по странам (топ-100):
- 🇷🇺 RU: 34
- 🇺🇸 US: 29
- 🇩🇪 DE: 12
- 🇫🇮 FI: 8
- 🇨🇦 CA: 6
- 🇸🇪 SE: 3
- 🇱🇻 LV: 3
- 🇳🇱 NL: 2
- 🇨🇾 CY: 1
- 🇵🇱 PL: 1
- 🇪🇪 EE: 1
<!-- STATS_END -->

## 📁 Структура репозитория

```
.
├── main.py                      # Основной скрипт (единственный .py файл)
├── setup_env.py                 # Настройка окружения
├── .env.example                 # Шаблон переменных окружения
├── .github/workflows/           # GitHub Actions
│   └── update-configs.yml       # Автообновление каждый час
├── README.md                    # Этот файл
├── top100_mobile_aggregated.txt # ⭐ Итоговый файл с конфигами
├── raw/                         # Сырые данные для отладки
└── LICENSE                      # MIT License
```

## 🔗 Итоговый файл

**Прямая ссылка на конфиги:**
```
https://raw.githubusercontent.com/ВАШНИК/russia-mobile-vpn-aggregator/main/top100_mobile_aggregated.txt
```

## ⚙️ Требования

- Python 3.11+
- sing-box (скачивается автоматически через singbox2proxy)

## 📦 Зависимости

Все зависимости устанавливаются автоматически:

- `singbox2proxy` — работа с sing-box
- `requests` — HTTP запросы
- `aiohttp` — асинхронные HTTP запросы
- `dnspython` — DNS резолвинг
- `python-dotenv` — переменные окружения

## 🛠️ Ручной запуск

```bash
# Установка зависимостей вручную (если нужно)
pip install singbox2proxy requests python-dotenv aiohttp dnspython

# Запуск
python main.py
```

## 📝 Формат выходного файла

```
text# profile-title: MITAY VPN | Белые списки

vless://...#🇩🇪 Mitay VPN | Germany
trojan://...#🇸🇬 Mitay VPN | Singapore
vmess://...#🇳🇱 Mitay VPN | Netherlands
...
```

## 🔔 GitHub Actions

Workflow запускается:
- Автоматически каждый час (`0 * * * *`)
- Вручную через вкладку Actions

Таймаут: 35 минут

## 📄 Лицензия

MIT License — см. файл [LICENSE](LICENSE)

## 👤 Автор

**Mitay VPN**

---

*Сгенерировано автоматически Russia Mobile VPN Aggregator*
