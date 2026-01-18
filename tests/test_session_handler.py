import pytest

from someipy._internal.session_handler import SessionHandler


def test_session_handler_initialization():
    handler = SessionHandler()
    assert handler.session_id == 0
    assert handler.reboot_flag is True

    assert handler.update_session() == (1, True)
    assert handler.update_session() == (2, True)


def test_session_handler_wrap_around():
    handler = SessionHandler(initial_value=0xFFFE)
    assert handler.session_id == 0xFFFE
    assert handler.reboot_flag is True

    assert handler.update_session() == (0xFFFF, True)
    assert handler.update_session() == (1, False)
    assert handler.update_session() == (2, False)
