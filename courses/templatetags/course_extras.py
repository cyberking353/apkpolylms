from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_item(d, key):
    return d.get(key) if d else None


LUCIDE_MAP = {
    '📚': 'book-open',
    '🔬': 'microscope',
    '📐': 'shapes',
    '⚗️': 'flask-conical',
    '⚗': 'flask-conical',
    '🌍': 'globe',
    '🎨': 'palette',
    '🧠': 'brain',
    '⚖️': 'scale',
    '⚖': 'scale',
    '🔐': 'lock-keyhole',
    '🧮': 'calculator',
    '🤖': 'bot',
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
    '⏱': 'timer',
    '⚡': 'zap',
    '💬': 'message-circle',
    '💻': 'laptop',
    '🔌': 'plug',
    '🔢': 'list-ordered',
}


def _is_emoji(s):
    return any(
        0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF or
        0x2190 <= ord(c) <= 0x21FF or 0x2300 <= ord(c) <= 0x23FF or
        0x2B00 <= ord(c) <= 0x2BFF or ord(c) in (0xFE0F, 0x200D)
        for c in s
    )


@register.filter(name='lucide', is_safe=True)
def lucide(value, icon_class=''):
    """Convert a stored icon value (emoji or lucide name) into a lucide icon."""
    text = str(value or '').replace('\ufe0f', '')
    name = LUCIDE_MAP.get(text) or LUCIDE_MAP.get(text.strip())
    if not name:
        name = text.strip() if (text.strip() and not _is_emoji(text)) else 'sparkles'
    cls = f' class="{icon_class}"' if icon_class else ''
    return mark_safe(f'<i data-lucide="{name}"{cls}></i>')
