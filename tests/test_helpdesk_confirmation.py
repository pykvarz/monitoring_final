"""Подтверждение сохранения по новой карточке, включая маршруты Naumen."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from helpdesk_service import HelpdeskService


CREATE_URL = "https://helpdesk.example/sd/operator/#add:serviceCall$request"
SAVED_URL = "https://helpdesk.example/sd/operator/#uuid:serviceCall$12345"


def make_page(url):
    page = MagicMock()
    page.url = url
    page.frames = []
    page.locator.return_value.count = AsyncMock(return_value=0)
    page.locator.return_value.first.inner_text = AsyncMock(return_value="Карточка заявки")
    return page


@pytest.mark.parametrize("form_closed", [False, True])
def test_new_naumen_card_confirms_save_even_when_fields_remain_visible(form_closed):
    page = make_page(SAVED_URL)
    with patch.object(HelpdeskService, "_wait_for_form_closed", new=AsyncMock(return_value=form_closed)):
        assert asyncio.run(HelpdeskService._confirm_ticket_saved(page, page, CREATE_URL))


def test_naumen_navigation_during_form_wait_confirms_save():
    page = make_page(CREATE_URL)

    async def wait_for_form(form_ctx):
        page.url = SAVED_URL
        return False  # Поля всё ещё видимы, но уже в сохранённой карточке.

    with patch.object(HelpdeskService, "_wait_for_form_closed", new=wait_for_form):
        assert asyncio.run(HelpdeskService._confirm_ticket_saved(page, page, CREATE_URL))


@pytest.mark.parametrize("before, current", [
    (SAVED_URL, SAVED_URL),
    (SAVED_URL, "https://helpdesk.example/sd/operator/?refresh=1#uuid:serviceCall$12345"),
    (CREATE_URL, CREATE_URL),
    (CREATE_URL, "https://helpdesk.example/sd/operator/#add:serviceCall$12345"),
    (CREATE_URL, "https://helpdesk.example/sd/operator/#uuid:serviceCall$error"),
    (CREATE_URL, "https://other.example/sd/operator/#uuid:serviceCall$12345"),
    (CREATE_URL, "https://helpdesk.example/login#uuid:serviceCall$12345"),
    (CREATE_URL, "http://helpdesk.example/sd/operator/#uuid:serviceCall$12345"),
    ("https://helpdesk.example/ticket/12345", "https://helpdesk.example/ticket/12345?refresh=1"),
])
def test_existing_card_or_untrusted_navigation_does_not_confirm_save(before, current):
    page = make_page(current)
    with patch.object(HelpdeskService, "_wait_for_form_closed", new=AsyncMock(return_value=True)):
        assert not asyncio.run(HelpdeskService._confirm_ticket_saved(page, page, before))


def test_new_path_card_confirms_save_when_fields_remain_visible():
    page = make_page("https://helpdesk.example/ticket/12345")
    with patch.object(HelpdeskService, "_wait_for_form_closed", new=AsyncMock(return_value=False)):
        assert asyncio.run(HelpdeskService._confirm_ticket_saved(page, page, CREATE_URL))
