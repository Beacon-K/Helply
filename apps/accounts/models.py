from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """A Helply user. Every user has exactly one business role."""

    class Role(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        TECHNICIAN = "technician", "Technician"
        ADMINISTRATOR = "administrator", "Administrator"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )
    phone = models.CharField(max_length=30, blank=True)
    email_notifications = models.BooleanField(default=True, help_text="Send email copies of important notifications.")

    @property
    def is_employee(self):
        return self.role == self.Role.EMPLOYEE

    @property
    def is_technician(self):
        return self.role == self.Role.TECHNICIAN

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMINISTRATOR

    @property
    def is_agent(self):
        """Technicians and administrators work tickets; employees only raise them."""
        return self.role in (self.Role.TECHNICIAN, self.Role.ADMINISTRATOR)

    def __str__(self):
        return self.get_full_name() or self.username


class LoginFailure(models.Model):
    """One wrong password at sign-in. See throttle.py: these rows drive the lockout."""

    username = models.CharField(max_length=150, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    at = models.DateTimeField(default=timezone.now, db_index=True)  # UTC, like every timestamp Django stores
    at_local = models.CharField(max_length=32, blank=True)  # the same moment in company time, for people reading the file

    class Meta:
        ordering = ["-at"]

    def save(self, *args, **kwargs):
        self.at_local = timezone.localtime(self.at).isoformat(sep=" ", timespec="seconds")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} from {self.ip} at {self.at_local or self.at}"


class ResetRequest(models.Model):
    """One use of the public 'forgot your password' form. See throttle.py: these rows limit how many reset emails
    one address, or one visitor, can trigger."""

    email = models.CharField(max_length=254, db_index=True)  # normalised, so spelling variants count together
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    sent = models.BooleanField(default=True)  # False when the limit stopped the email
    at = models.DateTimeField(default=timezone.now, db_index=True)
    at_local = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["-at"]

    def save(self, *args, **kwargs):
        self.at_local = timezone.localtime(self.at).isoformat(sep=" ", timespec="seconds")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} from {self.ip} at {self.at_local or self.at}"


class LoginRecord(models.Model):
    """One signed-in session: when, from where and for how long.

    Kept in the local database for audits and investigations only. It is deliberately not shown anywhere in
    the web app or the Django admin; read it with `python manage.py login_records` (see that command).
    """

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="login_records")
    username = models.CharField(max_length=150, db_index=True)  # kept even if the account is later renamed
    role = models.CharField(max_length=20, blank=True)  # the role at sign-in time
    ip = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=2, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    # The *_at columns are real timestamps stored in UTC, as Django always does. Anyone opening the database file
    # directly would read them four or five hours off local time, so each also has a *_local text copy in the
    # company's time zone (settings.TIME_ZONE) with its UTC offset, and online_seconds holds the duration.
    logged_in_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField(default=timezone.now)  # last page the person loaded in this session
    logged_out_at = models.DateTimeField(null=True, blank=True)  # empty when the session just expired
    logged_in_local = models.CharField(max_length=32, blank=True)
    last_seen_local = models.CharField(max_length=32, blank=True)
    logged_out_local = models.CharField(max_length=32, blank=True)
    online_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-logged_in_at"]

    @staticmethod
    def stamp(moment):
        """Local-time text such as '2026-10-06 14:57:33-04:00' (empty for None)."""
        return timezone.localtime(moment).isoformat(sep=" ", timespec="seconds") if moment else ""

    def save(self, *args, **kwargs):
        self.logged_in_local = self.stamp(self.logged_in_at)
        self.last_seen_local = self.stamp(self.last_seen_at)
        self.logged_out_local = self.stamp(self.logged_out_at)
        self.online_seconds = int(self.duration.total_seconds())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} from {self.ip} at {self.stamp(self.logged_in_at)}"

    @property
    def ended_at(self):
        return self.logged_out_at or self.last_seen_at

    @property
    def duration(self):
        """Time online: from sign-in to sign-out, or to the last page loaded if they never signed out."""
        return max(self.ended_at - self.logged_in_at, timedelta(0))


class SupportGroup(models.Model):
    """A team of technicians that owns one or more ticket categories."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(
        User,
        blank=True,
        related_name="support_groups",
        limit_choices_to={"role__in": [User.Role.TECHNICIAN, User.Role.ADMINISTRATOR]},
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
