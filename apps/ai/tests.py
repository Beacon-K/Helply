from django.test import TestCase

from apps.tickets.models import Category

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


class TextTests(TestCase):
    def test_tokenize_drops_stopwords(self):
        self.assertEqual(tokenize("The VPN is not working"), {"vpn"})

    def test_jaccard(self):
        self.assertEqual(jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(jaccard(set(), {"a"}), 0.0)
