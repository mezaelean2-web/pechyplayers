try:
    from tests._bootstrap import TEST_DB, REAL_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB, REAL_DB

import hashlib
import contextlib
import io
import json
import logging
import os
import sqlite3
import tempfile
import unittest
import urllib.error
from unittest import mock

import customer_order_email
import database


class ResendHttpForensicsPhase2C8211Test(unittest.TestCase):
    def error(self, body=b"", *, headers=None, status=400):
        return urllib.error.HTTPError(
            "https://api.resend.com/emails", status, "redacted",
            headers, io.BytesIO(body),
        )

    def inspect(self, body=b"", *, headers=None, status=400):
        return customer_order_email.inspect_resend_http_error(
            self.error(body, headers=headers, status=status)
        )[0]

    def test_body_vacio_headers_ausentes(self):
        diagnostic = self.inspect()
        self.assertFalse(diagnostic["body_present"])
        self.assertEqual(diagnostic["response_body_bytes_read"], 0)
        self.assertFalse(diagnostic["body_truncated"])
        self.assertEqual(diagnostic["json_parse"], "not_attempted")
        self.assertFalse(diagnostic["content_type_present"])

    def test_json_oficial_y_validation_error_conserva_safe_code(self):
        body = json.dumps({
            "name": "validation_error", "statusCode": 400,
            "message": "The `to` field contains FAKE_SECRET_DO_NOT_LEAK",
        }).encode()
        error = self.error(body, headers={"Content-Type": "application/json"})
        code, diagnostic = customer_order_email._safe_http_error_details(error)
        self.assertEqual(code, "provider_http_400_validation_error_to")
        self.assertEqual(diagnostic["json_parse"], "ok")
        self.assertEqual(diagnostic["json_top_level_type"], "object")
        self.assertTrue(diagnostic["name_allowlisted"])
        self.assertTrue(diagnostic["message_present"])
        self.assertTrue(diagnostic["statusCode_present"])
        self.assertNotIn("FAKE_SECRET_DO_NOT_LEAK", repr(diagnostic))

    def test_json_invalido_array_string_y_tipos_superiores(self):
        cases = (
            (b"not-json", "failed", "unknown"),
            (b"[]", "ok", "array"),
            (b'"text"', "ok", "string"),
            (b"123", "ok", "number"),
            (b"null", "ok", "null"),
        )
        for body, parse, top_type in cases:
            with self.subTest(top_type=top_type):
                diagnostic = self.inspect(body)
                self.assertEqual(diagnostic["json_parse"], parse)
                self.assertEqual(diagnostic["json_top_level_type"], top_type)

    def test_name_ausente_no_string_desconocido_y_unknown_keys(self):
        cases = (
            ({"message": "secret"}, False, "absent", False),
            ({"name": 123}, True, "non_string", False),
            ({"name": "invented", "extra_secret": "secret"}, True, "string", False),
        )
        for payload, present, kind, allowlisted in cases:
            with self.subTest(kind=kind):
                diagnostic = self.inspect(json.dumps(payload).encode())
                self.assertEqual(diagnostic["name_present"], present)
                self.assertEqual(diagnostic["name_type"], kind)
                self.assertEqual(diagnostic["name_allowlisted"], allowlisted)
        self.assertTrue(diagnostic["unknown_keys_present"])
        self.assertNotIn("extra_secret", repr(diagnostic))

    def test_truncamiento_lee_sentinel_y_hashea_solo_limite(self):
        body = b"x" * (customer_order_email.MAX_ERROR_BODY_BYTES + 100)
        diagnostic = self.inspect(body)
        self.assertTrue(diagnostic["body_truncated"])
        self.assertEqual(diagnostic["response_body_bytes_read"], 4097)
        self.assertEqual(diagnostic["response_body_bytes_analyzed"], 4096)
        self.assertEqual(
            diagnostic["response_body_sha256"], hashlib.sha256(body[:4096]).hexdigest()
        )

    def test_content_type_charset_y_content_metadata_allowlisted(self):
        cases = (
            ({"Content-Type": "application/json"}, "application/json", None, "ok"),
            ({"Content-Type": "application/json; charset=utf-8"}, "application/json", "utf-8", "ok"),
            ({"Content-Type": "text/html"}, "text/html", None, "ok"),
            ({}, None, None, "ok"),
            ({"Content-Type": "application/json; charset=made-up-secret"}, "application/json", "unknown", "not_attempted"),
        )
        for headers, media_type, charset, parse in cases:
            with self.subTest(headers=bool(headers), charset=charset):
                diagnostic = self.inspect(b"{}", headers=headers)
                self.assertEqual(diagnostic["content_type"], media_type)
                self.assertEqual(diagnostic["charset"], charset)
                self.assertEqual(diagnostic["json_parse"], parse)

    def test_content_length_encoding_no_exponen_valores_arbitrarios(self):
        diagnostic = self.inspect(b"{}", headers={
            "Content-Type": "application/fake-secret-do-not-leak",
            "Content-Length": "2", "Content-Encoding": "FAKE_SECRET_DO_NOT_LEAK",
            "X-Arbitrary": "fake-person@example.invalid",
        })
        self.assertEqual(diagnostic["content_length"], 2)
        self.assertEqual(diagnostic["content_type"], "unexpected")
        self.assertEqual(diagnostic["content_encoding"], "unknown")
        exposed = repr(diagnostic)
        self.assertNotIn("FAKE_SECRET_DO_NOT_LEAK", exposed)
        self.assertNotIn("fake-person@example.invalid", exposed)

    def test_read_error_es_seguro_y_body_solo_se_lee_una_vez(self):
        class BrokenBody:
            calls = 0
            def read(self, *_):
                self.calls += 1
                raise OSError("FAKE_API_KEY_DO_NOT_LEAK")
            def close(self):
                pass
        body = BrokenBody()
        error = urllib.error.HTTPError("https://api.resend.com/emails", 400, "redacted", {}, body)
        code, diagnostic = customer_order_email._safe_http_error_details(error)
        self.assertEqual(code, "provider_http_400")
        self.assertEqual(body.calls, 1)
        self.assertTrue(diagnostic["body_read_error"])
        self.assertNotIn("FAKE_API_KEY_DO_NOT_LEAK", repr(diagnostic))

    def test_request_urllib_exacto_sin_red(self):
        captured = {}
        class Response:
            status = 200
            def read(self): return b'{"id":"fake"}'
            def __enter__(self): return self
            def __exit__(self, *_): return False
        def fake_urlopen(request, timeout):
            captured.update(request=request, timeout=timeout)
            return Response()
        payload = {"from": "A <a@example.invalid>", "to": ["b@example.invalid"],
                   "subject": "s", "text": "t", "html": "<p>h</p>"}
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            customer_order_email._post_resend(payload, "fake-api-key", 8, "safe-idempotency-key")
        request = captured["request"]
        headers = {key.casefold(): value for key, value in request.header_items()}
        self.assertEqual(request.full_url, "https://api.resend.com/emails")
        self.assertEqual(request.method, "POST")
        self.assertIsInstance(request.data, bytes)
        self.assertEqual(json.loads(request.data.decode("utf-8")), payload)
        self.assertEqual(set(headers), {"authorization", "content-type", "user-agent", "idempotency-key"})
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(headers["user-agent"], customer_order_email.USER_AGENT)
        self.assertTrue(headers["authorization"].startswith("Bearer "))
        self.assertEqual(headers["idempotency-key"], "safe-idempotency-key")
        self.assertNotIn("\r", repr(headers))
        self.assertNotIn("\n", repr(headers))

    def test_aislamiento_db_y_testing(self):
        self.assertEqual(os.environ.get("PECHY_TESTING"), "1")
        self.assertNotEqual(TEST_DB, REAL_DB)
        self.assertNotEqual(database._ruta_resuelta_db(), REAL_DB)

    def test_clasificador_sin_name_campos_exactos(self):
        for field in customer_order_email.SAFE_RESEND_VALIDATION_FIELDS:
            with self.subTest(field=field):
                message = f"The `{field}` field is invalid."
                self.assertEqual(
                    customer_order_email.classify_resend_message_without_name(message),
                    f"validation_{field}",
                )

    def test_clasificador_conceptos_documentados_y_ambiguedad(self):
        cases = (
            ("The domain is not verified.", "validation_domain"),
            ("Missing API key in the authorization header.", "validation_api_key"),
            ("The request has a missing required field.", "validation_required"),
            ("The idempotency key must be between 1-256 chars.", "validation_idempotency"),
            ("The `from` and `to` fields are invalid.", "validation_unknown"),
            ("The `from` field and domain is not verified.", "validation_unknown"),
            ("unrecognized provider detail", "validation_unknown"),
        )
        for message, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    customer_order_email.classify_resend_message_without_name(message), expected
                )

    def test_clasificador_rechaza_message_ausente_tipo_vacio_y_extremo(self):
        values = (None, 123, "", "   ", "x" * 100_000)
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(
                    customer_order_email.classify_resend_message_without_name(value),
                    "validation_unknown",
                )

    def test_estructura_observada_ficticia_clasifica_sin_cambiar_safe_code(self):
        body = json.dumps({
            "message": "The `from` field is invalid.", "statusCode": 400,
        }).encode()
        code, diagnostic = customer_order_email._safe_http_error_details(
            self.error(body, headers={"Content-Type": "application/json", "Content-Length": str(len(body))})
        )
        self.assertEqual(code, "provider_http_400")
        self.assertEqual(diagnostic["json_parse"], "ok")
        self.assertEqual(diagnostic["json_top_level_type"], "object")
        self.assertFalse(diagnostic["name_present"])
        self.assertTrue(diagnostic["message_present"])
        self.assertTrue(diagnostic["statusCode_present"])
        self.assertFalse(diagnostic["unknown_keys_present"])
        self.assertEqual(diagnostic["message_safe_category"], "validation_from")

    def test_json_invalido_no_inventa_categoria(self):
        diagnostic = self.inspect(b'{"message":')
        self.assertEqual(diagnostic["json_parse"], "failed")
        self.assertEqual(diagnostic["message_safe_category"], "validation_unknown")

    def test_secretos_no_salen_ni_se_persisten_en_metadata_o_safe_code(self):
        secrets = (
            "FAKE_SECRET_DO_NOT_LEAK", "fake-person@example.invalid",
            "FAKE_API_KEY_DO_NOT_LEAK",
        )
        body = json.dumps({
            "message": "The `to` field is invalid. " + " ".join(secrets),
            "statusCode": 400,
        }).encode()
        stdout, stderr, logs = io.StringIO(), io.StringIO(), io.StringIO()
        handler = logging.StreamHandler(logs)
        logger = logging.getLogger("resend-forensics-test")
        logger.addHandler(handler)
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code, diagnostic = customer_order_email._safe_http_error_details(self.error(body))
        finally:
            logger.removeHandler(handler)
        self.assertEqual(code, "provider_http_400")
        self.assertEqual(diagnostic["message_safe_category"], "validation_to")
        descriptor, path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        try:
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE safe_result(code TEXT, category TEXT)")
            connection.execute("INSERT INTO safe_result VALUES(?,?)", (code, diagnostic["message_safe_category"]))
            connection.commit()
            persisted = repr(connection.execute("SELECT * FROM safe_result").fetchall())
            connection.close()
        finally:
            os.remove(path)
        exposed = repr(diagnostic) + repr(code) + stdout.getvalue() + stderr.getvalue() + logs.getvalue() + persisted
        for secret in secrets:
            self.assertNotIn(secret, exposed)


if __name__ == "__main__":
    unittest.main()
