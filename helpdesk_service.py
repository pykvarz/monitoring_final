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
    _background_tasks = set()
    _active_browser_holders = []
    _active_wrapper_tasks = set()
    _acquired_wrapper_tasks = set()
    _shutting_down = False
    TICKET_TIMEOUT_SECONDS = 60.0
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

    @classmethod
    def _track_background_task(cls, task):
        cls._background_tasks.add(task)
        task.add_done_callback(cls._background_tasks.discard)

    @classmethod
    async def _cleanup_browser_resources(cls, browser_holder):
        browser_holder["stop_requested"] = True
        cleanup_tasks = []
        browser = browser_holder.pop("browser", None)
        playwright = browser_holder.pop("playwright", None)
        if browser:
            cleanup_tasks.append(asyncio.create_task(browser.close()))
        if playwright:
            cleanup_tasks.append(asyncio.create_task(playwright.stop()))
        if not cleanup_tasks:
            return
        results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logging.warning(f"Ошибка очистки ресурсов Helpdesk: {result}")

    @classmethod
    async def _release_after_lifecycle(cls, tasks, semaphore, browser_holder):
        await asyncio.gather(*tasks, return_exceptions=True)
        semaphore.release()
        if browser_holder in cls._active_browser_holders:
            cls._active_browser_holders.remove(browser_holder)

    @classmethod
    async def _graceful_shutdown(cls):
        queued_tasks = cls._active_wrapper_tasks - cls._acquired_wrapper_tasks
        for task in queued_tasks:
            task.cancel()
        if queued_tasks:
            await asyncio.gather(*queued_tasks, return_exceptions=True)

        cleanup_tasks = [
            asyncio.create_task(cls._cleanup_browser_resources(holder))
            for holder in list(cls._active_browser_holders)
        ]
        pending = set(cls._active_wrapper_tasks) | set(cls._background_tasks)
        pending.update(cleanup_tasks)
        pending.discard(asyncio.current_task())
        if pending:
            await asyncio.wait(pending, timeout=5.0)

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
                
            cls._shutting_down = False
            cls._loop = asyncio.new_event_loop()
            cls._semaphore = asyncio.Semaphore(1)
            
            def run_loop():
                asyncio.set_event_loop(cls._loop)
                cls._loop.run_forever()
                
            cls._thread = threading.Thread(target=run_loop, daemon=True, name="HelpdeskAsyncLoop")
            cls._thread.start()

    @classmethod
    def _log_future_error(cls, future, host_name: str, action: str):
        """Callback для логирования ошибок из фоновых корутин и гарантированной отправки ticket_failed"""
        def _callback(fut):
            try:
                fut.result()
            except Exception as e:
                err_msg = f"Ошибка заявки ({action}) для {host_name}: {e}"
                logging.error(f"HelpdeskService: {err_msg}")
                cls.signals.ticket_failed.emit(host_name, action, err_msg)
        future.add_done_callback(_callback)

    @classmethod
    def shutdown(cls):
        """Остановка фонового потока и цикла событий"""
        try:
            if cls._loop and cls._loop.is_running():
                cls._shutting_down = True
                cleanup_future = asyncio.run_coroutine_threadsafe(
                    cls._graceful_shutdown(), cls._loop
                )
                try:
                    cleanup_future.result(timeout=6.0)
                except Exception as e:
                    logging.warning(f"Helpdesk: graceful shutdown не завершён: {e}")
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
                cls._process_ticket_task_async(config.helpdesk_url, host, "Установить", reason, headless=headless),
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
                cls._process_ticket_task_async(config.helpdesk_url, host, "Снять", reason, headless=headless),
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
    def get_launch_args(url: str, enable_delegation: bool = False) -> list:
        """
        Формирует аргументы запуска браузера с поддержкой Windows SSO / NTLM / Kerberos.
        Исключает кавычки в значениях флагов и использует строгий доменный allowlist
        без опасного широкого совпадения *domain* и без неконтролируемого делегирования Kerberos.
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
                # Строгий доменный allowlist: точное имя хоста и его поддомены
                args.insert(0, f'--auth-server-allowlist={domain},*.{domain}')
                if enable_delegation:
                    args.insert(1, f'--auth-negotiate-delegate-allowlist={domain},*.{domain}')
        return args

    # ==================== Утилиты формы Naumen SD ====================

    @staticmethod
    def _xpath_escape(s: str) -> str:
        """Экранирование строки для безопасной подстановки в XPath-выражение."""
        if "'" not in s:
            return f"'{s}'"
        if '"' not in s:
            return f'"{s}"'
        parts = s.split("'")
        return "concat(" + ",\"'\",".join(f"'{p}'" for p in parts) + ")"

    @staticmethod
    async def _find_form_context(page):
        """Поиск контекста формы (в основном окне или во встроенных iframes), до 25 секунд."""
        for _ in range(50):
            contexts = [page] + list(page.frames)
            for search_ctx in contexts:
                try:
                    # 1. Поиск по CSS маркерам (gwt-debug ID)
                    css_marker = search_ctx.locator(
                        "#gwt-debug-location-value, #gwt-debug-shortDescr-value, #gwt-debug-servCategory-value, "
                        "#gwt-debug-agreementServiceProperty-value, #gwt-debug-subCategory-value, #gwt-debug-apply"
                    ).first
                    if await css_marker.count() > 0 and await css_marker.is_visible():
                        return search_ctx

                    # 2. Поиск по XPath маркерам (раздельно от CSS во избежание синтаксических ошибок в браузере)
                    xpath_marker = search_ctx.locator(
                        "xpath=//*[self::label or self::div or self::span or self::td or self::th]"
                        "[contains(normalize-space(), 'Местонахождение') or contains(normalize-space(), 'Соглашение')]"
                    ).first
                    if await xpath_marker.count() > 0 and await xpath_marker.is_visible():
                        return search_ctx
                except Exception:
                    continue
            await page.wait_for_timeout(500)
        logging.warning("Контекст формы не обнаружен по маркерам, используем page")
        return page

    @classmethod
    async def _select_dropdown(cls, page, form_ctx, field_id: str, label_fallback: str, text_to_select: str) -> bool:
        """Выбор значения в выпадающем списке Naumen SD по gwt-debug ID или метке."""
        try:
            trigger = form_ctx.locator(f"#{field_id}").first
            if await trigger.count() == 0:
                trigger = page.locator(f"#{field_id}").first

            if await trigger.count() == 0:
                escaped = cls._xpath_escape(label_fallback)
                xpath = (
                    f"xpath=//*[self::label or self::div or self::span or self::td or self::th]"
                    f"[contains(normalize-space(), {escaped})]"
                )
                lbl = form_ctx.locator(xpath).first
                if await lbl.count() == 0:
                    lbl = page.locator(xpath).first
                if await lbl.count() > 0:
                    row = lbl.locator("xpath=ancestor::tr[1] | .. | ../..").first
                    trigger = row.locator(".formSelect__selected, [id*='-value'], input, select").first

            if await trigger.count() == 0:
                logging.warning(f"Поле выпадающего списка '{field_id}' ('{label_fallback}') не найдено")
                return False

            await trigger.scroll_into_view_if_needed()
            await trigger.click(timeout=3000)
            await page.wait_for_timeout(400)

            opt = None
            for target_text in [text_to_select, text_to_select.strip()]:
                for search_ctx in [form_ctx, page]:
                    candidate = search_ctx.get_by_text(target_text, exact=True).last
                    try:
                        if await candidate.count() > 0 and await candidate.is_visible():
                            opt = candidate
                            break
                    except Exception:
                        pass
                if opt:
                    break

            if not opt:
                pattern = re.compile(rf"^\s*{re.escape(text_to_select)}\s*$", re.IGNORECASE)
                for search_ctx in [form_ctx, page]:
                    candidate = search_ctx.get_by_text(pattern).first
                    try:
                        if await candidate.count() > 0 and await candidate.is_visible():
                            opt = candidate
                            break
                    except Exception:
                        pass

            if opt:
                await opt.scroll_into_view_if_needed()
                await opt.click(timeout=3000)
                await page.wait_for_timeout(400)
                return True

            inp = trigger.locator("input.formSelect, input").first
            if await inp.count() > 0 and await inp.is_visible():
                await inp.click()
                await inp.fill("")
                await inp.press_sequentially(text_to_select, delay=40)
                await page.wait_for_timeout(400)
                await inp.press("ArrowDown")
                await page.wait_for_timeout(200)
                await inp.press("Enter")
                await page.wait_for_timeout(400)
                return True
        except Exception as ex:
            logging.warning(f"Не удалось заполнить '{field_id}' ('{label_fallback}'): {ex}")
        return False

    @classmethod
    async def _fill_field(cls, page, form_ctx, field_id: str, label_fallback: str, value: str) -> bool:
        """Заполнение текстового поля формы по gwt-debug ID или метке."""
        try:
            container = form_ctx.locator(f"#{field_id}").first
            if await container.count() == 0:
                container = page.locator(f"#{field_id}").first

            if await container.count() > 0:
                target_input = container.locator("input, textarea").first
                if await target_input.count() == 0:
                    target_input = container
                await target_input.scroll_into_view_if_needed()
                await target_input.click(timeout=3000)
                await target_input.fill(value)
                await target_input.press("Tab")
                return True

            escaped = cls._xpath_escape(label_fallback)
            xpath = (
                f"xpath=//*[self::label or self::div or self::span or self::td or self::th]"
                f"[contains(normalize-space(), {escaped})]"
            )
            lbl = form_ctx.locator(xpath).first
            if await lbl.count() == 0:
                lbl = page.locator(xpath).first
            if await lbl.count() > 0:
                candidates = [
                    lbl.locator("xpath=ancestor::tr[1]//input[not(@type='hidden')]"),
                    lbl.locator("xpath=..//input[not(@type='hidden')]"),
                    lbl.locator("xpath=../..//input[not(@type='hidden')]"),
                    lbl.locator("xpath=following::input[not(@type='hidden')][1]"),
                ]
                for cand in candidates:
                    if await cand.count() > 0 and await cand.first.is_visible():
                        await cand.first.scroll_into_view_if_needed()
                        await cand.first.click()
                        await cand.first.fill(value)
                        return True
        except Exception as ex:
            logging.warning(f"Ошибка при заполнении поля '{field_id}' ('{label_fallback}'): {ex}")
        return False

    @classmethod
    async def _fill_description(cls, page, form_ctx, description: str) -> bool:
        """Заполнение поля 'Описание' формы заявки."""
        try:
            for desc_id in ["gwt-debug-description-value", "gwt-debug-description", "gwt-debug-descr-value", "gwt-debug-details-value"]:
                for search_ctx in [form_ctx, page]:
                    c = search_ctx.locator(f"#{desc_id}").first
                    if await c.count() > 0:
                        target = c.locator("textarea, [contenteditable='true']").first
                        if await target.count() == 0:
                            target = c
                        if await target.is_visible():
                            await target.scroll_into_view_if_needed()
                            await target.click()
                            await target.fill(description)
                            return True

            escaped = cls._xpath_escape("Описание")
            xpath = (
                f"xpath=//*[self::label or self::div or self::span or self::td or self::th]"
                f"[contains(normalize-space(), {escaped})]"
            )
            for search_ctx in [form_ctx, page]:
                lbl = search_ctx.locator(xpath).first
                if await lbl.count() > 0:
                    row = lbl.locator("xpath=ancestor::tr[1] | .. | ../..").first
                    area = row.locator("textarea, [contenteditable='true']").first
                    if await area.count() > 0 and await area.is_visible():
                        await area.scroll_into_view_if_needed()
                        await area.click()
                        await area.fill(description)
                        return True

            for f in page.frames:
                try:
                    body = f.locator("body[contenteditable='true'], body.cke_editable, body").first
                    if await body.count() > 0 and await body.get_attribute("contenteditable") == "true":
                        await body.fill(description)
                        return True
                except Exception:
                    continue
        except Exception as ex:
            logging.warning(f"Не удалось заполнить 'Описание': {ex}")
        return False

    @staticmethod
    async def _wait_for_form_closed(form_ctx) -> bool:
        """Ожидает закрытия формы; удалённый iframe также считается закрытой формой."""
        try:
            marker = form_ctx.locator(
                "#gwt-debug-location-value, #gwt-debug-shortDescr-value"
            ).first
            await marker.wait_for(state="hidden", timeout=5000)
            return True
        except Exception:
            is_detached = getattr(form_ctx, "is_detached", None)
            if callable(is_detached):
                try:
                    return bool(is_detached())
                except Exception:
                    pass
            return False

    @staticmethod
    def _missing_required_fields(field_results: dict) -> list:
        """Вернуть названия обязательных полей, которые не удалось заполнить."""
        return [name for name, filled in field_results.items() if not filled]

    @classmethod
    async def _confirm_ticket_saved(cls, page, form_ctx, page_url_before_save: str) -> bool:
        """Подтвердить закрытие формы без ухода со страницы Helpdesk на авторизацию."""
        if not await cls._wait_for_form_closed(form_ctx):
            return False

        current_url = str(getattr(page, "url", "") or "")
        before = urllib.parse.urlparse(page_url_before_save or "")
        current = urllib.parse.urlparse(current_url)
        auth_target = " ".join((current.path, current.query, current.fragment)).lower()
        if re.search(r"(^|[/_.?=&\s-])(login|signin|sign-in|auth|sso)([/_.?=&\s-]|$)", auth_target):
            return False
        if before.netloc and current.netloc and before.netloc.lower() != current.netloc.lower():
            return False

        # URL-подтверждение: /ticket/ID считается успехом ТОЛЬКО если URL изменился
        # относительно page_url_before_save (т.е. это новая карточка, а не та же старая)
        ticket_id = r"(?:[0-9]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
        if re.search(rf"/(?:ticket|servicecall|request)/{ticket_id}/?$", current.path, re.IGNORECASE):
            if current_url != page_url_before_save:
                return True

        # Текстовое подтверждение: сначала ищем в контейнерах уведомлений,
        # а не во всём body (предотвращает ложное срабатывание на старых записях)
        confirmation = re.compile(
            r"(?:заявк[а-я]*|обращен[а-я]*|инцидент[а-я]*|тикет[а-я]*|ticket|request|issue)(?:(?!\b(?:не|not|ошибка|error|failed)\b).){0,80}(?:создан[а-я]*|сохран[её]н[а-я]*|зарегистрирован[а-я]*|created|saved|registered)",
            re.IGNORECASE,
        )
        # ID заявки в тексте (для fallback проверки body — требуется конкретный идентификатор)
        ticket_id_in_text = re.compile(
            r"(?:№\s*|#\s*|ID\s*[:=]?\s*)\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.IGNORECASE,
        )
        notification_selector = (
            ".notification, .alert, .toast, [role='alert'], "
            ".gwt-Notification, .b-notification, .messages, "
            ".success-message, .status-message"
        )
        for context in [page, *page.frames]:
            try:
                # Сначала: контейнеры уведомлений
                notification_els = context.locator(notification_selector)
                count = await notification_els.count()
                for i in range(count):
                    try:
                        text = await notification_els.nth(i).inner_text(timeout=1000)
                        if confirmation.search(text):
                            return True
                    except Exception:
                        continue
            except Exception:
                continue

        # Fallback: body, но с дополнительным условием — текст должен содержать
        # идентификатор заявки (номер/UUID), что делает его уникальным для текущей операции
        for context in [page, *page.frames]:
            try:
                message = await context.locator("body").first.inner_text(timeout=2000)
                if confirmation.search(message) and ticket_id_in_text.search(message):
                    return True
            except Exception:
                continue
        return False

    # ==================== Основной процесс ====================

    @classmethod
    async def _process_ticket_task_async(cls, url: str, host_name: str, status_action: str, reason: str = "без связи", headless: bool = False):
        semaphore = cls._get_semaphore()
        wrapper_task = asyncio.current_task()
        cls._active_wrapper_tasks.add(wrapper_task)
        acquired = False
        release_in_finally = True
        browser_holder = {}
        session_task = None
        cleanup_task = None
        try:
            await semaphore.acquire()
            acquired = True
            cls._acquired_wrapper_tasks.add(wrapper_task)
            if cls._shutting_down:
                return None

            cls._active_browser_holders.append(browser_holder)
            session_task = asyncio.create_task(
                cls._process_ticket_session_async(
                    url,
                    host_name,
                    status_action,
                    reason,
                    headless=headless,
                    browser_holder=browser_holder,
                )
            )
            done, _ = await asyncio.wait(
                {session_task}, timeout=cls.TICKET_TIMEOUT_SECONDS
            )
            if not done and not browser_holder.get("terminal_emitted"):
                browser_holder["terminal_emitted"] = True
                cls.signals.ticket_failed.emit(
                    host_name,
                    status_action,
                    f"Глобальный таймаут: превышено {cls.TICKET_TIMEOUT_SECONDS:g} с",
                )

            cleanup_task = asyncio.create_task(
                cls._cleanup_browser_resources(browser_holder)
            )
            lifecycle_tasks = {session_task, cleanup_task}
            finished, pending = await asyncio.wait(lifecycle_tasks, timeout=5.0)
            for task in finished:
                try:
                    task.result()
                except Exception as e:
                    logging.warning(f"Ошибка завершения Helpdesk для {host_name}: {e}")

            if pending:
                release_in_finally = False
                cls._track_background_task(
                    asyncio.create_task(
                        cls._release_after_lifecycle(
                            pending, semaphore, browser_holder
                        )
                    )
                )
            return None
        except asyncio.CancelledError:
            if not acquired or session_task is None:
                raise
            if cleanup_task is None:
                cleanup_task = asyncio.create_task(
                    cls._cleanup_browser_resources(browser_holder)
                )
            pending = {
                task for task in (session_task, cleanup_task) if not task.done()
            }
            if pending:
                release_in_finally = False
                cls._track_background_task(
                    asyncio.create_task(
                        cls._release_after_lifecycle(
                            pending, semaphore, browser_holder
                        )
                    )
                )
            raise
        finally:
            cls._active_wrapper_tasks.discard(wrapper_task)
            cls._acquired_wrapper_tasks.discard(wrapper_task)
            if acquired and release_in_finally:
                semaphore.release()
                if browser_holder in cls._active_browser_holders:
                    cls._active_browser_holders.remove(browser_holder)

    @classmethod
    async def _process_ticket_session_async(
        cls,
        url: str,
        host_name: str,
        status_action: str,
        reason: str = "без связи",
        headless: bool = False,
        browser_holder=None,
    ):
        page = None
        browser = None
        terminal_state = browser_holder if browser_holder is not None else {}

        def emit_failed(message):
            if terminal_state.get("terminal_emitted"):
                return
            terminal_state["terminal_emitted"] = True
            HelpdeskService.signals.ticket_failed.emit(
                host_name, status_action, message
            )

        def emit_created():
            if terminal_state.get("terminal_emitted"):
                return
            terminal_state["terminal_emitted"] = True
            HelpdeskService.signals.ticket_created.emit(host_name, status_action)

        try:
            from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

            url = HelpdeskService.normalize_url(url)
            p = await async_playwright().start()
            terminal_state["playwright"] = p
            if terminal_state.get("stop_requested"):
                await cls._cleanup_browser_resources(terminal_state)
                return
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
            if browser_holder is not None:
                browser_holder["browser"] = browser
            if terminal_state.get("stop_requested"):
                await cls._cleanup_browser_resources(terminal_state)
                return

            context = await browser.new_context()
            page = await context.new_page()

            try:
                await page.goto(url, timeout=20000)
                try:
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except Exception:
                    pass

                form_ctx = await cls._find_form_context(page)

                agreement_ok = await cls._select_dropdown(page, form_ctx, "gwt-debug-agreementServiceProperty-value", "Соглашение/Услуга", "Устройство самообслуживания")
                await page.wait_for_timeout(800)
                category_ok = await cls._select_dropdown(page, form_ctx, "gwt-debug-servCategory-value", "Категория услуги", "ATM")
                await page.wait_for_timeout(800)
                subcategory_ok = await cls._select_dropdown(page, form_ctx, "gwt-debug-subCategory-value", "Подкатегория", "Статус 13")
                await page.wait_for_timeout(800)

                try:
                    await page.wait_for_load_state('networkidle', timeout=3000)
                except Exception:
                    await page.wait_for_timeout(1000)

                formatted_name = HelpdeskService.format_atm_number(host_name)
                loc_ok = await cls._fill_field(page, form_ctx, "gwt-debug-location-value", "Местонахождение", formatted_name)
                subj_ok = await cls._fill_field(page, form_ctx, "gwt-debug-shortDescr-value", "Тема", f"Лог. номер ATM: {formatted_name}")

                description = (
                    f"1. Лог. № банкомата: {formatted_name}\n"
                    f"2. Статус: Установить/Снять: {status_action}\n"
                    f"3. Причина: {reason}"
                )
                description_ok = await cls._fill_description(page, form_ctx, description)

                missing = cls._missing_required_fields({
                    "Соглашение/Услуга": agreement_ok,
                    "Категория услуги": category_ok,
                    "Подкатегория": subcategory_ok,
                    "Местонахождение": loc_ok,
                    "Тема": subj_ok,
                    "Описание": description_ok,
                })
                if missing:
                    await cls._capture_error_screenshot(page, host_name)
                    err_msg = f"Поля заявки ({', '.join(missing)}) не заполнены на форме для {host_name}"
                    logging.error(err_msg)
                    emit_failed(err_msg)
                    return

                save_btn = None
                for search_ctx in [form_ctx, page]:
                    btn = search_ctx.locator(HelpdeskService.SAVE_BUTTON_SELECTOR).first
                    if await btn.count() > 0 and await btn.is_visible():
                        save_btn = btn
                        break

                if not save_btn:
                    await cls._capture_error_screenshot(page, host_name)
                    err_msg = "Кнопка 'Сохранить' не найдена на форме заявки"
                    logging.error(err_msg)
                    emit_failed(err_msg)
                    return

                page_url_before_save = page.url
                await save_btn.click(timeout=5000)
                try:
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except Exception:
                    pass

                target_ctx = form_ctx if form_ctx else page
                if not await cls._confirm_ticket_saved(page, target_ctx, page_url_before_save):
                    await cls._capture_error_screenshot(page, host_name)
                    err_msg = f"Форма заявки не закрылась после сохранения для {host_name} (возможно, ошибка валидации на сервере)"
                    logging.error(err_msg)
                    emit_failed(err_msg)
                    return

                logging.info(f"Заявка ({status_action}) для {host_name} успешно заполнена и создана.")
                emit_created()

            except PlaywrightTimeoutError as e:
                logging.error(f"Таймаут Playwright при обработке {host_name} ({url}): {e}")
                await cls._capture_error_screenshot(page, host_name)
                emit_failed(f"Таймаут страницы: {e}")
            except asyncio.TimeoutError as e:
                logging.error(f"Глобальный таймаут при обработке {host_name} ({url}): {e}")
                await cls._capture_error_screenshot(page, host_name)
                emit_failed(f"Глобальный таймаут: {e}")
            except Exception as e:
                logging.error(f"Ошибка в процессе заполнения заявки для {host_name}: {e}")
                await cls._capture_error_screenshot(page, host_name)
                emit_failed(str(e))
        except Exception as e:
            logging.error(f"Глобальная ошибка HelpdeskService ({host_name}): {e}", exc_info=True)
            emit_failed(f"Глобальная ошибка: {e}")
