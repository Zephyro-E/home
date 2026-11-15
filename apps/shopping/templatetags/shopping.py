from django import template
from django.utils.translation import gettext as _

register = template.Library()


@register.filter
def vote_buttons(item):
    """(valor, icono, recuento, etiqueta accesible) de los dos botones de voto."""
    return [
        (1, "thumbs-up", item.up_count, _("Votar a favor")),
        (-1, "thumbs-down", item.down_count, _("Votar en contra")),
    ]
