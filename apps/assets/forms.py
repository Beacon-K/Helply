from django import forms

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
        labels = {"owner": "Assigned to", "warranty_expiry": "Warranty / renewal date"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        people = User.objects.filter(is_active=True).order_by("first_name", "username")
        if self.instance.pk and self.instance.owner_id:
            people = (people | User.objects.filter(pk=self.instance.owner_id)).distinct()  # keep a switched-off owner visible
        self.fields["owner"].queryset = people
        self.fields["owner"].empty_label = "Shared (nobody)"
        self.fields["department"].empty_label = "None"

    def clean_asset_tag(self):
        tag = self.cleaned_data["asset_tag"].strip()
        if Asset.objects.filter(asset_tag__iexact=tag).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"An asset tagged {tag} already exists.")
        return tag
