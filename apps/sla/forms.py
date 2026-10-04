import re

from django import forms

from apps.tickets.choices import Priority

from .models import SLAPolicy

MAX_MINUTES = 60 * 24 * 365
_UNITS = {"m": 1, "min": 1, "mins": 1, "minute": 1, "minutes": 1, "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60,
          "d": 1440, "day": 1440, "days": 1440, "w": 10080, "week": 10080, "weeks": 10080}


def parse_duration(text):
    """'30m', '4h', '1d 2h', '90' (minutes) -> minutes. Raises ValueError on anything else."""
    text = (text or "").strip().lower()
    if re.fullmatch(r"\d+", text):
        return int(text)
    parts = re.findall(r"(\d+)\s*([a-z]+)", text)
    if not parts or re.sub(r"(\d+)\s*([a-z]+)|\s+", "", text):
        raise ValueError("Use a time like 30m, 4h or 1d 2h.")
    total = 0
    for number, unit in parts:
        if unit not in _UNITS:
            raise ValueError(f'"{unit}" is not a unit - use m, h or d.')
        total += int(number) * _UNITS[unit]
    return total


def format_duration(minutes):
    """The inverse of parse_duration, in the largest whole units: 90 -> '1h 30m', 1440 -> '1d'."""
    days, rest = divmod(int(minutes or 0), 1440)
    hours, mins = divmod(rest, 60)
    return " ".join(p for p in (f"{days}d" if days else "", f"{hours}h" if hours else "", f"{mins}m" if mins else "") if p) or "0m"


class DurationField(forms.CharField):
    def clean(self, value):
        value = super().clean(value)
        try:
            minutes = parse_duration(value)
        except ValueError as error:
            raise forms.ValidationError(str(error))
        if not 1 <= minutes <= MAX_MINUTES:
            raise forms.ValidationError("Choose between 1 minute and 365 days.")
        return minutes


class PolicyForm(forms.Form):
    """One row of the SLA page: the targets for a single priority."""

    name = forms.CharField(max_length=100)
    response_minutes = DurationField(label="First response within", max_length=20)
    resolution_minutes = DurationField(label="Resolved within", max_length=20)
    is_active = forms.BooleanField(required=False, label="Track this SLA")

    def __init__(self, priority, policy=None, *args, **kwargs):
        kwargs["prefix"] = priority
        super().__init__(*args, **kwargs)
        self.priority = priority
        self.label = dict(Priority.choices)[priority]
        self.title = self.label.split(' - ')[-1]
        self.policy = policy
        if policy is not None and not self.is_bound:
            self.initial = {"name": policy.name, "is_active": policy.is_active,
                            "response_minutes": format_duration(policy.response_minutes),
                            "resolution_minutes": format_duration(policy.resolution_minutes)}
        elif policy is None and not self.is_bound:
            self.initial = {"is_active": False}

    def clean(self):
        data = super().clean()
        response, resolution = data.get("response_minutes"), data.get("resolution_minutes")
        if response and resolution and resolution < response:
            self.add_error("resolution_minutes", "The resolution time cannot be shorter than the first response time.")
        return data

    def save(self):
        policy = self.policy or SLAPolicy(priority=self.priority)
        for field in ("name", "response_minutes", "resolution_minutes", "is_active"):
            setattr(policy, field, self.cleaned_data[field])
        policy.save()
        return policy