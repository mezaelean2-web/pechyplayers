try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import customer_order_email
import database
import resend_diagnostic


class ResendDiagnosticPhase2C8210Test(unittest.TestCase):
    def setUp(self):
        descriptor, self.path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.previous_db = database.DB
        database.DB = self.path
        self.config = {
            "api_key": "test-secret-never-send",
            "from_email": "pedidos@pechy.org",
            "from_name": "PECHY PLAYERS",
        }
        connection = sqlite3.connect(self.path)
        connection.execute("CREATE TABLE sentinel(value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES('unchanged')")
        connection.commit()
        connection.close()

    def tearDown(self):
        database.DB = self.previous_db
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except FileNotFoundError:
                pass

    def execute(self, transport):
        return resend_diagnostic.execute(
            "authorized@example.invalid", transport=transport,
            config=self.config,
            idempotency_key="pechy-diagnostic-email-fixed-test-nonce",
        )

    def test_request_independiente_shape_contenido_timeout_y_una_sola_llamada(self):
        calls = []

        def transport(payload, api_key, timeout, key):
            calls.append((payload, api_key, timeout, key))
            return 201, b'{"id":"diagnostic-message-one"}'

        result = self.execute(transport)
        self.assertEqual(result["result"], "DIAGNOSTIC_SUCCESS")
        self.assertEqual(result["calls"], 1)
        self.assertEqual(len(calls), resend_diagnostic.MAX_REAL_RESEND_CALLS)
        payload, api_key, timeout, key = calls[0]
        self.assertEqual(payload, {
            "from": "PECHY PLAYERS <pedidos@pechy.org>",
            "to": ["authorized@example.invalid"],
            "subject": resend_diagnostic.SUBJECT,
            "text": resend_diagnostic.TEXT,
            "html": resend_diagnostic.HTML,
        })
        self.assertEqual(timeout, customer_order_email.HTTP_TIMEOUT_SECONDS)
        self.assertEqual(key, "pechy-diagnostic-email-fixed-test-nonce")
        self.assertEqual(api_key, "test-secret-never-send")

    def test_success_200_y_201(self):
        for status in (200, 201):
            with self.subTest(status=status):
                result = self.execute(lambda *_: (status, b'{"id":"one"}'))
                self.assertEqual(result["result"], "DIAGNOSTIC_SUCCESS")
                self.assertEqual(result["http_status"], status)
                self.assertEqual(result["provider_message_id"], "one")

    def test_errores_http_se_clasifican_sin_mostrar_message(self):
        cases = (
            (400, "validation_error", "The `from` field is invalid.", "provider_http_400_validation_error_from"),
            (400, "validation_error", "The `to` field is invalid.", "provider_http_400_validation_error_to"),
            (400, "validation_error", "unsafe arbitrary detail", "provider_http_400_validation_error_unknown"),
            (422, "invalid_from_address", "unsafe arbitrary detail", "provider_http_422_invalid_from_address"),
            (403, "invalid_api_key", "unsafe arbitrary detail", "provider_http_403_invalid_api_key"),
        )
        for status, name, message, expected in cases:
            with self.subTest(expected=expected):
                body = json.dumps({"name": name, "message": message}).encode()

                def transport(*_, code=status, data=body):
                    raise urllib.error.HTTPError("https://api.resend.com/emails", code, "redacted", {}, io.BytesIO(data))

                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    result = self.execute(transport)
                self.assertEqual(result["result"], "DIAGNOSTIC_PROVIDER_ERROR")
                self.assertEqual(result["safe_code"], expected)
                self.assertEqual(result["calls"], 1)
                self.assertNotIn(message, repr(result) + stdout.getvalue() + stderr.getvalue())

    def test_timeout_y_red(self):
        def timeout(*_):
            raise TimeoutError()

        def network(*_):
            raise urllib.error.URLError("sensitive network detail")

        for transport, code in ((timeout, "provider_timeout"), (network, "provider_network_error")):
            with self.subTest(code=code):
                result = self.execute(transport)
                self.assertEqual(result["safe_code"], code)
                self.assertEqual(result["calls"], 1)

    def test_no_escribe_db_ni_llama_bold_o_fulfillment(self):
        before = Path(self.path).read_bytes()
        with mock.patch("customer_bold_payments.create_or_reuse_checkout") as bold, \
             mock.patch("customer_fulfillment.fulfill_customer_order") as fulfillment:
            result = self.execute(lambda *_: (200, b'{"id":"one"}'))
        after = Path(self.path).read_bytes()
        self.assertEqual(result["result"], "DIAGNOSTIC_SUCCESS")
        self.assertEqual(before, after)
        bold.assert_not_called()
        fulfillment.assert_not_called()

    def test_red_real_bloqueada_en_testing(self):
        with mock.patch("customer_order_email._post_resend") as network:
            result = customer_order_email.send_resend_email(
                to="authorized@example.invalid", subject="x", text="x", html_body="<p>x</p>",
                idempotency_key="pechy-diagnostic-email-test", config=self.config,
            )
        network.assert_not_called()
        self.assertEqual(result["safe_code"], "test_network_blocked")

    def test_preflight_rechaza_crlf_none_y_shape_invalido(self):
        key = "pechy-diagnostic-email-test"
        self.assertTrue(resend_diagnostic.preflight("authorized@example.invalid", self.config, key))
        self.assertFalse(resend_diagnostic.preflight("bad\r\n@example.invalid", self.config, key))
        bad_config = dict(self.config, from_name=None)
        self.assertFalse(resend_diagnostic.preflight("authorized@example.invalid", bad_config, key))


if __name__ == "__main__":
    unittest.main()
