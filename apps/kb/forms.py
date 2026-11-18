from django import forms
from django.utils.text import slugify
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy

from .models import Article

RESERVED_SLUGS = {"new"}  # would collide with the /kb/new/ page


class ArticleForm(forms.ModelForm):
    slug = forms.SlugField(required=False, max_length=200, label=gettext_lazy("Slug"), help_text=gettext_lazy("Part of the article's web address. Leave blank to build it from the title."))

    class Meta:
        model = Article
        fields = ["title", "slug", "summary", "body", "keywords", "category", "audience", "status"]
        labels = {"title": gettext_lazy("Title"), "summary": gettext_lazy("Summary"), "body": gettext_lazy("Body"), "keywords": gettext_lazy("Keywords"),
                  "category": gettext_lazy("Category"), "audience": gettext_lazy("Audience"), "status": gettext_lazy("Status")}
        widgets = {"body": forms.Textarea(attrs={"rows": 16}), "summary": forms.Textarea(attrs={"rows": 2})}

    def clean_slug(self):
        slug = self.cleaned_data.get("slug", "")
        if slug in RESERVED_SLUGS:
            raise forms.ValidationError(gettext("That address is reserved. Choose another."))
        return slug

    def clean(self):
        data = super().clean()
        if not data.get("slug") and data.get("title") and "slug" not in self.errors:
            base = slugify(data["title"])[:190] or "article"
            if base in RESERVED_SLUGS:
                base += "-article"
            taken = Article.objects.exclude(pk=self.instance.pk)
            slug, n = base, 2
            while taken.filter(slug=slug).exists():
                slug, n = f"{base}-{n}", n + 1
            data["slug"] = slug
            self.instance.slug = slug
        return data
