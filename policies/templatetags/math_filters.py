from django import template
register = template.Library()

@register.filter
def abs(value):
    try:
        return abs(int(value))
    except (ValueError, TypeError):
        return value
