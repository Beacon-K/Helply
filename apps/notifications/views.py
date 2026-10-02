from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Notification
from .services import unread_count


@login_required
def notification_list(request):
    notes = Notification.objects.filter(recipient=request.user).select_related("ticket")[:100]
    return render(request, "notifications/list.html", {"notes": notes})


@login_required
def notification_open(request, pk):
    note = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=["is_read"])
    target = note.url if url_has_allowed_host_and_scheme(note.url, allowed_hosts={request.get_host()}) else ""
    return redirect(target or "notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return redirect("notifications:list")


@login_required
@require_POST
def email_preference(request):
    request.user.email_notifications = request.POST.get("email_notifications") == "on"
    request.user.save(update_fields=["email_notifications"])
    messages.success(request, "Email notifications turned " + ("on." if request.user.email_notifications else "off."))
    return redirect("notifications:list")


@login_required
def unread(request):
    return JsonResponse({"unread": unread_count(request.user)})
