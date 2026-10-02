from django import template

from apps.kb.markup import render

register = template.Library()


@register.filter
def kb_render(text):
    return render(text or "")
