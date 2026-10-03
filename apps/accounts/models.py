from django.contrib.auth.models import AbstractUser
from django.db import models


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
