from django import template

register = template.Library()

@register.filter
def get(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    if hasattr(dictionary, '__getitem__'):
        try:
            return dictionary[key]
        except (KeyError, IndexError, TypeError):
            return ''
    return ''
