from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.sla.forms import format_duration, parse_duration
from apps.sla.models import SLAPolicy
from apps.tickets.choices import Priority

from .models import Department, SupportGroup, User


class PeopleBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dept = Department.objects.create(name="IT")
        cls.team = SupportGroup.objects.create(name="Service Desk")
        cls.admin = User.objects.create_user("alice", password="x", first_name="Alice", email="alice@example.com",
                                             role=User.Role.ADMINISTRATOR)
        cls.tech = User.objects.create_user("tina", password="x", first_name="Tina", email="tina@example.com",
                                            role=User.Role.TECHNICIAN)
        cls.emp = User.objects.create_user("emma", password="x", first_name="Emma", email="emma@example.com")

    def payload(self, **over):
        data = {"first_name": "Nora", "last_name": "Diaz", "username": "nora", "email": "nora@example.com",
                "role": "technician", "department": self.dept.pk, "phone": "", "is_active": "on",
                "support_groups": [self.team.pk]}
        data.update(over)
        return data


class PeopleAccessTests(PeopleBase):
    def test_only_administrators_get_in(self):
        urls = [reverse("people:list"), reverse("people:create"), reverse("people:edit", args=[self.emp.pk]),
                reverse("sla:settings")]
        for user, expected in ((self.emp, 403), (self.tech, 403), (self.admin, 200)):
            self.client.force_login(user)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, expected, (user.username, url))
        self.client.logout()
        self.assertEqual(self.client.get(urls[0]).status_code, 302)  # sent to sign in

    def test_actions_need_post_and_admin(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.post(reverse("people:toggle", args=[self.emp.pk])).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("people:toggle", args=[self.emp.pk])).status_code, 405)

    def test_sidebar_links_are_for_administrators_only(self):
        self.client.force_login(self.tech)
        self.assertNotContains(self.client.get(reverse("core:dashboard")), reverse("people:list"))
        self.client.force_login(self.admin)
        page = self.client.get(reverse("core:dashboard"))
        self.assertContains(page, reverse("people:list"))
        self.assertContains(page, reverse("sla:settings"))


class PeopleListTests(PeopleBase):
    def test_search_and_filters(self):
        User.objects.create_user("gone", password="x", first_name="Gary", is_active=False)
        self.client.force_login(self.admin)
        names = lambda **q: sorted(p.username for p in self.client.get(reverse("people:list"), q).context["people"])
        self.assertEqual(names(), ["alice", "emma", "tina"])  # active people by default
        self.assertEqual(names(status="inactive"), ["gone"])
        self.assertEqual(names(status="all"), names())  # there is no "everyone" view: unknown values mean Active
        self.assertEqual(names(role="technician"), ["tina"])
        self.assertEqual(names(q="emma@example"), ["emma"])
        self.assertEqual(names(q="nobody"), [])


