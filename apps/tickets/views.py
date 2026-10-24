from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import agent_required
from apps.accounts.models import User
from apps.ai import services as ai
from apps.sla.services import sla_state

from . import services, workflow
from .choices import DEFAULT_LIST_FILTER, LIST_FILTERS, Status
from .forms import AssignForm, CategoryForm, CommentForm, SurveyForm, TicketCreateForm, TicketOnBehalfForm
from .selectors import visible_tickets


@login_required
def ticket_list(request):
    visible = visible_tickets(request.user)
    current = request.GET.get("status", DEFAULT_LIST_FILTER)
    if current in LIST_FILTERS:
        tickets = visible.filter(status__in=LIST_FILTERS[current][1])
    elif current in Status.values:  # exact status, e.g. ?status=triaged (kept for direct links)
        tickets = visible.filter(status=current)
    else:
        current, tickets = DEFAULT_LIST_FILTER, visible.filter(status__in=LIST_FILTERS[DEFAULT_LIST_FILTER][1])

    # ?assignee=none: only tickets no technician has picked up (the dashboard's "Unassigned" link). Agents only.
    unassigned_only = request.GET.get("assignee") == "none" and request.user.is_agent
    if unassigned_only:
        tickets = tickets.filter(assignee__isnull=True)

    per_status = dict(visible.order_by().values_list("status").annotate(n=Count("pk", distinct=True)))
    filters = [
        (key, label, sum(per_status.get(s, 0) for s in statuses))
        for key, (label, statuses) in LIST_FILTERS.items()
    ]
    rows = [(t, sla_state(t)) for t in tickets[:200]]
    return render(request, "tickets/list.html", {"rows": rows, "filters": filters, "current": current,
                                                 "unassigned_only": unassigned_only})


@login_required
def ticket_create(request):
    # Prefill from links such as "Open a ticket" on a KB article or "Report a problem" on a device.
    initial = {key: request.GET[key] for key in ("category", "asset") if request.GET.get(key, "").isdigit()}
    form = TicketCreateForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        ticket = services.create_ticket(requester=request.user, **form.cleaned_data)
        messages.success(request, f"Ticket {ticket.reference} submitted.")
        return redirect(ticket)
    return render(request, "tickets/form.html", {"form": form})


@agent_required
def ticket_create_for(request, user_id):
    """IT staff submit a ticket for an employee (reached from People). The employee is the requester and is notified."""
    person = get_object_or_404(User, pk=user_id, is_active=True)
    initial = {key: request.GET[key] for key in ("category", "asset") if request.GET.get(key, "").isdigit()}
    form = TicketOnBehalfForm(request.POST or None, user=person, initial=initial)
    if request.method == "POST" and form.is_valid():
        ticket = services.create_ticket(requester=person, created_by=request.user, **form.cleaned_data)
        messages.success(request, f"Ticket {ticket.reference} submitted for {person}.")
        return redirect(ticket)
    return render(request, "tickets/form_for.html", {"form": form, "person": person})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    user = request.user
    ticket.notifications.filter(recipient=user, is_read=False).update(is_read=True)
    comments = ticket.comments.select_related("author")
    if not user.is_agent:
        comments = comments.filter(is_internal=False)
    context = {
        "ticket": ticket,
        "comments": comments,
        "events": ticket.events.select_related("actor"),
        "actions": workflow.available_transitions(ticket, user),
        "sla": sla_state(ticket),
        "comment_form": CommentForm(),
        "related_articles": ai.related_articles(f"{ticket.title} {ticket.description}", user=user, category=ticket.category),
    }
    if user.is_agent:
        context["similar"] = ai.similar_tickets(ticket)
    if workflow.can_recategorize(ticket, user):
        context["category_form"] = CategoryForm(initial={"category": ticket.category})
    if user.is_administrator and ticket.is_open:
        context["assign_form"] = AssignForm(initial={"assignee": ticket.assignee or ai.suggest_assignee(ticket)})
    if ticket.requester_id == user.pk and ticket.status in (Status.RESOLVED, Status.CLOSED) \
            and not hasattr(ticket, "satisfaction"):
        context["survey_form"] = SurveyForm()
    return render(request, "tickets/detail.html", context)


@login_required
@require_POST
def ticket_action(request, pk, action):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    try:
        workflow.perform(ticket, action, request.user, note=request.POST.get("note", ""))
        messages.success(request, f"Ticket is now {ticket.get_status_display().lower()}.")
    except workflow.TransitionError as e:
        messages.error(request, str(e))
    return redirect(ticket)


@login_required
@require_POST
def ticket_assign(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    form = AssignForm(request.POST)
    if form.is_valid():
        try:
            workflow.assign(ticket, form.cleaned_data["assignee"], actor=request.user)
            messages.success(request, f"Assigned to {ticket.assignee}.")
        except workflow.TransitionError as e:
            messages.error(request, str(e))
    return redirect(ticket)


@login_required
@require_POST
def ticket_categorize(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    form = CategoryForm(request.POST)
    if form.is_valid():
        try:
            workflow.recategorize(ticket, form.cleaned_data["category"], request.user)
            messages.success(request, f"Category set to {ticket.category}.")
        except workflow.TransitionError as e:
            messages.error(request, str(e))
    return redirect(ticket)


@login_required
@require_POST
def ticket_comment(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        services.add_comment(ticket, request.user, form.cleaned_data["body"], form.cleaned_data["is_internal"])
    return redirect(ticket)


@login_required
@require_POST
def ticket_survey(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    form = SurveyForm(request.POST)
    if form.is_valid():
        try:
            services.submit_survey(ticket, request.user, form.cleaned_data["rating"], form.cleaned_data["comment"])
            messages.success(request, "Thanks for your feedback!")
        except (PermissionError, ValueError) as e:
            messages.error(request, str(e))
    return redirect(ticket)
