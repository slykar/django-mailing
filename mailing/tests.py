import pytest
import uuid

from unittest import mock
from contextlib import contextmanager
from pytest_mock import MockFixture
from collections import Counter

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.dispatch.dispatcher import receiver, Signal
from django.template import engines
from django.template.loader import get_template

from mailing.mailer import EmailName, Mailer, before_render, before_send, after_send

TestMail = EmailName('test_mail')

TEST_EMAIL_SUBJECT = 'This is a test mail -- {{ test_data }}'
TEST_EMAIL_RECIPIENTS = ['sylwester.kardziejonek@apptimia.com']
TEST_EMAIL_TEST_DATA = str(uuid.uuid4())

TEST_EMAIL_RENDER_CONTEXT = {
    'test_data': TEST_EMAIL_TEST_DATA
}


@contextmanager
def signal_listener(signal, sender):
    listener = mock.Mock()
    signal.connect(listener, sender=sender)
    yield listener
    signal.disconnect(listener, sender=sender)


@pytest.fixture
def email_template():
    return EmailMultiAlternatives(
        to=TEST_EMAIL_RECIPIENTS,
        subject=engines['django'].from_string(TEST_EMAIL_SUBJECT),
        body=get_template('_test/test-email.txt'),
        alternatives=[(get_template('_test/test-email.html'), 'text/html')]
    )


@pytest.fixture
def mailer(email_template):
    m = Mailer()
    m.register(TestMail, email_template)
    return m


def test_can_register_email(email_template):
    mailer = Mailer()

    mailer.register(TestMail, email_template)
    registered_template = mailer.get_template(TestMail)

    assert registered_template is email_template


def test_can_send_email(mailer):
    mailer.send(TestMail)
    assert len(mail.outbox) == 1, 'A single email should be sent out'


@pytest.mark.parametrize('signal,expected_params', [
    (before_render, {'mailer', 'template_name', 'email_template', 'context'}),
    (before_send, {'mailer', 'template_name', 'email', 'context'}),
    (after_send, {'mailer', 'template_name', 'email', 'context', 'sent_count'}),
])
def test_signal_sends_expected_params(mocker: MockFixture, mailer: Mailer, signal: Signal, expected_params: set):

    def _check_params(**kwargs):
        signal_params = set(kwargs.keys())
        assert expected_params <= signal_params, 'Signal should receive expected params'

    signal_send = mocker.patch.object(signal, 'send', wraps=_check_params)
    mailer.send(TestMail, context=TEST_EMAIL_RENDER_CONTEXT)
    assert signal_send.called, 'Signal was not triggered at all. Could not validate received listener params.'


@pytest.mark.parametrize('email_property', ['subject', 'body'])
def test_should_render_template_property(mailer: Mailer, email_property: str):
    mailer.send(TestMail, context=TEST_EMAIL_RENDER_CONTEXT)
    sent_mail = mail.outbox[0]
    assert TEST_EMAIL_TEST_DATA in getattr(sent_mail, email_property)


def test_should_render_alternatives(mailer: Mailer):
    mailer.send(TestMail, context=TEST_EMAIL_RENDER_CONTEXT)
    sent_mail = mail.outbox[0]  # type: EmailMultiAlternatives
    for alternative_content, mime_type in sent_mail.alternatives:
        assert TEST_EMAIL_TEST_DATA in alternative_content


def test_can_add_recipients(mailer: Mailer):
    # TODO make this tests more generic (test all merged properties) and parametrize it
    new_recipients = TEST_EMAIL_RECIPIENTS + [
        'totally-random-email@random.com',
        'another-non-existing@random.com'
    ]
    merge_email = EmailMultiAlternatives(to=new_recipients)

    mailer.send(TestMail, merge=merge_email)
    sent_mail = mail.outbox[0]  # type: EmailMultiAlternatives

    expected_recipients = set(TEST_EMAIL_RECIPIENTS) | set(new_recipients)

    assert Counter(expected_recipients) == Counter(sent_mail.to)


@pytest.mark.skip
def test_send_enqueue(mailer: Mailer):
    """
    Implement email enqueueing with Celery queues.
    >>> mailer.enqueue(TestMail)
    """
