from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.tickets.models import Category

from .forms import ArticleForm
from .models import Article, ArticleSuggestion, ArticleVote


@login_required
def article_list(request):
    visible = Article.objects.for_user(request.user).select_related("category")
    category_id = request.GET.get("category", "")

    categories = Category.objects.annotate(
        n=Count("articles", filter=Q(articles__in=visible))
    ).filter(n__gt=0)

    if category_id.isdigit():
        visible = visible.filter(category_id=category_id)
    groups = {}
    if request.user.is_agent:
        visible = visible.annotate(open_suggestions=Count(
            "suggestions", filter=Q(suggestions__status=ArticleSuggestion.Status.OPEN)))
    for article in visible.order_by(F("category__name").asc(nulls_last=True), "title"):
        groups.setdefault(article.category, []).append(article)
    return render(request, "kb/list.html", {
        "groups": groups.items(),
        "categories": categories,
        "current_category": category_id,
        "total": visible.count(),
        "popular": Article.objects.visible_to(request.user).filter(views__gt=0).order_by("-views")[:5],
    })


@login_required
def article_detail(request, slug):
    article = get_object_or_404(Article.objects.for_user(request.user), slug=slug)
    Article.objects.filter(pk=article.pk).update(views=F("views") + 1)
    related = (
        Article.objects.for_user(request.user)
        .filter(category=article.category)
        .exclude(pk=article.pk)[:5]
        if article.category_id else []
    )
    my_vote = article.votes.filter(user=request.user).values_list("value", flat=True).first()
    suggestions = article.suggestions.select_related("user") if request.user.is_agent else []
    return render(request, "kb/detail.html", {"article": article, "related": related, "my_vote": my_vote,
                                              "suggestions": suggestions})


VOTE_VALUES = {"up": ArticleVote.Value.HELPFUL, "down": ArticleVote.Value.NOT_HELPFUL}


@login_required
@require_POST
def article_vote(request, slug):
    """Toggle the user's thumbs-up / thumbs-down.

    Same thumb again -> vote removed; other thumb -> vote switched.
    Returns JSON for the in-page update; falls back to a redirect without JS.
    """
    article = get_object_or_404(Article.objects.visible_to(request.user), slug=slug)
    value = VOTE_VALUES.get(request.POST.get("vote"))
    if value is None:
        return HttpResponseBadRequest("vote must be 'up' or 'down'")

    with transaction.atomic():
        vote, created = ArticleVote.objects.select_for_update().get_or_create(
            article=article, user=request.user, defaults={"value": value}
        )
        if not created and vote.value == value:
            vote.delete()
            mine = None
        else:
            if vote.value != value:
                vote.value = value
                vote.save(update_fields=["value", "updated_at"])
            mine = value

    if request.headers.get("X-Requested-With") != "fetch":
        return redirect(f"{article.get_absolute_url()}#feedback")
    return JsonResponse({
        "yes": article.helpful_yes,
        "no": article.helpful_no,
        "total": article.helpful_total,
        "percent": article.helpful_percent,
        "mine": {ArticleVote.Value.HELPFUL: "up", ArticleVote.Value.NOT_HELPFUL: "down"}.get(mine),
    })


@login_required
@require_POST
def article_suggest(request, slug):
    """Save an improvement suggestion (offered after a thumbs-down)."""
    article = get_object_or_404(Article.objects.visible_to(request.user), slug=slug)
    text = request.POST.get("text", "").strip()
    if not text:
        return HttpResponseBadRequest("Suggestion text is required")
    ArticleSuggestion.objects.create(article=article, user=request.user, text=text[:2000])
    if request.headers.get("X-Requested-With") != "fetch":
        return redirect(f"{article.get_absolute_url()}#feedback")
    return JsonResponse({"ok": True})


def _require_agent(user):
    # Every IT staff member (technician or administrator) maintains the knowledge base.
    if not user.is_agent:
        raise PermissionDenied


@login_required
def article_create(request):
    _require_agent(request.user)
    form = ArticleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.author = request.user
        article.save()
        messages.success(request, "Article created.")
        return redirect(article)
    return render(request, "kb/form.html", {"form": form, "article": None})


@login_required
def article_edit(request, slug):
    _require_agent(request.user)
    article = get_object_or_404(Article, slug=slug)
    form = ArticleForm(request.POST or None, instance=article)
    if request.method == "POST" and form.is_valid():
        article = form.save()
        messages.success(request, "Article saved.")
        return redirect(article)
    return render(request, "kb/form.html", {"form": form, "article": article})


@login_required
def article_delete(request, slug):
    """Asks first, then deletes. Votes and suggestions go with the article."""
    _require_agent(request.user)
    article = get_object_or_404(Article, slug=slug)
    if request.method == "POST":
        article.delete()
        messages.success(request, f"Deleted “{article.title}”.")
        return redirect("kb:list")
    return render(request, "kb/confirm_delete.html", {"article": article})


@login_required
@require_POST
def suggestion_done(request, slug, pk):
    """IT staff mark a reader's suggestion as dealt with (or reopen it)."""
    _require_agent(request.user)
    suggestion = get_object_or_404(ArticleSuggestion, pk=pk, article__slug=slug)
    reopened = suggestion.status == ArticleSuggestion.Status.DONE
    suggestion.status = ArticleSuggestion.Status.OPEN if reopened else ArticleSuggestion.Status.DONE
    suggestion.save(update_fields=["status"])
    return redirect(f"{suggestion.article.get_absolute_url()}#suggestions")
