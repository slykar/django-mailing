from typing import NamedTuple

import celery
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render
from django.template.loader import get_template, render_to_string

from mailing.emails import html_alternative_template

mailer = object()
settings = object()
InvoiceEmail = object()


class InvoiceEmailSerializer:
    pass


class InvitationContext(NamedTuple):
    order_id: int


class EmailTask(celery.Task):
    pass


@celery.task(base=EmailTask)
def send_email(template_name, context):
    mailer.resolve()


@mailer.register(InvoiceEmail)
def invoice_email(context: InvitationContext):
    return EmailMultiAlternatives(
        subject=f'You have been invited to {settings.PROJECT_NAME}.',
        bcc=settings.EMAIL_BCC_USER_INVITATION,
        body=get_template('email/no-body.txt'),
        alternatives=[render_to_string('postmark/user_invitation.html')]
    )
