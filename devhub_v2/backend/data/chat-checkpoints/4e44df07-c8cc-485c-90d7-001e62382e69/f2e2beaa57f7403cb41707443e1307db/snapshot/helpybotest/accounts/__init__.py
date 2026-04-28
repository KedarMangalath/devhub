from django.template import Library

register = Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using key in template"""
    return dictionary.get(key, None)