from standardweb.lib import helpers as h

from django import template


register = template.Library()


@register.tag
def git_revision(parser, token):
    return GitRevisionNode()


class GitRevisionNode(template.Node):
    def __init__(self):
        pass

    def render(self, context):
        return h.git_revision