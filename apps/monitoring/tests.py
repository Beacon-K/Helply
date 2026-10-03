import importlib.util
import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Department, User
from apps.assets.models import Asset
from apps.core.reference_data import SLA, ensure_categories
from apps.sla.models import SLAPolicy
from apps.tickets.choices import Channel, Status
from apps.tickets.models import TicketEvent

from . import alerts, services
from .models import Alert, Metric, MetricHourly, Server

GB = 1024**3


def report(cpu=20.0, mem=40.0, disk=50.0, **extra):
    data = {
        "version": "1.0.0", "cpu": cpu,
        "mem": {"used": int(8 * GB * mem / 100), "total": 8 * GB},
        "swap": {"used": 0, "total": 2 * GB},
        "disk": {"used": int(100 * GB * disk / 100), "total": 100 * GB},
        "net": {"rx_rate": 1000, "tx_rate": 2000, "rx_total": 10**9, "tx_total": 2 * 10**9},
        "load": [0.5, 0.4, 0.3], "processes": 120, "uptime": 3600,
        "host": {"hostname": "web-1", "os_family": "linux", "os_name": "Ubuntu 24.04", "arch": "x86_64",
                 "cpu_model": "Xeon", "cpu_cores": 2},
    }
    data.update(extra)
    return data


class MonitoringBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_categories()
        for priority, name, response, resolution in SLA:
            SLAPolicy.objects.create(priority=priority, name=name, response_minutes=response,
                                     resolution_minutes=resolution)
        it = Department.objects.create(name="IT")
        cls.admin = User.objects.create_user("alice", role=User.Role.ADMINISTRATOR, department=it, password="x")
        cls.tech = User.objects.create_user("tina", role=User.Role.TECHNICIAN, department=it, password="x")
        cls.employee = User.objects.create_user("emma", role=User.Role.EMPLOYEE, password="x")

    def setUp(self):
        self.server = Server.objects.create(name="web-prod-01", provider="aws", owner=self.tech,
                                            monthly_cost=Decimal("38.00"), criticality=Server.Criticality.HIGH)
        services.sync_asset(self.server)
        self.token = self.server.issue_token()
        self.server.save()

    def push(self, data, token=None, **headers):
        return self.client.post(reverse("monitoring:ingest"), data=json.dumps(data), content_type="application/json",
                                HTTP_AUTHORIZATION=f"Bearer {token or self.token}", **headers)

    def feed(self, minutes, **values):
        """Store readings every 30 seconds for the last `minutes`, ending now."""
        now = timezone.now()
        server = Server.objects.get(pk=self.server.pk)
        for i in range(minutes * 2, -1, -1):
            server.last_seen_at = None
            services.ingest(server, report(**values), now=now - timedelta(seconds=30 * i))
        return server


class TokenTests(MonitoringBase):
    def test_only_a_hash_is_stored(self):
        self.assertTrue(self.token.startswith("hly_"))
        self.assertNotIn(self.token, self.server.token_hash)
        self.assertEqual(Server.for_token(self.token), self.server)

    def test_wrong_or_revoked_tokens_are_rejected(self):
        self.assertIsNone(Server.for_token("hly_" + "x" * 40))
        self.assertIsNone(Server.for_token(self.token[:-1] + ("A" if self.token[-1] != "A" else "B")))
        self.assertIsNone(Server.for_token(""))
        old = self.token
        self.server.issue_token()
        self.server.save()
        self.assertIsNone(Server.for_token(old))


