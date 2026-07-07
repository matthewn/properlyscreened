from extlinks.middleware import RewriteExternalLinksMiddleware


class FakeResponse:
    def __init__(self, html, content_length=None):
        self.content = html.encode('utf-8')
        self.charset = 'utf-8'
        self._headers = {}
        if content_length is not None:
            self._headers['Content-Length'] = content_length

    def has_header(self, name):
        return name in self._headers

    def __delitem__(self, name):
        del self._headers[name]

    @property
    def text(self):
        # the middleware assigns a str back to .content; before that it is bytes
        if isinstance(self.content, bytes):
            return self.content.decode('utf-8')
        return self.content


rewrite = RewriteExternalLinksMiddleware._rewrite_links


class TestRewriteLinks:
    def test_external_link_gets_target_blank(self):
        resp = FakeResponse('<a href="http://example.com">x</a>')
        rewrite(resp)
        assert 'target="_blank"' in resp.text

    def test_class_attribute_preserved(self):
        resp = FakeResponse('<a class="foo" href="http://example.com">x</a>')
        rewrite(resp)
        assert 'class="foo"' in resp.text and 'target="_blank"' in resp.text

    def test_ignored_domain_untouched(self):
        resp = FakeResponse('<a href="http://properlyscreened.com/x">x</a>')
        rewrite(resp)
        assert 'target=' not in resp.text

    def test_relative_link_untouched(self):
        resp = FakeResponse('<a href="/about/">x</a>')
        rewrite(resp)
        assert 'target=' not in resp.text

    def test_existing_target_not_doubled(self):
        resp = FakeResponse('<a target="_self" href="http://example.com">x</a>')
        rewrite(resp)
        assert resp.text.count('target=') == 1

    def test_stale_content_length_header_cleared(self):
        resp = FakeResponse('<a href="http://example.com">x</a>', content_length='10')
        rewrite(resp)
        assert not resp.has_header('Content-Length')
