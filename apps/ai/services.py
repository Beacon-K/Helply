"""AI features embedded in the ticket workflow.

| Feature                    | Where it is used                          |
|----------------------------|-------------------------------------------|
| auto_triage                | ticket submission (tickets.services)      |
| auto_assign                | right after a confident auto-triage       |
| similar_tickets            | ticket detail page, for technicians       |
| related_articles           | ticket detail page / KB self-service      |
| SLA risk                   | apps.sla.services (rule based for now)    |

Every output is logged to AISuggestion so accuracy can be measured.
"""
from django.conf import settings
from django.db.models import Count, Q
from django.utils.module_loading import import_string

from .models import AISuggestion
from .text import jaccard, tokenize


def get_backend():
    return import_string(settings.HELPLY_AI_BACKEND)()


def auto_triage(ticket):
    """Classify a new ticket; if confident enough, set its category and mark it triaged."""
    from apps.tickets.choices import Status
    from apps.tickets.models import Category, TicketEvent

    backend = get_backend()
    result = backend.classify(f"{ticket.title}\n{ticket.description}", Category.objects.filter(is_active=True))
    confident = result.category is not None and result.confidence >= settings.HELPLY_AI_AUTO_TRIAGE_THRESHOLD

    AISuggestion.objects.create(
        ticket=ticket, kind=AISuggestion.Kind.CLASSIFY, backend=backend.name,
        payload={"category_id": result.category.pk if result.category else None,
                 "category": str(result.category) if result.category else None, "reason": result.reason},
        confidence=result.confidence, applied=confident,
    )
    if confident:
        ticket.category = result.category
        ticket.support_group = result.category.default_group
        ticket.ai_classified = True
        ticket.status = Status.TRIAGED
        TicketEvent.objects.create(
            ticket=ticket, kind=TicketEvent.Kind.AI, from_status=Status.NEW, to_status=Status.TRIAGED,
            note=f"Auto-classified as '{result.category}' (confidence {result.confidence:.0%}; {result.reason})",
        )
    return result


def suggest_assignee(ticket):
    """Least-loaded active technician in the ticket's support group."""
    from apps.accounts.models import User
    from apps.tickets.choices import OPEN_STATUSES

    if ticket.support_group_id is None:
        return None
    return (
        ticket.support_group.members.filter(role=User.Role.TECHNICIAN, is_active=True)
        .annotate(load=Count("assigned_tickets", filter=Q(assigned_tickets__status__in=OPEN_STATUSES)))
        .order_by("load", "pk")
        .first()
    )


def auto_assign(ticket):
    from apps.tickets import workflow

    if not settings.HELPLY_AI_AUTO_ASSIGN:
        return None
    technician = suggest_assignee(ticket)
    AISuggestion.objects.create(
        ticket=ticket, kind=AISuggestion.Kind.ASSIGN, backend="least-loaded",
        payload={"assignee_id": technician.pk if technician else None}, applied=technician is not None,
    )
    if technician:
        workflow.assign(ticket, technician, actor=None)
    return technician


def similar_tickets(ticket, limit=5, min_score=0.1):
    """Resolved/closed tickets whose text overlaps with this one."""
    from apps.tickets.choices import Status
    from apps.tickets.models import Ticket

    target = tokenize(f"{ticket.title} {ticket.description}")
    pool = Ticket.objects.filter(status__in=[Status.RESOLVED, Status.CLOSED]).exclude(pk=ticket.pk)
    if ticket.category_id:
        pool = pool.filter(category_id=ticket.category_id)
    scored = [(jaccard(target, tokenize(f"{t.title} {t.description}")), t) for t in pool[:500]]
    return [(round(s, 2), t) for s, t in sorted(scored, key=lambda x: -x[0]) if s >= min_score][:limit]


# Where a query word is found matters: a hit in the title or keywords says far
# more than a passing mention somewhere in a long article body.
FIELD_WEIGHTS = {"title": 3, "keywords": 3, "summary": 2, "body": 1}


def score_article(query_tokens, article):
    if not query_tokens:
        return 0.0
    fields = {
        "title": article.title,
        "keywords": article.keywords.replace(",", " "),
        "summary": article.summary,
        "body": article.body,
    }
    earned = sum(w * len(query_tokens & tokenize(fields[f])) for f, w in FIELD_WEIGHTS.items())
    return earned / (sum(FIELD_WEIGHTS.values()) * len(query_tokens))


SAME_CATEGORY_BONUS = 0.1


def related_articles(text, user=None, limit=3, min_score=0.12, category=None):
    """Rank published KB articles for free text (a search query or a ticket).

    Pass the viewing user so employees never see internal runbooks, and the
    ticket's category so articles from the same area rank higher.
    """
    from apps.kb.models import Article

    query = tokenize(text)
    pool = Article.objects.visible_to(user).select_related("category")
    scored = []
    for article in pool[:1000]:
        score = score_article(query, article)
        if category is not None and article.category_id == category.pk and score > 0:
            score += SAME_CATEGORY_BONUS
        scored.append((score, article))
    return [a for s, a in sorted(scored, key=lambda x: -x[0]) if s >= min_score][:limit]
