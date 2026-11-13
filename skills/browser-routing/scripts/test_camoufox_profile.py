#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import ast
import collections
import inspect
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("camoufox_profile.py")
SPEC = importlib.util.spec_from_file_location("camoufox_profile", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakePage:
    url = "data:text/html,<title>Managed Canary</title>"

    def goto(self, url: str, **_kwargs: object) -> None:
        self.url = url

    def wait_for_timeout(self, _milliseconds: int) -> None:
        return None

    def title(self) -> str:
        return "Managed Canary"


class FakeContext:
    def __init__(self) -> None:
        self.pages = [FakePage()]

    def new_page(self) -> FakePage:
        return FakePage()


class FakeCamoufox:
    last_options: dict[str, object] | None = None

    def __init__(self, *, from_options: dict[str, object], persistent_context: bool) -> None:
        self.options = from_options
        self.persistent_context = persistent_context

    def __enter__(self) -> FakeContext:
        type(self).last_options = self.options
        return FakeContext()

    def __exit__(self, *_args: object) -> None:
        return None


class FakeInspectLocator:
    def __init__(self, page: "FakeInspectPage", selector: str) -> None:
        self.page = page
        self.selector = selector

    def inner_text(self, **_kwargs: object) -> str:
        return self.page.body_text

    def evaluate_all(self, _script: str, limits: dict[str, int]) -> dict[str, object]:
        self.page.evaluate_limits = limits
        return self.page.controls_payload


class FakeInspectPage:
    def __init__(
        self,
        *,
        url: str = "https://claude.ai/upgrade/max?token=secret#payment",
        body_text: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        title: str = "Upgrade Max",
        inaccessible: bool = False,
    ) -> None:
        self.url = url
        self.body_text = body_text
        self.page_title = title
        self.inaccessible = inaccessible
        self.goto_calls: list[str] = []
        self.goto_kwargs: list[dict[str, object]] = []
        self.wait_calls: list[int] = []
        self.evaluate_limits: dict[str, int] | None = None
        self.controls_payload = {
            "total": 2,
            "controls": [
                {
                    "tag": "input",
                    "type": "email",
                    "name": "billing-email",
                    "id": "email",
                    "role": "textbox",
                    "aria-label": "Billing email",
                    "placeholder": "name@example.com",
                    "button_text": "",
                    "value": "must-never-escape",
                },
                {
                    "tag": "select",
                    "type": "select-one",
                    "name": "payment-method",
                    "id": "payment-method",
                    "role": "combobox",
                    "aria-label": "Payment method",
                    "placeholder": "",
                    "button_text": "",
                    "options": [
                        {"text": "Card", "value": "card", "selected": True},
                        {"text": "Bank", "value": "bank", "selected": False},
                    ],
                },
            ],
        }
        self.frames = [self]

    def goto(self, url: str, **kwargs: object) -> None:
        self.goto_calls.append(url)
        self.goto_kwargs.append(kwargs)
        self.url = url

    def title(self) -> str:
        return self.page_title

    def wait_for_timeout(self, milliseconds: int) -> None:
        self.wait_calls.append(milliseconds)

    def locator(self, selector: str) -> FakeInspectLocator:
        if self.inaccessible:
            raise RuntimeError("cross-origin access denied?token=must-not-escape")
        return FakeInspectLocator(self, selector)


class FakeInspectContext:
    def __init__(self, page: FakeInspectPage) -> None:
        self.pages = [page]


class FakeInspectCamoufox:
    page = FakeInspectPage()
    closed = False
    entered = False

    def __init__(self, *, from_options: dict[str, object], persistent_context: bool) -> None:
        self.options = from_options
        self.persistent_context = persistent_context

    def __enter__(self) -> FakeInspectContext:
        type(self).entered = True
        type(self).closed = False
        return FakeInspectContext(type(self).page)

    def __exit__(self, *_args: object) -> None:
        type(self).closed = True


class FakeCountrySelect:
    def __init__(self, frame: "FakeSurveyFrame") -> None:
        self.frame = frame

    def count(self) -> int:
        if self.frame.context.missing_country_control_reads > 0:
            self.frame.context.missing_country_control_reads -= 1
            return 0
        return 1

    def evaluate(self, _script: str) -> dict[str, object]:
        return {
            "tag": "select",
            "id": "billingAddress-countryInput",
            "name": "country",
            "value": self.frame.context.country,
            "options": [
                {"value": value, "label": label}
                for value, label in self.frame.context.country_options
            ],
        }

    def select_option(self, *, value: str) -> list[str]:
        self.frame.context.select_calls.append((self.frame.generation, self.frame.selector, value))
        if value in self.frame.context.fail_countries:
            raise RuntimeError("selection failed?client_secret=must-not-escape")
        if value == self.frame.context.original_country and self.frame.context.fail_restore:
            raise RuntimeError("restore failed?token=must-not-escape")
        self.frame.context.country = value
        self.frame.context.generation += 1
        return [value]


class FakeSurveyLocator(FakeInspectLocator):
    def count(self) -> int:
        return 0


class FakeSurveyFrame(FakeInspectPage):
    def __init__(
        self,
        context: "FakeSurveyContext",
        *,
        generation: int,
        kind: str,
    ) -> None:
        country = context.country
        if kind == "main":
            url = "https://claude.ai/upgrade/max?token=top-secret#checkout"
            body = f"Max plan USD 100 today; renews monthly; country {country}"
        elif kind == "address":
            url = "https://js.stripe.com/address?client_secret=hidden"
            body = f"Billing address and tax ID type for {country} token=hidden"
        else:
            url = "https://js.stripe.com/payment?client_secret=hidden"
            body = f"Card number Supported cards include Visa Mastercard for {country}"
        super().__init__(url=url, body_text=body, title=f"{kind}-{generation}")
        self.context = context
        self.generation = generation
        self.kind = kind
        self.selector = ""
        if kind == "address":
            self.controls_payload = {
                "total": 2,
                "controls": [
                    {
                        "tag": "select",
                        "type": "select-one",
                        "name": "country",
                        "id": "billingAddress-countryInput",
                        "role": "combobox",
                        "aria-label": "Country",
                        "placeholder": "",
                        "button_text": "",
                        "options": [{"text": country, "value": country, "selected": True}],
                    },
                    {
                        "tag": "input",
                        "type": "text",
                        "name": "tax-id",
                        "id": "tax-id",
                        "role": "textbox",
                        "aria-label": "Tax ID",
                        "placeholder": "Tax number",
                        "button_text": "",
                        "value": "must-never-escape",
                    },
                ],
            }

    def locator(self, selector: str) -> object:
        self.selector = selector
        if self.kind == "address" and selector == MODULE.PAYMENT_COUNTRY_SELECTOR:
            return FakeCountrySelect(self)
        return FakeSurveyLocator(self, selector)


class FakeSurveyPage(FakeSurveyFrame):
    def __init__(self, context: "FakeSurveyContext") -> None:
        super().__init__(context, generation=context.generation, kind="main")
        self.goto_calls = context.goto_calls
        self.goto_kwargs = context.goto_kwargs
        self.wait_calls = context.wait_calls

    @property
    def frames(self) -> list[FakeSurveyFrame]:
        generation = self.context.generation
        self.context.frame_reads.append(generation)
        return [
            FakeSurveyFrame(self.context, generation=generation, kind="main"),
            FakeSurveyFrame(self.context, generation=generation, kind="address"),
            FakeSurveyFrame(self.context, generation=generation, kind="payment"),
        ]

    @frames.setter
    def frames(self, _value: object) -> None:
        return None


class FakeSurveyContext:
    def __init__(
        self,
        *,
        original_country: str = "KR",
        country_options: list[tuple[str, str]] | None = None,
    ) -> None:
        self.original_country = original_country
        self.country = original_country
        self.country_options = country_options or [
            (original_country, original_country),
            ("JP", "Japan"),
            ("DE", "Germany"),
        ]
        self.generation = 0
        self.fail_countries: set[str] = set()
        self.fail_restore = False
        self.missing_country_control_reads = 0
        self.select_calls: list[tuple[int, str, str]] = []
        self.frame_reads: list[int] = []
        self.goto_calls: list[str] = []
        self.goto_kwargs: list[dict[str, object]] = []
        self.wait_calls: list[int] = []
        self.pages = [FakeSurveyPage(self)]


class FakeSurveyCamoufox:
    context = FakeSurveyContext()
    entered = False
    closed = False

    def __init__(self, *, from_options: dict[str, object], persistent_context: bool) -> None:
        self.options = from_options
        self.persistent_context = persistent_context

    def __enter__(self) -> FakeSurveyContext:
        type(self).entered = True
        type(self).closed = False
        return type(self).context

    def __exit__(self, *_args: object) -> None:
        type(self).closed = True


class CamoufoxProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root_patch = mock.patch.object(MODULE, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def make_profile(self, profile_id: str = "sample") -> Path:
        profile_dir = self.root / profile_id
        (profile_dir / "firefox-profile").mkdir(parents=True)
        config = {
            "navigator.userAgent": "Mozilla/5.0 (Macintosh)",
            "canvas:aaOffset": 7,
            "timezone": "Europe/Berlin",
            "locale:language": "de",
            "locale:region": "DE",
            "geolocation:latitude": 52.5,
            "geolocation:longitude": 13.4,
        }
        MODULE.write_private_json(
            profile_dir / "launch-options.json",
            {
                "env": {
                    "CAMOU_CONFIG_1": json.dumps(config, separators=(",", ":")),
                    "UNRELATED_SECRET": "must-not-survive",
                },
                "proxy": {"server": "socks5://hidden.example:1080"},
                "user_data_dir": str(profile_dir / "firefox-profile"),
            },
        )
        MODULE.write_private_json(
            profile_dir / "profile.json",
            {
                "schema_version": 1,
                "id": profile_id,
                "engine": "camoufox",
                "fingerprint_id": "stable-fingerprint",
                "profile_path": str(profile_dir / "firefox-profile"),
                "proxy": {
                    "country": "DE",
                    "protocol": "socks5",
                    "source": "proxy-pick",
                    "exit_id": "old-exit",
                },
                "target": {"title": "Old", "url": "https://example.com/"},
                "login_allowed": False,
            },
        )
        return profile_dir

    def test_list_and_inspect_are_sanitized(self) -> None:
        self.make_profile()
        listed = MODULE.list_profiles()
        inspected = MODULE.inspect_profile("sample")
        serialized = json.dumps([listed, inspected])
        self.assertEqual([item["id"] for item in listed], ["sample"])
        self.assertEqual(inspected["proxy"]["country"], "DE")
        self.assertNotIn("hidden.example", serialized)
        self.assertNotIn("UNRELATED_SECRET", serialized)

    def test_profile_id_rejects_path_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "profile id"):
            MODULE.inspect_profile("../escape")

    def test_launch_reuses_saved_config_and_closes(self) -> None:
        profile_dir = self.make_profile()
        fingerprint_before = MODULE.device_fingerprint(
            json.loads((profile_dir / "launch-options.json").read_text())
        )
        before = MODULE.decode_config(
            json.loads((profile_dir / "launch-options.json").read_text())["env"]
        )
        with (
            mock.patch.object(MODULE, "Camoufox", FakeCamoufox),
            mock.patch.object(
                MODULE,
                "validate_saved_proxy",
                return_value={"country": "DE", "exit_id": "old-exit"},
            ) as validate,
        ):
            result = MODULE.launch_profile(
                "sample", "data:text/html,<title>Managed Canary</title>", wait_ms=0
            )
        after = MODULE.decode_config(FakeCamoufox.last_options["env"])
        persisted = json.loads((profile_dir / "launch-options.json").read_text())
        self.assertTrue(result["ok"])
        self.assertFalse(result["handoff"])
        self.assertEqual(before, after)
        self.assertEqual(MODULE.device_fingerprint(persisted), fingerprint_before)
        self.assertEqual(set(persisted["env"]), {"CAMOU_CONFIG_1"})
        validate.assert_called_once()
        self.assertFalse((profile_dir / "run-state.json").exists())
        self.assertEqual((profile_dir / ".manager.lock").stat().st_mode & 0o777, 0o600)

    def test_launch_sanitizes_before_proxy_validation_failure(self) -> None:
        profile_dir = self.make_profile()
        with mock.patch.object(
            MODULE,
            "validate_saved_proxy",
            side_effect=RuntimeError("proxy unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "proxy unavailable"):
                MODULE.launch_profile("sample", "https://example.com/", wait_ms=0)
        persisted = json.loads((profile_dir / "launch-options.json").read_text())
        self.assertEqual(set(persisted["env"]), {"CAMOU_CONFIG_1"})

    def test_inspect_page_redacts_url_and_input_value_and_limits_text(self) -> None:
        self.make_profile()
        page = FakeInspectPage()
        FakeInspectCamoufox.page = page
        with (
            mock.patch.object(MODULE, "Camoufox", FakeInspectCamoufox),
            mock.patch.object(
                MODULE,
                "validate_saved_proxy",
                return_value={"country": "DE", "exit_id": "old-exit"},
            ),
        ):
            result = MODULE.inspect_page("sample", text_limit=12)
        self.assertEqual(result["url"], "https://claude.ai/upgrade/max")
        self.assertEqual(result["body_text"], "0123456789AB")
        self.assertTrue(result["body_text_truncated"])
        self.assertNotIn("value", result["controls"][0])
        self.assertEqual(result["controls"][1]["options"][0]["value"], "card")
        self.assertEqual(result["controls_total"], 2)
        self.assertFalse(result["controls_truncated"])
        self.assertEqual(page.wait_calls, [5000])
        self.assertEqual(result["frames"][0]["access"], "available")
        self.assertEqual(page.goto_calls, [])
        self.assertTrue(FakeInspectCamoufox.closed)

    def test_inspect_page_navigates_only_when_url_is_given(self) -> None:
        self.make_profile()
        page = FakeInspectPage()
        FakeInspectCamoufox.page = page
        with (
            mock.patch.object(MODULE, "Camoufox", FakeInspectCamoufox),
            mock.patch.object(MODULE, "validate_saved_proxy"),
        ):
            result = MODULE.inspect_page(
                "sample",
                "https://example.com/pay?session=secret#form",
                text_limit=20,
                wait_ms=1250,
            )
        self.assertEqual(page.goto_calls, ["https://example.com/pay?session=secret#form"])
        self.assertEqual(page.wait_calls, [1250])
        self.assertEqual(result["url"], "https://example.com/pay")
        self.assertTrue(FakeInspectCamoufox.closed)

    def test_inspect_page_reuses_existing_blank_page(self) -> None:
        self.make_profile()
        page = FakeInspectPage(url="about:blank")
        FakeInspectCamoufox.page = page
        with (
            mock.patch.object(MODULE, "Camoufox", FakeInspectCamoufox),
            mock.patch.object(MODULE, "validate_saved_proxy"),
        ):
            result = MODULE.inspect_page("sample", "https://example.com/pay", wait_ms=0)
        self.assertEqual(page.goto_calls, ["https://example.com/pay"])
        self.assertEqual(result["url"], "https://example.com/pay")

    def test_inspect_page_merges_accessible_frames_and_redacts_failure(self) -> None:
        self.make_profile()
        main = FakeInspectPage(body_text="Main checkout")
        child = FakeInspectPage(
            url="https://payments.example/frame?client_secret=hidden#card",
            body_text="Card and bank transfer",
            title="Payment methods",
        )
        child.controls_payload = {
            "total": 1,
            "controls": [
                {
                    "tag": "button",
                    "type": "button",
                    "name": "continue",
                    "id": "continue",
                    "role": "button",
                    "aria-label": "Continue",
                    "placeholder": "",
                    "button_text": "Continue",
                }
            ],
        }
        denied = FakeInspectPage(
            url="https://secure.example/challenge?token=hidden#step",
            inaccessible=True,
        )
        main.frames = [main, child, denied]
        FakeInspectCamoufox.page = main
        with (
            mock.patch.object(MODULE, "Camoufox", FakeInspectCamoufox),
            mock.patch.object(MODULE, "validate_saved_proxy"),
        ):
            result = MODULE.inspect_page("sample", wait_ms=0)
        self.assertEqual(result["body_text"], "Main checkout\n\nCard and bank transfer")
        self.assertEqual(result["controls_total"], 3)
        self.assertEqual(len(result["controls"]), 3)
        self.assertEqual([frame["access"] for frame in result["frames"]], [
            "available",
            "available",
            "unavailable",
        ])
        self.assertEqual(
            result["frames"][1]["url"], "https://payments.example/frame"
        )
        self.assertEqual(
            result["frames"][2],
            {"url": "https://secure.example/challenge", "access": "unavailable"},
        )
        self.assertNotIn("hidden", json.dumps(result))
        self.assertTrue(FakeInspectCamoufox.closed)

    def test_inspect_page_wait_range(self) -> None:
        self.make_profile()
        for wait_ms in (-1, 30_001):
            with self.assertRaisesRegex(ValueError, "wait-ms"):
                MODULE.inspect_page("sample", wait_ms=wait_ms)

    def test_inspect_page_rejects_running_profile_before_launch(self) -> None:
        profile_dir = self.make_profile()
        FakeInspectCamoufox.entered = False
        with (
            mock.patch.object(MODULE, "is_running", return_value=True),
            mock.patch.object(MODULE, "Camoufox", FakeInspectCamoufox),
            mock.patch.object(MODULE, "profile_lock") as lock,
        ):
            with self.assertRaisesRegex(RuntimeError, "running"):
                MODULE.inspect_page("sample")
        lock.assert_not_called()
        self.assertFalse(FakeInspectCamoufox.entered)
        self.assertTrue(profile_dir.exists())

    def test_survey_normalizes_deduplicates_and_limits_countries(self) -> None:
        self.assertEqual(MODULE.normalize_countries(["kr", "JP", "kr"]), ["KR", "JP"])
        with self.assertRaisesRegex(ValueError, "at most"):
            MODULE.normalize_countries(["KR"] * 251)
        with self.assertRaisesRegex(ValueError, "country"):
            MODULE.normalize_countries(["K1"])

    def test_survey_uses_only_exact_select_reenumerates_frames_and_restores(self) -> None:
        profile_dir = self.make_profile()
        context = FakeSurveyContext(original_country="KR")
        FakeSurveyCamoufox.context = context
        with (
            mock.patch.object(MODULE, "Camoufox", FakeSurveyCamoufox),
            mock.patch.object(MODULE, "validate_saved_proxy"),
        ):
            result = MODULE.survey_payment_countries(
                "sample",
                "https://claude.ai/upgrade/max?token=navigation-secret",
                ["jp", "DE", "jp"],
                initial_wait_ms=30_000,
                settle_ms=1250,
            )
        self.assertEqual([item["country"] for item in result["countries"]], ["JP", "DE"])
        self.assertEqual([item["status"] for item in result["countries"]], ["ok", "ok"])
        self.assertEqual(result["restore"], {"attempted": True, "status": "ok"})
        self.assertEqual(context.country, "KR")
        self.assertEqual([call[2] for call in context.select_calls], ["JP", "DE", "KR"])
        self.assertTrue(all(call[1] == MODULE.PAYMENT_COUNTRY_SELECTOR for call in context.select_calls))
        self.assertGreaterEqual(len(set(context.frame_reads)), 3)
        self.assertEqual(context.goto_calls, ["https://claude.ai/upgrade/max?token=navigation-secret"])
        self.assertEqual(
            context.goto_kwargs,
            [{"wait_until": "commit", "timeout": 45_000}],
        )
        self.assertEqual(
            context.wait_calls,
            [30_000, 1250, 1000, 1250, 1000, 1250, 1000],
        )
        serialized = json.dumps(result)
        self.assertNotIn("navigation-secret", serialized)
        self.assertNotIn("client_secret", serialized)
        self.assertNotIn("must-never-escape", serialized)
        self.assertNotIn("token=hidden", serialized)
        self.assertTrue(FakeSurveyCamoufox.closed)
        checkpoint = json.loads(
            (profile_dir / "last-survey-result.json").read_text()
        )
        stage = json.loads((profile_dir / "last-operation.json").read_text())
        self.assertTrue(checkpoint["closed"])
        self.assertEqual(stage["operation"], "survey-payment-countries")
        self.assertEqual(stage["stage"], "complete")
        self.assertNotIn("navigation-secret", json.dumps(checkpoint))
        self.assertEqual(
            set(stage),
            {"schema_version", "operation", "stage", "updated_at"},
        )

    def test_survey_continues_after_country_failure_and_reports_restore_failure(self) -> None:
        self.make_profile()
        context = FakeSurveyContext(original_country="KR")
        context.fail_countries = {"DE"}
        context.fail_restore = True
        FakeSurveyCamoufox.context = context
        with (
            mock.patch.object(MODULE, "Camoufox", FakeSurveyCamoufox),
            mock.patch.object(MODULE, "validate_saved_proxy"),
        ):
            result = MODULE.survey_payment_countries(
                "sample", "https://claude.ai/upgrade/max", ["DE", "JP"],
                initial_wait_ms=0, settle_ms=0,
            )
        self.assertEqual([item["status"] for item in result["countries"]], ["error", "ok"])
        self.assertEqual(result["countries"][0]["failure_stage"], "select-country")
        self.assertEqual(result["countries"][0]["failure_code"], "unexpected-runtime-error")
        self.assertEqual(result["restore"]["status"], "error")
        self.assertEqual(result["restore"]["failure_code"], "unexpected-runtime-error")
        self.assertNotIn("must-not-escape", json.dumps(result))
        self.assertTrue(FakeSurveyCamoufox.closed)

    def test_survey_stop_on_error_prevents_cascading_country_failures(self) -> None:
        self.make_profile()
        context = FakeSurveyContext(original_country="KR")
        context.fail_countries = {"DE"}
        FakeSurveyCamoufox.context = context
        with (
            mock.patch.object(MODULE, "Camoufox", FakeSurveyCamoufox),
            mock.patch.object(MODULE, "validate_saved_proxy"),
        ):
            result = MODULE.survey_payment_countries(
                "sample", "https://claude.ai/upgrade/max", ["DE", "JP"],
                initial_wait_ms=0, settle_ms=0, stop_on_error=True,
            )
        self.assertEqual([item["country"] for item in result["countries"]], ["DE"])
        self.assertEqual(result["countries"][0]["status"], "error")
        self.assertEqual([call[2] for call in context.select_calls], ["DE"])
        self.assertEqual(result["restore"], {"attempted": False, "status": "not-needed"})
        self.assertTrue(FakeSurveyCamoufox.closed)

    def test_survey_failure_codes_are_allowlisted_and_secret_free(self) -> None:
        cases = {
            RuntimeError("exactly one billing country control is required"): "country-control-count",
            RuntimeError("billing country selector is ambiguous"): "country-control-ambiguous",
            RuntimeError("billing country control identity mismatch"): "country-control-identity",
            RuntimeError("billing country control has no selected country"): "country-control-unselected",
            RuntimeError("billing country selection was not accepted"): "country-selection-rejected",
            RuntimeError("billing country did not settle to the requested value"): "country-settle-mismatch",
            RuntimeError("billing country control did not become stable"): "country-control-timeout",
            RuntimeError("secret?client_secret=must-not-escape"): "unexpected-runtime-error",
            ValueError("secret?token=must-not-escape"): "unexpected-error",
        }
        for error, expected in cases.items():
            with self.subTest(error=type(error).__name__, expected=expected):
                code = MODULE.classify_survey_failure(error)
                self.assertEqual(code, expected)
                self.assertNotIn("secret", code)

    def test_wait_for_payment_country_stable_recovers_after_frame_replacement(self) -> None:
        context = FakeSurveyContext(original_country="BH")
        context.missing_country_control_reads = 2
        MODULE.wait_for_payment_country_stable(
            context.pages[0], "BH", timeout_ms=5_000, poll_ms=1_000, stable_reads=2
        )
        self.assertEqual(context.wait_calls, [1_000, 1_000, 1_000])

    def test_wait_for_payment_country_stable_times_out_without_mutation(self) -> None:
        context = FakeSurveyContext(original_country="BH")
        context.missing_country_control_reads = 10
        with self.assertRaisesRegex(RuntimeError, "did not become stable"):
            MODULE.wait_for_payment_country_stable(
                context.pages[0], "BH", timeout_ms=2_000, poll_ms=1_000, stable_reads=2
            )
        self.assertEqual(context.wait_calls, [1_000])
        self.assertEqual(context.select_calls, [])

    def test_survey_reuses_existing_blank_page(self) -> None:
        self.make_profile()
        context = FakeSurveyContext(original_country="KR")
        context.pages[0].url = "about:blank"
        unused_page = FakeSurveyPage(context)
        unused_page.goto = mock.Mock(side_effect=AssertionError("must use first page"))
        context.pages.append(unused_page)
        context.new_page = mock.Mock(side_effect=AssertionError("must reuse page"))
        FakeSurveyCamoufox.context = context
        with (
            mock.patch.object(MODULE, "Camoufox", FakeSurveyCamoufox),
            mock.patch.object(MODULE, "validate_saved_proxy"),
        ):
            result = MODULE.survey_payment_countries(
                "sample", "https://claude.ai/upgrade/max", ["AU"],
                initial_wait_ms=0, settle_ms=0,
            )
        self.assertEqual(result["countries"][0]["status"], "ok")
        context.new_page.assert_not_called()

    def test_survey_rejects_running_profile_before_lock_or_browser(self) -> None:
        self.make_profile()
        FakeSurveyCamoufox.entered = False
        with (
            mock.patch.object(MODULE, "is_running", return_value=True),
            mock.patch.object(MODULE, "profile_lock") as lock,
            mock.patch.object(MODULE, "Camoufox", FakeSurveyCamoufox),
        ):
            with self.assertRaisesRegex(RuntimeError, "running"):
                MODULE.survey_payment_countries(
                    "sample", "https://claude.ai/upgrade/max", ["KR"]
                )
        lock.assert_not_called()
        self.assertFalse(FakeSurveyCamoufox.entered)

    def test_manual_ready_wait_consumes_private_signal(self) -> None:
        profile_dir = self.make_profile()
        signal_path = profile_dir / "survey-ready.json"
        context = FakeSurveyContext(original_country="KR")

        def create_signal(_seconds: float) -> None:
            MODULE.write_private_json(signal_path, {"ready": True})

        with (
            mock.patch.object(MODULE.time, "monotonic", side_effect=[0.0, 0.1]),
            mock.patch.object(MODULE.time, "sleep", side_effect=create_signal),
        ):
            MODULE.wait_for_manual_ready(
                profile_dir, context.pages[0], timeout_seconds=1
            )
        self.assertFalse(signal_path.exists())
        observation = json.loads(
            (profile_dir / "last-survey-observation.json").read_text()
        )
        self.assertTrue(observation["page_alive"])
        self.assertTrue(observation["ready"])
        self.assertEqual(observation["country_control_count"], 1)
        self.assertNotIn("must-never-escape", json.dumps(observation))

    def test_manual_ready_wait_records_page_loss_without_raw_error(self) -> None:
        profile_dir = self.make_profile()

        class DeadPage:
            @property
            def frames(self) -> object:
                raise RuntimeError("page closed?token=must-not-escape")

        with self.assertRaisesRegex(RuntimeError, "became unavailable"):
            MODULE.wait_for_manual_ready(profile_dir, DeadPage(), timeout_seconds=1)
        observation = json.loads(
            (profile_dir / "last-survey-observation.json").read_text()
        )
        self.assertFalse(observation["page_alive"])
        self.assertEqual(observation["error_code"], "page-unavailable")
        self.assertNotIn("must-not-escape", json.dumps(observation))

    def test_manual_ready_survey_uses_same_context_after_signal(self) -> None:
        profile_dir = self.make_profile()
        context = FakeSurveyContext(original_country="KR")
        FakeSurveyCamoufox.context = context
        with (
            mock.patch.object(MODULE, "Camoufox", FakeSurveyCamoufox),
            mock.patch.object(MODULE, "validate_saved_proxy"),
            mock.patch.object(MODULE, "wait_for_manual_ready") as wait_ready,
            mock.patch.object(MODULE, "ensure_not_running") as ensure_stopped,
        ):
            result = MODULE.survey_payment_countries(
                "sample", "https://claude.ai/upgrade/max", ["AU"],
                initial_wait_ms=0, settle_ms=0, manual_ready=True,
                manual_timeout_seconds=600,
            )
        wait_ready.assert_called_once_with(
            profile_dir, context.pages[0], timeout_seconds=600
        )
        ensure_stopped.assert_not_called()
        self.assertEqual(result["countries"][0]["status"], "ok")
        self.assertFalse((profile_dir / "run-state.json").exists())
        self.assertFalse((profile_dir / "survey-ready.json").exists())

    def test_survey_validates_wait_ranges_and_cli_contract(self) -> None:
        self.make_profile()
        self.assertEqual(MODULE.MAX_SURVEY_SETTLE_MS, 15_000)
        for initial, settle in ((-1, 0), (120_001, 0), (0, -1), (0, 15_001)):
            with self.assertRaisesRegex(ValueError, "must be between"):
                MODULE.survey_payment_countries(
                    "sample", "https://claude.ai/upgrade/max", ["KR"],
                    initial_wait_ms=initial, settle_ms=settle,
                )
        args = MODULE.build_parser().parse_args([
            "survey-payment-countries", "sample", "--url", "https://claude.ai/upgrade/max",
            "--country", "KR", "--country", "JP", "--initial-wait-ms", "1234",
            "--settle-ms", "321", "--manual-ready", "--manual-timeout-seconds", "600",
            "--stop-on-error",
        ])
        self.assertEqual(args.country, ["KR", "JP"])
        self.assertEqual(args.initial_wait_ms, 1234)
        self.assertEqual(args.settle_ms, 321)
        self.assertTrue(args.manual_ready)
        self.assertEqual(args.manual_timeout_seconds, 600)
        self.assertTrue(args.stop_on_error)

    def test_survey_frame_output_caps_body_and_controls(self) -> None:
        raw = {
            "url": "https://js.stripe.com/payment?client_secret=hidden",
            "title": "Payment",
            "access": "available",
            "body_text": "x" * (MODULE.SURVEY_FRAME_TEXT_LIMIT + 10),
            "body_text_truncated": False,
            "controls": [
                {
                    "tag": "button",
                    "type": "button",
                    "name": f"method-{index}",
                    "id": f"method-{index}",
                    "role": "button",
                    "aria-label": "Card",
                    "placeholder": "",
                    "button_text": "Card",
                }
                for index in range(MODULE.MAX_SURVEY_CONTROLS + 5)
            ],
            "controls_total": MODULE.MAX_SURVEY_CONTROLS + 5,
        }
        compact = MODULE.compact_survey_frame(raw)
        self.assertEqual(len(compact["body_text"]), MODULE.SURVEY_FRAME_TEXT_LIMIT)
        self.assertEqual(len(compact["controls"]), MODULE.MAX_SURVEY_CONTROLS)
        self.assertTrue(compact["body_text_truncated"])
        self.assertTrue(compact["controls_truncated"])
        self.assertNotIn("client_secret", json.dumps(compact))

    def test_survey_call_graph_has_no_forbidden_interactions(self) -> None:
        functions = (
            MODULE.survey_payment_countries,
            MODULE.select_payment_country,
            MODULE.sample_payment_country,
            MODULE.find_payment_country_select,
        )
        calls = [
            node.func.attr
            for function in functions
            for node in ast.walk(ast.parse(inspect.getsource(function)))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        for forbidden in ("click", "fill", "type", "press", "submit", "requestSubmit"):
            self.assertNotIn(forbidden, calls)
        self.assertEqual(calls.count("select_option"), 1)
        self.assertEqual(
            MODULE.PAYMENT_COUNTRY_SELECTOR,
            "select#billingAddress-countryInput[name=country]",
        )

    def test_manual_review_call_graph_only_changes_country_after_user_event(self) -> None:
        functions = (
            MODULE.manual_payment_country_review,
            MODULE.run_manual_review_cycle,
            MODULE.ManualPaymentCountryController.refresh,
            MODULE.ManualPaymentCountryController.handle,
            MODULE.payment_country_options,
            MODULE.select_payment_country,
            MODULE.find_payment_country_select,
        )
        calls = [
            node.func.attr
            for function in functions
            for node in ast.walk(
                ast.parse(textwrap.dedent(inspect.getsource(function)))
            )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        for forbidden in ("click", "fill", "type", "press", "submit", "requestSubmit"):
            self.assertNotIn(forbidden, calls)
        self.assertEqual(calls.count("select_option"), 1)
        self.assertNotIn("sample_payment_country", " ".join(calls))

    def test_rotate_proxy_defaults_to_profile_country(self) -> None:
        profile_dir = self.make_profile()
        before_options = json.loads((profile_dir / "launch-options.json").read_text())
        fingerprint_before = MODULE.device_fingerprint(before_options)
        new_geo = {
            "timezone": "Europe/Berlin",
            "locale:language": "de",
            "locale:region": "DE",
            "geolocation:latitude": 53.5,
            "geolocation:longitude": 10.0,
        }
        generated = {
            "env": {"CAMOU_CONFIG_1": json.dumps(new_geo, separators=(",", ":"))},
            "user_data_dir": str(profile_dir / "firefox-profile"),
        }
        with (
            mock.patch.object(
                MODULE,
                "select_eligible_proxy",
                return_value=(
                    {"server": "socks5://replacement.example:1080"},
                    {
                        "country": "DE",
                        "protocol": "socks5",
                        "source": "proxy-pick",
                        "exit_id": "new-exit",
                    },
                    new_geo,
                    "192.0.2.40",
                ),
            ) as select,
            mock.patch.object(
                MODULE, "build_official_launch_options", return_value=generated
            ) as build,
        ):
            result = MODULE.rotate_proxy("sample")
        options = json.loads((profile_dir / "launch-options.json").read_text())
        config = MODULE.decode_config(options["env"])
        metadata = json.loads((profile_dir / "profile.json").read_text())
        self.assertEqual(result["fingerprint_id"], "stable-fingerprint")
        self.assertEqual(MODULE.device_fingerprint(options), fingerprint_before)
        self.assertEqual(config["canvas:aaOffset"], 7)
        self.assertEqual(config["timezone"], "Europe/Berlin")
        self.assertEqual(set(options["env"]), {"CAMOU_CONFIG_1"})
        self.assertEqual(metadata["proxy"]["exit_id"], "new-exit")
        self.assertEqual(metadata["proxy"]["country"], "DE")
        self.assertNotIn("server", metadata["proxy"])
        select.assert_called_once_with(exclude_exit_id="old-exit", country="DE")
        build.assert_called_once_with(
            proxy={"server": "socks5://replacement.example:1080"},
            exit_ip="192.0.2.40",
            geo=new_geo,
            user_data_dir=str(profile_dir / "firefox-profile"),
        )

    def test_rotate_proxy_allows_explicit_country(self) -> None:
        profile_dir = self.make_profile()
        jp_geo = {
            "timezone": "Asia/Tokyo",
            "locale:language": "ja",
            "locale:region": "JP",
            "geolocation:latitude": 35.7,
            "geolocation:longitude": 139.7,
        }
        with mock.patch.object(
            MODULE,
            "select_eligible_proxy",
            return_value=(
                {"server": "socks5://replacement.example:1080"},
                {
                    "country": "JP",
                    "protocol": "socks5",
                    "source": "proxy-pick",
                    "exit_id": "jp-exit",
                },
                jp_geo,
                "192.0.2.50",
            ),
        ) as select, mock.patch.object(
            MODULE,
            "build_official_launch_options",
            return_value={
                "env": {"CAMOU_CONFIG_1": json.dumps(jp_geo, separators=(",", ":"))},
                "user_data_dir": str(profile_dir / "firefox-profile"),
            },
        ):
            result = MODULE.rotate_proxy("sample", country="jp")
        metadata = json.loads((profile_dir / "profile.json").read_text())
        self.assertEqual(result["proxy"]["country"], "JP")
        self.assertEqual(metadata["proxy"]["country"], "JP")
        select.assert_called_once_with(exclude_exit_id="old-exit", country="JP")

    def test_load_external_proxy_config_requires_private_file(self) -> None:
        config_path = self.root / "external-proxy.json"
        config_path.write_text(json.dumps({
            "provider": "catproxies",
            "country": "US",
            "server": "socks5://gateway.example:9000",
            "username": "private-user",
            "password": "private-password",
        }))
        os.chmod(config_path, 0o644)
        with self.assertRaisesRegex(RuntimeError, "permissions"):
            MODULE.load_external_proxy_config(config_path)

        os.chmod(config_path, 0o600)
        proxy, metadata = MODULE.load_external_proxy_config(config_path)
        self.assertEqual(proxy["server"], "socks5://gateway.example:9000")
        self.assertEqual(proxy["username"], "private-user")
        self.assertEqual(metadata, {
            "country": "US",
            "protocol": "socks5",
            "source": "catproxies",
        })

    def test_set_external_proxy_preserves_fingerprint_and_redacts_output(self) -> None:
        profile_dir = self.make_profile()
        config_path = self.root / "external-proxy.json"
        MODULE.write_private_json(config_path, {
            "provider": "catproxies",
            "country": "DE",
            "server": "socks5://gateway.example:9000",
            "username": "private-user",
            "password": "private-password",
        })
        new_geo = {
            "timezone": "Europe/Berlin",
            "locale:language": "de",
            "locale:region": "DE",
            "geolocation:latitude": 53.5,
            "geolocation:longitude": 10.0,
        }
        generated = {
            "env": {"CAMOU_CONFIG_1": json.dumps(new_geo, separators=(",", ":"))},
            "user_data_dir": str(profile_dir / "firefox-profile"),
        }
        before = MODULE.device_fingerprint(json.loads(
            (profile_dir / "launch-options.json").read_text()
        ))
        with (
            mock.patch.object(MODULE, "check_public_ip", return_value="192.0.2.70"),
            mock.patch.object(MODULE, "geolocation_config", return_value=new_geo),
            mock.patch.object(MODULE, "build_official_launch_options", return_value=generated),
        ):
            result = MODULE.set_external_proxy("sample", config_path)
        options = json.loads((profile_dir / "launch-options.json").read_text())
        metadata = json.loads((profile_dir / "profile.json").read_text())
        self.assertEqual(MODULE.device_fingerprint(options), before)
        self.assertEqual(metadata["proxy"]["source"], "catproxies")
        self.assertEqual(metadata["proxy"]["country"], "DE")
        self.assertNotIn("server", metadata["proxy"])
        serialized = json.dumps(result)
        self.assertNotIn("private-user", serialized)
        self.assertNotIn("private-password", serialized)
        self.assertNotIn("gateway.example", serialized)

    def test_set_external_proxy_rejects_cross_country_profile(self) -> None:
        self.make_profile()
        config_path = self.root / "external-proxy.json"
        MODULE.write_private_json(config_path, {
            "provider": "catproxies",
            "country": "US",
            "server": "http://gateway.example:9000",
            "username": "private-user",
            "password": "private-password",
        })
        with self.assertRaisesRegex(RuntimeError, "country"):
            MODULE.set_external_proxy("sample", config_path)

    def test_set_proxy_cli_uses_config_path_without_secret_arguments(self) -> None:
        args = MODULE.build_parser().parse_args([
            "set-proxy", "sample", "--config", "/private/provider.json",
        ])
        self.assertEqual(args.profile_id, "sample")
        self.assertEqual(args.config, "/private/provider.json")
        parser_help = MODULE.build_parser().format_help()
        self.assertIn("set-proxy", parser_help)
        self.assertNotIn("--password", parser_help)

    def test_bootstrap_passes_normalized_country_and_records_actual_country(self) -> None:
        geo = {
            "timezone": "Europe/Berlin",
            "locale:language": "de",
            "locale:region": "DE",
            "geolocation:latitude": 52.5,
            "geolocation:longitude": 13.4,
        }
        options = {
            "env": {"CAMOU_CONFIG_1": json.dumps(geo, separators=(",", ":"))},
            "user_data_dir": "placeholder",
        }
        with (
            mock.patch.object(
                MODULE,
                "select_eligible_proxy",
                return_value=(
                    {"server": "socks5://selected.example:1080"},
                    {
                        "country": "DE",
                        "protocol": "socks5",
                        "source": "proxy-pick",
                        "exit_id": "de-exit",
                    },
                    geo,
                    "192.0.2.60",
                ),
            ) as select,
            mock.patch.object(
                MODULE, "build_official_launch_options", return_value=options
            ) as build,
            mock.patch.object(MODULE, "Camoufox", FakeCamoufox),
        ):
            result = MODULE.bootstrap(
                "claude-account-de-01",
                "data:text/html,<title>Managed Canary</title>",
                country="de",
            )
        metadata = json.loads(
            (self.root / "claude-account-de-01" / "profile.json").read_text()
        )
        self.assertEqual(result["country"], "DE")
        self.assertEqual(metadata["proxy"]["country"], "DE")
        persisted_options = json.loads(
            (self.root / "claude-account-de-01" / "launch-options.json").read_text()
        )
        self.assertEqual(result["fingerprint_id"], MODULE.device_fingerprint(persisted_options))
        select.assert_called_once_with(country="DE")
        build.assert_called_once_with(
            proxy={"server": "socks5://selected.example:1080"},
            exit_ip="192.0.2.60",
            geo=geo,
            user_data_dir=mock.ANY,
        )

    def test_official_launch_options_use_geoip_and_locale_parameters(self) -> None:
        geo = {
            "timezone": "Europe/Berlin",
            "locale:language": "de",
            "locale:region": "DE",
            "locale:script": "Latn",
            "geolocation:latitude": 52.5,
            "geolocation:longitude": 13.4,
        }
        with mock.patch.object(MODULE, "launch_options", return_value={}) as launch:
            MODULE.build_official_launch_options(
                proxy={"server": "socks5://selected.example:1080"},
                exit_ip="192.0.2.60",
                geo=geo,
                user_data_dir="/tmp/profile",
            )
        kwargs = launch.call_args.kwargs
        self.assertNotIn("config", kwargs)
        self.assertNotIn("i_know_what_im_doing", kwargs)
        self.assertEqual(kwargs["geoip"], "192.0.2.60")
        self.assertEqual(kwargs["locale"], "de-DE")
        self.assertEqual(kwargs["proxy"]["server"], "socks5://selected.example:1080")

    def test_picker_retries_geoip_mismatch_and_uses_new_contract(self) -> None:
        first = {
            "proxy": {
                "host": "first.example",
                "port": 1080,
                "protocol": "socks5",
            },
            "exitCountry": "DE",
            "exitIp": "192.0.2.10",
            "claudeStatus": "AVAILABLE",
        }
        second = {
            "proxy": {
                "host": "second.example",
                "port": 1081,
                "protocol": "socks5",
            },
            "exitCountry": "JP",
            "exitIp": "192.0.2.20",
            "claudeStatus": "CF_CHALLENGE",
        }
        completed = [
            mock.Mock(returncode=0, stdout=json.dumps([first])),
            mock.Mock(returncode=0, stdout=json.dumps([second])),
        ]
        jp_geo = {
            "timezone": "Asia/Tokyo",
            "locale:language": "ja",
            "locale:region": "JP",
            "geolocation:latitude": 35.7,
            "geolocation:longitude": 139.7,
        }
        with (
            mock.patch.object(MODULE.subprocess, "run", side_effect=completed) as run,
            mock.patch.object(
                MODULE,
                "check_public_ip",
                side_effect=["192.0.2.10", "192.0.2.20"],
            ),
            mock.patch.object(
                MODULE,
                "geolocation_config",
                side_effect=[RuntimeError("country mismatch"), jp_geo],
            ),
        ):
            _proxy, metadata, geo, exit_ip = MODULE.select_eligible_proxy(max_attempts=3)
        self.assertEqual(run.call_count, 2)
        expected_args = [
            MODULE.PROXY_PICK,
            "--new",
            "--top",
            "5",
            "--json",
            "--no-copy",
        ]
        self.assertEqual(run.call_args_list[0].args[0], expected_args)
        self.assertEqual(run.call_args_list[1].args[0], expected_args)
        self.assertEqual(metadata["country"], "JP")
        self.assertEqual(metadata["protocol"], "socks5")
        self.assertEqual(geo["locale:region"], "JP")
        self.assertEqual(exit_ip, "192.0.2.20")

    def test_picker_adds_explicit_country_to_command(self) -> None:
        candidate = {
            "proxy": {
                "host": "selected.example",
                "port": 1080,
                "protocol": "socks5",
            },
            "exitCountry": "DE",
            "exitIp": "192.0.2.30",
            "claudeStatus": "AVAILABLE",
        }
        completed = mock.Mock(returncode=0, stdout=json.dumps([candidate]))
        de_geo = {
            "timezone": "Europe/Berlin",
            "locale:language": "de",
            "locale:region": "DE",
            "geolocation:latitude": 52.5,
            "geolocation:longitude": 13.4,
        }
        with (
            mock.patch.object(MODULE.subprocess, "run", return_value=completed) as run,
            mock.patch.object(MODULE, "check_public_ip", return_value="192.0.2.30"),
            mock.patch.object(MODULE, "geolocation_config", return_value=de_geo),
        ):
            MODULE.select_eligible_proxy(country="de", max_attempts=1)
        self.assertEqual(
            run.call_args.args[0],
            [
                MODULE.PROXY_PICK,
                "--new",
                "--country",
                "DE",
                "--top",
                "5",
                "--json",
                "--no-copy",
            ],
        )

    def test_country_must_be_iso_alpha2(self) -> None:
        self.assertEqual(MODULE.normalize_country("de"), "DE")
        for value in ("D", "DEU", "D1", "德国"):
            with self.assertRaisesRegex(ValueError, "country"):
                MODULE.normalize_country(value)

    def test_normalize_manual_review_annotation_is_bounded_and_secret_free(self) -> None:
        annotation = MODULE.normalize_manual_review_annotation(
            {
                "has_unique_method": True,
                "observed_methods": [
                    " SEPA Direct Debit ",
                    "SEPA Direct Debit",
                    "x" * 200,
                ],
                "note": "n" * 300,
                "client_secret": "must-not-escape",
            }
        )
        self.assertEqual(annotation["observed_methods"][0], "SEPA Direct Debit")
        self.assertEqual(len(annotation["observed_methods"]), 2)
        self.assertLessEqual(len(annotation["observed_methods"][1]), 80)
        self.assertEqual(len(annotation["note"]), 200)
        self.assertNotIn("client_secret", json.dumps(annotation))
        self.assertNotIn("must-not-escape", json.dumps(annotation))

    def test_false_manual_review_annotation_discards_method_names(self) -> None:
        annotation = MODULE.normalize_manual_review_annotation(
            {
                "has_unique_method": False,
                "observed_methods": ["PayPal"],
                "note": "人工确认未发现",
            }
        )
        self.assertEqual(annotation["observed_methods"], [])

    def test_manual_review_state_keeps_only_allowlisted_fields(self) -> None:
        state = MODULE.normalize_manual_review_state(
            "sample",
            {
                "current_country": "de",
                "reviewed_countries": ["AW", "DE", "AW"],
                "annotations": {
                    "DE": {
                        "has_unique_method": True,
                        "observed_methods": ["iDEAL"],
                    }
                },
                "cookies": "must-not-escape",
            },
        )
        self.assertEqual(state["current_country"], "DE")
        self.assertEqual(state["reviewed_countries"], ["AW", "DE"])
        self.assertEqual(
            set(state),
            {
                "schema_version",
                "profile_id",
                "updated_at",
                "current_country",
                "reviewed_countries",
                "annotations",
            },
        )
        self.assertNotIn("must-not-escape", json.dumps(state))

    def test_manual_review_state_write_is_private_and_atomic(self) -> None:
        profile_dir = self.make_profile()
        state_path = profile_dir / "manual-payment-country-review.json"
        MODULE.write_manual_review_state(
            state_path,
            MODULE.normalize_manual_review_state("sample", {}),
        )
        self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(profile_dir.glob(".manual-payment-country-review.json.*")), [])

    def test_manual_review_asset_has_required_controls_and_no_automatic_timer(self) -> None:
        asset = MODULE.MANUAL_REVIEW_ASSET.read_text(encoding="utf-8")
        for control_id in (
            "review-prev",
            "review-next",
            "review-unique",
            "review-methods",
            "review-note",
            "review-save",
            "review-clear",
            "review-export",
            "review-hide",
        ):
            self.assertIn(control_id, asset)
        self.assertIn("altKey", asset)
        self.assertIn("ArrowLeft", asset)
        self.assertIn("ArrowRight", asset)
        self.assertNotIn("setInterval", asset)
        self.assertNotIn("setTimeout", asset)
        self.assertNotIn("fetch(", asset)
        self.assertNotIn("XMLHttpRequest", asset)
        self.assertNotIn("billingAddress-countryInput", asset)

    def make_manual_review_controller(
        self, *, country: str = "BA"
    ) -> tuple[FakeSurveyContext, object]:
        profile_dir = self.make_profile()
        context = FakeSurveyContext(
            original_country=country,
            country_options=[
                ("AW", "Aruba"),
                ("BA", "Bosnia & Herzegovina"),
                ("BB", "Barbados"),
            ],
        )
        controller = MODULE.ManualPaymentCountryController(
            "sample", context.pages[0], profile_dir
        )
        return context, controller

    def test_manual_controller_never_switches_without_user_event(self) -> None:
        context, controller = self.make_manual_review_controller()
        view = controller.refresh()
        self.assertEqual(context.select_calls, [])
        self.assertEqual(view["current_country"], "BA")
        self.assertEqual(view["position"], 2)
        self.assertEqual(view["total"], 3)

    def test_manual_controller_moves_exactly_one_country_per_event(self) -> None:
        context, controller = self.make_manual_review_controller()
        controller.handle({"id": "1", "type": "next"})
        self.assertEqual([call[2] for call in context.select_calls], ["BB"])
        controller.handle({"id": "2", "type": "previous"})
        self.assertEqual([call[2] for call in context.select_calls], ["BB", "BA"])

    def test_manual_controller_disables_boundary_without_wrapping(self) -> None:
        context, controller = self.make_manual_review_controller(country="AW")
        view = controller.handle({"id": "1", "type": "previous"})
        self.assertEqual(context.select_calls, [])
        self.assertTrue(view["previous_disabled"])
        self.assertFalse(view["next_disabled"])

    def test_manual_controller_does_not_replay_event_after_frame_replacement(self) -> None:
        context, controller = self.make_manual_review_controller()
        controller.handle({"id": "same", "type": "next"})
        context.generation += 1
        controller.handle({"id": "same", "type": "next"})
        self.assertEqual([call[2] for call in context.select_calls], ["BB"])

    def test_manual_controller_saves_clears_and_exports_annotations(self) -> None:
        _context, controller = self.make_manual_review_controller()
        view = controller.handle(
            {
                "id": "save-1",
                "type": "save",
                "has_unique_method": True,
                "methods_text": "iDEAL, iDEAL\nSEPA Direct Debit",
                "note": "人工观察",
                "client_secret": "must-not-escape",
            }
        )
        self.assertTrue(view["has_unique_method"])
        self.assertEqual(view["methods_text"], "iDEAL, SEPA Direct Debit")
        export_view = controller.handle({"id": "export-1", "type": "export"})
        export_path = controller.export_path
        self.assertTrue(export_path.is_file())
        self.assertEqual(export_path.stat().st_mode & 0o777, 0o600)
        self.assertIn(str(export_path), export_view["status_text"])
        self.assertNotIn("must-not-escape", export_path.read_text())
        cleared = controller.handle({"id": "clear-1", "type": "clear"})
        self.assertFalse(cleared["has_unique_method"])
        self.assertEqual(cleared["methods_text"], "")

    def test_manual_controller_reports_not_ready_without_country_control(self) -> None:
        context, controller = self.make_manual_review_controller()
        context.missing_country_control_reads = 20
        view = controller.refresh()
        self.assertFalse(view["ready"])
        self.assertEqual(context.select_calls, [])

    def test_manual_review_cli_contract(self) -> None:
        args = MODULE.build_parser().parse_args(
            [
                "manual-payment-country-review",
                "sample",
                "--url",
                "https://claude.ai/upgrade/max",
            ]
        )
        self.assertEqual(args.profile_id, "sample")
        self.assertEqual(args.url, "https://claude.ai/upgrade/max")
        self.assertFalse(args.foreground_worker)

    def test_manual_review_detaches_worker_from_caller_session(self) -> None:
        profile_dir = self.make_profile()
        process = mock.Mock(pid=4242)
        with (
            mock.patch.object(MODULE.subprocess, "Popen", return_value=process) as popen,
            mock.patch.object(
                MODULE,
                "wait_for_manual_review_start",
                return_value={"manager_pid": 4242},
            ) as wait_for_start,
        ):
            result = MODULE.start_manual_payment_country_review(
                "sample", "https://claude.ai/upgrade/max"
            )
        popen.assert_called_once_with(
            [
                sys.executable,
                str(MODULE.SCRIPT_PATH),
                "manual-payment-country-review",
                "sample",
                "--url",
                "https://claude.ai/upgrade/max",
                "--foreground-worker",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        wait_for_start.assert_called_once_with(profile_dir, process)
        self.assertTrue(result["detached"])
        self.assertEqual(result["status"], "running")

    def test_manual_review_start_waits_for_matching_run_state(self) -> None:
        profile_dir = self.make_profile()
        process = mock.Mock(pid=4242)
        process.poll.return_value = None
        state = {
            "operation": "manual-payment-country-review",
            "profile_id": "sample",
            "manager_pid": 4242,
            "process_start": "stable-start",
        }
        with (
            mock.patch.object(MODULE, "read_run_state", return_value=state),
            mock.patch.object(MODULE, "managed_process_matches", return_value=True),
        ):
            result = MODULE.wait_for_manual_review_start(
                profile_dir, process, timeout=0.01
            )
        self.assertEqual(result, state)

    def test_managed_process_matches_manual_review_and_rejects_unknown(self) -> None:
        state = {
            "operation": "manual-payment-country-review",
            "profile_id": "sample",
            "manager_pid": 4242,
            "process_start": "stable-start",
        }
        completed = subprocess.CompletedProcess(
            [],
            0,
            stdout=(
                f"{MODULE.SCRIPT_PATH} manual-payment-country-review sample "
                "--url https://claude.ai/upgrade/max"
            ),
        )
        with (
            mock.patch.object(MODULE, "process_start_token", return_value="stable-start"),
            mock.patch.object(MODULE.subprocess, "run", return_value=completed),
        ):
            self.assertTrue(MODULE.managed_process_matches(state))
            self.assertFalse(
                MODULE.managed_process_matches({**state, "operation": "unknown-operation"})
            )

    def test_manual_review_cycle_without_event_only_refreshes(self) -> None:
        page = mock.Mock()
        page.locator.return_value.count.return_value = 0
        controller = mock.Mock()
        controller.refresh.return_value = {"ready": False}
        events: collections.deque[dict[str, object]] = collections.deque()
        view = MODULE.run_manual_review_cycle(page, controller, events, "asset-script")
        self.assertEqual(view, {"ready": False})
        controller.refresh.assert_called_once_with()
        controller.handle.assert_not_called()
        self.assertEqual(page.evaluate.call_args_list[0], mock.call("asset-script"))
        page.wait_for_timeout.assert_called_once_with(500)

    def test_manual_review_cycle_retries_after_navigation_destroys_context(self) -> None:
        page = mock.Mock()
        page.locator.return_value.count.return_value = 0
        page.evaluate.side_effect = MODULE.PlaywrightError(
            "Execution context was destroyed"
        )
        controller = mock.Mock()
        events: collections.deque[dict[str, object]] = collections.deque()
        view = MODULE.run_manual_review_cycle(page, controller, events, "asset-script")
        self.assertFalse(view["ready"])
        self.assertEqual(view["status_text"], "页面导航中")
        controller.refresh.assert_not_called()
        controller.handle.assert_not_called()
        page.wait_for_timeout.assert_called_once_with(500)

    def test_manual_review_runtime_cleans_run_state_after_close(self) -> None:
        profile_dir = self.make_profile()
        page = mock.Mock()
        context = mock.Mock()
        context.pages = [page]
        browser = mock.MagicMock()
        browser.__enter__.return_value = context
        browser.__exit__.return_value = None
        with (
            mock.patch.object(MODULE, "Camoufox", return_value=browser),
            mock.patch.object(MODULE, "validate_saved_proxy"),
            mock.patch.object(MODULE, "process_start_token", return_value="stable-start"),
            mock.patch.object(
                MODULE,
                "run_manual_review_cycle",
                side_effect=MODULE.ManagedClose(),
            ),
            mock.patch.object(MODULE.signal, "signal"),
        ):
            result = MODULE.manual_payment_country_review(
                "sample", "https://claude.ai/upgrade/max"
            )
        self.assertEqual(result["status"], "closed")
        self.assertFalse((profile_dir / "run-state.json").exists())
        page.expose_binding.assert_called_once()
        page.goto.assert_called_once_with(
            "https://claude.ai/upgrade/max", wait_until="commit", timeout=45_000
        )
        browser.__exit__.assert_called_once()

    def test_invalid_bootstrap_country_leaves_no_staging(self) -> None:
        with self.assertRaisesRegex(ValueError, "country"):
            MODULE.bootstrap("account-invalid", "https://example.com/", country="DEU")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_close_only_signals_matching_managed_process(self) -> None:
        profile_dir = self.make_profile()
        MODULE.write_private_json(
            profile_dir / "run-state.json",
            {
                "schema_version": 1,
                "profile_id": "sample",
                "manager_pid": 4242,
                "process_start": "stable-start-token",
            },
        )
        with (
            mock.patch.object(MODULE, "managed_process_matches", return_value=True),
            mock.patch.object(os, "kill") as kill,
            mock.patch.object(MODULE, "wait_for_exit", return_value=True),
        ):
            result = MODULE.close_profile("sample")
        kill.assert_called_once_with(4242, signal.SIGTERM)
        self.assertTrue(result["closed"])
        self.assertFalse((profile_dir / "run-state.json").exists())

    def test_close_refuses_unrelated_pid(self) -> None:
        profile_dir = self.make_profile()
        MODULE.write_private_json(
            profile_dir / "run-state.json",
            {
                "schema_version": 1,
                "profile_id": "sample",
                "manager_pid": 4242,
                "process_start": "stable-start-token",
            },
        )
        with (
            mock.patch.object(MODULE, "managed_process_matches", return_value=False),
            mock.patch.object(os, "kill") as kill,
        ):
            result = MODULE.close_profile("sample")
        kill.assert_not_called()
        self.assertFalse(result["closed"])
        self.assertEqual(result["status"], "stale-state")


if __name__ == "__main__":
    unittest.main()