class IngestTests(MonitoringBase):
    def test_report_updates_server_and_history(self):
        response = self.push(report(cpu=33.3), REMOTE_ADDR="203.0.113.9")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["stored"])
        self.server.refresh_from_db()
        self.assertEqual(self.server.cpu, 33.3)
        self.assertEqual(self.server.mem_percent, 40.0)
        self.assertEqual(self.server.os_name, "Ubuntu 24.04")
        self.assertEqual(self.server.reported_ip, "203.0.113.9")
        self.assertEqual(self.server.status, "online")
        self.assertEqual(Metric.objects.filter(server=self.server).count(), 1)

    def test_cloudflare_client_ip_is_used_only_behind_the_local_tunnel(self):
        self.push(report(), REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="198.51.100.4")
        self.server.refresh_from_db()
        self.assertEqual(self.server.reported_ip, "198.51.100.4")

    def test_rejects_missing_token_bad_json_and_huge_bodies(self):
        self.assertEqual(self.client.post(reverse("monitoring:ingest"), data="{}",
                                          content_type="application/json").status_code, 401)
        self.assertEqual(self.push(report(), token="hly_wrongwrongwrongwrongwrong").status_code, 401)
        bad = self.client.post(reverse("monitoring:ingest"), data="not json", content_type="application/json",
                               HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.push({"cpu": 5}).status_code, 400)  # no memory block
        self.assertEqual(self.push(report(notes="x" * 70_000)).status_code, 413)
        self.assertEqual(self.client.get(reverse("monitoring:ingest")).status_code, 405)

    def test_values_are_sanitised(self):
        self.push(report(cpu=500, load=["nan", -3, "abc"], processes=-5,
                         host={"hostname": "<script>" * 40, "os_family": "plan9"}))
        self.server.refresh_from_db()
        self.assertEqual(self.server.cpu, 100)
        self.assertEqual(self.server.load5, 0)
        self.assertIsNone(self.server.load1)
        self.assertEqual(self.server.processes, 0)
        self.assertEqual(len(self.server.hostname), 120)
        self.assertEqual(self.server.os_family, "other")

    def test_too_frequent_reports_are_ignored(self):
        self.push(report())
        response = self.push(report())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["stored"])
        self.assertEqual(Metric.objects.count(), 1)


