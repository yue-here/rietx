# `py:fields`: a model's fields as one Python-domain directive (WP-2022).
#
# The API reference (`reference_pages.py`) renders each model as a `py:class`
# and its fields as attributes.  One `py:attribute` a field costs about sixty
# characters of fence and options each, which took the page of 102 models and
# 826 fields from 38 000 characters to 80 000, over the page contract's cap,
# and pydata spaced the fields as whole entries.  This directive takes one
# field a line in its body, written as the signature reads,
#
#     name: annotation = default
#
# and renders them as the signatures of one object: stacked lines in one list,
# each with its own anchor, its annotation linked where the domain describes
# the type, and indexed as an `attribute`, so `{py:attr}` finds it.  MyST hands
# a directive only its first line as an argument, so the signatures are read
# from the body.

from docutils.statemachine import StringList as _StringList
from sphinx.domains.python import PyAttribute as _PyAttribute


class PyFields(_PyAttribute):
    """Each body line a field, `name: annotation = default`."""

    required_arguments = 0
    optional_arguments = 0
    has_content = True

    def run(self):
        self._fields = [line for line in self.content if line.strip()]
        self.content = _StringList()
        # A model's twenty fields would bury the page's sections in its contents.
        self.options.setdefault("no-contents-entry", True)
        return super().run()

    def get_signatures(self) -> list[str]:
        return self._fields

    def handle_signature(self, sig, signode):
        name, _, rest = sig.partition(":")
        annotation, equals, default = rest.partition(" = ")
        self.options["type"] = annotation.strip()
        if equals:
            self.options["value"] = default.strip()
        else:
            self.options.pop("value", None)
        return super().handle_signature(name.strip(), signode)

    def add_target_and_index(self, name_cls, sig, signode):
        # Registered as the attribute it is, so `{py:attr}` resolves to it:
        # the domain declares no "fields" object type.
        objtype, self.objtype = self.objtype, "attribute"
        try:
            super().add_target_and_index(name_cls, sig, signode)
        finally:
            self.objtype = objtype


def setup(app):
    app.add_directive_to_domain("py", "fields", PyFields)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
