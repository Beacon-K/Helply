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
        self.assertEqual(response.context["kpi"], {"in_use": 1, "in_stock": 1, "in_repair": 1, "expired": 1, "expiring": 1,
                                                   "hardware_value": 0, "subscriptions": 0})
        tags = lambda **p: [a.asset_tag for a in self.client.get(reverse("assets:list"), p).context["assets"]]
        self.assertEqual(tags(type="laptop"), ["LT-1", "LT-2"])
        self.assertEqual(tags(status="warranty"), ["LT-1", "PR-1"])
        self.assertEqual(tags(q="spare"), ["LT-2"])

    def test_detail_shows_ticket_history(self):
        services.create_ticket(requester=self.emp, title="Laptop is slow", description="d", impact=3, urgency=3,
                               asset=self.laptop)
        # Administrators see every ticket; technicians only those in their support groups.
        self.client.force_login(User.objects.create_user("sup", password="x", role=User.Role.ADMINISTRATOR))
        self.assertContains(self.client.get(self.laptop.get_absolute_url()), "Laptop is slow")

    def test_report_problem_prefills_asset(self):
        self.client.force_login(self.emp)
        form = self.client.get(reverse("tickets:create"), {"asset": self.laptop.pk}).context["form"]
        self.assertEqual(form.initial["asset"], str(self.laptop.pk))


class LiveUpdateTests(TestCase):
    def setUp(self):
        self.emp = User.objects.create_user("emp", password="x")
        self.other = User.objects.create_user("other", password="x")
        self.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        self.laptop = Asset.objects.create(asset_tag="LT-1", name="Laptop", type="laptop", status="in_use", owner=self.emp)
        self.printer = Asset.objects.create(asset_tag="PR-1", name="Printer", type="printer", status="in_use")

    def version(self, user, url):
        self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.json()["version"]

    def test_list_version_is_stable_until_something_changes(self):
        url = reverse("assets:live")
        v1 = self.version(self.tech, url)
        self.assertEqual(self.version(self.tech, url), v1)
        Asset.objects.filter(pk=self.printer.pk).update(updated_at=self.printer.updated_at)  # no real change
        self.assertEqual(self.version(self.tech, url), v1)

        self.printer.status = "in_repair"
        self.printer.save()
        v2 = self.version(self.tech, url)
        self.assertNotEqual(v2, v1)

        services.create_ticket(requester=self.emp, title="Printer jam", description="d", impact=3, urgency=3,
                               asset=self.printer)
        self.assertNotEqual(self.version(self.tech, url), v2)

    def test_new_and_deleted_assets_change_the_version(self):
        url = reverse("assets:live")
        v1 = self.version(self.tech, url)
        spare = Asset.objects.create(asset_tag="LT-9", name="Spare", type="laptop")
        v2 = self.version(self.tech, url)
        self.assertNotEqual(v2, v1)
        spare.delete()
        # Back to exactly the original data, so back to the original version - but different from v2,
        # which is what a page still showing the spare laptop needs in order to refresh.
        self.assertEqual(self.version(self.tech, url), v1)

    def test_detail_version_follows_the_asset_and_its_tickets(self):
        url = reverse("assets:detail_live", args=[self.laptop.pk])
        v1 = self.version(self.emp, url)
        self.laptop.owner = self.other
        self.laptop.save()
        self.assertNotEqual(self.version(self.tech, url), v1)

    def test_employees_only_poll_their_own_devices(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("assets:detail_live", args=[self.laptop.pk])).status_code, 404)
        other_v = self.version(self.other, reverse("assets:live"))
        self.printer.status = "retired"
        self.printer.save()  # a shared printer is not in "my devices", so nothing changes for this employee
        self.assertEqual(self.version(self.other, reverse("assets:live")), other_v)

    def test_pages_are_wired_for_live_updates(self):
        self.client.force_login(self.tech)
        for url in (reverse("assets:list"), self.laptop.get_absolute_url()):
            html = self.client.get(url).content.decode()
            self.assertIn("data-live-url", html)
            self.assertIn("data-live-region", html)
            self.assertIn("js/live.js", html)



class AssetSearchTests(TestCase):
    def setUp(self):
        self.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        owner = User.objects.create_user("emma", password="x", first_name="Emma", last_name="Clark")
        Asset.objects.create(asset_tag="LT-1", name="Dell Latitude 5440", type="laptop", status="in_use", owner=owner)
        Asset.objects.create(asset_tag="LT-2", name="Lenovo ThinkPad", type="laptop", status="in_repair")
        Asset.objects.create(asset_tag="PR-1", name="HP LaserJet", type="printer", status="in_use")
        self.client.force_login(self.tech)

    def tags(self, q):
        return sorted(a.asset_tag for a in self.client.get(reverse("assets:list"), {"q": q}).context["assets"])

    def test_search_by_type_status_owner_and_combinations(self):
        self.assertEqual(self.tags("laptop"), ["LT-1", "LT-2"])
        self.assertEqual(self.tags("Printer"), ["PR-1"])
        self.assertEqual(self.tags("in repair"), ["LT-2"])
        self.assertEqual(self.tags("laptop repair"), ["LT-2"])
        self.assertEqual(self.tags("emma"), ["LT-1"])
        self.assertEqual(self.tags("shared"), ["LT-2", "PR-1"])
        self.assertEqual(self.tags("latitude 5440"), ["LT-1"])
        self.assertEqual(self.tags("nothing-like-this"), [])



class AssetValueTests(TestCase):
    def test_hardware_value_and_subscriptions_are_kept_apart(self):
        tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        Asset.objects.create(asset_tag="LT-1", name="Laptop", type="laptop", status="in_use", purchase_cost=1500)
        Asset.objects.create(asset_tag="SV-1", name="Server", type="server", status="in_stock", purchase_cost=5000)
        Asset.objects.create(asset_tag="LT-0", name="Old laptop", type="laptop", status="retired", purchase_cost=900)
        Asset.objects.create(asset_tag="LC-1", name="Microsoft 365", type="license", status="in_use", purchase_cost=7200)
        self.client.force_login(tech)
        kpi = self.client.get(reverse("assets:list")).context["kpi"]
        self.assertEqual((kpi["hardware_value"], kpi["subscriptions"]), (6500, 7200))
