from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Department, User
from apps.assets.models import Asset

from .models import Category, Ticket


class _EmployeeSelect(forms.Select):
    """Employee list whose options carry their department, so the page can narrow it when a department is chosen."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-department"] = instance.department_id or ""
        return option


class TicketCreateForm(forms.ModelForm):
    # Agents (IT staff) can raise a ticket for an employee, e.g. after a phone call or a desk visit.
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False,
                                        empty_label=_("All departments"), label=_("Department"))
    requester = forms.ModelChoiceField(queryset=User.objects.none(), required=False, widget=_EmployeeSelect,
                                       label=_("Employee"), empty_label=_("Myself"))

    class Meta:
        model = Ticket
        fields = ["title", "description", "category", "asset", "impact", "urgency"]
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}
        labels = {"title": _("Title"), "description": _("Description"), "category": _("Category"), "asset": _("Asset"),
                  "impact": _("Impact"), "urgency": _("Urgency")}
        help_texts = {
            "impact": _("How many people or how much of the business is affected?"),
            "urgency": _("How quickly does this need to be fixed?"),
        }

    def __init__(self, *args, user, **kwargs):
        kwargs.setdefault("label_suffix", "")  # labels read cleaner without a colon
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["category"].empty_label = _("Not sure - let Helply decide")
        self.fields["asset"].empty_label = _("None / not listed")
        self.for_other = user.is_agent
        if self.for_other:
            self.fields["requester"].queryset = (
                User.objects.filter(role=User.Role.EMPLOYEE, is_active=True)
                .select_related("department").order_by("first_name", "last_name", "username"))
            self.fields["asset"].queryset = Asset.objects.filter(owner__isnull=False).select_related("owner")
            self.order_fields(["department", "requester", "title", "description", "category", "asset", "impact", "urgency"])
        else:
            # Only agents may file for someone else; for everyone else these fields do not exist at all.
            del self.fields["department"], self.fields["requester"]
            self.fields["asset"].queryset = Asset.objects.filter(owner=user)
        self.user = user

    def clean(self):
        data = super().clean()
        requester, department, asset = data.get("requester"), data.get("department"), data.get("asset")
        if requester and department and requester.department_id != department.pk:
            self.add_error("requester", _("This employee is not in the selected department."))
        # A device can only be reported for the person who owns it.
        owner = requester or self.user
        if asset and asset.owner_id != owner.pk:
            self.add_error("asset", _("This device belongs to someone else."))
        return data


class CommentForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="")
    is_internal = forms.BooleanField(required=False, label=_("Internal note (hidden from requester)"))


class AssignForm(forms.Form):
    assignee = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=[User.Role.TECHNICIAN, User.Role.ADMINISTRATOR], is_active=True)
    )


class CategoryForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.filter(is_active=True), label="")


class SurveyForm(forms.Form):
    rating = forms.TypedChoiceField(choices=[(i, f"{i} / 5") for i in range(5, 0, -1)], coerce=int)
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
