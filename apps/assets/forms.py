from django import forms
from django.utils.translation import gettext, gettext_lazy

from apps.accounts.models import User

from .models import Asset


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ["asset_tag", "name", "type", "status", "serial_number", "owner", "department", "location",
                  "supplier", "purchase_date", "purchase_cost", "warranty_expiry", "notes"]
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "warranty_expiry": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {"asset_tag": gettext_lazy("Asset tag"), "name": gettext_lazy("Name"), "type": gettext_lazy("Type"),
                  "status": gettext_lazy("Status"), "serial_number": gettext_lazy("Serial number"),
                  "owner": gettext_lazy("Assigned to"), "department": gettext_lazy("Department"),
                  "location": gettext_lazy("Location"), "supplier": gettext_lazy("Supplier"),
                  "purchase_date": gettext_lazy("Purchase date"), "purchase_cost": gettext_lazy("Purchase cost"),
                  "warranty_expiry": gettext_lazy("Warranty / renewal date"), "notes": gettext_lazy("Notes")}
        help_texts = {"location": gettext_lazy('Where it is, e.g. "Server room" or "Remote".'),
                      "purchase_cost": gettext_lazy("Purchase price (CAD). For subscriptions: cost per year."),
                      "warranty_expiry": gettext_lazy("Warranty end, or renewal date for licences and subscriptions.")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        people = User.objects.filter(is_active=True).order_by("first_name", "username")
        if self.instance.pk and self.instance.owner_id:
            people = (people | User.objects.filter(pk=self.instance.owner_id)).distinct()  # keep a switched-off owner visible
        self.fields["owner"].queryset = people
        self.fields["owner"].empty_label = gettext("Shared (nobody)")
        self.fields["department"].empty_label = gettext("None")

    def clean_asset_tag(self):
        tag = self.cleaned_data["asset_tag"].strip()
        if Asset.objects.filter(asset_tag__iexact=tag).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(gettext("An asset tagged %(tag)s already exists.") % {"tag": tag})
        return tag
