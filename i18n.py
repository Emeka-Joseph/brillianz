"""Lightweight English/Arabic translation for the public website.

Templates call {{ _("English text") }}; when the visitor chose Arabic the matching entry from
translations_ar.AR is returned (falling back to English). Database content uses tr(obj, "field"),
which reads `field_ar` when Arabic is active.
"""
from flask import request, g

from translations_ar import AR

LANGS = ("en", "ar")
COOKIE = "lang"


def get_lang():
    if "lang" not in g:
        lang = request.cookies.get(COOKIE, "en") if request else "en"
        g.lang = lang if lang in LANGS else "en"
    return g.lang


def is_ar():
    return get_lang() == "ar"


def _(text, **kwargs):
    out = AR.get(text, text) if is_ar() else text
    return out.format(**kwargs) if kwargs else out


def tr(obj, field):
    """Localised attribute of a model, e.g. tr(service, "summary") -> summary_ar in Arabic."""
    if obj is None:
        return ""
    if is_ar():
        value = getattr(obj, f"{field}_ar", None)
        if value:
            return value
    return getattr(obj, field, "") or ""


def init_app(app):
    app.jinja_env.globals.update(_=_, tr=tr, get_lang=get_lang, is_ar=is_ar)
