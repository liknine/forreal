# ForReal v58 — fix WebApp orders not reaching bot

Причина: каталог открывался через inline web_app кнопку. Для `Telegram.WebApp.sendData()` нужен запуск Mini App через `KeyboardButton(web_app)` — кнопку внизу у поля ввода.

Что заменить:
- `bot/keyboards.py`
- `bot/main.py`

Что НЕ трогать:
- `bot/.env`
- `data/products.json`
- `images/products/`
- `.venv/`
- `forreal.sqlite3`

После замены:
1. Перезапустить бота.
2. В Telegram отправить `/start`.
3. Открывать каталог только через кнопку `Открыть каталог` снизу возле поля ввода, не через старую кнопку под старым сообщением.
4. Оформить заказ через CDEK/Яндекс.
5. В терминале должно появиться `WEB_APP_DATA RECEIVED`.