class AlertTests(MonitoringBase):
    def test_full_disk_raises_one_ticket_assigned_to_the_owner(self):
        self.push(report(disk=93))
        alert = Alert.objects.get(server=self.server, rule=Alert.Rule.DISK)
        ticket = alert.ticket
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.channel, Channel.MONITORING)
        self.assertEqual(ticket.category.name, "Servers & Cloud")
        self.assertEqual(ticket.assignee, self.tech)
        self.assertEqual(ticket.status, Status.ASSIGNED)
        self.assertEqual(ticket.asset, self.server.asset)
        self.assertEqual(ticket.requester.username, alerts.SYSTEM_USERNAME)
        self.assertFalse(ticket.requester.is_active)
        self.assertIsNotNone(ticket.resolution_due_at)
        self.assertIn("Suggested first steps", ticket.description)

        server = Server.objects.get(pk=self.server.pk)
        server.last_seen_at = None
        services.ingest(server, report(disk=95))
        self.assertEqual(Alert.objects.filter(server=self.server).count(), 1)
        self.assertEqual(Alert.objects.get().peak, 95)

    def test_recovery_notes_the_ticket_but_leaves_it_open(self):
        self.push(report(disk=93))
        server = Server.objects.get(pk=self.server.pk)
        server.last_seen_at = None
        services.ingest(server, report(disk=88))  # inside the hysteresis band: still open
        self.assertTrue(Alert.objects.get().is_open)
        server.last_seen_at = None
        services.ingest(server, report(disk=80))
        alert = Alert.objects.get()
        self.assertFalse(alert.is_open)
        self.assertTrue(alert.ticket.is_open)
        self.assertTrue(alert.ticket.events.filter(kind=TicketEvent.Kind.MONITOR, note__startswith="Recovered").exists())
        self.assertTrue(self.tech.notifications.filter(kind="monitor").exists())

    def test_cpu_must_stay_high_for_the_whole_window(self):
        self.push(report(cpu=99))
        self.assertFalse(Alert.objects.exists())
        self.feed(settings.HELPLY_MONITOR_SUSTAIN_MINUTES + 1, cpu=97)
        alert = Alert.objects.get(rule=Alert.Rule.CPU)
        self.assertEqual(alert.ticket.priority, "P2")  # high criticality x medium urgency

    def test_a_dip_below_the_limit_prevents_a_cpu_alert(self):
        now = timezone.now()
        server = Server.objects.get(pk=self.server.pk)
        for i in range(12, -1, -1):
            server.last_seen_at = None
            services.ingest(server, report(cpu=50 if i == 4 else 97), now=now - timedelta(seconds=30 * i))
        self.assertFalse(Alert.objects.filter(rule=Alert.Rule.CPU).exists())

    def test_offline_detection_and_return(self):
        self.push(report())
        Server.objects.filter(pk=self.server.pk).update(last_seen_at=timezone.now() - timedelta(minutes=10))
        self.assertEqual(alerts.check_offline(), 1)
        self.assertEqual(alerts.check_offline(), 0)  # only once
        alert = Alert.objects.get(rule=Alert.Rule.OFFLINE)
        self.assertEqual(alert.ticket.priority, "P1")  # high criticality, server down
        self.push(report())
        alert.refresh_from_db()
        self.assertFalse(alert.is_open)

    def test_problem_coming_back_reuses_the_open_ticket(self):
        self.push(report(disk=93))
        first = Alert.objects.get().ticket
        server = Server.objects.get(pk=self.server.pk)
        server.last_seen_at = None
        services.ingest(server, report(disk=50))
        server.last_seen_at = None
        services.ingest(server, report(disk=94))
        self.assertEqual(Alert.objects.count(), 2)
        self.assertEqual(Alert.objects.filter(resolved_at__isnull=True).get().ticket, first)
        self.assertTrue(first.events.filter(note__startswith="The problem came back").exists())

    def test_maintenance_records_the_alert_without_a_ticket(self):
        Server.objects.filter(pk=self.server.pk).update(maintenance_until=timezone.now() + timedelta(hours=1))
        self.push(report(disk=93))
        alert = Alert.objects.get()
        self.assertIsNone(alert.ticket)

    def test_without_an_owner_the_ticket_is_auto_assigned(self):
        Server.objects.filter(pk=self.server.pk).update(owner=None)
        group = ensure_categories()[1]["Servers & Cloud"].default_group
        group.members.add(self.tech)
        self.push(report(disk=93))
        self.assertEqual(Alert.objects.get().ticket.assignee, self.tech)


class RollupTests(MonitoringBase):
    def test_hourly_averages_and_pruning(self):
        now = timezone.now().replace(minute=30, second=0, microsecond=0)
        Metric.objects.create(server=self.server, at=now - timedelta(days=5), cpu=1, mem=1, disk=1, net_rx=0, net_tx=0)
        for minute, cpu in ((0, 10), (10, 30), (20, 50)):
            Metric.objects.create(server=self.server, at=now - timedelta(minutes=minute), cpu=cpu, mem=40, disk=50,
                                  net_rx=100, net_tx=200)
        written, deleted_raw, _ = services.rollup(now=now)
        self.assertEqual(deleted_raw, 1)
        row = MetricHourly.objects.get(server=self.server)
        self.assertEqual(row.cpu, 30)
        self.assertEqual(row.cpu_max, 50)
        self.assertEqual(row.samples, 3)
        services.rollup(now=now)  # idempotent
        self.assertEqual(MetricHourly.objects.count(), 1)


