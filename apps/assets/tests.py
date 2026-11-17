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


class RenewalReminderTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.owner = User.objects.create_user("owner", password="x", email="owner@acme-corp.com")
        self.admin = User.objects.create_user("boss", password="x", email="boss@acme-corp.com",
                                              role=User.Role.ADMINISTRATOR)
        self.tech = User.objects.create_user("tech2", password="x", role=User.Role.TECHNICIAN)

    def asset(self, days, **kw):
        data = dict(asset_tag="SUB-1", name="Office 365", type="license", status="in_use", owner=self.owner,
                    warranty_expiry=self.today + timedelta(days=days))
        data.update(kw)
        return Asset.objects.create(**data)

    def test_milestones(self):
        from .renewals import current_milestone
        self.assertEqual([current_milestone(d) for d in (45, 30, 20, 14, 10, 7, 3, 0, -5, -14, -15)],
                         [None, 30, 30, 14, 14, 7, 7, 0, 0, 0, None])

    def test_reminds_owner_and_administrators_once_per_milestone(self):
        from .renewals import send_renewal_reminders
        from apps.notifications.models import Notification
        self.asset(20)
        self.assertEqual(len(send_renewal_reminders()), 1)
        self.assertEqual(Notification.objects.filter(kind="renewal").count(), 2)  # owner + administrator
        self.assertFalse(Notification.objects.filter(recipient=self.tech).exists())
        self.assertEqual(send_renewal_reminders(), [])  # same day again: nothing new
        self.assertEqual(Notification.objects.filter(kind="renewal").count(), 2)
        self.assertEqual(len(send_renewal_reminders(today=self.today + timedelta(days=7))), 1)  # 13 days left

    def test_new_renewal_date_starts_a_new_cycle(self):
        from .renewals import send_renewal_reminders
        asset = self.asset(5)
        send_renewal_reminders()
        asset.warranty_expiry = self.today + timedelta(days=360)
        asset.save()
        self.assertEqual(send_renewal_reminders(), [])
        asset.warranty_expiry = self.today + timedelta(days=6)
        asset.save()
        self.assertEqual(len(send_renewal_reminders()), 1)  # a different date is a different cycle

    def test_ignores_hardware_retired_and_far_away(self):
        from .renewals import send_renewal_reminders
        self.asset(5, asset_tag="LT-9", type="laptop")
        self.asset(5, asset_tag="OLD-1", status="retired")
        self.asset(90, asset_tag="FAR-1")
        self.assertEqual(send_renewal_reminders(), [])

    def test_cloud_server_and_email(self):
        from django.core import mail
        from django.core.management import call_command
        self.asset(3, asset_tag="VPS-1", name="web-1", type="cloud")
        with self.captureOnCommitCallbacks(execute=True):
            call_command("renewal_reminders", stdout=__import__("io").StringIO())
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("web-1 renews in 3 days", mail.outbox[0].subject)


