# 🍪 Cookies для Linux сервера

## Проблема:
На Linux сервере нет Chrome/Firefox → yt-dlp не может читать cookies из браузера

## Решение:
Экспортировать cookies в файл на Mac → загрузить на сервер

---

## 📝 Инструкция:

### Шаг 1: Экспорт cookies из Chrome (на Mac)

#### Вариант A: Расширение "Get cookies.txt LOCALLY" (РЕКОМЕНДУЮ)
```bash
# 1. Установи расширение:
open "https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc"

# 2. Зайди на youtube.com в Chrome (войди в аккаунт если нужно)

# 3. Кликни на иконку расширения → Export → youtube.com
# Сохрани как: youtube_cookies.txt
```

#### Вариант B: Вручную через Python
```bash
# На Mac:
pip3 install browser-cookie3

python3 << 'PYEOF'
import browser_cookie3
import http.cookiejar

# Получаем cookies из Chrome
cj = browser_cookie3.chrome(domain_name='.youtube.com')

# Сохраняем в Netscape формат
with open('youtube_cookies.txt', 'w') as f:
    f.write('# Netscape HTTP Cookie File\n')
    for cookie in cj:
        if '.youtube.com' in cookie.domain:
            f.write(f'{cookie.domain}\tTRUE\t{cookie.path}\t'
                   f'{"TRUE" if cookie.secure else "FALSE"}\t{cookie.expires or 0}\t'
                   f'{cookie.name}\t{cookie.value}\n')
print("✅ Saved to youtube_cookies.txt")
PYEOF
```

### Шаг 2: Загрузить на сервер

```bash
# Скопируй файл на Linux сервер
scp youtube_cookies.txt server2:/home/user/sambot-v2/cookies/

# Или в Docker volume
scp youtube_cookies.txt server2:/var/docker/sambot/cookies/
```

### Шаг 3: Настроить на сервере

```bash
# На Linux сервере, в .env добавь:
echo "COOKIES_FILE=/app/cookies/youtube_cookies.txt" >> .env

# В docker-compose.yml добавь volume:
# volumes:
#   - ./cookies:/app/cookies:ro
```

---

## 🔄 Обновление cookies

**Как часто:** Каждые 30-60 дней (когда YouTube сессия истекает)

**Автоматизация:**
```bash
# Cron job на Mac (каждый месяц):
0 0 1 * * cd /path/to/project && python3 export_cookies.py && scp youtube_cookies.txt server2:/path/
```

---

## ✅ Проверка:

```bash
# На сервере:
docker-compose logs youtube_extractor | grep "cookiefile"
# Должно быть: Using cookiefile: /app/cookies/youtube_cookies.txt

# Тест:
curl -X POST 'http://localhost:8001/extract' \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://www.youtube.com/watch?v=TEST_ID"}'
```
