"""Renewal reminders for subscriptions (software licences and cloud servers).

A reminder goes out 30, 14 and 7 days before the renewal date and once more when it is due.
Each one is sent once per renewal date (see RenewalReminder). Recipients are the administrators and
the asset's owner. Servers added through monitoring are covered because their renewal date is
mirrored into the asset register.
"""
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Asset, RenewalReminder

MILESTONES = (30, 14, 7, 0)
# A renewal that has been overdue this long is stale data, not news - stop nagging.
OVERDUE_GRACE_DAYS = 14


def current_milestone(days_left):
    """The most urgent milestone reached, or None when it is too early or too long overdue."""
    if days_left < -OVERDUE_GRACE_DAYS:
        return None
    reached = [m for m in MILESTONES if days_left <= m]
    return min(reached) if reached else None


def _message(asset, days_left):
    when = asset.warranty_expiry.strftime("%b %d, %Y")
    if days_left < 0:
        title = f"{asset.name} renewal is {-days_left} day{'s' if days_left != -1 else ''} overdue"
    elif days_left == 0:
        title = f"{asset.name} renews today"
    else:
        title = f"{asset.name} renews in {days_left} day{'s' if days_left != 1 else ''}"
    cost = f" Yearly cost: ${asset.purchase_cost:,.2f} CAD." if asset.purchase_cost else ""
    return title, f"{asset.asset_tag} - renewal date {when}.{cost} Renew it or update the date after paying."


def send_renewal_reminders(today=None):
    """Send every reminder that is due. Returns the list of assets that were reminded about."""
    today = today or timezone.localdate()
    assets = Asset.objects.filter(
        type__in=(Asset.Type.LICENSE, Asset.Type.CLOUD), warranty_expiry__isnull=False,
        warranty_expiry__lte=today + timedelta(days=max(MILESTONES)),
    ).exclude(status=Asset.Status.RETIRED).select_related("owner")
    admins = list(User.objects.filter(role=User.Role.ADMINISTRATOR, is_active=True))
    reminded = []
    for asset in assets:
        days_left = (asset.warranty_expiry - today).days
        milestone = current_milestone(days_left)
        if milestone is None:
            continue
        _, created = RenewalReminder.objects.get_or_create(
            asset=asset, renewal_date=asset.warranty_expiry, milestone=milestone)
        if not created:
            continue  # already sent for this renewal date
        title, body = _message(asset, days_left)
        notify([asset.owner, *admins], Notification.Kind.RENEWAL, title, body=body,
               url=asset.get_absolute_url(), email=True)
        reminded.append(asset)
    return reminded