class ViewTests(MonitoringBase):
    def test_access_by_role(self):
        url = reverse("monitoring:list")
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(reverse("monitoring:create")).status_code, 403)
        self.assertEqual(self.client.post(reverse("monitoring:token", args=[self.server.pk])).status_code, 403)

    def test_pages_render_with_data(self):
        self.feed(3, cpu=40, disk=93)
        self.client.force_login(self.tech)
        page = self.client.get(reverse("monitoring:list"))
        self.assertContains(page, "web-prod-01")
        self.assertContains(page, "fx-card is-warning")
        for range_key in ("1h", "24h", "7d", "30d"):
            self.assertEqual(self.client.get(reverse("monitoring:detail", args=[self.server.pk]),
                                             {"range": range_key}).status_code, 200)
        fleet = self.client.get(reverse("monitoring:data")).json()
        self.assertEqual(fleet["summary"]["total"], 1)
        self.assertEqual(fleet["servers"][0]["state"], "warning")
        self.assertEqual(fleet["summary"]["alerts"], 1)
        self.assertTrue(any(v is not None for v in fleet["servers"][0]["spark"]))
        detail = self.client.get(reverse("monitoring:detail_data", args=[self.server.pk]), {"range": "1h"}).json()
        self.assertEqual(len(detail["series"]["t"]), len(detail["series"]["cpu"]))
        self.assertGreater(len(detail["series"]["t"]), 3)
        latest = self.client.get(reverse("monitoring:detail_data", args=[self.server.pk]), {"latest": "1"}).json()
        self.assertNotIn("series", latest)
        self.assertEqual(latest["server"]["name"], "web-prod-01")

    def test_one_click_add_then_the_first_report_fills_everything_in(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("monitoring:create")).status_code, 200)  # GET changes nothing
        before = Server.objects.count()
        response = self.client.post(reverse("monitoring:create"))
        self.assertEqual(Server.objects.count(), before + 1)
        server = Server.objects.latest("pk")
        self.assertTrue(server.auto_named)
        self.assertTrue(server.name.startswith("new-server-"))
        self.assertEqual(server.asset.type, Asset.Type.CLOUD)
        self.assertRedirects(response, reverse("monitoring:install", args=[server.pk]), fetch_redirect_response=False)

        first = self.client.get(reverse("monitoring:install", args=[server.pk]))
        token = first.context["token"]
        self.assertEqual(Server.for_token(token), server)
        self.assertContains(first, token)
        self.assertIn("no-cache", first["Cache-Control"])
        second = self.client.get(reverse("monitoring:install", args=[server.pk]))
        self.assertIsNone(second.context["token"])
        self.assertNotContains(second, token)

        data = report(host={"hostname": "instance-20260616-1155", "os_family": "linux", "os_name": "Ubuntu 24.04.4 LTS",
                            "arch": "x86_64", "cpu_model": "AMD EPYC 7551", "cpu_cores": 2, "vendor": "QEMU OracleCloud.com",
                            "provider": "oracle", "region": "ca-toronto-1", "instance_type": "VM.Standard.E2.1.Micro"})
        self.push(data, token=token, REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="40.233.75.87")
        server.refresh_from_db()
        self.assertEqual(server.name, "instance-20260616-1155")
        self.assertFalse(server.auto_named)
        self.assertEqual(server.provider, Server.Provider.ORACLE)
        self.assertEqual(server.region, "ca-toronto-1")
        self.assertEqual(server.public_ip, "40.233.75.87")
        self.assertEqual(server.instance_type, "VM.Standard.E2.1.Micro")
        self.assertIn("2 vCPU", server.plan)
        self.assertEqual(server.asset.name, "instance-20260616-1155")
        info = self.client.get(reverse("monitoring:detail_data", args=[server.pk]), {"latest": "1"}).json()["server"]["info"]
        self.assertEqual(info["provider"], "Oracle Cloud (OCI)")

    def test_detection_never_overwrites_what_a_person_entered(self):
        Server.objects.filter(pk=self.server.pk).update(region="Montreal", plan="Custom", public_ip="203.0.113.5")
        self.push(report(host={"hostname": "box", "provider": "oracle", "region": "ca-toronto-1"}),
                  REMOTE_ADDR="198.51.100.7")
        self.server.refresh_from_db()
        self.assertEqual(self.server.name, "web-prod-01")  # not auto-named: keeps its name
        self.assertEqual(self.server.provider, "aws")
        self.assertEqual((self.server.region, self.server.plan, self.server.public_ip), ("Montreal", "Custom", "203.0.113.5"))

    def test_hostname_clash_gets_a_suffix(self):
        Server.objects.create(name="box")
        pending = Server.objects.create(name="new-server-ab12", auto_named=True)
        token = pending.issue_token()
        pending.save()
        self.push(report(host={"hostname": "box"}), token=token)
        pending.refresh_from_db()
        self.assertEqual(pending.name, "box-2")

    def test_discarding_and_abandoned_placeholders(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("monitoring:create"))
        pending = Server.objects.latest("pk")
        asset_pk = pending.asset_id
        self.client.post(reverse("monitoring:delete", args=[pending.pk]))
        self.assertFalse(Asset.objects.filter(pk=asset_pk).exists())  # never connected: nothing kept

        old = Server.objects.create(name="new-server-old1", auto_named=True)
        services.sync_asset(old)
        Server.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2))
        self.assertEqual(services.discard_abandoned(), 1)
        self.assertTrue(Server.objects.filter(pk=self.server.pk).exists())

    def test_maintenance_and_delete(self):
        self.push(report())  # connected at least once
        self.client.force_login(self.admin)
        self.client.post(reverse("monitoring:maintenance", args=[self.server.pk]), {"hours": "4"})
        self.server.refresh_from_db()
        self.assertTrue(self.server.in_maintenance)
        asset_pk = self.server.asset_id
        self.client.post(reverse("monitoring:delete", args=[self.server.pk]))
        self.assertFalse(Server.objects.filter(pk=self.server.pk).exists())
        self.assertEqual(Asset.objects.get(pk=asset_pk).status, Asset.Status.RETIRED)

    def test_agent_files_are_public_and_use_unix_line_endings(self):
        for name in ("helply_agent.py", "install.sh", "install.ps1"):
            response = self.client.get(reverse("monitoring:agent_file", args=[name]))
            self.assertEqual(response.status_code, 200)
            if not name.endswith(".ps1"):
                self.assertNotIn(b"\r\n", response.content)
        self.assertEqual(self.client.get("/monitoring/agent/manage.py").status_code, 404)
        self.assertEqual(self.client.get("/monitoring/agent/..%2Fmanage.py").status_code, 404)
        self.assertEqual(self.client.get(reverse("monitoring:agent_file", args=[".env"])).status_code, 404)


