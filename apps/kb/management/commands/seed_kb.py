from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.core.reference_data import ensure_categories
from apps.kb.loader import load_all
from apps.kb.models import Article


class Command(BaseCommand):
    help = ("Import the knowledge base content pack (apps/kb/articles/*.md). The database is the source of truth: "
            "by default only articles that do not exist yet are added, so edits made in Helply are kept. "
            "--overwrite replaces existing articles with the version from the files.")

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true",
                            help="Replace articles that already exist with the content from the files.")

    @transaction.atomic
    def handle(self, *args, overwrite=False, **options):
        _, categories = ensure_categories()
        author = User.objects.filter(role=User.Role.ADMINISTRATOR).order_by("pk").first()
        created = updated = kept = 0
        for f in load_all():
            if f.category and f.category not in categories:
                self.stdout.write(self.style.WARNING(f"{f.slug}: unknown category '{f.category}', left empty"))
            values = {
                "title": f.title, "summary": f.summary, "body": f.body, "keywords": f.keywords,
                "category": categories.get(f.category), "audience": f.audience,
            }
            article = Article.objects.filter(slug=f.slug).first()
            if article is None:
                Article.objects.create(slug=f.slug, status=Article.Status.PUBLISHED, author=author, **values)
                created += 1
            elif overwrite:
                for field, value in values.items():
                    setattr(article, field, value)
                article.save()
                updated += 1
            else:
                kept += 1
        self.stdout.write(self.style.SUCCESS(
            f"Knowledge base: {created} added, {updated} overwritten, {kept} kept as edited in Helply."
        ))
