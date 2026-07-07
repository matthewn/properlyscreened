import pytest
import requests
from django.core.cache import cache
from django.test import RequestFactory

from properlyscreened import newsletter


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


class TestProcessSignup:
    def test_honeypot_silently_accepts_without_subscribing(self, rf, monkeypatch):
        called = False

        def fake_subscribe(email):
            nonlocal called
            called = True
            return 'ok'

        monkeypatch.setattr(newsletter, '_subscribe', fake_subscribe)
        request = rf.post('/newsletter/', {'website': 'bot', 'email': 'a@example.com'})
        assert newsletter.process_signup(request) == 'ok'
        assert called is False

    def test_invalid_email_returns_message(self, rf):
        request = rf.post('/newsletter/', {'email': 'not-an-email'})
        result = newsletter.process_signup(request)
        assert result == 'Please enter a valid email address.'

    def test_missing_email_returns_message(self, rf):
        assert newsletter.process_signup(rf.post('/newsletter/', {})) == (
            'Please enter a valid email address.'
        )

    def test_valid_email_passes_through_subscribe_result(self, rf, monkeypatch):
        monkeypatch.setattr(newsletter, '_subscribe', lambda email: 'ok')
        assert newsletter.process_signup(rf.post('/newsletter/', {'email': 'a@example.com'})) == 'ok'

    def test_existing_contact_returns_exists(self, rf, monkeypatch):
        monkeypatch.setattr(newsletter, '_subscribe', lambda email: 'exists')
        assert newsletter.process_signup(rf.post('/newsletter/', {'email': 'a@example.com'})) == 'exists'

    def test_subscribe_error_becomes_user_message(self, rf, monkeypatch):
        monkeypatch.setattr(newsletter, '_subscribe', lambda email: 'error')
        result = newsletter.process_signup(rf.post('/newsletter/', {'email': 'a@example.com'}))
        assert result == 'Sorry, something went wrong. Please try again later.'

    def test_throttled_after_limit(self, rf, monkeypatch):
        monkeypatch.setattr(newsletter, '_subscribe', lambda email: 'ok')
        request = rf.post('/newsletter/', {'email': 'a@example.com'})
        for _ in range(newsletter.THROTTLE_LIMIT):
            assert newsletter.process_signup(request) == 'ok'
        assert newsletter.process_signup(request) == 'Too many attempts. Please try again later.'


class TestThrottled:
    def test_allows_up_to_limit_then_blocks(self, rf):
        request = rf.post('/', {})
        for _ in range(newsletter.THROTTLE_LIMIT):
            assert newsletter._throttled(request) is False
        assert newsletter._throttled(request) is True

    def test_separate_ips_are_independent(self, rf):
        a = rf.post('/', {}, REMOTE_ADDR='1.1.1.1')
        b = rf.post('/', {}, REMOTE_ADDR='2.2.2.2')
        for _ in range(newsletter.THROTTLE_LIMIT):
            newsletter._throttled(a)
        assert newsletter._throttled(a) is True
        assert newsletter._throttled(b) is False


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError('no json')
        return self._payload


class TestSubscribe:
    def test_no_api_key_short_circuits_to_error(self, settings):
        settings.BREVO_API_KEY = ''
        assert newsletter._subscribe('a@example.com') == 'error'

    def test_2xx_is_ok(self, settings, monkeypatch):
        settings.BREVO_API_KEY = 'key'
        monkeypatch.setattr(requests, 'post', lambda *a, **k: _FakeResponse(201))
        assert newsletter._subscribe('a@example.com') == 'ok'

    def test_duplicate_parameter_is_exists(self, settings, monkeypatch):
        settings.BREVO_API_KEY = 'key'
        resp = _FakeResponse(400, {'code': 'duplicate_parameter'})
        monkeypatch.setattr(requests, 'post', lambda *a, **k: resp)
        assert newsletter._subscribe('a@example.com') == 'exists'

    def test_other_400_is_error(self, settings, monkeypatch):
        settings.BREVO_API_KEY = 'key'
        resp = _FakeResponse(400, {'code': 'something_else'})
        monkeypatch.setattr(requests, 'post', lambda *a, **k: resp)
        assert newsletter._subscribe('a@example.com') == 'error'

    def test_request_exception_is_error(self, settings, monkeypatch):
        settings.BREVO_API_KEY = 'key'

        def boom(*a, **k):
            raise requests.RequestException('down')

        monkeypatch.setattr(requests, 'post', boom)
        assert newsletter._subscribe('a@example.com') == 'error'
