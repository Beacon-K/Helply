from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render

from apps.accounts.decorators import role_required
from apps.accounts.models import User
from apps.tickets.choices import OPEN_STATUSES, Priority
from apps.tickets.models import Ticket

from .forms import PolicyForm
from .models import SLAPolicy


@role_required(User.Role.ADMINISTRATOR)
def policy_settings(request):
    """Edit the response and resolution targets for every priority on one page."""
    policies = {p.priority: p for p in SLAPolicy.objects.all()}
    open_counts = dict(Ticket.objects.filter(status__in=OPEN_STATUSES).values_list("priority").annotate(n=Count("pk")))
    data = request.POST if request.method == "POST" else None
    forms = [PolicyForm(priority, policies.get(priority), data) for priority, _ in Priority.choices]
    if request.method == "POST":
        if all([f.is_valid() for f in forms]):
            for form in forms:
                form.save()
            messages.success(request, "SLA policies saved. New tickets use them straight away; open tickets keep their due dates.")
            return redirect("sla:settings")
        messages.error(request, "Some targets need attention - see below.")
    for form in forms:
        form.open_count = open_counts.get(form.priority, 0)
    return render(request, "sla/settings.html", {"forms": forms})