class AssetBulkExcelTests(TestCase):
    """Bulk .xlsx export / import (apps/assets/bulk.py, xlsx.py)."""

    def setUp(self):
        import io
        from apps.accounts.models import Department
        from . import bulk, xlsx
        self.io, self.bulk, self.xlsx = io, bulk, xlsx
        self.emp = User.objects.create_user("emp", password="x", email="emp@example.com")
        self.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        self.dept = Department.objects.create(name="Finance")
        self.laptop = Asset.objects.create(asset_tag="LT-1", name="Laptop", type="laptop", status="in_use",
                                           owner=self.emp, notes='=HYPERLINK("http://evil")', location="HQ")
        self.printer = Asset.objects.create(asset_tag="PR-1", name="Printer", type="printer", status="in_repair")
        self.client.force_login(self.tech)

    def sheet(self, rows, header=None):
        data = self.xlsx.write_workbook([("Assets", [header or self.bulk.HEADERS] + rows, [])])
        f = self.io.BytesIO(data)
        f.name = "assets.xlsx"
        return f

    def row(self, **kw):
        base = {k: "" for k in self.bulk.KEYS}
        base.update(kw)
        return [base[k] for k in self.bulk.KEYS]

    def upload(self, fileobj):
        return self.client.post(reverse("assets:import"), {"file": fileobj})

    def confirm(self):
        return self.client.post(reverse("assets:import_confirm"),
                                {"token": self.client.session["asset_import"]["token"]})

    def read_back(self, response):
        return self.xlsx.read_rows(self.io.BytesIO(response.content))

    # --- export / template
    def test_export_has_every_asset_and_strips_formulas(self):
        r = self.client.get(reverse("assets:export"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml.sheet", r["Content-Type"])
        self.assertIn("attachment", r["Content-Disposition"])
        rows = self.read_back(r)
        self.assertEqual(rows[0][1], self.bulk.HEADERS)
        self.assertEqual(len(rows), 3)
        by_tag = {cells[0]: cells for _, cells in rows[1:]}
        self.assertEqual(by_tag["LT-1"][5], "emp")
        self.assertFalse(by_tag["LT-1"][12].startswith(("=", "+", "-", "@")))

    def test_export_honours_filters(self):
        rows = self.read_back(self.client.get(reverse("assets:export"), {"status": "in_repair"}))
        self.assertEqual([c[0] for _, c in rows[1:]], ["PR-1"])
        rows = self.read_back(self.client.get(reverse("assets:export"), {"q": "laptop"}))
        self.assertEqual([c[0] for _, c in rows[1:]], ["LT-1"])

    def test_safe_text(self):
        for raw in ("=1+1", "+1", "-1", "@SUM(A1)", "  =x", "\t=x"):
            self.assertFalse(self.bulk.safe_text(raw).lstrip().startswith(("=", "+", "-", "@")), raw)
        self.assertEqual(self.bulk.safe_text("Dell XPS"), "Dell XPS")

    def test_template_has_headers_and_instructions(self):
        import zipfile
        r = self.client.get(reverse("assets:import_template"))
        self.assertEqual(self.read_back(r)[0][1], self.bulk.HEADERS)
        workbook = zipfile.ZipFile(self.io.BytesIO(r.content)).read("xl/workbook.xml").decode()
        self.assertIn("Instructions", workbook)

    def test_exported_file_reimports_without_creating_anything(self):
        data = self.client.get(reverse("assets:export")).content
        plan = self.bulk.classify(self.bulk.read_upload(self.io.BytesIO(data)))
        self.assertEqual(plan["create"], [])
        self.assertEqual(plan["errors"], [])
        # Only the formula-looking note differs (export stripped its leading "=").
        self.assertEqual([i["tag"] for i in plan["update"]], ["LT-1"])

    # --- preview classification
    def test_preview_classifies_rows(self):
        r = self.upload(self.sheet([
            self.row(asset_tag="NEW-1", name="Monitor", type="Monitor", owner="emp@example.com", department="Finance",
                     purchase_date="2025-01-31", purchase_cost="199.5"),
            self.row(asset_tag="PR-1", status="In use"),
            self.row(asset_tag="LT-1", name="Laptop"),
            self.row(asset_tag="BAD-1", name="X", type="spaceship"),
            self.row(asset_tag="BAD-2", name="X", type="laptop", owner="nobody"),
            self.row(asset_tag="BAD-3", name="X", type="laptop", purchase_date="31/01/2025"),
            self.row(asset_tag="BAD-4", name="X", type="laptop", department="Nope"),
            self.row(asset_tag="NEW-1", name="Dup", type="laptop"),
            self.row(asset_tag="BAD-5", type="laptop"),
        ]))
        self.assertRedirects(r, reverse("assets:import_preview"))
        page = self.client.get(reverse("assets:import_preview"))
        plan = page.context["plan"]
        self.assertEqual([i["tag"] for i in plan["create"]], ["NEW-1"])
        self.assertEqual([i["tag"] for i in plan["update"]], ["PR-1"])
        self.assertEqual([i["tag"] for i in plan["unchanged"]], ["LT-1"])
        self.assertEqual(len(plan["errors"]), 6)
        text = " ".join(e for i in plan["errors"] for e in i["errors"])
        self.assertIn("Duplicate of row 2", text)
        self.assertIn("nobody", text)
        self.assertEqual(Asset.objects.count(), 2)  # the preview saves nothing

    # --- confirm
    def test_confirm_applies_valid_rows_and_deletes_nothing(self):
        rows = [
            self.row(asset_tag="NEW-1", name="Monitor", type="monitor", owner="emp", purchase_cost="10"),
            self.row(asset_tag="PR-1", status="retired", location="Store"),
            self.row(asset_tag="BAD", name="x", type="zzz"),
        ]
        self.upload(self.sheet(rows))
        self.client.post(reverse("assets:import_confirm"), {"token": "wrong"})
        self.assertEqual(Asset.objects.count(), 2)
        self.confirm()
        self.assertEqual(Asset.objects.count(), 3)
        new = Asset.objects.get(asset_tag="NEW-1")
        self.assertEqual((new.owner, str(new.purchase_cost), new.status), (self.emp, "10.00", "in_stock"))
        self.printer.refresh_from_db()
        self.assertEqual((self.printer.status, self.printer.location, self.printer.name),
                         ("retired", "Store", "Printer"))
        self.laptop.refresh_from_db()  # absent from the file: untouched
        self.assertEqual((self.laptop.owner, self.laptop.status), (self.emp, "in_use"))
        self.assertNotIn("asset_import", self.client.session)

    def test_empty_cell_never_clears_existing_value(self):
        self.upload(self.sheet([self.row(asset_tag="LT-1", status="in_stock")]))
        self.confirm()
        self.laptop.refresh_from_db()
        self.assertEqual((self.laptop.status, self.laptop.owner, self.laptop.location), ("in_stock", self.emp, "HQ"))

    # --- bad files
    def test_bad_files_are_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        ok_row = self.row(asset_tag="A", name="n", type="laptop")
        xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        bad = [
            SimpleUploadedFile("a.xlsx", b"not a workbook", content_type=xlsx_mime),
            SimpleUploadedFile("a.xlsx", b""),
            SimpleUploadedFile("a.xlsx", b"PK\x03\x04garbage"),
            SimpleUploadedFile("a.xlsx", b"asset_tag,name\nA,b\n", content_type="text/csv"),
            self.sheet([ok_row], header=["Tag", "Name"]),
            self.sheet([ok_row], header=self.bulk.HEADERS + ["Extra"]),
            self.sheet([ok_row], header=self.bulk.HEADERS[1:]),
            self.sheet([]),
        ]
        for f in bad:
            r = self.upload(f)
            self.assertRedirects(r, reverse("assets:list"), fetch_redirect_response=False)
            self.assertNotIn("asset_import", self.client.session)
        self.assertEqual(self.client.post(reverse("assets:import"), {}).status_code, 302)

    def test_row_limit_and_size_limit(self):
        rows = [self.row(asset_tag=f"T{i}", name="n", type="laptop") for i in range(self.bulk.MAX_ROWS + 1)]
        with self.assertRaises(self.bulk.SheetError):
            self.bulk.read_upload(self.sheet(rows))
        big = self.io.BytesIO(b"PK\x03\x04" + b"0" * (self.xlsx.MAX_FILE_BYTES + 1))
        with self.assertRaises(self.bulk.SheetError):
            self.bulk.read_upload(big)

    def _patched(self, fileobj, part, fn):
        import zipfile
        out = self.io.BytesIO()
        with zipfile.ZipFile(self.io.BytesIO(fileobj.getvalue())) as zin, zipfile.ZipFile(out, "w") as zout:
            for item in zin.namelist():
                data = zin.read(item)
                zout.writestr(item, fn(data) if item == part else data)
        out.seek(0)
        return out

    def test_formula_cells_are_refused_not_evaluated(self):
        f = self.sheet([self.row(asset_tag="F-1", name="n", type="laptop")])
        patched = self._patched(f, "xl/worksheets/sheet1.xml", lambda d: d.replace(
            b'<c r="B2" s="0" t="inlineStr"><is><t xml:space="preserve">n</t></is></c>',
            b'<c r="B2"><f>1+1</f><v>2</v></c>'))
        plan = self.bulk.classify(self.bulk.read_upload(patched))
        self.assertEqual(len(plan["errors"]), 1)
        self.assertIn("formulas", " ".join(plan["errors"][0]["errors"]))

    def test_xml_entities_rejected(self):
        patched = self._patched(self.sheet([]), "xl/workbook.xml", lambda d: (
            b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]>' + d.split(b"?>", 1)[1]))
        with self.assertRaises(self.bulk.SheetError):
            self.bulk.read_upload(patched)

    def test_dates_and_numbers_are_understood(self):
        import datetime
        data = self.xlsx.write_workbook([("Assets", [self.bulk.HEADERS, [
            "D-2", "n", "laptop", "", 12345, "", "", "", "", datetime.date(2025, 3, 4), 5.5, "", ""]], [])])
        values = self.bulk.read_upload(self.io.BytesIO(data))[0][1]
        self.assertEqual((values["serial_number"], values["purchase_date"], values["purchase_cost"]),
                         ("12345", "2025-03-04", "5.5"))

    # --- permissions
    def test_employees_and_anonymous_are_blocked(self):
        gets = ["assets:export", "assets:import_template", "assets:import_preview"]
        posts = ["assets:import", "assets:import_confirm", "assets:import_cancel"]
        self.client.force_login(self.emp)
        for n in gets:
            self.assertEqual(self.client.get(reverse(n)).status_code, 403, n)
        for n in posts:
            self.assertEqual(self.client.post(reverse(n), {}).status_code, 403, n)
        self.client.logout()
        for n in gets:
            self.assertEqual(self.client.get(reverse(n)).status_code, 302, n)

    def test_list_page_shows_bulk_tools_to_staff_only(self):
        self.assertContains(self.client.get(reverse("assets:list")), reverse("assets:export"))
        self.client.force_login(self.emp)
        self.assertNotContains(self.client.get(reverse("assets:list")), reverse("assets:export"))


class AssetManagementTests(TestCase):
    """Every IT staff member adds, edits and deletes assets in the app itself (no Django Admin needed)."""

    def setUp(self):
        self.emp = User.objects.create_user("emp", password="x")
        self.tech = User.objects.create_user("tech", password="x", role=User.Role.TECHNICIAN)
        self.asset = Asset.objects.create(asset_tag="LT-9", name="Laptop", type="laptop", status="in_use")

    def payload(self, **over):
        data = {"asset_tag": "MN-1", "name": "Monitor", "type": "monitor", "status": "in_stock"}
        data.update(over)
        return data

    def test_technician_creates_edits_and_deletes(self):
        self.client.force_login(self.tech)
        response = self.client.post(reverse("assets:create"), self.payload())
        created = Asset.objects.get(asset_tag="MN-1")
        self.assertRedirects(response, created.get_absolute_url(), fetch_redirect_response=False)
        self.client.post(reverse("assets:edit", args=[created.pk]), self.payload(name="Big monitor", status="in_use"))
        created.refresh_from_db()
        self.assertEqual((created.name, created.status), ("Big monitor", "in_use"))
        self.client.post(reverse("assets:delete", args=[created.pk]))
        self.assertFalse(Asset.objects.filter(asset_tag="MN-1").exists())

    def test_duplicate_tag_is_rejected(self):
        self.client.force_login(self.tech)
        response = self.client.post(reverse("assets:create"), self.payload(asset_tag="lt-9"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Asset.objects.count(), 1)

    def test_employee_is_refused(self):
        self.client.force_login(self.emp)
        for url in (reverse("assets:create"), reverse("assets:edit", args=[self.asset.pk])):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("assets:delete", args=[self.asset.pk])).status_code, 403)
        self.assertTrue(Asset.objects.filter(pk=self.asset.pk).exists())

    def test_asset_of_a_monitored_server_cannot_be_deleted_here(self):
        from apps.monitoring.models import Server
        server = Server.objects.create(name="web", asset=self.asset)
        self.client.force_login(self.tech)
        self.client.post(reverse("assets:delete", args=[self.asset.pk]))
        self.assertTrue(Asset.objects.filter(pk=self.asset.pk).exists())
        self.assertTrue(Server.objects.filter(pk=server.pk).exists())

    def test_no_admin_links_on_asset_pages(self):
        self.client.force_login(self.tech)
        self.assertNotContains(self.client.get(reverse("assets:list")), "/admin/")
        self.assertNotContains(self.client.get(self.asset.get_absolute_url()), "/admin/")
