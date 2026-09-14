#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для автоматического создания заявок в Helpdesk через Playwright.
(Asyncio Version)
"""
import logging
import asyncio
import threading
import urllib.parse
from models import AppConfig
from PyQt5.QtCore import QObject, pyqtSignal

class HelpdeskSignals(QObject):
    ticket_created = pyqtSignal(str, str) # host_name, status_action
    ticket_failed = pyqtSignal(str, str, str) # host_name, status_action, error_msg

class HelpdeskService:
    """Сервис для работы с Helpdesk (Асинхронная реализация)"""
    _loop = None
    _thread = None
    signals = HelpdeskSignals()

    @classmethod
    def _start_loop(cls):
        if cls._thread and cls._thread.is_alive():
            return
            
        cls._loop = asyncio.new_event_loop()
        
        def run_loop():
            asyncio.set_event_loop(cls._loop)
            cls._loop.run_forever()
            
        cls._thread = threading.Thread(target=run_loop, daemon=True, name="HelpdeskAsyncLoop")
        cls._thread.start()

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
        for host in hosts:
            logging.info(f"HelpdeskService: Планирование заявки (Установить) для {host}")
            asyncio.run_coroutine_threadsafe(
                asyncio.wait_for(cls._process_ticket_task_async(config.helpdesk_url, host, "Установить", reason), timeout=60.0),
                cls._loop
            )
            
    @classmethod
    def process_recovered(cls, hosts: list, config: AppConfig, reason: str = "восстановление связи"):
        if not config.helpdesk_enabled or not config.helpdesk_url:
            return
        cls._start_loop()
        for host in hosts:
            logging.info(f"HelpdeskService: Планирование заявки (Снять) для {host}")
            asyncio.run_coroutine_threadsafe(
                asyncio.wait_for(cls._process_ticket_task_async(config.helpdesk_url, host, "Снять", reason), timeout=60.0),
                cls._loop
            )

    @staticmethod
    async def _process_ticket_task_async(url: str, host_name: str, status_action: str, reason: str = "без связи"):
        try:
            from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
            
            async with async_playwright() as p:
                logging.info(f"Запуск Playwright для {host_name} ({status_action})")
                domain = urllib.parse.urlparse(url).netloc
                if ":" in domain:
                    domain = domain.split(":")[0]
                
                browser = await p.chromium.launch(
                    headless=True,
                    args=[f'--auth-server-allowlist="{domain}"']
                )
                context = await browser.new_context()
                page = await context.new_page()
                
                try:
                    # Переход на страницу добавления заявки с явным таймаутом
                    await page.goto(url, timeout=15000)
                    await page.wait_for_load_state('networkidle', timeout=15000)
                    
                    # Асинхронная функция для выбора значения в выпадающем списке
                    async def select_dropdown(label: str, text_to_select: str):
                        try:
                            label_el = page.locator(f"xpath=//label[contains(text(), '{label}')]")
                            if await label_el.count() > 0:
                                parent = label_el.locator("..")

                                # 1. Проверяем стандартный HTML <select>
                                select_el = parent.locator("select")
                                if await select_el.count() > 0 and await select_el.first.is_visible():
                                    try:
                                        await select_el.first.select_option(label=text_to_select, timeout=3000)
                                        await page.wait_for_timeout(400)
                                        return
                                    except Exception:
                                        pass

                                # 2. Для кастомных выпадающих списков (Select2, комбобоксы)
                                input_el = parent.locator("input, select, .select2-selection, .combo-box, [role='combobox']").first
                                await input_el.click(timeout=3000)
                                await page.wait_for_timeout(300)
                                option = page.get_by_text(text_to_select, exact=True).last
                                await option.click(timeout=3000)
                                await page.wait_for_timeout(400)
                        except Exception as ex:
                            logging.warning(f"Не удалось заполнить '{label}': {ex}")

                    # Заполняем каскадные выпадающие списки:
                    # - "Тип заявки" не трогаем (автоматически заполнен при открытии ссылки)
                    await select_dropdown("Соглашение/Услуга", "Устройство самообслуживания")
                    await select_dropdown("Категория услуги", "ATM")
                    await select_dropdown("Подкатегория", "Статус 13")

                    # - "Шаблон" и "Режим работы" автоматически заполняются веб-формой при выборе "Подкатегория".
                    # Даем странице время отработать встроенные AJAX-скрипты автозаполнения:
                    try:
                        await page.wait_for_load_state('networkidle', timeout=3000)
                    except Exception:
                        await page.wait_for_timeout(1000)
                    
                    # Текстовые поля
                    try:
                        loc_box = page.locator("xpath=//label[contains(text(), 'Местонахождение')]/..//input")
                        if await loc_box.count() > 0:
                            await loc_box.first.fill(host_name)
                    except Exception:
                        pass

                    try:
                        subj_box = page.locator("xpath=//label[contains(text(), 'Тема')]/..//input")
                        if await subj_box.count() > 0:
                            await subj_box.first.fill(f"Лог. номер ATM: {host_name}")
                    except Exception:
                        pass
                    
                    description = (
                        f"1. Лог. № банкомата: {host_name}\n"
                        f"2. Статус: {status_action}\n"
                        f"3. Причина: {reason}"
                    )
                    try:
                        desc_box = page.locator("xpath=//label[contains(text(), 'Описание')]/..//*[self::textarea or @contenteditable='true']")
                        if await desc_box.count() > 0:
                            await desc_box.first.fill(description)
                        else:
                            frames = page.frames
                            for f in frames:
                                body = f.locator("body")
                                if await body.count() > 0 and await body.get_attribute("contenteditable") == "true":
                                    await body.fill(description)
                                    break
                    except Exception as ex:
                        logging.warning(f"Не удалось заполнить 'Описание': {ex}")

                    # Нажимаем кнопку Сохранить / Создать
                    try:
                        save_btn = page.locator("button:has-text('Сохранить'), button:has-text('Создать'), input[type='submit']").first
                        if await save_btn.count() > 0:
                            await save_btn.click(timeout=5000)
                            await page.wait_for_load_state('networkidle', timeout=15000)
                            logging.info(f"Заявка ({status_action}) для {host_name} успешно создана.")
                            HelpdeskService.signals.ticket_created.emit(host_name, status_action)
                        else:
                            logging.error("Кнопка Сохранить/Создать не найдена.")
                            HelpdeskService.signals.ticket_failed.emit(host_name, status_action, "Кнопка Сохранить/Создать не найдена.")
                    except Exception as ex:
                        logging.error(f"Ошибка при сохранении заявки: {ex}")
                        HelpdeskService.signals.ticket_failed.emit(host_name, status_action, str(ex))

                except PlaywrightTimeoutError as e:
                    logging.error(f"Таймаут Playwright при обработке {host_name} ({url})")
                    HelpdeskService.signals.ticket_failed.emit(host_name, status_action, "Таймаут страницы (Playwright)")
                except asyncio.TimeoutError as e:
                    logging.error(f"Глобальный таймаут при обработке {host_name} ({url})")
                    HelpdeskService.signals.ticket_failed.emit(host_name, status_action, "Глобальный таймаут")
                except Exception as e:
                    logging.error(f"Ошибка в процессе заполнения заявки для {host_name}: {e}")
                    HelpdeskService.signals.ticket_failed.emit(host_name, status_action, str(e))
                finally:
                    await browser.close()
                    
        except Exception as e:
            logging.error(f"Глобальная ошибка HelpdeskService ({host_name}): {e}", exc_info=True)
            HelpdeskService.signals.ticket_failed.emit(host_name, status_action, f"Глобальная ошибка: {e}")
