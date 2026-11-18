"""English / French: language choice, translated pages, and a compiled catalogue that matches its .po file."""
import importlib.util
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation

from apps.accounts.models import User

ROOT = Path(settings.BASE_DIR)


def _compile_module():
    spec = importlib.util.spec_from_file_location("compile_messages", ROOT / "tools" / "compile_messages.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LanguageChoiceTests(TestCase):
    def test_english_by_default(self):
        html = self.client.get(reverse("login")).content.decode()
        self.assertIn('lang="en"', html)
        self.assertIn("Forgot your password?", html)

    def test_browser_language_is_used_when_no_choice_was_made(self):
        html = self.client.get(reverse("login"), headers={"accept-language": "fr-CA,fr;q=0.9,en;q=0.5"}).content.decode()
        self.assertIn('lang="fr"', html)
        self.assertIn("Mot de passe oublié", html)

    def test_switching_sets_a_cookie_that_beats_the_browser_header(self):
        r = self.client.post(reverse("set_language"), {"language": "fr", "next": reverse("login")})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.cookies["django_language"].value, "fr")
        html = self.client.get(reverse("login"), headers={"accept-language": "en-US"}).content.decode()
        self.assertIn("Mot de passe oublié", html)
        self.client.post(reverse("set_language"), {"language": "en", "next": reverse("login")})
        self.assertIn("Forgot your password?", self.client.get(reverse("login")).content.decode())

    def test_unknown_language_is_refused(self):
        r = self.client.post(reverse("set_language"), {"language": "xx", "next": "/"})
        self.assertNotIn("django_language", r.cookies)

    def test_both_languages_are_offered_on_every_page(self):
        html = self.client.get(reverse("password_reset")).content.decode()
        self.assertIn('value="en"', html)
        self.assertIn('value="fr"', html)


class FrenchPagesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="adm", password="x-Test-12345", role="administrator", first_name="Ann")
        self.employee = User.objects.create_user(username="emp", password="x-Test-12345", role="employee", first_name="Ed")

    def _fr(self, user):
        c = Client()
        c.force_login(user)
        c.cookies["django_language"] = "fr"
        return c

    def test_administrator_dashboard_in_french(self):
        body = self._fr(self.admin).get(reverse("core:dashboard")).content.decode()
        for phrase in ("Tableau de bord", "Tickets ouverts", "Charge de l’équipe", "Vue d’ensemble de l’entreprise"):
            self.assertIn(phrase, body)
        self.assertNotIn("Open tickets", body)

    def test_employee_dashboard_and_new_ticket_form_in_french(self):
        c = self._fr(self.employee)
        self.assertIn("De quelle aide avez-vous besoin", c.get(reverse("core:dashboard")).content.decode())
        form = c.get(reverse("tickets:create")).content.decode()
        for phrase in ("Signaler un problème informatique", "Urgence", "Soumettre le ticket"):
            self.assertIn(phrase, form)

    def test_choice_labels_and_time_filters_follow_the_language(self):
        with translation.override("fr"):
            self.assertEqual(str(User.Role.ADMINISTRATOR.label), "Administrateur")
            from apps.core.templatetags.helply import _compact
            self.assertEqual(_compact(90 * 60), "1 h 30 min")
        with translation.override("en"):
            self.assertEqual(str(User.Role.ADMINISTRATOR.label), "Administrator")


class CatalogueTests(TestCase):
    def test_compiled_catalogue_matches_the_po_file(self):
        """Windows servers have no msgfmt, so the .mo is committed; it must not lag behind the .po."""
        mod = _compile_module()
        po = ROOT / "locale" / "fr" / "LC_MESSAGES" / "django.po"
        mo = po.with_suffix(".mo")
        self.assertTrue(mo.exists(), "run: python tools/compile_messages.py")
        tmp = mo.with_name("check.mo")
        try:
            mod.write_mo(mod.parse(po), tmp)
            self.assertEqual(tmp.read_bytes(), mo.read_bytes(), "locale/fr django.mo is out of date: python tools/compile_messages.py")
        finally:
            tmp.unlink(missing_ok=True)

    def test_every_french_message_keeps_its_placeholders(self):
        mod = _compile_module()
        import re
        for msgid, msgstr in mod.parse(ROOT / "locale" / "fr" / "LC_MESSAGES" / "django.po").items():
            if not msgid:
                continue
            ids = sorted(re.findall(r"%\([a-z_]+\)[sd]", msgid.split("\x00")[0]))
            for part in msgstr.split("\x00"):
                self.assertEqual(ids, sorted(re.findall(r"%\([a-z_]+\)[sd]", part)), msg=msgid)
