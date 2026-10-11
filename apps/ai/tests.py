import io
import json
import urllib.error
from unittest import mock

from django.test import TestCase, override_settings

from apps.tickets.models import Category

from .backends.cloudflare import CloudflareBackend
from .backends.keyword import KeywordBackend
from .text import jaccard, tokenize


class KeywordBackendTests(TestCase):
    def setUp(self):
        self.net = Category.objects.create(name="Network", keywords="vpn,wifi,internet")
        self.hw = Category.objects.create(name="Hardware", keywords="laptop,printer")
        self.cats = Category.objects.all()

    def test_confident_match(self):
        r = KeywordBackend().classify("VPN drops and wifi is slow", self.cats)
        self.assertEqual(r.category, self.net)
        self.assertEqual(r.confidence, 1.0)

    def test_weak_match_has_low_confidence(self):
        r = KeywordBackend().classify("my laptop", self.cats)
        self.assertEqual(r.category, self.hw)
        self.assertLess(r.confidence, 0.6)

    def test_no_match(self):
        r = KeywordBackend().classify("hello there", self.cats)
        self.assertIsNone(r.category)
        self.assertEqual(r.confidence, 0.0)


class CloudflareBackendTests(TestCase):
    """The network is always mocked; these tests never call Cloudflare."""

    def setUp(self):
        self.net = Category.objects.create(name="Network", keywords="vpn,wifi")
        self.hw = Category.objects.create(name="Hardware", keywords="laptop")
        self.cats = Category.objects.all()

    def _backend(self):
        return CloudflareBackend()

    def _reply(self, answer):
        body = json.dumps({"success": True, "result": {"response": answer}}).encode()
        return mock.patch("urllib.request.urlopen", return_value=io.BytesIO(body))

    def _creds(self):
        return override_settings(HELPLY_CF_ACCOUNT_ID="acct", HELPLY_CF_API_TOKEN="test-token")

    def test_valid_answer(self):
        with self._creds(), self._reply(f'{{"category_id": {self.net.pk}, "confidence": 0.9, "reason": "vpn"}}'):
            r = self._backend().classify("VPN down", self.cats)
        self.assertEqual((r.category, r.confidence), (self.net, 0.9))

    def test_answer_wrapped_in_text_and_confidence_clamped(self):
        with self._creds(), self._reply(f'Sure! {{"category_id": "{self.hw.pk}", "confidence": 7}}'):
            r = self._backend().classify("laptop", self.cats)
        self.assertEqual((r.category, r.confidence), (self.hw, 1.0))

    def test_unknown_category_is_rejected(self):
        with self._creds(), self._reply('{"category_id": 99999, "confidence": 0.99}'):
            r = self._backend().classify("anything", self.cats)
        self.assertIsNone(r.category)
        self.assertEqual(r.confidence, 0.0)

    def test_garbage_answer_falls_back_to_keywords(self):
        backend = self._backend()
        with self._creds(), self._reply("I cannot help"):
            r = backend.classify("VPN and wifi down", self.cats)
        self.assertEqual(r.category, self.net)
        self.assertEqual(backend.name, "keyword-baseline")

    def test_missing_credentials_fall_back_without_network(self):
        with mock.patch("urllib.request.urlopen") as opener:
            r = self._backend().classify("VPN and wifi down", self.cats)
        opener.assert_not_called()
        self.assertEqual(r.category, self.net)

    def test_network_error_falls_back(self):
        with self._creds(), mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            r = self._backend().classify("VPN and wifi down", self.cats)
        self.assertEqual(r.category, self.net)


class TextTests(TestCase):
    def test_tokenize_drops_stopwords(self):
        self.assertEqual(tokenize("The VPN is not working"), {"vpn"})

    def test_jaccard(self):
        self.assertEqual(jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(jaccard(set(), {"a"}), 0.0)
