"""The dashboard's company overview: unassigned tickets, people, cloud servers and renewals."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Department, SupportGroup, User
from apps.assets.models import Asset
from apps.monitoring.models import Alert, Server
from apps.tickets import services
from apps.tickets.models import Category, Ticket

from . import overview

GB = 1024**3


class OverviewBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.it = Department.objects.create(name="IT")
        cls.sales = Department.objects.create(name="Sales")
        cls.admin = User.objects.create_user("alice", password="x", role="administrator", department=cls.it,
                                             email="alice@acme-corp.com")
        cls.tech = User.objects.create_user("tom", password="x", role="technician", department=cls.it,
                                            email="tom@acme-corp.com")
        cls.emp = User.objects.create_user("emma", password="x", department=cls.sales, email="emma@acme-corp.com")
        cls.cat = Category.objects.create(name="Hardware")

    def ticket(self, title="Printer jam", **kw):
        data = dict(requester=self.emp, title=title, description="x", impact=2, urgency=2, category=self.cat)
        data.update(kw)
        return services.create_ticket(**data)

    def server(self, name, minutes_ago=0, cpu=20.0, **kw):
        seen = None if minutes_ago is None else timezone.now() - timedelta(minutes=minutes_ago)
        data = dict(name=name, provider="aws", last_seen_at=seen, cpu=None if seen is None else cpu,
                    mem_used=4 * GB, mem_total=8 * GB, disk_used=10 * GB, disk_total=100 * GB)
        data.update(kw)
        return Server.objects.create(**data)


class UnassignedTicketTests(OverviewBase):
    def test_counts_only_open_tickets_nobody_owns_most_urgent_first(self):
        low = self.ticket("Low one", impact=3, urgency=3)
        urgent = self.ticket("Urgent one", impact=1, urgency=1)
        taken = self.ticket("Taken")
        Ticket.objects.filter(pk=taken.pk).update(assignee=self.tech)
        closed = self.ticket("Closed")
        Ticket.objects.filter(pk=closed.pk).update(status="closed")
        Ticket.objects.exclude(pk__in=[low.pk, urgent.pk]).update(assignee=self.tech)  # whatever auto-assign did
        result = overview.unassigned_tickets(self.admin)
        self.assertEqual(result["count"], 2)
        self.assertEqual([t.title for t in result["rows"]], ["Urgent one", "Low one"])
        self.assertEqual(result["more"], 0)

    def test_limit_and_more(self):
        tickets = [self.ticket(f"T{i}") for i in range(7)]
        Ticket.objects.filter(pk__in=[t.pk for t in tickets]).update(assignee=None)
        result = overview.unassigned_tickets(self.admin, limit=5)
        self.assertEqual((result["count"], len(result["rows"]), result["more"]), (7, 5, 2))

    def test_kpi_and_link_on_the_dashboards(self):
        group = SupportGroup.objects.create(name="Desk")
        group.members.add(self.tech)
        t = self.ticket()
        Ticket.objects.filter(pk=t.pk).update(assignee=None, support_group=group)
        for user in (self.admin, self.tech):
            self.client.force_login(user)
            page = self.client.get(reverse("core:dashboard"))
            self.assertEqual(page.context["kpi"]["unassigned"], 1)
            self.assertContains(page, "?status=open&assignee=none")

    def test_ticket_list_can_show_unassigned_only_for_agents(self):
        mine = self.ticket("Mine")
        Ticket.objects.filter(pk=mine.pk).update(assignee=self.tech)
        free = self.ticket("Free")
        desk = SupportGroup.objects.create(name="Desk")
        desk.members.add(self.tech)  # a technician sees the unassigned tickets of their own support groups
        Ticket.objects.filter(pk=free.pk).update(assignee=None, support_group=desk)
        titles = lambda user, **q: sorted(t.title for t, _ in self.client.get(reverse("tickets:list"), q).context["rows"])
        self.client.force_login(self.tech)
        self.assertEqual(titles(self.tech, status="open", assignee="none"), ["Free"])
        self.assertEqual(titles(self.tech, status="open"), ["Free", "Mine"])
        self.assertContains(self.client.get(reverse("tickets:list"), {"status": "open", "assignee": "none"}), "no technician has picked up")
        self.client.force_login(self.emp)  # employees only ever see their own tickets and cannot use the filter
        self.assertEqual(titles(self.emp, status="open", assignee="none"), ["Free", "Mine"])


    def test_a_technician_only_counts_tickets_of_their_own_support_groups(self):
        mine, other = SupportGroup.objects.create(name="Desk"), SupportGroup.objects.create(name="Network")
        mine.members.add(self.tech)
        visible, hidden = self.ticket("In my group"), self.ticket("In another group")
        Ticket.objects.filter(pk=visible.pk).update(assignee=None, support_group=mine)
        Ticket.objects.filter(pk=hidden.pk).update(assignee=None, support_group=other)
        self.assertEqual(overview.unassigned_tickets(self.tech)["count"], 1)
        self.assertEqual([t.title for t in overview.unassigned_tickets(self.tech)["rows"]], ["In my group"])
        self.assertEqual(overview.unassigned_tickets(self.admin)["count"], 2)  # administrators see everything
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse("core:dashboard")).context["kpi"]["unassigned"], 1)


class PeopleOverviewTests(OverviewBase):
    def test_counts_by_role_and_department_include_it(self):
        User.objects.create_user("gone", password="x", department=self.sales, is_active=False)
        data = overview.people_overview()
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["roles"], {"employee": 1, "technician": 1, "administrator": 1})
        self.assertEqual({d["name"]: d["n"] for d in data["departments"]}, {"IT": 2, "Sales": 1})
        self.assertEqual(data["turned_off"], 1)
        self.assertEqual(data["departments"][0]["name"], "IT")  # biggest first

    def test_every_department_is_listed_however_many_there_are(self):
        for i in range(10):
            User.objects.create_user(f"p{i}", password="x", department=Department.objects.create(name=f"Dept {i}"))
        data = overview.people_overview()
        self.assertEqual((len(data["departments"]), data["dept_total"]), (12, 12))
        self.assertNotIn("dept_more", data)
        self.client.force_login(self.admin)
        page = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertNotIn("more department", page)
        for i in range(10):
            self.assertIn(f"Dept {i}", page)

    def test_only_administrators_see_the_people_card(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("core:dashboard")), "active people in")
        self.client.force_login(self.tech)
        self.assertNotContains(self.client.get(reverse("core:dashboard")), "active people in")


class ServerHealthTests(OverviewBase):
    def test_no_servers_is_an_honest_empty_state(self):
        data = overview.server_health()
        self.assertEqual((data["total"], data["rows"], data["avg_cpu"]), (0, [], None))
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("core:dashboard")), "No servers connected yet")

    def test_counts_states_alerts_cost_and_sorts_the_worst_first(self):
        healthy = self.server("web-ok", cpu=10.0, monthly_cost=Decimal("20.00"))
        sick = self.server("web-sick", cpu=50.0, monthly_cost=Decimal("30.50"))
        Alert.objects.create(server=sick, rule="disk", started_at=timezone.now(), message="Disk almost full")
        self.server("web-off", minutes_ago=30)
        self.server("web-new", minutes_ago=None)
        data = overview.server_health()
        self.assertEqual(data["total"], 4)
        self.assertEqual(data["counts"], {"healthy": 1, "warning": 1, "offline": 1, "pending": 1})
        self.assertEqual(data["alerts"], 1)
        self.assertEqual(data["avg_cpu"], 30.0)  # only the two online servers
        self.assertEqual(data["monthly"], 50.5)
        self.assertEqual([r["server"].name for r in data["rows"]], ["web-sick", "web-off", "web-new", "web-ok"])
        self.assertEqual(sum(pct for *_, pct in data["segments"]), 100.0)
        self.assertEqual(healthy.status, "online")

    def test_dashboard_lists_servers_with_country_flag(self):
        self.server("web-ca", country_code="CA")
        for user in (self.admin, self.tech):
            self.client.force_login(user)
            page = self.client.get(reverse("core:dashboard"))
            self.assertContains(page, "web-ca")
            self.assertContains(page, "img/flags/ca.svg")
            self.assertContains(page, "Canada")

    def test_row_limit(self):
        for i in range(8):
            self.server(f"s{i}")
        data = overview.server_health(limit=5)
        self.assertEqual((len(data["rows"]), data["more"]), (5, 3))


class RenewalOverviewTests(OverviewBase):
    def asset(self, tag, days, **kw):
        data = dict(asset_tag=tag, name=f"Thing {tag}", type="license", status="in_use",
                    warranty_expiry=timezone.localdate() + timedelta(days=days))
        data.update(kw)
        return Asset.objects.create(**data)

    def test_lists_subscriptions_renewing_within_30_days_or_just_overdue(self):
        self.asset("S-1", 10)
        self.asset("S-2", -3)
        self.asset("S-3", 0)
        self.asset("S-4", 60)                      # too far away
        self.asset("S-5", -40)                     # long overdue: stale, not news
        self.asset("S-6", 5, status="retired")     # retired
        self.asset("S-7", 5, asset_tag="HW-1", type="laptop")  # hardware warranty is not a renewal
        self.asset("C-1", 20, type="cloud")
        data = overview.renewals_and_assets()
        self.assertEqual([r["asset"].asset_tag for r in data["due"]], ["S-2", "S-3", "S-1", "C-1"])
        self.assertEqual([r["text"] for r in data["due"]], ["3 days overdue", "today", "in 10 days", "in 20 days"])
        self.assertEqual((data["due_count"], data["overdue_count"]), (4, 1))

    def test_warranty_and_repair_numbers_ignore_subscriptions_and_retired(self):
        self.asset("L-1", -100, type="laptop")
        self.asset("L-2", -1, type="monitor", status="in_repair")
        self.asset("L-3", -50, type="laptop", status="retired")
        self.asset("L-4", 100, type="laptop")
        self.asset("S-1", -100)  # a lapsed licence is a renewal matter, not a warranty
        data = overview.renewals_and_assets()
        self.assertEqual((data["warranty_expired"], data["in_repair"], data["assets_total"]), (2, 1, 4 + 1 - 1))

    def test_dashboard_shows_the_card(self):
        self.asset("S-1", 4, name="Office 365")
        self.client.force_login(self.admin)
        page = self.client.get(reverse("core:dashboard"))
        self.assertContains(page, "Renewals &amp; assets")
        self.assertContains(page, "Office 365")
        self.assertContains(page, "in 4 days")


class EmployeeDashboardTests(OverviewBase):
    def test_employees_do_not_get_company_overview(self):
        self.client.force_login(self.emp)
        page = self.client.get(reverse("core:dashboard"))
        self.assertEqual(page.status_code, 200)
        for text in ("Company overview", "Cloud servers", "Unassigned", "active people in"):
            self.assertNotContains(page, text)
