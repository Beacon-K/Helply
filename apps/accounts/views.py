"""People management for administrators: the pages that replace most trips to the Django admin."""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.tickets.choices import OPEN_STATUSES

from .decorators import role_required
from .forms import UserForm, last_admin_guard
from .models import User

log = logging.getLogger(__name__)
admin_only = role_required(User.Role.ADMINISTRATOR)


def _with_counts(queryset):
    """Open tickets each person is working on (agents) or waiting for (everyone)."""
    return queryset.annotate(
        open_assigned=Count("assigned_tickets", filter=Q(assigned_tickets__status__in=OPEN_STATUSES), distinct=True),
        open_requested=Count("requested_tickets", filter=Q(requested_tickets__status__in=OPEN_STATUSES), distinct=True),
    )


def _role_menus(everyone, status):
    """For each role: how many people it has and how they split across departments (for the dropdown).

    Counts follow the Active / Turned off / Everyone switch, so a number always matches the list it opens.
    """
    base = everyone
    if status == "active":
        base = base.filter(is_active=True)
    elif status == "inactive":
        base = base.filter(is_active=False)
    rows = base.values("role", "department_id", "department__name").annotate(n=Count("pk"))
    by_role = {value: {"value": value, "label": label, "total": 0, "depts": []} for value, label in User.Role.choices}
    for row in rows:
        menu = by_role[row["role"]]
        menu["total"] += row["n"]
        menu["depts"].append({"key": row["department_id"] or "none", "name": row["department__name"] or "No department",
                              "n": row["n"]})
    for menu in by_role.values():
        menu["depts"].sort(key=lambda d: (d["key"] == "none", d["name"].lower()))
    return list(by_role.values())


@admin_only
def people_list(request):
    role = request.GET.get("role", "")
    status = request.GET.get("status", "active")
    query = request.GET.get("q", "").strip()
    dept = request.GET.get("dept", "") if role in User.Role.values else ""
    everyone = User.objects.all()
    people = _with_counts(everyone.select_related("department").prefetch_related("support_groups"))
    if role in User.Role.values:
        people = people.filter(role=role)
    if dept == "none":
        people = people.filter(department__isnull=True)
    elif dept.isdigit():
        people = people.filter(department_id=int(dept))
    else:
        dept = ""
    if status == "active":
        people = people.filter(is_active=True)
    elif status == "inactive":
        people = people.filter(is_active=False)
    for word in query.split():
        people = people.filter(Q(first_name__icontains=word) | Q(last_name__icontains=word) | Q(username__icontains=word)
                               | Q(email__icontains=word) | Q(department__name__icontains=word))
    counts = {r: everyone.filter(role=r, is_active=True).count() for r in User.Role.values}
    menus = _role_menus(everyone, status)
    return render(request, "people/list.html", {
        "people": people.order_by("-is_active", "first_name", "username"), "q": query, "role": role, "status": status,
        "dept": dept, "role_menus": menus,
        "dept_name": next((d["name"] for m in menus for d in m["depts"] if str(d["key"]) == dept and m["value"] == role), ""),
        "roles": User.Role.choices, "counts": counts, "active_total": sum(counts.values()),
        "inactive_total": everyone.filter(is_active=False).count(),
    })


def _setup_link(user):
    """A one-time link where the person chooses their own password (Django's password-reset flow)."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    path = reverse("password_reset_confirm", args=[uid, default_token_generator.make_token(user)])
    return f"{settings.HELPLY_SITE_URL}{path}"


def _send_setup_email(user, link, welcome):
    intro = "An administrator created a Helply account for you." if welcome else "An administrator reset your Helply password."
    try:
        send_mail("Set your Helply password" if welcome else "Reset your Helply password",
                  f"Hi {user.first_name or user.username},\n\n{intro}\nChoose your password here (the link works once "
                  f"and expires in a few days):\n\n{link}\n\nYour username is: {user.username}\n\n--\nHelply IT Service Desk",
                  None, [user.email])
        return True
    except Exception:  # a mail outage must not stop an administrator handing the link over by hand
        log.exception("Could not email the setup link to user %s", user.pk)
        return False


@never_cache
def _show_link(request, user, welcome):
    link = _setup_link(user)
    return render(request, "people/invite.html", {
        "person": user, "link": link, "welcome": welcome, "emailed": _send_setup_email(user, link, welcome)})


@admin_only
def people_create(request):
    form = UserForm(request.POST or None, acting_user=request.user, initial={"role": User.Role.EMPLOYEE, "is_active": True})
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.set_unusable_password()
        user.save()
        form.save_groups(user)
        return _show_link(request, user, welcome=True)
    return render(request, "people/form.html", {"form": form, "person": None, "teams": form.fields["support_groups"].queryset})


@admin_only
def people_edit(request, pk):
    person = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=person, acting_user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved {person}.")
        return redirect("people:list")
    return render(request, "people/form.html", {
        "form": form, "person": person, "is_self": person.pk == request.user.pk,
        "open_assigned": person.assigned_tickets.filter(status__in=OPEN_STATUSES).count(),
        "can_remove": last_admin_guard(person) or not (person.role == User.Role.ADMINISTRATOR and person.is_active),
        "teams": form.fields["support_groups"].queryset})


@admin_only
@require_POST
def people_toggle(request, pk):
    """Switch someone's sign-in off or back on. Their tickets and history stay."""
    person = get_object_or_404(User, pk=pk)
    if person.pk == request.user.pk:
        messages.error(request, "You cannot turn off your own account.")
    elif person.is_active and person.role == User.Role.ADMINISTRATOR and not last_admin_guard(person):
        messages.error(request, "Helply needs at least one active administrator.")
    else:
        person.is_active = not person.is_active
        person.save(update_fields=["is_active"])
        messages.success(request, f"{person} {'can sign in again' if person.is_active else 'can no longer sign in'}.")
    return redirect("people:edit", pk=person.pk)


@admin_only
@require_POST
def people_reset(request, pk):
    person = get_object_or_404(User, pk=pk)
    if not person.is_active:
        messages.error(request, "Turn the account back on before resetting its password.")
        return redirect("people:edit", pk=person.pk)
    return _show_link(request, person, welcome=False)
