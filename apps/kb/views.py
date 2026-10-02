from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.ai.services import related_articles
from apps.tickets.models import Category

from .models import Article, ArticleSuggestion, ArticleVote


@login_required
def article_list(request):
    visible = Article.objects.visible_to(request.user).select_related("category")
    q = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "")

    categories = Category.objects.annotate(
        n=Count("articles", filter=Q(articles__in=visible))
    ).filter(n__gt=0)

    if q:
        results = related_articles(q, user=request.user, limit=15, min_score=0.05)
        return render(request, "kb/list.html", {"q": q, "results": results, "categories": categories})

    if category_id.isdigit():
        visible = visible.filter(category_id=category_id)
    groups = {}
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
    article = get_object_or_404(Article.objects.visible_to(request.user), slug=slug)
    Article.objects.filter(pk=article.pk).update(views=F("views") + 1)
    related = (
        Article.objects.visible_to(request.user)
        .filter(category=article.category)
        .exclude(pk=article.pk)[:5]
        if article.category_id else []
    )
    my_vote = article.votes.filter(user=request.user).values_list("value", flat=True).first()
    return render(request, "kb/detail.html", {"article": article, "related": related, "my_vote": my_vote})


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