class PeopleCreateEditTests(PeopleBase):
    def test_create_gives_a_one_time_link_and_no_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("people:create"), self.payload(email="nora@acme-corp.com"))
        self.assertEqual(response.status_code, 200)
        nora = User.objects.get(username="nora")
        self.assertFalse(nora.has_usable_password())
        self.assertEqual(list(nora.support_groups.all()), [self.team])
        link = response.context["link"]
        self.assertIn("/accounts/reset/", link)
        self.assertContains(response, link)
        self.assertIn("no-cache", response["Cache-Control"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(link, mail.outbox[0].body)
        # The link really lets her choose a password, once.
        path = link.split("/accounts", 1)[1]
        page = self.client.get("/accounts" + path, follow=True)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Choose a password")

    def test_reserved_placeholder_address_gets_no_email_but_still_a_link(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("people:create"), self.payload())  # nora@example.com
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(response.context["reserved_address"])
        self.assertContains(response, "placeholder address that cannot receive email")
        self.assertContains(response, response.context["link"])  # the administrator can still hand it over
    def test_employee_gets_no_support_teams(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("people:create"), self.payload(username="eve", email="eve@example.com", role="employee"))
        self.assertEqual(User.objects.get(username="eve").support_groups.count(), 0)

    def test_duplicate_email_and_username_are_refused(self):
        self.client.force_login(self.admin)
        page = self.client.post(reverse("people:create"), self.payload(email="EMMA@example.com"))
        self.assertContains(page, "already uses this email")
        page = self.client.post(reverse("people:create"), self.payload(username="emma"))
        self.assertEqual(User.objects.filter(username="emma").count(), 1)
        self.assertEqual(page.status_code, 200)

    def test_edit_changes_role_and_teams(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("people:edit", args=[self.emp.pk]), self.payload(
            first_name="Emma", username="emma", email="emma@example.com", role="technician"))
        self.assertRedirects(response, reverse("people:list"))
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.role, "technician")
        self.assertEqual(list(self.emp.support_groups.all()), [self.team])

    def test_reset_link_is_made_for_active_people_only(self):
        self.client.force_login(self.admin)
        page = self.client.post(reverse("people:reset", args=[self.emp.pk]))
        self.assertContains(page, "/accounts/reset/")
        self.emp.is_active = False
        self.emp.save()
        self.assertRedirects(self.client.post(reverse("people:reset", args=[self.emp.pk])),
                             reverse("people:edit", args=[self.emp.pk]))


class AdministratorGuardTests(PeopleBase):
    def test_cannot_turn_off_or_demote_yourself(self):
        other = User.objects.create_user("bob", password="x", first_name="Bob", email="bob@example.com",
                                         role=User.Role.ADMINISTRATOR)
        self.client.force_login(self.admin)
        self.client.post(reverse("people:toggle", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        page = self.client.post(reverse("people:edit", args=[self.admin.pk]), self.payload(
            username="alice", email="alice@example.com", first_name="Alice", role="technician"))
        self.assertContains(page, "cannot remove your own administrator access")
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "administrator")
        self.assertTrue(other.is_active)

    def test_last_active_administrator_cannot_be_removed(self):
        self.client.force_login(self.admin)
        other = User.objects.create_user("bob", password="x", first_name="Bob", email="bob@example.com",
                                         role=User.Role.ADMINISTRATOR)
        self.client.post(reverse("people:toggle", args=[other.pk]))  # fine: Alice is still there
        other.refresh_from_db()
        self.assertFalse(other.is_active)
        other.is_active = True
        other.save()
        self.client.force_login(other)
        self.client.post(reverse("people:toggle", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)  # Bob is still active, so this is allowed
        # Now Bob is the only one: he cannot be demoted by a stale second administrator either.
        ghost = User.objects.create_user("carl", password="x", first_name="Carl", email="carl@example.com",
                                         role=User.Role.ADMINISTRATOR, is_active=False)
        self.assertFalse(User.objects.filter(role="administrator", is_active=True).exclude(pk=other.pk).exists())
        from .forms import last_admin_guard
        self.assertFalse(last_admin_guard(other))
        self.assertTrue(last_admin_guard(ghost))

    def test_toggle_turns_a_person_off_and_on(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("people:toggle", args=[self.emp.pk]))
        self.emp.refresh_from_db()
        self.assertFalse(self.emp.is_active)
        self.assertFalse(self.client.login(username="emma", password="x"))
        self.client.force_login(self.admin)
        self.client.post(reverse("people:toggle", args=[self.emp.pk]))
        self.emp.refresh_from_db()
        self.assertTrue(self.emp.is_active)


class RolePickerTests(PeopleBase):
    """Choosing a role on the form really changes what the person can do, straight away."""

    def test_form_marks_the_current_role_and_names_each_role_once(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse("people:edit", args=[self.tech.pk])).content.decode()
        self.assertEqual(page.count('type="radio"'), 3)
        self.assertRegex(page, r'value="technician"[^>]*checked')
        self.assertNotRegex(page, r'value="employee"[^>]*checked')
        self.assertEqual(page.count("<b>Technician</b>"), 1)
        # Each card must point at its own input, otherwise every click selects the first role.
        import re
        ids = re.findall(r'<input type="radio"[^>]*id="([^"]+)"', page)
        self.assertEqual(sorted(ids), ["role-administrator", "role-employee", "role-technician"])
        for role_id in ids:
            self.assertIn(f'for="{role_id}"', page)
        self.assertNotIn("None", re.findall(r'(?:for|id)="([^"]*)"', page))

    def test_saving_a_new_role_changes_access_immediately(self):
        self.client.force_login(self.admin)
        monitoring = reverse("monitoring:list")
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(monitoring).status_code, 200)  # technicians see cloud servers
        self.client.force_login(self.admin)
        response = self.client.post(reverse("people:edit", args=[self.tech.pk]), {
            "first_name": "Tina", "last_name": "", "username": "tina", "email": "tina@example.com",
            "role": "employee", "department": "", "phone": "", "is_active": "on"})
        self.assertRedirects(response, reverse("people:list"))
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.role, User.Role.EMPLOYEE)
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(monitoring).status_code, 403)  # no longer allowed in
        # And promoting works the other way round.
        self.client.force_login(self.admin)
        self.client.post(reverse("people:edit", args=[self.emp.pk]), {
            "first_name": "Emma", "last_name": "", "username": "emma", "email": "emma@example.com",
            "role": "administrator", "department": "", "phone": "", "is_active": "on"})
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("people:list")).status_code, 200)

