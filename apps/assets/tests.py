from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.tickets import services

from .models import Asset


class AssetTests(TestCase):
    def setUp(self):
        self.emp = User.objects.create_user("emp", password="x")
        self.other = User.objects.create_user("other", password="x")
        self.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        today = timezone.localdate()
        self.laptop = Asset.objects.create(asset_tag="LT-1", name="Laptop", type="laptop", status="in_use",
                                           owner=self.emp, warranty_expiry=today - timedelta(days=1))
        self.printer = Asset.objects.create(asset_tag="PR-1", name="Printer", type="printer", status="in_repair",
                                            warranty_expiry=today + timedelta(days=30))
        self.spare = Asset.objects.create(asset_tag="LT-2", name="Spare", type="laptop", status="in_stock",
                                          warranty_expiry=today + timedelta(days=400))

    def test_warranty_state(self):
        self.assertEqual([a.warranty_state for a in (self.laptop, self.printer, self.spare)], ["expired", "expiring", "ok"])
        self.assertEqual(Asset(asset_tag="X").warranty_state, "none")

    def test_employee_sees_only_own_devices(self):
        self.client.force_login(self.emp)
        response = self.client.get(reverse("assets:list"))
        self.assertTemplateUsed(response, "assets/my_devices.html")
        self.assertEqual([a.asset_tag for a in response.context["assets"]], ["LT-1"])
        self.assertEqual(self.client.get(self.printer.get_absolute_url()).status_code, 404)

    def test_register_filters_and_kpis(self):
        self.client.force_login(self.tech)
        response = self.client.get(reverse("assets:list"))
        self.assertEqual(response.context["kpi"], {"in_use": 1, "in_stock": 1, "in_repair": 1, "expired": 1, "expiring": 1})
        tags = lambda **p: [a.asset_tag for a in self.client.get(reverse("assets:list"), p).context["assets"]]
        self.assertEqual(tags(type="laptop"), ["LT-1", "LT-2"])
        self.assertEqual(tags(status="warranty"), ["LT-1", "PR-1"])
        self.assertEqual(tags(q="spare"), ["LT-2"])

    def test_detail_shows_ticket_history(self):
        services.create_ticket(requester=self.emp, title="Laptop is slow", description="d", impact=3, urgency=3,
                               asset=self.laptop)
        # Supervisors see every ticket; technicians only those in their support groups.
        self.client.force_login(User.objects.create_user("sup", password="x", role=User.Role.SUPERVISOR))
        self.assertContains(self.client.get(self.laptop.get_absolute_url()), "Laptop is slow")

    def test_report_problem_prefills_asset(self):
        self.client.force_login(self.emp)
        form = self.client.get(reverse("tickets:create"), {"asset": self.laptop.pk}).context["form"]
        self.assertEqual(form.initial["asset"], str(self.laptop.pk))
