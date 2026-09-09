#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для автоматического создания заявок в Helpdesk через Playwright.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from models import AppConfig

class HelpdeskService:
    """Сервис для работы с Helpdesk (Singletone-like через класс-методы)"""
    _executor = ThreadPoolExecutor(max_workers=2)

    @classmethod
    def shutdown(cls):
        """Остановка пула потоков при выходе из приложения"""
        try:
            import sys
            if sys.version_info >= (3, 9):
                cls._executor.shutdown(wait=False, cancel_futures=True)
            else:
                cls._executor.shutdown(wait=False)
        except Exception as e:
            logging.error(f"Ошибка при остановке пула Helpdesk: {e}")

    @classmethod
    def process_offline(cls, hosts: list, config: AppConfig):
        if not config.helpdesk_enabled or not config.helpdesk_url:
            return
        for host in hosts:
            logging.info(f"HelpdeskService: Планирование заявки (Установить) для {host}")
            cls._executor.submit(cls._process_ticket_task, config.helpdesk_url, host, "Установить")
            
    @classmethod
    def process_recovered(cls, hosts: list, config: AppConfig):
        if not config.helpdesk_enabled or not config.helpdesk_url:
            return
        for host in hosts:
            logging.info(f"HelpdeskService: Планирование заявки (Снять) для {host}")
            cls._executor.submit(cls._process_ticket_task, config.helpdesk_url, host, "Снять")

    @staticmethod
    def _process_ticket_task(url: str, host_name: str, status_action: str):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                logging.info(f"Запуск Playwright для {host_name} ({status_action})")
                import urllib.parse
                domain = urllib.parse.urlparse(url).netloc
                if ":" in domain:
                    domain = domain.split(":")[0]
                
                browser = p.chromium.launch(
                    headless=True,
                    args=[f'--auth-server-allowlist="{domain}"']
                )
                context = browser.new_context()
                page = context.new_page()
                
                # Переход на страницу добавления заявки
                page.goto(url)
                page.wait_for_load_state('networkidle')
                
                # Функция для выбора значения в выпадающем списке (Naumen SMP или аналогичные)
                def select_dropdown(label: str, text_to_select: str):
                    try:
                        # Пытаемся найти поле по метке
                        label_el = page.locator(f"xpath=//label[contains(text(), '{label}')]")
                        if label_el.count() > 0:
                            # Кликаем по инпуту/комбобоксу рядом с лейблом
                            parent = label_el.locator("..")
                            parent.locator("input, select, .select2-selection, .combo-box").first.click(timeout=3000)
                            # Ждем появления списка и кликаем
                            page.get_by_text(text_to_select, exact=True).last.click(timeout=3000)
                    except Exception as ex:
                        logging.warning(f"Не удалось заполнить '{label}': {ex}")

                # Заполняем выпадающие списки (попытка эмуляции пользовательского ввода)
                select_dropdown("Тип заявки", "Запрос на обслуживание")
                select_dropdown("Соглашение/Услуга", "Устройство самообслуживания")
                select_dropdown("Категория услуги", "ATM")
                select_dropdown("Подкатегория", "Статус 13")
                select_dropdown("Шаблон", "Статус 13")
                select_dropdown("Режим работы", "Офис")
                
                # Текстовые поля (Локатор ищет инпуты после лейблов)
                try:
                    loc_box = page.locator("xpath=//label[contains(text(), 'Местонахождение')]/..//input")
                    if loc_box.count() > 0:
                        loc_box.fill(host_name)
                except Exception:
                    pass

                try:
                    subj_box = page.locator("xpath=//label[contains(text(), 'Тема')]/..//input")
                    if subj_box.count() > 0:
                        subj_box.fill(f"Лог. номер ATM: {host_name}")
                except Exception:
                    pass
                
                # Rich text редактор (Описание) - обычно это iframe, div[contenteditable] или textarea
                description = (
                    f"1. Лог. № банкомата: {host_name}\n"
                    f"2. Статус: {status_action}\n"
                    f"3. Причина: без связи"
                )
                try:
                    desc_box = page.locator("xpath=//label[contains(text(), 'Описание')]/..//*[self::textarea or @contenteditable='true']")
                    if desc_box.count() > 0:
                        desc_box.first.fill(description)
                    else:
                        # Если это iframe
                        frames = page.frames
                        for f in frames:
                            body = f.locator("body")
                            if body.count() > 0 and body.get_attribute("contenteditable") == "true":
                                body.fill(description)
                                break
                except Exception as ex:
                    logging.warning(f"Не удалось заполнить 'Описание': {ex}")

                # Нажимаем кнопку Сохранить / Создать
                try:
                    # Ищем кнопку "Сохранить" или "Создать"
                    save_btn = page.locator("button:has-text('Сохранить'), button:has-text('Создать'), input[type='submit']").first
                    if save_btn.count() > 0:
                        save_btn.click()
                        page.wait_for_load_state('networkidle', timeout=10000)
                        logging.info(f"Заявка ({status_action}) для {host_name} успешно создана.")
                    else:
                        logging.error("Кнопка Сохранить/Создать не найдена.")
                except Exception as ex:
                    logging.error(f"Ошибка при сохранении заявки: {ex}")

                browser.close()
        except Exception as e:
            logging.error(f"Глобальная ошибка HelpdeskService ({host_name}): {e}", exc_info=True)