class CountryTests(MonitoringBase):
    """The country (and its flag) comes from the public IP, unless a person picked one."""

    def test_lookup_knows_public_addresses_only(self):
        from . import geo
        self.assertEqual(geo.country_for_ip("8.8.8.8"), "US")
        self.assertEqual(geo.country_for_ip("2a09:bac1:14c0:d8::2ac:69"), "CA")  # IPv6 works too
        for unusable in ("192.168.1.5", "10.0.0.1", "127.0.0.1", "", "not-an-ip", None):
            self.assertEqual(geo.country_for_ip(unusable), "")

    def test_first_report_sets_country_from_the_ip(self):
        server = Server.objects.get(pk=self.server.pk)
        services.ingest(server, report(), remote_ip="8.8.8.8")
        server.refresh_from_db()
        self.assertEqual((server.country_code, server.country_name), ("US", "United States"))
        self.assertTrue(server.country_auto)
        self.assertTrue(server.flag_url.endswith("img/flags/us.svg"))
        self.assertIn("United States", server.asset.location)

    def test_private_address_leaves_country_unknown_and_shows_no_flag(self):
        server = Server.objects.get(pk=self.server.pk)
        services.ingest(server, report(), remote_ip="192.168.1.20")
        server.refresh_from_db()
        self.assertEqual((server.country_code, server.flag_url), ("", ""))

    def test_a_manual_choice_is_never_overwritten(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("monitoring:edit", args=[self.server.pk]), {
            "name": "web-prod-01", "provider": "aws", "country_code": "DE", "criticality": 1, "alerts_enabled": "on"})
        self.assertEqual(response.status_code, 302)
        server = Server.objects.get(pk=self.server.pk)
        self.assertEqual((server.country_code, server.country_auto), ("DE", False))
        services.ingest(server, report(), remote_ip="8.8.8.8")
        server.refresh_from_db()
        self.assertEqual(server.country_code, "DE")
        # Back to "Detect automatically": the next report fills it in again.
        self.client.post(reverse("monitoring:edit", args=[self.server.pk]), {
            "name": "web-prod-01", "provider": "aws", "country_code": "", "criticality": 1, "alerts_enabled": "on"})
        server.refresh_from_db()
        self.assertTrue(server.country_auto)
        server.last_seen_at = None  # reports closer together than the minimum interval are ignored
        services.ingest(server, report(), remote_ip="8.8.8.8")
        server.refresh_from_db()
        self.assertEqual(server.country_code, "US")

    def test_pages_show_flag_country_and_search_text(self):
        server = Server.objects.get(pk=self.server.pk)
        services.ingest(server, report(), remote_ip="2a09:bac1:14c0:d8::2ac:69")
        self.client.force_login(self.tech)
        page = self.client.get(reverse("monitoring:list"))
        self.assertContains(page, "img/flags/ca.svg")
        self.assertContains(page, "Canada")
        self.assertContains(self.client.get(reverse("monitoring:detail", args=[server.pk])), "Canada")
        info = self.client.get(reverse("monitoring:data")).json()["servers"][0]["info"]
        self.assertEqual((info["country"], info["country_code"]), ("Canada", "CA"))
        self.assertTrue(info["flag"].endswith("img/flags/ca.svg"))

    def test_every_country_has_a_flag_file(self):
        from pathlib import Path
        from .countries import COUNTRIES
        flags = Path(settings.BASE_DIR) / "static" / "img" / "flags"
        self.assertEqual([c for c in COUNTRIES if not (flags / f"{c.lower()}.svg").exists()], [])

