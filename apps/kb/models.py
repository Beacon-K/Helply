from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.functional import cached_property


class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Article.Status.PUBLISHED)

    def visible_to(self, user):
        """Employees see self-service articles; IT staff also see internal runbooks."""
        qs = self.published()
        if user is None or not user.is_agent:
            qs = qs.filter(audience=Article.Audience.EVERYONE)
        return qs


class Article(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    class Audience(models.TextChoices):
        EVERYONE = "everyone", "Everyone (self-service)"
        INTERNAL = "internal", "IT staff only (runbook)"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    summary = models.CharField(max_length=300, blank=True, help_text="One or two sentences shown in search results.")
    body = models.TextField(help_text="Supports ## headings, - bullets, 1. numbered steps, **bold**, `code` and > tips.")
    keywords = models.CharField(max_length=300, blank=True, help_text="Comma-separated search terms and synonyms.")
    category = models.ForeignKey(
        "tickets.Category", null=True, blank=True, on_delete=models.SET_NULL, related_name="articles"
    )
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.EVERYONE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    source_ticket = models.ForeignKey(
        "tickets.Ticket",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="kb_articles",
        help_text="Ticket this article was written from, if any.",
    )
    views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ArticleQuerySet.as_manager()

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("kb:detail", args=[self.slug])

    @cached_property
    def vote_counts(self):
        """(helpful, not helpful) vote counts, from one query."""
        agg = self.votes.aggregate(
            yes=Count("pk", filter=Q(value=ArticleVote.Value.HELPFUL)),
            no=Count("pk", filter=Q(value=ArticleVote.Value.NOT_HELPFUL)),
        )
        return agg["yes"], agg["no"]

    @property
    def helpful_yes(self):
        return self.vote_counts[0]

    @property
    def helpful_no(self):
        return self.vote_counts[1]

    @property
    def helpful_total(self):
        return self.helpful_yes + self.helpful_no

    @property
    def helpful_percent(self):
        """Share of votes that were 'helpful', or None before anyone has voted."""
        if not self.helpful_total:
            return None
        return round(100 * self.helpful_yes / self.helpful_total)

    @property
    def is_internal(self):
        return self.audience == self.Audience.INTERNAL


class ArticleVote(models.Model):
    """One user's 'was this helpful?' vote on an article. Clicking the same thumb again removes it."""

    class Value(models.IntegerChoices):
        HELPFUL = 1, "Helpful"
        NOT_HELPFUL = -1, "Not helpful"

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kb_votes")
    value = models.SmallIntegerField(choices=Value.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["article", "user"], name="kb_one_vote_per_user")]


class ArticleSuggestion(models.Model):
    """An improvement suggestion left by a reader after a thumbs-down."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Addressed"

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="suggestions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="kb_suggestions")
    text = models.TextField(max_length=2000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.article}: {self.text[:50]}"
