"""JSON endpoints behind the assistant panels. All POST-only, login required, CSRF protected."""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from apps.tickets.selectors import visible_tickets

from . import assistant, chat as chat_service, insights
from .models import AISuggestion


def _body(request):
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


@login_required
@require_POST
def ask(request):
    try:
        return JsonResponse(assistant.ask(request.user, _body(request).get("question", "")))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except assistant.RateLimited as exc:
        return JsonResponse({"error": str(exc)}, status=429)


@login_required
@require_POST
def ticket_copilot(request, pk):
    if not request.user.is_agent:
        return JsonResponse({"error": "Technicians only."}, status=403)
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    try:
        return JsonResponse(assistant.copilot(request.user, ticket))
    except assistant.RateLimited as exc:
        return JsonResponse({"error": str(exc)}, status=429)


@login_required
@require_POST
def feedback(request, pk):
    """Thumbs up/down on an answer; this is what makes assistant quality measurable."""
    value = _body(request).get("helpful")
    if not isinstance(value, bool):
        return JsonResponse({"error": "helpful must be true or false."}, status=400)
    suggestion = get_object_or_404(AISuggestion, pk=pk, user=request.user)
    suggestion.accepted = value
    suggestion.save(update_fields=["accepted"])
    return JsonResponse({"ok": True})

@login_required
@require_POST
def chat(request):
    body = _body(request)
    try:
        return JsonResponse(chat_service.chat(request.user, body.get("message", ""), body.get("history")))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except assistant.RateLimited as exc:
        return JsonResponse({"error": str(exc)}, status=429)


@login_required
@require_POST
def insights_refresh(request):
    """Re-run the ticket analysis now (administrators). A cooldown keeps it from burning the AI quota."""
    if not request.user.is_administrator:
        return JsonResponse({"error": "Administrators only."}, status=403)
    wait = insights.cooldown_left()
    if wait:
        return JsonResponse({"error": f"The analysis was refreshed a moment ago. Try again in {max(1, wait // 60)} min."},
                            status=429)
    report = insights.generate(force=True)
    return JsonResponse({"ok": True, "ai": bool(report.analysis)})