class DepartmentDropdownTests(PeopleBase):
    """The Department dropdown lists every department with its head count (any role), and picking one filters the list."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sales = Department.objects.create(name="Sales")
        User.objects.filter(username__in=["alice", "tina"]).update(department=cls.dept)  # IT: an administrator and a technician
        for i, dept in enumerate([cls.sales, cls.sales, cls.dept, None]):
            User.objects.create_user(f"extra{i}", password="x", first_name=f"Extra{i}", email=f"x{i}@example.com", department=dept)
        User.objects.create_user("off", password="x", first_name="Off", email="off@example.com", department=cls.sales, is_active=False)

    def test_counts_per_department_count_everyone_not_just_employees(self):
        self.client.force_login(self.admin)
        menu = self.client.get(reverse("people:list")).context["dept_menu"]
        counts = {d["name"]: d["n"] for d in menu["depts"]}
        # IT holds an administrator, a technician and one employee: it must be listed, and counted in full.
        self.assertEqual(counts, {"IT": 3, "Sales": 2, "No department": 2})
        self.assertEqual(menu["total"], 7)  # the turned-off person is not counted
        self.assertEqual(menu["depts"][-1]["name"], "No department")  # always last
        inactive = self.client.get(reverse("people:list"), {"status": "inactive"}).context["dept_menu"]
        self.assertEqual({d["name"]: d["n"] for d in inactive["depts"]}, {"Sales": 1})  # counts follow the status switch

    def test_a_department_with_no_employees_is_still_listed(self):
        self.client.force_login(self.admin)
        User.objects.filter(username="extra2").update(department=self.sales)  # IT now has no employee at all
        menu = self.client.get(reverse("people:list")).context["dept_menu"]
        self.assertEqual({d["name"]: d["n"] for d in menu["depts"]}["IT"], 2)  # administrator + technician

    def test_picking_a_department_filters_the_list(self):
        self.client.force_login(self.admin)
        names = lambda **q: sorted(p.username for p in self.client.get(reverse("people:list"), q).context["people"])
        self.assertEqual(names(dept=self.dept.pk), ["alice", "extra2", "tina"])  # every role in IT
        self.assertEqual(names(dept=self.sales.pk), ["extra0", "extra1"])
        self.assertEqual(names(dept="none"), ["emma", "extra3"])
        page = self.client.get(reverse("people:list"), {"dept": self.sales.pk})
        self.assertEqual(page.context["dept_name"], "Sales")
        self.assertContains(page, "· Sales")
        self.assertEqual(len(names(dept="garbage")), 7)  # an unknown value filters nothing

    def test_dropdown_markup(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse("people:list")).content.decode()
        self.assertEqual(page.count("data-pop-btn"), 1)  # one Department dropdown, no role buttons
        self.assertIn("By department", page)
        self.assertNotIn("Technician", page.split('aria-label="Filter by department"')[1].split("</form>")[0])
        self.assertNotIn("Everyone", page)
        self.assertIn(f"dept={self.dept.pk}", page)
        self.assertIn(">IT<", page.replace("\n", "").replace("  ", ""))

    def test_the_status_switch_only_has_active_and_turned_off(self):
        self.client.force_login(self.admin)
        names = lambda **q: sorted(p.username for p in self.client.get(reverse("people:list"), q).context["people"])
        self.assertEqual(names(status="inactive"), ["off"])
        everyone = names()
        self.assertEqual(names(status="anything-else"), everyone)  # unknown values fall back to Active
        self.assertEqual(self.client.get(reverse("people:list"), {"status": "all"}).context["status"], "active")

class SLASettingsTests(PeopleBase):
    def test_duration_parsing_round_trips(self):
        self.assertEqual([parse_duration(t) for t in ("30m", "4h", "1d 2h", "90", "1h30m", "2 days")],
                         [30, 240, 1560, 90, 90, 2880])
        self.assertEqual([format_duration(m) for m in (30, 90, 1440, 1560, 0)], ["30m", "1h 30m", "1d", "1d 2h", "0m"])
        for bad in ("", "soon", "5x", "h"):
            with self.assertRaises(ValueError):
                parse_duration(bad)

    def post_data(self, **over):
        data = {}
        for priority, hours in (("P1", (1, 4)), ("P2", (4, 8)), ("P3", (8, 24)), ("P4", (24, 72))):
            data.update({f"{priority}-name": f"{priority} policy", f"{priority}-response_minutes": f"{hours[0]}h",
                         f"{priority}-resolution_minutes": f"{hours[1]}h", f"{priority}-is_active": "on"})
        data.update(over)
        return data

    def test_page_shows_existing_policies_and_creates_missing_ones(self):
        SLAPolicy.objects.create(priority="P1", name="Critical", response_minutes=15, resolution_minutes=240)
        self.client.force_login(self.admin)
        page = self.client.get(reverse("sla:settings"))
        self.assertContains(page, 'value="15m"')
        self.assertContains(page, 'value="4h"')
        self.assertEqual(len(page.context["forms"]), len(Priority.choices))
        self.assertRedirects(self.client.post(reverse("sla:settings"), self.post_data()), reverse("sla:settings"))
        self.assertEqual(SLAPolicy.objects.count(), 4)
        p1 = SLAPolicy.objects.get(priority="P1")
        self.assertEqual((p1.name, p1.response_minutes, p1.resolution_minutes, p1.is_active), ("P1 policy", 60, 240, True))

    def test_validation_keeps_everything_unsaved(self):
        self.client.force_login(self.admin)
        page = self.client.post(reverse("sla:settings"), self.post_data(**{"P2-resolution_minutes": "1h", "P3-response_minutes": "soon"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "cannot be shorter than the first response")
        self.assertContains(page, "Use a time like")
        self.assertEqual(SLAPolicy.objects.count(), 0)  # all or nothing

    def test_switching_a_policy_off_stops_new_due_dates(self):
        from apps.sla import services
        from apps.tickets.models import Ticket
        self.client.force_login(self.admin)
        self.client.post(reverse("sla:settings"), self.post_data(**{"P3-is_active": ""}))
        self.assertFalse(SLAPolicy.objects.get(priority="P3").is_active)
        ticket = Ticket(priority="P3")
        services.apply_policy(ticket)
        self.assertIsNone(ticket.resolution_due_at)


class OrganizationTests(PeopleBase):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_page_lists_departments_and_teams_for_administrators_only(self):
        self.team.members.add(self.tech)
        page = self.client.get(reverse("people:organization"))
        self.assertContains(page, "Service Desk")
        self.assertContains(page, "Tina")
        for user in (self.tech, self.emp):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("people:organization")).status_code, 403)
            self.assertEqual(self.client.post(reverse("people:department_create"), {"new-name": "X"}).status_code, 403)

    def test_add_and_rename_department_refuse_duplicates(self):
        self.client.post(reverse("people:department_create"), {"new-name": "  Finance  "})
        finance = Department.objects.get(name="Finance")
        self.client.post(reverse("people:department_create"), {"new-name": "finance"})
        self.assertEqual(Department.objects.filter(name__iexact="finance").count(), 1)
        self.client.post(reverse("people:department_rename", args=[finance.pk]), {f"d{finance.pk}-name": "Accounting"})
        finance.refresh_from_db()
        self.assertEqual(finance.name, "Accounting")
        self.client.post(reverse("people:department_rename", args=[finance.pk]), {f"d{finance.pk}-name": "it"})
        finance.refresh_from_db()
        self.assertEqual(finance.name, "Accounting")

    def test_only_an_empty_department_can_be_removed(self):
        self.emp.department = self.dept
        self.emp.save()
        self.client.post(reverse("people:department_delete", args=[self.dept.pk]))
        self.assertTrue(Department.objects.filter(pk=self.dept.pk).exists())
        self.emp.department = None
        self.emp.save()
        self.client.post(reverse("people:department_delete", args=[self.dept.pk]))
        self.assertFalse(Department.objects.filter(pk=self.dept.pk).exists())

    def test_create_and_edit_team_with_members(self):
        response = self.client.post(reverse("people:team_create"), {
            "name": "Network", "description": "Wi-Fi and VPN", "members": [self.tech.pk]})
        self.assertRedirects(response, reverse("people:organization"))
        team = SupportGroup.objects.get(name="Network")
        self.assertEqual(list(team.members.all()), [self.tech])
        self.client.post(reverse("people:team_edit", args=[team.pk]), {"name": "Network", "members": [self.admin.pk]})
        self.assertEqual(list(team.members.all()), [self.admin])
        page = self.client.post(reverse("people:team_edit", args=[team.pk]), {"name": "service desk"})
        self.assertContains(page, "already exists")

    def test_employees_cannot_be_team_members(self):
        page = self.client.post(reverse("people:team_create"), {"name": "Ops", "members": [self.emp.pk]})
        self.assertEqual(page.status_code, 200)
        self.assertFalse(SupportGroup.objects.filter(name="Ops").exists())

    def test_team_that_owns_a_category_cannot_be_removed(self):
        from apps.tickets.models import Category

        Category.objects.create(name="Email", default_group=self.team)
        self.client.post(reverse("people:team_delete", args=[self.team.pk]))
        self.assertTrue(SupportGroup.objects.filter(pk=self.team.pk).exists())
        Category.objects.update(default_group=None)
        self.client.post(reverse("people:team_delete", args=[self.team.pk]))
        self.assertFalse(SupportGroup.objects.filter(pk=self.team.pk).exists())
