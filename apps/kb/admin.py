from django.contrib import admin
from django.db.models import Count, Q

from .models import Article, ArticleSuggestion, ArticleVote


class ArticleSuggestionInline(admin.TabularInline):
    model = ArticleSuggestion
    extra = 0
    fields = ("created_at", "user", "text", "status")
    readonly_fields = ("created_at", "user", "text")


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "audience", "status", "views", "votes_up", "votes_down", "updated_at")
    list_filter = ("status", "audience", "category")
    search_fields = ("title", "summary", "keywords", "body")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("views", "created_at", "updated_at")
    inlines = [ArticleSuggestionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _up=Count("votes", filter=Q(votes__value=ArticleVote.Value.HELPFUL)),
            _down=Count("votes", filter=Q(votes__value=ArticleVote.Value.NOT_HELPFUL)),
        )

    @admin.display(description="👍", ordering="_up")
    def votes_up(self, obj):
        return obj._up

    @admin.display(description="👎", ordering="_down")
    def votes_down(self, obj):
        return obj._down


@admin.register(ArticleVote)
class ArticleVoteAdmin(admin.ModelAdmin):
    list_display = ("article", "user", "value", "updated_at")
    list_filter = ("value",)


@admin.register(ArticleSuggestion)
class ArticleSuggestionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "article", "user", "short_text", "status")
    list_filter = ("status",)
    search_fields = ("text", "article__title")
    actions = ["mark_addressed"]

    @admin.display(description="Suggestion")
    def short_text(self, obj):
        return obj.text[:80]

    @admin.action(description="Mark selected suggestions as addressed")
    def mark_addressed(self, request, queryset):
        queryset.update(status=ArticleSuggestion.Status.DONE)
