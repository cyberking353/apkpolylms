from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_item(d, key):
    return d.get(key) if d else None


LUCIDE_MAP = {
    '📚': 'book-open',
    '📝': 'clipboard-list',
    '📄': 'file-text',
    '🎓': 'graduation-cap',
    '👨\u200d🎓': 'graduation-cap',
    '🏫': 'school',
    '🏠': 'house',
    '📊': 'chart-column',
    '✉': 'mail',
    '👤': 'user',
    '👥': 'users',
    '👨\u200d🏫': 'presentation',
    '🚪': 'log-out',
    '🔔': 'bell',
    '🗑': 'trash',
    '📎': 'paperclip',
    '📌': 'pin',
    '📅': 'calendar',
    '🗓': 'calendar',
    '🖥': 'monitor',
    '🔴': 'circle',
    '📥': 'download',
    '📤': 'upload',
    '📢': 'megaphone',
    '🏆': 'trophy',
    '🎉': 'party-popper',
    '⭐': 'star',
    '🔑': 'key',
    '🔒': 'lock',
    '🔍': 'search',
    '🔄': 'refresh-cw',
    '📋': 'clipboard-list',
    '🎥': 'clapperboard',
    '🎬': 'clapperboard',
    '🎯': 'target',
    '🎲': 'dice-5',
    '🏁': 'flag',
    '👁': 'eye',
    '👋': 'hand',
    '🙈': 'eye-off',
    '😔': 'circle-x',
    '🚫': 'ban',
    '⚠': 'triangle-alert',
    '✅': 'circle-check',
    '✏': 'pencil',
    '✎': 'pencil',
    '✓': 'check',
    '✗': 'x',
    '✕': 'x',
    '➕': 'plus',
    '←': 'arrow-left',
    '→': 'arrow-right',
    '⚙': 'settings',
    '☰': 'menu',
    '⏳': 'hourglass',
    '⏱': 'stopwatch',
}


@register.filter(name='lucide', is_safe=True)
def lucide(value, icon_class=''):
    """Convert a stored icon value (emoji or lucide name) into a lucide icon."""
    text = str(value or '').replace('\ufe0f', '')
    name = LUCIDE_MAP.get(text) or LUCIDE_MAP.get(text.strip()) or text.strip()
    if not name:
        name = 'sparkles'
    cls = f' class="{icon_class}"' if icon_class else ''
    return mark_safe(f'<i data-lucide="{name}"{cls}></i>')
