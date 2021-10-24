from typing import NamedTuple

from django.conf import settings
from django.core.mail.message import EmailMultiAlternatives
from django.template.loader import get_template

from mailing.mailer import EmailName, mailer

UserInvitation = EmailName()


class InvoiceEmail(NamedTuple):
    order_id: int


def html_alternative_template(template_name):
    return get_template(template_name), 'text/html'


mailer.register(UserInvitation, EmailMultiAlternatives(
    subject=f'You have been invited to {settings.PROJECT_NAME}.',
    bcc=settings.EMAIL_BCC_USER_INVITATION,
    body=get_template('email/no-body.txt'),
    alternatives=[html_alternative_template('postmark/user_invitation.html'),
                  'SomePDFRendererAttachment()']
))

# ======================================================================
# Showcase Note
# ----------------------------------------------------------------------
# Below is just an example usage of the mailer.
# I've extracted it from other application module just for the showcase.
# ======================================================================

def send_user_invitation_email(user_invitation: dict):
    """
    Send an email with invitation link to registration page on frontend.
    It's sent by administrators to different types of users.
    The invitation is authorized with a JWT token.
    """
    invitation_token = get_user_invitation_token(user_invitation)
    email_context = {
        'action_url': get_user_invite_url(invitation_token),
        'project_name': settings.PROJECT_NAME
    }

    mailer.send(UserInvitation, context=email_context, merge=EmailMultiAlternatives(
        to=[user_invitation['email']]
    ))

    # enqueue example if we want to async send the email in case it takes long time
    # to generate Invoice PDF, etc.
    # pass the minimum required context and load all data in the async job
    mailer.enqueue(InvoiceEmail(order_id=123))
