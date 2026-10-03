from django import forms

from apps.accounts.models import User

from .countries import COUNTRIES
from .models import Server


class ServerForm(forms.ModelForm):
    country_code = forms.ChoiceField(
        label="Country", required=False,
        choices=[("", "Detect automatically")] + sorted(((c, n) for c, n in COUNTRIES.items()), key=lambda x: x[1]),
        help_text="Worked out from the server's IP address. Pick one only if the detected country is wrong.")

    class Meta:
        model = Server
        fields = ["name", "purpose", "provider", "country_code", "region", "public_ip", "plan", "monthly_cost", "expires_on",
                  "criticality", "owner", "alerts_enabled", "notes"]
        widgets = {
            "expires_on": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"public_ip": "Public IP", "monthly_cost": "Monthly cost (CAD)", "expires_on": "Renews / expires on",
                  "owner": "Looked after by", "alerts_enabled": "Raise tickets for alerts"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = User.objects.filter(
            role__in=[User.Role.TECHNICIAN, User.Role.ADMINISTRATOR], is_active=True).order_by("first_name")
        self.fields["name"].widget.attrs.update({"placeholder": "web-prod-01", "autocomplete": "off"})
        self.fields["purpose"].widget.attrs["placeholder"] = "Company website and client portal"
        self.fields["region"].widget.attrs["placeholder"] = "Toronto (ca-central-1)"
        self.fields["plan"].widget.attrs["placeholder"] = "2 vCPU / 4 GB RAM / 80 GB SSD"

    def save(self, commit=True):
        server = super().save(commit=False)
        # Choosing a country pins it; leaving it on "Detect automatically" lets the next report refresh it.
        server.country_auto = not self.cleaned_data.get("country_code")
        if commit:
            server.save()
            self.save_m2m()
        return server

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Give the server a name.")
        return name
