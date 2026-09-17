import os
import re
import tempfile
import logging
import asyncio
import threading
import urllib.parse
from typing import Optional
from models import AppConfig
from PyQt5.QtCore import QObject, pyqtSignal

class HelpdeskSignals(QObject):
    ticket_created = pyqtSignal(str, str) # host_name, status_action
    ticket_failed = pyqtSignal(str, str, str) # host_name, status_action, error_msg

class HelpdeskService:
    """Сервис для работы с Helpdesk (Асинхронная реализация)"""
    _loop = None
    _thread = None
    _lock = threading.Lock()
    _semaphore = None
    signals = HelpdeskSignals()

    SAVE_BUTTON_SELECTOR = (
        "#gwt-debug-apply, #gwt-debug-buttons .g-button, [id*='debug-apply'], "
        "div.g-button:has-text('Сохранить'), button:has-text('Сохранить'), "
        "[role='button']:has-text('Сохранить'), .g-button:has-text('Сохранить')"
    )

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        """Семафор для ограничения: не более 1 параллельной сессии браузера"""
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(1)
        return cls._semaphore

    @staticmethod
    def _get_error_screenshot_path(host_name: str) -> str:
        """Безопасный путь к скриншоту ошибки в системной временной папке %TEMP%"""
        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(host_name or "unknown"))
        return os.path.join(tempfile.gettempdir(), f"helpdesk_error_{clean_name}.png")

    @classmethod
    async def _capture_error_screenshot(cls, page, host_name: str) -> Optional[str]:
        """Сохранение скриншота при ошибке в %TEMP%"""
        if not page:
            return None
        try:
            path = cls._get_error_screenshot_path(host_name)
            await page.screenshot(path=path)
            logging.info(f"Helpdesk: Скриншот ошибки сохранён: {path}")
            return path
        except Exception as e:
            logging.debug(f"Helpdesk: Не удалось сохранить скриншот ошибки: {e}")
            return None

    @classmethod
    def _start_loop(cls):
        with cls._lock:
            if cls._thread and cls._thread.is_alive():
                return
                
            cls._loop = asyncio.new_event_loop()
            
            def run_loop():
                asyncio.set_event_loop(cls._loop)
                cls._loop.run_forever()
                
            cls._thread = threading.Thread(target=run_loop, daemon=True, name="HelpdeskAsyncLoop")
            cls._thread.start()

    @classmethod
    def _log_future_error(cls, future, host_name: str, action: str):
        """Callback для логирования ошибок из фоновых корутин"""
        def _callback(fut):
            try:
                fut.result()
            except Exception as e:
                logging.error(f"HelpdeskService: Ошибка заявки ({action}) для {host_name}: {e}")
        future.add_done_callback(_callback)

    @classmethod
    def shutdown(cls):
        """Остановка фонового потока и цикла событий"""
        try:
            if cls._loop and cls._loop.is_running():
                cls._loop.call_soon_threadsafe(cls._loop.stop)
            if cls._thread and cls._thread.is_alive():
                cls._thread.join(timeout=2.0)
        except Exception as e:
            logging.error(f"Ошибка при остановке пула Helpdesk: {e}")

    @classmethod
    def process_offline(cls, hosts: list, config: AppConfig, reason: str = "без связи"):
        if not config.helpdesk_enabled or not config.helpdesk_url:
            return
        cls._start_loop()
        headless = getattr(config, 'helpdesk_headless', False)
        for host in hosts:
            logging.info(f"HelpdeskService: Планирование заявки (Установить) для {host} (headless={headless})")
            future = asyncio.run_coroutine_threadsafe(
                asyncio.wait_for(cls._process_ticket_task_async(config.helpdesk_url, host, "Установить", reason, headless=headless), timeout=60.0),
                cls._loop
            )
            cls._log_future_error(future, host, "Установить")
            
    @classmethod
    def process_recovered(cls, hosts: list, config: AppConfig, reason: str = "восстановление связи"):
        if not config.helpdesk_enabled or not config.helpdesk_url:
            return
        cls._start_loop()
        headless = getattr(config, 'helpdesk_headless', False)
        for host in hosts:
            logging.info(f"HelpdeskService: Планирование заявки (Снять) для {host} (headless={headless})")
            future = asyncio.run_coroutine_threadsafe(
                asyncio.wait_for(cls._process_ticket_task_async(config.helpdesk_url, host, "Снять", reason, headless=headless), timeout=60.0),
                cls._loop
            )
            cls._log_future_error(future, host, "Снять")

    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Нормализует URL Helpdesk:
        обрезает пробелы и гарантирует схему https://, если протокол не указан.
        """
        if not url:
            return ""
        url = str(url).strip()
        if not url:
            return ""
        if not url.startswith("http://") and not url.startswith("https://"):
            return f"https://{url}"
        return url

    @staticmethod
    def format_atm_number(host_name: str) -> str:
        """
        Форматирует имя хоста/номер банкомата для Helpdesk:
        добавляет префикс '0000', если значение уже не начинается с '0000'.
        """
        if not host_name:
            return ""
        name = str(host_name).strip()
        if not name:
            return ""
        if name.startswith("0000"):
            return name
        return f"0000{name}"

    @staticmethod
    def get_launch_args(url: str) -> list:
        """
        Формирует аргументы запуска браузера с поддержкой Windows SSO / NTLM / Kerberos.
        Исключает кавычки в значениях флагов, блокирующие распознавание домена Chromium.
        """
        args = [
            '--auth-schemes=basic,digest,ntlm,negotiate',
            '--disable-blink-features=AutomationControlled',
        ]
        if url:
            domain = urllib.parse.urlparse(url).netloc
            if ":" in domain:
                domain = domain.split(":")[0]
            domain = domain.strip()
            if domain:
                args.insert(0, f'--auth-server-allowlist=*{domain}*')
                args.insert(1, f'--auth-negotiate-delegate-allowlist=*{domain}*')
        return args

    @classmethod
    async def _process_ticket_task_async(cls, url: str, host_name: str, status_action: str, reason: str = "без связи", headless: bool = False):
        async with cls._get_semaphore():
            page = None
            browser = None
            try:
                from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
                
                url = HelpdeskService.normalize_url(url)
                async with async_playwright() as p:
                    logging.info(f"Запуск Playwright для {host_name} ({status_action}), URL: {url}, headless: {headless}")
                    launch_args = cls.get_launch_args(url)
                    for channel in ["msedge", "chrome", None]:
                        try:
                            kwargs = {"headless": headless, "args": launch_args}
                            if channel:
                                kwargs["channel"] = channel
                            browser = await p.chromium.launch(**kwargs)
                            break
                        except Exception:
                            continue

                    if not browser:
                        raise RuntimeError("Не удалось запустить браузер (Microsoft Edge или Chrome не найдены в системе)")

                    context = await browser.new_context()
                    page = await context.new_page()
                    
                    try:
                        # Переход на страницу добавления заявки с явным таймаутом
                        await page.goto(url, timeout=20000)
                        try:
                            await page.wait_for_load_state('networkidle', timeout=10000)
                        except Exception:
                            pass

                        # 1. Поиск контекста формы (в основном окне или во встроенных iframes)
                        form_ctx = None
                        for _ in range(50):  # До 25 секунд с шагом 500мс
                            contexts = [page] + list(page.frames)
                            for ctx in contexts:
                                try:
                                    marker = ctx.locator(
                                        "xpath=//*[self::label or self::div or self::span or self::td or self::th]"
                                        "[contains(normalize-space(), 'Местонахождение') or contains(normalize-space(), 'Соглашение') or contains(normalize-space(), 'Услуга')]"
                                    ).first
                                    if await marker.count() > 0 and await marker.is_visible():
                                        form_ctx = ctx
                                        break
                                except Exception:
                                    continue
                            if form_ctx:
                                break
                            await page.wait_for_timeout(500)

                        if not form_ctx:
                            logging.warning("Контекст формы не обнаружен по маркерам, используем page")
                            form_ctx = page

                        # 2. Асинхронная функция для выбора значения в выпадающем списке
                        async def select_dropdown(label: str, text_to_select: str) -> bool:
                            try:
                                lbl = form_ctx.locator(
                                    f"xpath=//*[self::label or self::div or self::span or self::td or self::th][contains(normalize-space(), '{label}')]"
                                ).first
                                if await lbl.count() == 0:
                                    lbl = page.locator(
                                        f"xpath=//*[self::label or self::div or self::span or self::td or self::th][contains(normalize-space(), '{label}')]"
                                    ).first
                                    if await lbl.count() == 0:
                                        logging.warning(f"Метка выпадающего списка '{label}' не найдена")
                                        return False

                                row = lbl.locator("xpath=ancestor::tr[1] | .. | ../..").first

                                # а) Стандартный HTML <select>
                                sel = row.locator("select").first
                                if await sel.count() > 0 and await sel.is_visible():
                                    try:
                                        await sel.select_option(label=text_to_select, timeout=3000)
                                        await page.wait_for_timeout(400)
                                        return True
                                    except Exception:
                                        pass

                                # б) Кастомный выпадающий список (GWT / Select2 / input)
                                clickable = row.locator("input, select, .select2-selection, .combo-box, [role='combobox'], .gwt-SuggestBox").first
                                if await clickable.count() > 0 and await clickable.is_visible():
                                    await clickable.click(timeout=3000)
                                    await page.wait_for_timeout(400)

                                    opt = form_ctx.get_by_text(text_to_select, exact=True).last
                                    if await opt.count() == 0:
                                        opt = page.get_by_text(text_to_select, exact=True).last
                                    if await opt.count() > 0:
                                        await opt.click(timeout=3000)
                                        await page.wait_for_timeout(400)
                                        return True
                            except Exception as ex:
                                logging.warning(f"Не удалось заполнить '{label}': {ex}")
                            return False

                        # Заполняем каскадные выпадающие списки:
                        await select_dropdown("Соглашение/Услуга", "Устройство самообслуживания")
                        await select_dropdown("Категория услуги", "ATM")
                        await select_dropdown("Подкатегория", "Статус 13")

                        try:
                            await page.wait_for_load_state('networkidle', timeout=3000)
                        except Exception:
                            await page.wait_for_timeout(1000)

                        formatted_name = HelpdeskService.format_atm_number(host_name)

                        # 3. Функция заполнения текстового поля по названию метки
                        async def fill_field(label_text: str, value: str) -> bool:
                            try:
                                lbl = form_ctx.locator(
                                    f"xpath=//*[self::label or self::div or self::span or self::td or self::th][contains(normalize-space(), '{label_text}')]"
                                ).first
                                if await lbl.count() == 0:
                                    lbl = page.locator(
                                        f"xpath=//*[self::label or self::div or self::span or self::td or self::th][contains(normalize-space(), '{label_text}')]"
                                    ).first
                                    if await lbl.count() == 0:
                                        return False

                                candidates = [
                                    lbl.locator("xpath=ancestor::tr[1]//input[not(@type='hidden')]"),
                                    lbl.locator("xpath=..//input[not(@type='hidden')]"),
                                    lbl.locator("xpath=../..//input[not(@type='hidden')]"),
                                    lbl.locator("xpath=following::input[not(@type='hidden')][1]"),
                                ]
                                for cand in candidates:
                                    if await cand.count() > 0 and await cand.first.is_visible():
                                        await cand.first.click()
                                        await cand.first.fill(value)
                                        return True
                            except Exception as ex:
                                logging.warning(f"Ошибка при заполнении поля '{label_text}': {ex}")
                            return False

                        loc_ok = await fill_field("Местонахождение", formatted_name)
                        subj_ok = await fill_field("Тема", f"Лог. номер ATM: {formatted_name}")

                        description = (
                            f"1. Лог. № банкомата: {formatted_name}\n"
                            f"2. Статус: Установить/Снять: {status_action}\n"
                            f"3. Причина: {reason}"
                        )

                        # 4. Заполнение описания
                        desc_ok = False
                        try:
                            lbl = form_ctx.locator(
                                "xpath=//*[self::label or self::div or self::span or self::td or self::th][contains(normalize-space(), 'Описание')]"
                            ).first
                            if await lbl.count() > 0:
                                row = lbl.locator("xpath=ancestor::tr[1] | .. | ../..").first
                                area = row.locator("textarea, [contenteditable='true']").first
                                if await area.count() > 0 and await area.is_visible():
                                    await area.click()
                                    await area.fill(description)
                                    desc_ok = True

                            if not desc_ok:
                                for f in page.frames:
                                    try:
                                        body = f.locator("body[contenteditable='true'], body.cke_editable, body").first
                                        if await body.count() > 0 and await body.get_attribute("contenteditable") == "true":
                                            await body.fill(description)
                                            desc_ok = True
                                            break
                                    except Exception:
                                        continue
                        except Exception as ex:
                            logging.warning(f"Не удалось заполнить 'Описание': {ex}")

                        # 5. СТРОГАЯ ВАЛИДАЦИЯ: нельзя сохранять пустую заявку!
                        if not loc_ok and not subj_ok:
                            await cls._capture_error_screenshot(page, host_name)
                            err_msg = f"Поля заявки ('Местонахождение', 'Тема') не найдены на форме для {host_name}"
                            logging.error(err_msg)
                            HelpdeskService.signals.ticket_failed.emit(host_name, status_action, err_msg)
                            return

                        # 6. Поиск и нажатие кнопки Сохранить
                        save_btn = None
                        for ctx in [form_ctx, page]:
                            btn = ctx.locator(HelpdeskService.SAVE_BUTTON_SELECTOR).first
                            if await btn.count() > 0 and await btn.is_visible():
                                save_btn = btn
                                break

                        if not save_btn:
                            await cls._capture_error_screenshot(page, host_name)
                            err_msg = "Кнопка 'Сохранить' не найдена на форме заявки"
                            logging.error(err_msg)
                            HelpdeskService.signals.ticket_failed.emit(host_name, status_action, err_msg)
                            return

                        await save_btn.click(timeout=5000)
                        try:
                            await page.wait_for_load_state('networkidle', timeout=10000)
                        except Exception:
                            pass

                        # Пауза 3 секунды в видимом режиме, чтобы оператор увидел результат
                        if not headless:
                            await page.wait_for_timeout(3000)

                        logging.info(f"Заявка ({status_action}) для {host_name} успешно заполнена и создана.")
                        HelpdeskService.signals.ticket_created.emit(host_name, status_action)

                    except PlaywrightTimeoutError as e:
                        logging.error(f"Таймаут Playwright при обработке {host_name} ({url})")
                        await cls._capture_error_screenshot(page, host_name)
                        HelpdeskService.signals.ticket_failed.emit(host_name, status_action, "Таймаут страницы (Playwright)")
                    except asyncio.TimeoutError as e:
                        logging.error(f"Глобальный таймаут при обработке {host_name} ({url})")
                        await cls._capture_error_screenshot(page, host_name)
                        HelpdeskService.signals.ticket_failed.emit(host_name, status_action, "Глобальный таймаут")
                    except Exception as e:
                        logging.error(f"Ошибка в процессе заполнения заявки для {host_name}: {e}")
                        await cls._capture_error_screenshot(page, host_name)
                        HelpdeskService.signals.ticket_failed.emit(host_name, status_action, str(e))
                    finally:
                        if browser:
                            await browser.close()
                            
            except Exception as e:
                logging.error(f"Глобальная ошибка HelpdeskService ({host_name}): {e}", exc_info=True)
                HelpdeskService.signals.ticket_failed.emit(host_name, status_action, f"Глобальная ошибка: {e}")

