from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.core.reference_data import ensure_categories
from apps.kb.loader import load_all
from apps.kb.models import Article


class Command(BaseCommand):
    help = "Create or update knowledge base articles from apps/kb/articles/*.md (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        _, categories = ensure_categories()
        author = User.objects.filter(role=User.Role.SUPERVISOR).order_by("pk").first()
        created = updated = 0
        for f in load_all():
            if f.category and f.category not in categories:
                self.stdout.write(self.style.WARNING(f"{f.slug}: unknown category '{f.category}', left empty"))
            _, was_created = Article.objects.update_or_create(
                slug=f.slug,
                defaults={
                    "title": f.title,
                    "summary": f.summary,
                    "body": f.body,
                    "keywords": f.keywords,
                    "category": categories.get(f.category),
                    "audience": f.audience,
                    "status": Article.Status.PUBLISHED,
                    "author": author,
                },
            )
            created += was_created
            updated += not was_created
        self.stdout.write(self.style.SUCCESS(f"Knowledge base: {created} created, {updated} updated."))
