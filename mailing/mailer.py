import typing
import copy
import premailer

from django.core.mail import EmailMultiAlternatives
from django.dispatch import Signal
from django.utils.functional import LazyObject

EmailName = object


before_render = Signal(['message', 'context'])
before_send = Signal(['message', 'context'])
after_send = Signal(['message', 'context'])

EmailAlternative = typing.Tuple[str, str]


def can_render(template) -> bool:
    """
    Check whatever we can render the `template`.

    We are limited to duck-typing, because of how Django template backends handle template loading,
    returning a Template class that derivatives from the `object`.
    """
    return hasattr(template, 'render')


def render_email_properties(email_template: EmailMultiAlternatives, context: dict):
    for prop in ('subject', 'body'):
        email_prop = getattr(email_template, prop)
        if can_render(email_prop):
            render_value = email_prop.render(context=context)
            setattr(email_template, prop, render_value)


def get_rendered_email_alternatives(email_template: EmailMultiAlternatives, context: dict)\
        -> typing.List[EmailAlternative]:

    def _render_alternative(email_alternative):
        content, mime_type = email_alternative
        if can_render(content):
            content = content.render(context=context)

        # TODO this might not be the most ideal place for this
        if mime_type == 'text/html':
            content = premailer.transform(content)

        return content, mime_type

    return [_render_alternative(alt) for alt in email_template.alternatives]


def render_email_alternatives(email_template: EmailMultiAlternatives, context: dict):
    email_template.alternatives = get_rendered_email_alternatives(email_template, context)


def render_email_template(email_template: EmailMultiAlternatives, context: dict) -> EmailMultiAlternatives:
    template_copy = copy.copy(email_template)
    render_email_properties(template_copy, context)
    render_email_alternatives(template_copy, context)
    return template_copy


def merge_email(email: EmailMultiAlternatives, merge: EmailMultiAlternatives):
    merge_props = ['to', 'cc', 'bcc', 'attachments', 'headers', 'alternatives']

    for prop in merge_props:
        original_value = getattr(email, prop, [])  # type: list
        merge_value = getattr(merge, prop, [])
        new_value = list(set(original_value) | set(merge_value))
        setattr(email, prop, new_value)

    return email


class Mailer(object):

    def __init__(self):
        self.template_registry = {}  # type: typing.Dict[EmailName, EmailMultiAlternatives]

    def register(self, template_name: EmailName, email_template: EmailMultiAlternatives):
        """
        Registers an email template that can later be used for sending the email
        using it's `template_name` token.
        """
        self.template_registry[template_name] = email_template

    def get_template(self, template_name: EmailName) -> EmailMultiAlternatives:
        return self.template_registry.get(template_name)

    def enqueue(self, template_name: EmailName, context: dict = None):
        """
        Enqueue email to be sent with Celery queue worker. Note, that Celery can only work with JSON payloads,
        so make sure that `context` is JSON serializable.

        Preferably, serialize it with some known interface, described as a ``rest_framework.serializers.Serializer``
        for example.
        """
        raise NotImplementedError('This feature is not yet implemented. '
                                  'It is supposed to enqueue emails for sending with Celery.')

        # celery apply_async(template_name, context)

    def send(self, template_name: EmailName, context: dict = None, merge: EmailMultiAlternatives = None,
             fail_silently=False):

        email_template = self.get_template(template_name)

        before_render.send(sender=template_name,
                           mailer=self,
                           template_name=template_name,
                           email_template=email_template,
                           context=context)

        email = render_email_template(email_template, context)

        email = merge_email(email, merge)

        before_send.send(sender=template_name,
                         mailer=self,
                         template_name=template_name,
                         email=email,
                         context=context)

        sent_count = email.send(fail_silently=fail_silently)

        after_send.send(sender=template_name,
                        mailer=self,
                        template_name=template_name,
                        email=email,
                        context=context,
                        sent_count=sent_count)

        return sent_count


class DefaultMailer(LazyObject):
    def _setup(self):
        self._wrapped = Mailer()


mailer = DefaultMailer()  # type: Mailer
