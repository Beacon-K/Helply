from django import forms

from apps.accounts.models import User
from apps.assets.models import Asset

from .models import Category, Ticket


class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "category", "asset", "impact", "urgency"]
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}
        help_texts = {
            "impact": "How many people or how much of the business is affected?",
            "urgency": "How quickly does this need to be fixed?",
        }

    def __init__(self, *args, user, **kwargs):
        kwargs.setdefault("label_suffix", "")  # labels read cleaner without a colon
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        self.fields["category"].empty_label = "Not sure - let Helply decide"
        self.fields["asset"].queryset = Asset.objects.filter(owner=user)
        self.fields["asset"].empty_label = "None / not listed"


class CommentForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="")
    is_internal = forms.BooleanField(required=False, label="Internal note (hidden from requester)")


class AssignForm(forms.Form):
    assignee = forms.ModelChoiceField(
        queryset=User.objects.filter(role__in=[User.Role.TECHNICIAN, User.Role.ADMINISTRATOR], is_active=True)
    )


class CategoryForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.filter(is_active=True), label="")


class SurveyForm(forms.Form):
    rating = forms.TypedChoiceField(choices=[(i, f"{i} ★") for i in range(5, 0, -1)], coerce=int)
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
