from django import template

register = template.Library()

@register.filter(name='split')
def split(value, delimiter=','):
    """Split a string into a list on the given delimiter"""
    if value:
        return value.split(delimiter)
    return [] 