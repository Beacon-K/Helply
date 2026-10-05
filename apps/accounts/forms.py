from django import forms

from .models import Department, SupportGroup, User


class UserForm(forms.ModelForm):
    """Create or edit a person. Passwords are never typed here: a new person gets a one-time setup link."""

    support_groups = forms.ModelMultipleChoiceField(
        label="Support teams", required=False, queryset=SupportGroup.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Teams whose tickets this person works on. Employees do not work tickets, so this is ignored for them.")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "role", "department", "phone", "is_active"]
        labels = {"is_active": "Can sign in", "first_name": "First name", "last_name": "Last name"}
        help_texts = {
            "username": "What they type to sign in. Letters, numbers and . @ + - _ only.",
            "role": "Employees raise tickets; technicians work them; administrators also manage people and SLA policies.",
            "is_active": "Turn off to stop someone signing in without deleting their tickets and history.",
        }

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        self.fields["email"].required = True
        self.fields["first_name"].required = True
        self.fields["department"].queryset = Department.objects.all()
        self.fields["department"].empty_label = "No department"
        self.fields["username"].widget.attrs.update({"autocomplete": "off", "autocapitalize": "none"})
        self.fields["first_name"].widget.attrs["placeholder"] = "Alice"
        self.fields["email"].widget.attrs["placeholder"] = "alice@company.com"
        if self.instance.pk:
            self.initial["support_groups"] = list(self.instance.support_groups.values_list("pk", flat=True))

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        clash = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("Another person already uses this email address.")
        return email

    def clean(self):
        data = super().clean()
        user = self.instance
        if not user.pk or "role" not in data:
            return data
        is_self = self.acting_user is not None and user.pk == self.acting_user.pk
        was_admin = user.role == User.Role.ADMINISTRATOR and user.is_active
        still_admin = data.get("role") == User.Role.ADMINISTRATOR and data.get("is_active")
        if is_self and not still_admin:
            raise forms.ValidationError("You cannot remove your own administrator access or sign-in. Ask another administrator.")
        if was_admin and not still_admin and not last_admin_guard(user):
            raise forms.ValidationError("Helply needs at least one active administrator. Make someone else an administrator first.")
        return data

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self.save_groups(user)
        return user

    def save_groups(self, user):
        groups = self.cleaned_data.get("support_groups") if user.is_agent else []
        user.support_groups.set(groups or [])


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "New department, e.g. Finance", "autocomplete": "off"})}

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if Department.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"A department called {name} already exists.")
        return name


class TeamForm(forms.ModelForm):
    """A support team: who is in it decides whose queue a category's tickets land in."""

    members = forms.ModelMultipleChoiceField(
        label="Members", required=False, widget=forms.CheckboxSelectMultiple,
        queryset=User.objects.filter(role__in=[User.Role.TECHNICIAN, User.Role.ADMINISTRATOR], is_active=True)
        .order_by("first_name", "username"),
        help_text="Technicians and administrators who work this team's tickets. Employees do not work tickets.")

    class Meta:
        model = SupportGroup
        fields = ["name", "description", "members"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3, "placeholder": "What this team looks after"})}
        help_texts = {"description": "Shown to administrators only."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # people who were turned off stay in the team until someone removes them, so keep them selectable
            current = self.instance.members.all()
            self.fields["members"].queryset = (self.fields["members"].queryset | current).distinct().order_by("first_name", "username")
            self.initial["members"] = list(current.values_list("pk", flat=True))

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        if SupportGroup.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"A team called {name} already exists.")
        return name


def last_admin_guard(user):
    """True when `user` is not the only active administrator (so it is safe to remove their access)."""
    return User.objects.filter(role=User.Role.ADMINISTRATOR, is_active=True).exclude(pk=user.pk).exists()
