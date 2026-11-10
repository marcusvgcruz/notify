"""Testes do endpoint de webhook do Notify.

Cobrem o cálculo de totais e a persistência do evento, com CallMeBot e SMTP
simulados (sem chamadas externas).
"""
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from webhooks.models import Webhook


PAYLOAD = {
    'event_type': 'create_outflow',
    'timestamp': '2026-11-10 14:32:05',
    'product': 'Camisa Polo M',
    'product_cost_price': 39.90,
    'product_selling_price': 89.90,
    'quantity': 2,
    'description': 'Venda no balcão',
}


class SettingsBootTests(TestCase):
    """O settings precisa importar (bug prévio: MAILERS + EMAIL_HOST* quebravam
    o boot no Django 6.1) e expor EMAIL_ADMIN_RECEIVER."""

    def test_settings_sobe_com_email_admin_receiver(self):
        self.assertTrue(hasattr(settings, 'EMAIL_ADMIN_RECEIVER'))
        self.assertTrue(settings.EMAIL_ADMIN_RECEIVER)
        self.assertEqual(settings.EMAIL_ADMIN_RECEIVER, 'admin@example.com')

    def test_settings_sem_conflito_mailers_email_host(self):
        self.assertFalse(hasattr(settings, 'MAILERS'), 'MAILERS não deve coexistir com EMAIL_HOST*')
        self.assertTrue(hasattr(settings, 'EMAIL_BACKEND'))


class WebhookOrderViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    @patch('webhooks.views.send_mail')
    @patch('webhooks.views.CallMeBot')
    def test_post_grava_evento_e_calcula_totais(self, mock_callmebot, mock_send_mail):
        response = self.client.post(
            '/api/v1/webhooks/order/',
            PAYLOAD,
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        # total = 89.90 * 2 = 179.80; lucro = 179.80 - (39.90 * 2) = 100.00
        self.assertAlmostEqual(data['total_value'], 179.80, places=2)
        self.assertAlmostEqual(data['profit_value'], 100.00, places=2)
        self.assertEqual(data['product'], 'Camisa Polo M')

        webhook = Webhook.objects.get()
        self.assertEqual(webhook.event_type, 'create_outflow')

        # CallMeBot e e-mail disparados (simulados)
        mock_callmebot.return_value.send_message.assert_called_once()
        mock_send_mail.assert_called_once()
        self.assertEqual(
            mock_send_mail.call_args.kwargs['recipient_list'],
            ['admin@example.com'],
        )

    @patch('webhooks.views.send_mail')
    @patch('webhooks.views.CallMeBot')
    def test_envio_nao_interrompe_gravacao(self, mock_callmebot, mock_send_mail):
        """Se o CallMeBot falhar, o evento já gravado não deve sumir."""
        mock_callmebot.return_value.send_message.side_effect = RuntimeError('cb down')

        with self.assertRaises(RuntimeError):
            self.client.post('/api/v1/webhooks/order/', PAYLOAD, format='json')

        # O evento foi gravado antes do envio (comportamento documentado)
        self.assertEqual(Webhook.objects.count(), 1)
