from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.ai.services import related_articles

from .loader import ARTICLES_DIR, load_all, parse
from .markup import render
from .models import Article, ArticleSuggestion, ArticleVote


class MarkupTests(TestCase):
    def test_escapes_html(self):
        html = render("<script>alert(1)</script> **bold**")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<strong>bold</strong>", html)

    def test_blocks(self):
        html = render("## Title\n\n1. one\n2. two\n\n- a\n- b\n\n> **Tip:** hi\n\nText `code`")
        self.assertIn("<h2>Title</h2>", html)
        self.assertIn("<ol><li>one</li><li>two</li></ol>", html)
        self.assertIn("<ul><li>a</li><li>b</li></ul>", html)
        self.assertIn('<div class="callout"><strong>Tip:</strong> hi</div>', html)
        self.assertIn("<code>code</code>", html)


class LoaderTests(TestCase):
    def test_all_article_files_parse(self):
        articles = load_all()
        self.assertGreaterEqual(len(articles), 40)
        for a in articles:
            self.assertTrue(a.title and a.summary and a.body, a.slug)
            self.assertIn(a.audience, Article.Audience.values, a.slug)
            self.assertFalse(a.title.startswith('"'), a.slug)

    def test_quoted_title(self):
        self.assertEqual(parse(ARTICLES_DIR / "windows-updates.md").title, "Windows updates: pending, stuck or failing")


class KnowledgeBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_kb", stdout=StringIO())
        cls.emp = User.objects.create_user("emp", password="x")
        cls.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)

    def test_search_finds_the_right_article(self):
        cases = {
            "printer offline": "printer-offline-jobs-stuck",
            "vpn keeps disconnecting": "vpn-disconnecting",
            "accidentally deleted a file": "recover-deleted-file",
            "clicked a phishing link": "clicked-suspicious-link",
        }
        for query, slug in cases.items():
            self.assertEqual(related_articles(query, user=self.emp, limit=1, min_score=0.05)[0].slug, slug, query)

    def test_internal_runbooks_hidden_from_employees(self):
        runbook = Article.objects.filter(audience=Article.Audience.INTERNAL).first()
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(runbook.get_absolute_url()).status_code, 404)
        self.assertNotIn(runbook, related_articles(runbook.title, user=self.emp, min_score=0.01))
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(runbook.get_absolute_url()).status_code, 200)

    def vote(self, slug, value, user=None):
        self.client.force_login(user or self.emp)
        return self.client.post(reverse("kb:vote", args=[slug]), {"vote": value},
                                headers={"X-Requested-With": "fetch"}).json()

    def test_vote_toggle_switch_and_undo(self):
        self.assertEqual(self.vote("mailbox-full", "up"), {"yes": 1, "no": 0, "total": 1, "percent": 100, "mine": "up"})
        # same thumb again removes the vote
        self.assertEqual(self.vote("mailbox-full", "up")["yes"], 0)
        # switching from up to down moves the vote
        self.vote("mailbox-full", "up")
        state = self.vote("mailbox-full", "down")
        self.assertEqual((state["yes"], state["no"], state["mine"]), (0, 1, "down"))
        self.assertEqual(ArticleVote.objects.filter(user=self.emp).count(), 1)

    def test_votes_from_different_users_add_up(self):
        self.vote("mailbox-full", "up")
        state = self.vote("mailbox-full", "down", user=self.tech)
        self.assertEqual((state["yes"], state["no"], state["percent"]), (1, 1, 50))
        article = Article.objects.get(slug="mailbox-full")
        self.assertEqual((article.helpful_total, article.helpful_percent), (2, 50))

    def test_vote_without_js_redirects_back_to_article(self):
        self.client.force_login(self.emp)
        response = self.client.post(reverse("kb:vote", args=["mailbox-full"]), {"vote": "up"})
        self.assertRedirects(response, "/kb/mailbox-full/#feedback", fetch_redirect_response=False)

    def test_invalid_vote_rejected(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.post(reverse("kb:vote", args=["mailbox-full"]), {"vote": "x"}).status_code, 400)

    def test_suggestion_saved(self):
        self.client.force_login(self.emp)
        url = reverse("kb:suggest", args=["mailbox-full"])
        response = self.client.post(url, {"text": "  Add steps for Outlook on Mac  "}, headers={"X-Requested-With": "fetch"})
        self.assertEqual(response.json(), {"ok": True})
        suggestion = ArticleSuggestion.objects.get()
        self.assertEqual((suggestion.text, suggestion.user, suggestion.status), ("Add steps for Outlook on Mac", self.emp, "open"))

    def test_empty_suggestion_rejected(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.post(reverse("kb:suggest", args=["mailbox-full"]), {"text": "  "}).status_code, 400)
        self.assertFalse(ArticleSuggestion.objects.exists())

    def test_list_page_renders(self):
        self.client.force_login(self.emp)
        self.assertContains(self.client.get(reverse("kb:list")), "Recover a deleted or overwritten file")
        self.assertContains(self.client.get(reverse("kb:list"), {"q": "paper jam"}), "Print quality problems")