class AgentTests(TestCase):
    def test_agent_builds_a_report_the_server_accepts(self):
        if importlib.util.find_spec("psutil") is None:
            self.skipTest("psutil is not installed here")
        spec = importlib.util.spec_from_file_location("helply_agent", settings.BASE_DIR / "agent" / "helply_agent.py")
        agent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent)
        data = agent.Collector().report()
        for key in ("cpu", "mem", "disk", "net", "processes", "uptime", "host"):
            self.assertIn(key, data)
        server = Server.objects.create(name="self")
        self.assertTrue(services.ingest(server, json.loads(json.dumps(data))))


class EmptyStateTests(MonitoringBase):
    def test_no_servers_shows_onboarding_not_sample_data(self):
        Server.objects.all().delete()
        self.client.force_login(self.admin)
        page = self.client.get(reverse("monitoring:list"))
        self.assertContains(page, "Add your first server")
        self.assertEqual(self.client.get(reverse("monitoring:data")).json()["summary"]["total"], 0)


@override_settings(HELPLY_ENVIRONMENT="demo")
class DemoTests(TestCase):
    def test_demo_seed_never_invents_servers_and_removes_old_samples(self):
        from io import StringIO

        from django.core.management import call_command

        sample = Server.objects.create(name="erp-01")
        services.sync_asset(sample)
        real = Server.objects.create(name="web-prod-01")
        services.sync_asset(real)
        real.issue_token()
        real.save()  # connected for real: must survive
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(list(Server.objects.values_list("name", flat=True)), ["web-prod-01"])
        self.assertFalse(Asset.objects.filter(pk=sample.asset_id).exists())
