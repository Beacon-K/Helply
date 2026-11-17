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


class ArticleManagementTests(TestCase):
    """Every IT staff member can create, edit and delete articles; employees cannot."""

    @classmethod
    def setUpTestData(cls):
        cls.emp = User.objects.create_user("emp", password="x")
        cls.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        cls.admin = User.objects.create_user("boss", password="x", role=User.Role.ADMINISTRATOR)
        cls.article = Article.objects.create(title="Old", slug="old", body="b", status=Article.Status.PUBLISHED)

    def test_technician_and_administrator_can_create_with_generated_slug(self):
        for user in (self.tech, self.admin):
            self.client.force_login(user)
            response = self.client.post(reverse("kb:create"), {
                "title": "Reset a password", "body": "Steps", "audience": "everyone", "status": "draft"})
            self.assertEqual(response.status_code, 302)
        slugs = set(Article.objects.filter(title="Reset a password").values_list("slug", flat=True))
        self.assertEqual(slugs, {"reset-a-password", "reset-a-password-2"})
        self.assertEqual(Article.objects.get(slug="reset-a-password").author, self.tech)

    def test_technician_can_edit_and_delete(self):
        self.client.force_login(self.tech)
        self.client.post(reverse("kb:edit", args=["old"]), {
            "title": "New title", "slug": "old", "body": "b", "audience": "internal", "status": "published"})
        self.article.refresh_from_db()
        self.assertEqual((self.article.title, self.article.audience), ("New title", "internal"))
        self.assertEqual(self.client.get(reverse("kb:delete", args=["old"])).status_code, 200)
        self.assertTrue(Article.objects.filter(slug="old").exists())  # GET only asks
        self.client.post(reverse("kb:delete", args=["old"]))
        self.assertFalse(Article.objects.filter(slug="old").exists())

    def test_employee_is_refused(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("kb:create")).status_code, 403)
        self.assertEqual(self.client.post(reverse("kb:edit", args=["old"]), {"title": "x"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("kb:delete", args=["old"])).status_code, 403)
        self.assertTrue(Article.objects.filter(slug="old").exists())

    def test_reserved_slug_rejected_and_drafts_only_for_it_staff(self):
        self.client.force_login(self.tech)
        response = self.client.post(reverse("kb:create"), {
            "title": "x", "slug": "new", "body": "b", "audience": "everyone", "status": "draft"})
        self.assertEqual(response.status_code, 200)
        Article.objects.create(title="Draft one", slug="draft-one", body="b")
        self.assertContains(self.client.get(reverse("kb:list")), "Draft one")
        self.client.force_login(self.emp)
        self.assertNotContains(self.client.get(reverse("kb:list")), "Draft one")
        self.assertEqual(self.client.get("/kb/draft-one/").status_code, 404)


class SuggestionReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.emp = User.objects.create_user("emp", password="x")
        cls.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        cls.article = Article.objects.create(title="A", slug="a", body="b", status=Article.Status.PUBLISHED)
        cls.suggestion = ArticleSuggestion.objects.create(article=cls.article, user=cls.emp, text="Step 3 is wrong")

    def test_it_staff_see_and_toggle_suggestions_employees_do_not(self):
        self.client.force_login(self.emp)
        self.assertNotContains(self.client.get(self.article.get_absolute_url()), "Step 3 is wrong")
        self.assertEqual(self.client.post(reverse("kb:suggestion_done", args=["a", self.suggestion.pk])).status_code, 403)
        self.client.force_login(self.tech)
        self.assertContains(self.client.get(self.article.get_absolute_url()), "Step 3 is wrong")
        self.assertContains(self.client.get(reverse("kb:list")), "1 suggestion")
        self.client.post(reverse("kb:suggestion_done", args=["a", self.suggestion.pk]))
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, "done")
        self.client.post(reverse("kb:suggestion_done", args=["a", self.suggestion.pk]))
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, "open")
