#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from camoufox.ip import Proxy, public_ip
try:
    from camoufox.geolocation import get_geolocation
except ImportError:  # Camoufox 0.4.x
    from camoufox.locale import get_geolocation
from camoufox.sync_api import Camoufox
from camoufox.utils import get_env_vars, get_target_os, launch_options
from playwright.sync_api import Error as PlaywrightError


ROOT = Path("~/.agents/browser-profiles/camoufox").expanduser()
PROXY_PICK = "/opt/homebrew/bin/proxy-pick"
SCRIPT_PATH = Path(__file__).resolve()
MANUAL_REVIEW_ASSET = SCRIPT_PATH.with_name("assets") / "manual_payment_country_review.js"
MAX_PROXY_PICK_ATTEMPTS = 3
PAGE_TEXT_LIMIT = 20_000
PAGE_TITLE_LIMIT = 500
MAX_FORM_CONTROLS = 200
MAX_SELECT_OPTIONS = 200
CONTROL_TEXT_LIMIT = 500
DEFAULT_INSPECT_WAIT_MS = 5000
MAX_INSPECT_WAIT_MS = 30_000
MAX_INSPECT_FRAMES = 20
FRAME_TEXT_LIMIT = 10_000
PAYMENT_COUNTRY_SELECTOR = "select#billingAddress-countryInput[name=country]"
MAX_SURVEY_COUNTRIES = 250
DEFAULT_SURVEY_INITIAL_WAIT_MS = 30_000
MAX_SURVEY_INITIAL_WAIT_MS = 120_000
MAX_MANUAL_READY_SECONDS = 900
DEFAULT_SURVEY_SETTLE_MS = 2_000
MAX_SURVEY_SETTLE_MS = 15_000
MAX_SURVEY_FRAMES = 8
SURVEY_FRAME_TEXT_LIMIT = 4_000
SURVEY_SUMMARY_TEXT_LIMIT = 6_000
MAX_SURVEY_CONTROLS = 80
MAX_REVIEW_METHODS = 10
MAX_REVIEW_METHOD_LENGTH = 80
MAX_REVIEW_NOTE_LENGTH = 200
PROFILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ManagedClose(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_private_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def write_operation_stage(path: Path, operation: str, stage: str) -> None:
    write_private_json(
        path / "last-operation.json",
        {
            "schema_version": 1,
            "operation": operation,
            "stage": stage,
            "updated_at": utc_now(),
        },
    )


def validate_profile_id(profile_id: str) -> str:
    if not PROFILE_ID_PATTERN.fullmatch(profile_id):
        raise ValueError("profile id must use 1-64 ASCII letters, digits, dot, dash or underscore")
    return profile_id


def profile_dir(profile_id: str, *, must_exist: bool = True) -> Path:
    path = ROOT / validate_profile_id(profile_id)
    if must_exist and not path.is_dir():
        raise FileNotFoundError(f"profile does not exist: {profile_id}")
    return path


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read valid profile state: {path.name}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"profile state must be an object: {path.name}")
    return value


def load_profile(profile_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    path = profile_dir(profile_id)
    metadata = read_json(path / "profile.json")
    options = read_json(path / "launch-options.json")
    if metadata.get("id") != profile_id or metadata.get("engine") != "camoufox":
        raise RuntimeError("profile metadata identity mismatch")
    expected_data_dir = str(path / "firefox-profile")
    if options.get("user_data_dir") != expected_data_dir:
        raise RuntimeError("profile launch path mismatch")
    return path, metadata, options


@contextlib.contextmanager
def profile_lock(path: Path, *, blocking: bool = True):
    lock_path = path / ".manager.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    acquired = False
    try:
        os.chmod(lock_path, 0o600)
        operation = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        try:
            fcntl.flock(descriptor, operation)
        except BlockingIOError as exc:
            raise RuntimeError("profile is running or busy") from exc
        acquired = True
        yield
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def decode_config(env: object) -> dict[str, Any]:
    if not isinstance(env, dict):
        raise RuntimeError("Camoufox launch environment is missing")
    chunks: list[tuple[int, str]] = []
    for key, value in env.items():
        match = re.fullmatch(r"CAMOU_CONFIG_(\d+)", str(key))
        if match:
            chunks.append((int(match.group(1)), str(value)))
    if not chunks:
        raise RuntimeError("Camoufox fingerprint configuration is missing")
    try:
        config = json.loads("".join(value for _, value in sorted(chunks)))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Camoufox fingerprint configuration is invalid") from exc
    if not isinstance(config, dict):
        raise RuntimeError("Camoufox fingerprint configuration must be an object")
    return config


def encode_config(config: dict[str, Any]) -> dict[str, str | float | bool]:
    return get_env_vars(config, get_target_os(config))


def sanitized_options(options: dict[str, Any]) -> dict[str, Any]:
    clean = dict(options)
    clean["env"] = encode_config(decode_config(options.get("env")))
    return clean


def is_location_key(key: str) -> bool:
    return key == "timezone" or key.startswith("locale:") or key.startswith("geolocation:")


def device_fingerprint(options: dict[str, object]) -> str:
    config = {
        key: value
        for key, value in decode_config(options.get("env")).items()
        if not is_location_key(key)
    }
    encoded = json.dumps(config, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]


def proxy_exit_id(exit_ip: str) -> str:
    return hashlib.sha256(exit_ip.encode()).hexdigest()[:12]


def normalize_country(country: str | None) -> str | None:
    if country is None:
        return None
    if not isinstance(country, str) or not re.fullmatch(r"[A-Za-z]{2}", country):
        raise ValueError("country must be a two-letter ASCII ISO code")
    return country.upper()


def normalize_countries(countries: list[str]) -> list[str]:
    if not countries:
        raise ValueError("at least one --country is required")
    if len(countries) > MAX_SURVEY_COUNTRIES:
        raise ValueError(f"at most {MAX_SURVEY_COUNTRIES} countries may be requested")
    normalized: list[str] = []
    seen: set[str] = set()
    for country in countries:
        value = normalize_country(country)
        assert value is not None
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


def bounded_review_text(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def normalize_manual_review_annotation(value: object) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    has_unique_method = source.get("has_unique_method") is True
    methods: list[str] = []
    raw_methods = source.get("observed_methods", [])
    if has_unique_method and isinstance(raw_methods, list):
        for raw_method in raw_methods:
            method = bounded_review_text(raw_method, MAX_REVIEW_METHOD_LENGTH)
            if method and method not in methods:
                methods.append(method)
            if len(methods) >= MAX_REVIEW_METHODS:
                break
    supplied_updated_at = source.get("updated_at")
    updated_at = (
        supplied_updated_at
        if isinstance(supplied_updated_at, str) and len(supplied_updated_at) <= 64
        else utc_now()
    )
    return {
        "has_unique_method": has_unique_method,
        "observed_methods": methods,
        "note": bounded_review_text(source.get("note"), MAX_REVIEW_NOTE_LENGTH),
        "updated_at": updated_at,
    }


def normalize_manual_review_state(profile_id: str, value: object) -> dict[str, Any]:
    validate_profile_id(profile_id)
    source = value if isinstance(value, dict) else {}
    current_country = normalize_country(source.get("current_country"))
    reviewed_countries: list[str] = []
    raw_reviewed = source.get("reviewed_countries", [])
    if isinstance(raw_reviewed, list):
        for raw_country in raw_reviewed:
            try:
                country = normalize_country(raw_country)
            except ValueError:
                continue
            if country is not None and country not in reviewed_countries:
                reviewed_countries.append(country)
    annotations: dict[str, dict[str, Any]] = {}
    raw_annotations = source.get("annotations", {})
    if isinstance(raw_annotations, dict):
        for raw_country, annotation in raw_annotations.items():
            try:
                country = normalize_country(raw_country)
            except ValueError:
                continue
            if country is not None:
                annotations[country] = normalize_manual_review_annotation(annotation)
    return {
        "schema_version": 1,
        "profile_id": profile_id,
        "updated_at": utc_now(),
        "current_country": current_country,
        "reviewed_countries": reviewed_countries,
        "annotations": annotations,
    }


def write_manual_review_state(path: Path, state: dict[str, Any]) -> None:
    profile_id = validate_profile_id(str(state.get("profile_id", "")))
    write_private_json(path, normalize_manual_review_state(profile_id, state))


def geolocation_config(exit_ip: str, expected_country: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Z]{2}", expected_country):
        raise RuntimeError("proxy-pick exitCountry must be an ISO alpha-2 code")
    config = get_geolocation(exit_ip).as_config()
    if config.get("locale:region") != expected_country:
        raise RuntimeError("proxy GeoIP country does not match proxy-pick exitCountry")
    return config


def locale_tag_from_geo(geo: dict[str, Any]) -> str:
    language = str(geo.get("locale:language", ""))
    region = str(geo.get("locale:region", ""))
    if not re.fullmatch(r"[A-Za-z]{2,3}", language):
        raise RuntimeError("GeoIP locale language is invalid")
    if not re.fullmatch(r"[A-Z]{2}", region):
        raise RuntimeError("GeoIP locale region is invalid")
    return f"{language.lower()}-{region}"


def build_official_launch_options(
    *,
    proxy: dict[str, str],
    exit_ip: str,
    geo: dict[str, Any],
    user_data_dir: str,
) -> dict[str, Any]:
    return launch_options(
        os="macos",
        humanize=True,
        block_webrtc=True,
        geoip=exit_ip,
        locale=locale_tag_from_geo(geo),
        proxy=proxy,
        headless=False,
        user_data_dir=user_data_dir,
        env={},
    )


def check_public_ip(proxy: dict[str, str]) -> str:
    cache_clear = getattr(public_ip, "cache_clear", None)
    if cache_clear:
        cache_clear()
    return public_ip(Proxy(**proxy).as_string())


def validate_saved_proxy(
    proxy: object, expected: object
) -> dict[str, str]:
    if not isinstance(proxy, dict) or not isinstance(proxy.get("server"), str):
        raise RuntimeError("saved proxy configuration is missing")
    source = str(expected.get("source", "")) if isinstance(expected, dict) else ""
    has_username = isinstance(proxy.get("username"), str) and bool(proxy.get("username"))
    has_password = isinstance(proxy.get("password"), str) and bool(proxy.get("password"))
    if has_username != has_password:
        raise RuntimeError("saved authenticated proxy credentials are incomplete")
    if has_username and source == "proxy-pick":
        raise RuntimeError("proxy-pick profiles must not contain credentials")
    expected_country = str(expected.get("country", "")).upper() if isinstance(expected, dict) else ""
    exit_ip = check_public_ip(proxy)
    geo = geolocation_config(exit_ip, expected_country)
    current_exit_id = proxy_exit_id(exit_ip)
    expected_exit_id = expected.get("exit_id") if isinstance(expected, dict) else None
    if expected_exit_id and current_exit_id != expected_exit_id:
        raise RuntimeError("saved proxy exit changed; run rotate-proxy before launch")
    return {"country": str(geo["locale:region"]), "exit_id": current_exit_id}


def load_external_proxy_config(
    config_path: Path,
) -> tuple[dict[str, str], dict[str, str]]:
    try:
        stat = config_path.stat()
    except OSError as exc:
        raise RuntimeError("cannot read external proxy config") from exc
    if not config_path.is_file() or stat.st_mode & 0o077:
        raise RuntimeError("external proxy config permissions must be 0600")
    value = read_json(config_path)
    provider = str(value.get("provider", "")).lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,31}", provider):
        raise RuntimeError("external proxy provider is invalid")
    country = normalize_country(value.get("country"))
    assert country is not None
    server = value.get("server")
    username = value.get("username")
    password = value.get("password")
    if not all(isinstance(item, str) and item for item in (server, username, password)):
        raise RuntimeError("external proxy config is incomplete")
    parsed = urlsplit(server)
    if parsed.scheme not in {"http", "https", "socks5"} or not parsed.hostname or not parsed.port:
        raise RuntimeError("external proxy server is invalid")
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError("external proxy server must not embed credentials or URL data")
    proxy = {"server": server, "username": username, "password": password}
    metadata = {"country": country, "protocol": parsed.scheme, "source": provider}
    return proxy, metadata


def select_eligible_proxy(
    *,
    exclude_exit_id: str | None = None,
    country: str | None = None,
    max_attempts: int = MAX_PROXY_PICK_ATTEMPTS,
) -> tuple[dict[str, str], dict[str, object], dict[str, Any], str]:
    if not 1 <= max_attempts <= 10:
        raise ValueError("max proxy-pick attempts must be between 1 and 10")
    requested_country = normalize_country(country)
    command = [PROXY_PICK, "--new"]
    if requested_country:
        command.extend(["--country", requested_country])
    command.extend(["--top", "5", "--json", "--no-copy"])
    for _attempt in range(max_attempts):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode:
            continue
        try:
            candidates = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        if not isinstance(candidates, list) or len(candidates) != 1:
            continue
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            continue
        raw = candidate.get("proxy", {})
        protocol = str(raw.get("protocol", "")).lower()
        host = raw.get("host")
        port = raw.get("port")
        exit_country = str(candidate.get("exitCountry", "")).upper()
        measured_ip = candidate.get("exitIp")
        claude_status = candidate.get("claudeStatus")
        if (
            protocol != "socks5"
            or not host
            or not isinstance(port, int)
            or raw.get("username")
            or raw.get("password")
            or not re.fullmatch(r"[A-Z]{2}", exit_country)
            or (requested_country is not None and exit_country != requested_country)
            or not isinstance(measured_ip, str)
            or claude_status not in {"AVAILABLE", "CF_CHALLENGE"}
        ):
            continue
        proxy = {"server": f"socks5://{host}:{port}"}
        try:
            exit_ip = check_public_ip(proxy)
            if exit_ip != measured_ip:
                continue
            geo = geolocation_config(exit_ip, exit_country)
        except Exception:
            continue
        exit_id = proxy_exit_id(exit_ip)
        if exclude_exit_id and exit_id == exclude_exit_id:
            continue
        return (
            proxy,
            {
                "country": exit_country,
                "protocol": "socks5",
                "source": "proxy-pick",
                "exit_id": exit_id,
            },
            geo,
            exit_ip,
        )
    raise RuntimeError(
        f"proxy-pick did not yield a newly validated Claude-eligible SOCKS5 exit "
        f"after {max_attempts} attempts"
    )


def process_start_token(pid: int) -> str | None:
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=False,
        env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"},
    )
    token = result.stdout.strip()
    return token or None


def managed_process_matches(state: dict[str, Any]) -> bool:
    pid = state.get("manager_pid")
    profile_id = state.get("profile_id")
    if not isinstance(pid, int) or pid <= 1 or not isinstance(profile_id, str):
        return False
    operation = state.get("operation")
    operation_markers = {
        "survey-payment-countries": (
            "survey-payment-countries",
            profile_id,
            "--manual-ready",
        ),
        "manual-payment-country-review": (
            "manual-payment-country-review",
            profile_id,
        ),
        "launch": ("launch", profile_id, "--handoff"),
        None: ("launch", profile_id, "--handoff"),
    }
    marker_tail = operation_markers.get(operation)
    if marker_tail is None:
        return False
    if process_start_token(pid) != state.get("process_start"):
        return False
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
        env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"},
    )
    command = result.stdout.strip()
    markers = (str(SCRIPT_PATH), *marker_tail)
    return all(marker in command for marker in markers)


@contextlib.contextmanager
def manual_survey_state(path: Path, profile_id: str, enabled: bool):
    if not enabled:
        yield
        return
    ready_path = path / "survey-ready.json"
    observation_path = path / "last-survey-observation.json"
    run_state_path = path / "run-state.json"
    ready_path.unlink(missing_ok=True)
    observation_path.unlink(missing_ok=True)
    state = {
        "schema_version": 1,
        "operation": "survey-payment-countries",
        "profile_id": profile_id,
        "manager_pid": os.getpid(),
        "process_start": process_start_token(os.getpid()),
    }
    write_private_json(run_state_path, state)
    try:
        yield
    finally:
        ready_path.unlink(missing_ok=True)
        run_state_path.unlink(missing_ok=True)


def probe_manual_payment_page(page: object) -> dict[str, Any]:
    try:
        frames = list(getattr(page, "frames", []) or [page])[:MAX_INSPECT_FRAMES]
    except Exception as exc:
        raise RuntimeError("manual payment page became unavailable") from exc

    country_control_count = 0
    payment_frame_ready = False
    loading_visible = False
    payment_error_visible = False
    accessible_frames = 0
    for frame in frames:
        try:
            country_control_count += int(frame.locator(PAYMENT_COUNTRY_SELECTOR).count())
        except Exception:
            pass
        try:
            extracted = extract_frame(frame, text_limit=SURVEY_FRAME_TEXT_LIMIT)
        except Exception:
            continue
        if extracted.get("access") != "available":
            continue
        accessible_frames += 1
        body_text = str(extracted.get("body_text", ""))
        body_lower = body_text.lower()
        loading_visible = loading_visible or "loading..." in body_lower
        payment_error_visible = payment_error_visible or (
            "failed to load the payment form" in body_lower
        )
        controls = extracted.get("controls", [])
        has_payment_number = any(
            isinstance(control, dict)
            and control.get("id") == "payment-numberInput"
            and control.get("name") == "number"
            for control in controls
        )
        payment_frame_ready = payment_frame_ready or has_payment_number or (
            "card number" in body_lower and "supported cards" in body_lower
        )
    ready = (
        country_control_count == 1
        and payment_frame_ready
        and not loading_visible
        and not payment_error_visible
    )
    return {
        "schema_version": 1,
        "observed_at": utc_now(),
        "page_alive": True,
        "ready": ready,
        "country_control_count": country_control_count,
        "payment_frame_ready": payment_frame_ready,
        "loading_visible": loading_visible,
        "payment_error_visible": payment_error_visible,
        "accessible_frames": accessible_frames,
    }


def wait_for_manual_ready(path: Path, page: object, *, timeout_seconds: int) -> None:
    if not 1 <= timeout_seconds <= MAX_MANUAL_READY_SECONDS:
        raise ValueError(
            f"manual ready timeout must be between 1 and {MAX_MANUAL_READY_SECONDS} seconds"
        )
    ready_path = path / "survey-ready.json"
    observation_path = path / "last-survey-observation.json"
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            observation = probe_manual_payment_page(page)
        except Exception as exc:
            observation = {
                "schema_version": 1,
                "observed_at": utc_now(),
                "page_alive": False,
                "ready": False,
                "error_code": "page-unavailable",
            }
            write_private_json(observation_path, observation)
            raise RuntimeError("manual payment page became unavailable") from exc
        write_private_json(observation_path, observation)
        if ready_path.is_file():
            ready_path.unlink(missing_ok=True)
            return
        if time.monotonic() >= deadline:
            raise RuntimeError("manual payment-page readiness timed out")
        time.sleep(1.0)


def mark_survey_ready(profile_id: str) -> dict[str, Any]:
    path = profile_dir(profile_id)
    state = read_run_state(path)
    if (
        not state
        or state.get("operation") != "survey-payment-countries"
        or not managed_process_matches(state)
    ):
        raise RuntimeError("no managed manual-ready survey is running")
    write_private_json(
        path / "survey-ready.json",
        {"schema_version": 1, "ready_at": utc_now()},
    )
    return {"ok": True, "profile_id": profile_id, "status": "ready"}


def read_run_state(path: Path) -> dict[str, Any] | None:
    state_path = path / "run-state.json"
    if not state_path.exists():
        return None
    try:
        return read_json(state_path)
    except RuntimeError:
        return None


def is_running(path: Path) -> bool:
    state = read_run_state(path)
    return bool(state and managed_process_matches(state))


def public_metadata(metadata: dict[str, Any], *, running: bool) -> dict[str, Any]:
    proxy = metadata.get("proxy") if isinstance(metadata.get("proxy"), dict) else {}
    return {
        "id": metadata.get("id"),
        "engine": metadata.get("engine"),
        "fingerprint_id": metadata.get("fingerprint_id"),
        "profile_path": metadata.get("profile_path"),
        "proxy": {
            "country": proxy.get("country"),
            "protocol": proxy.get("protocol"),
            "source": proxy.get("source"),
            "exit_id": proxy.get("exit_id"),
        },
        "target": metadata.get("target"),
        "login_allowed": metadata.get("login_allowed", False),
        "created_at": metadata.get("created_at"),
        "rotated_at": metadata.get("rotated_at"),
        "last_launched_at": metadata.get("last_launched_at"),
        "running": running,
    }


def list_profiles() -> list[dict[str, Any]]:
    if not ROOT.exists():
        return []
    profiles: list[dict[str, Any]] = []
    for path in sorted(ROOT.iterdir()):
        if not path.is_dir() or path.name.startswith(".") or not (path / "profile.json").is_file():
            continue
        try:
            metadata = read_json(path / "profile.json")
            profiles.append(public_metadata(metadata, running=is_running(path)))
        except RuntimeError:
            profiles.append({"id": path.name, "status": "invalid", "running": False})
    return profiles


def inspect_profile(profile_id: str) -> dict[str, Any]:
    path, metadata, _options = load_profile(profile_id)
    return public_metadata(metadata, running=is_running(path))


def sanitize_page_url(value: object) -> str:
    raw = str(value or "")
    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return f"{scheme}:" if scheme else parsed.path[:CONTROL_TEXT_LIMIT]
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = f"{host}:{port}" if port else host
    return urlunsplit((scheme, netloc, parsed.path or "/", "", ""))


def limited_text(value: object, limit: int) -> str:
    return str(value or "")[:limit]


def sanitize_control(raw: object) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    control = {
        key: limited_text(raw.get(key), CONTROL_TEXT_LIMIT)
        for key in (
            "tag",
            "type",
            "name",
            "id",
            "role",
            "aria-label",
            "placeholder",
            "button_text",
        )
    }
    if control["tag"] == "select" and isinstance(raw.get("options"), list):
        options: list[dict[str, Any]] = []
        for option in raw["options"][:MAX_SELECT_OPTIONS]:
            if not isinstance(option, dict):
                continue
            options.append(
                {
                    "text": limited_text(option.get("text"), CONTROL_TEXT_LIMIT),
                    "value": limited_text(option.get("value"), CONTROL_TEXT_LIMIT),
                    "selected": bool(option.get("selected")),
                }
            )
        control["options"] = options
    return control


def extract_frame(frame: object, *, text_limit: int) -> dict[str, Any]:
    body_text = frame.locator("body").inner_text(timeout=10_000)
    raw_controls = frame.locator(
        "input, select, textarea, button, "
        "[role=button], [role=checkbox], [role=radio], [role=combobox]"
    ).evaluate_all(
        """
        (elements, limits) => {
          const visible = elements.filter((element) => {
            if (element.hidden) return false;
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== "none"
              && style.visibility !== "hidden"
              && Number(style.opacity || 1) !== 0
              && rect.width > 0
              && rect.height > 0;
          });
          const clip = (value) => String(value || "").slice(0, limits.textLimit);
          const controls = visible.slice(0, limits.maxControls).map((element) => {
            const tag = element.tagName.toLowerCase();
            const role = element.getAttribute("role") || "";
            const item = {
              tag,
              type: clip(element.getAttribute("type") || element.type || ""),
              name: clip(element.getAttribute("name") || ""),
              id: clip(element.id || ""),
              role: clip(role),
              "aria-label": clip(element.getAttribute("aria-label") || ""),
              placeholder: clip(element.getAttribute("placeholder") || ""),
              button_text: tag === "button" || role === "button"
                ? clip(element.innerText || element.textContent || "")
                : "",
            };
            if (tag === "select") {
              item.options = Array.from(element.options || [])
                .slice(0, limits.maxOptions)
                .map((option) => ({
                  text: clip(option.text),
                  value: clip(option.value),
                  selected: Boolean(option.selected),
                }));
            }
            return item;
          });
          return { controls, total: visible.length };
        }
        """,
        {
            "maxControls": MAX_FORM_CONTROLS,
            "maxOptions": MAX_SELECT_OPTIONS,
            "textLimit": CONTROL_TEXT_LIMIT,
        },
    )
    payload = raw_controls if isinstance(raw_controls, dict) else {}
    controls = (
        [
            sanitized
            for item in payload.get("controls", [])[:MAX_FORM_CONTROLS]
            if (sanitized := sanitize_control(item)) is not None
        ]
        if isinstance(payload.get("controls"), list)
        else []
    )
    total = payload.get("total")
    controls_total = total if isinstance(total, int) and total >= len(controls) else len(controls)
    return {
        "url": sanitize_page_url(getattr(frame, "url", "")),
        "title": limited_text(frame.title(), PAGE_TITLE_LIMIT),
        "access": "available",
        "body_text": body_text[:text_limit],
        "body_text_truncated": len(body_text) > text_limit,
        "controls": controls,
        "controls_total": controls_total,
        "controls_truncated": controls_total > len(controls),
    }


def sanitize_survey_text(value: object, limit: int) -> str:
    text = str(value or "")
    text = re.sub(
        r"(?i)\b(client_secret|access_token|refresh_token|id_token|api_key|token)"
        r"\b\s*(?:=|:)\s*[^\s&]+",
        r"\1=[redacted]",
        text,
    )
    text = re.sub(r"(?i)\bsocks5h?://[^\s]+", "[redacted-proxy]", text)
    return text[:limit]


def sanitize_survey_value(value: object) -> object:
    if isinstance(value, str):
        return sanitize_survey_text(value, CONTROL_TEXT_LIMIT)
    if isinstance(value, list):
        return [sanitize_survey_value(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_survey_value(item) for key, item in value.items()}
    return value


SURVEY_FAILURE_CODES = {
    "exactly one billing country control is required": "country-control-count",
    "billing country selector is ambiguous": "country-control-ambiguous",
    "billing country control identity mismatch": "country-control-identity",
    "billing country control has no selected country": "country-control-unselected",
    "billing country selection was not accepted": "country-selection-rejected",
    "billing country did not settle to the requested value": "country-settle-mismatch",
    "billing country control did not become stable": "country-control-timeout",
}


def classify_survey_failure(exc: Exception) -> str:
    code = SURVEY_FAILURE_CODES.get(str(exc))
    if code is not None:
        return code
    if isinstance(exc, RuntimeError):
        return "unexpected-runtime-error"
    return "unexpected-error"


def country_select_state(locator: object) -> dict[str, str]:
    state = locator.evaluate(
        """
        (element) => ({
          tag: element.tagName.toLowerCase(),
          id: element.id || "",
          name: element.getAttribute("name") || "",
          value: element.value || "",
        })
        """
    )
    if not isinstance(state, dict) or (
        state.get("tag"), state.get("id"), state.get("name")
    ) != ("select", "billingAddress-countryInput", "country"):
        raise RuntimeError("billing country control identity mismatch")
    value = normalize_country(str(state.get("value", "")))
    if value is None:
        raise RuntimeError("billing country control has no selected country")
    return {"value": value}


def find_payment_country_select(page: object) -> object:
    matches: list[object] = []
    for frame in list(getattr(page, "frames", []) or [page])[:MAX_INSPECT_FRAMES]:
        try:
            locator = frame.locator(PAYMENT_COUNTRY_SELECTOR)
            count = locator.count()
        except Exception:
            continue
        if count == 1:
            country_select_state(locator)
            matches.append(locator)
        elif count > 1:
            raise RuntimeError("billing country selector is ambiguous")
    if len(matches) != 1:
        raise RuntimeError("exactly one billing country control is required")
    return matches[0]


def select_payment_country(page: object, country: str) -> None:
    locator = find_payment_country_select(page)
    country_select_state(locator)
    selected = locator.select_option(value=country)
    if not isinstance(selected, list) or country not in selected:
        raise RuntimeError("billing country selection was not accepted")


def payment_country_options(page: object) -> dict[str, Any]:
    locator = find_payment_country_select(page)
    raw = locator.evaluate(
        """
        (element) => ({
          tag: element.tagName.toLowerCase(),
          id: element.id || "",
          name: element.getAttribute("name") || "",
          value: element.value || "",
          options: Array.from(element.options).map((option) => ({
            value: option.value || "",
            label: option.textContent || option.value || "",
          })),
        })
        """
    )
    if not isinstance(raw, dict) or (
        raw.get("tag"), raw.get("id"), raw.get("name")
    ) != ("select", "billingAddress-countryInput", "country"):
        raise RuntimeError("billing country control identity mismatch")
    try:
        current = normalize_country(raw.get("value"))
    except ValueError as exc:
        raise RuntimeError("billing country control has no selected country") from exc
    if current is None:
        raise RuntimeError("billing country control has no selected country")
    options: list[dict[str, str]] = []
    raw_options = raw.get("options", [])
    if isinstance(raw_options, list):
        for item in raw_options[:MAX_SURVEY_COUNTRIES]:
            if not isinstance(item, dict):
                continue
            try:
                country = normalize_country(item.get("value"))
            except ValueError:
                continue
            if country is None or any(option["value"] == country for option in options):
                continue
            options.append(
                {
                    "value": country,
                    "label": bounded_review_text(item.get("label"), 80) or country,
                }
            )
    index = next(
        (
            position
            for position, option in enumerate(options)
            if option["value"] == current
        ),
        -1,
    )
    if index < 0:
        raise RuntimeError("billing country control has no selected country")
    return {"current": current, "options": options, "index": index}


class ManualPaymentCountryController:
    def __init__(self, profile_id: str, page: object, profile_path: Path) -> None:
        self.profile_id = validate_profile_id(profile_id)
        self.page = page
        self.state_path = profile_path / "manual-payment-country-review.json"
        self.export_path = profile_path / "manual-payment-country-review-export.json"
        try:
            existing = read_json(self.state_path)
        except RuntimeError:
            existing = {}
        self.state = normalize_manual_review_state(profile_id, existing)
        self.processed_ids: collections.deque[str] = collections.deque(maxlen=100)
        self.status_text = ""

    def _persist(self, path: Path | None = None) -> None:
        self.state = normalize_manual_review_state(self.profile_id, self.state)
        write_private_json(path or self.state_path, self.state)

    def _not_ready_view(self) -> dict[str, Any]:
        return {
            "ready": False,
            "current_country": None,
            "country_label": "",
            "position": 0,
            "total": 0,
            "previous_disabled": True,
            "next_disabled": True,
            "has_unique_method": False,
            "methods_text": "",
            "note": "",
            "annotation_updated_at": "",
            "status_text": self.status_text or "付款表单未就绪",
        }

    def _view(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        country = snapshot["current"]
        annotation = self.state["annotations"].get(country, {})
        return {
            "ready": True,
            "current_country": country,
            "country_label": snapshot["options"][snapshot["index"]]["label"],
            "position": snapshot["index"] + 1,
            "total": len(snapshot["options"]),
            "previous_disabled": snapshot["index"] == 0,
            "next_disabled": snapshot["index"] + 1 == len(snapshot["options"]),
            "has_unique_method": annotation.get("has_unique_method", False),
            "methods_text": ", ".join(annotation.get("observed_methods", [])),
            "note": annotation.get("note", ""),
            "annotation_updated_at": annotation.get("updated_at", ""),
            "status_text": self.status_text,
        }

    def refresh(self) -> dict[str, Any]:
        try:
            snapshot = payment_country_options(self.page)
        except (RuntimeError, ValueError):
            return self._not_ready_view()
        country = snapshot["current"]
        changed = self.state.get("current_country") != country
        self.state["current_country"] = country
        if country not in self.state["reviewed_countries"]:
            self.state["reviewed_countries"].append(country)
            changed = True
        if changed:
            self._persist()
        return self._view(snapshot)

    def handle(self, event: object) -> dict[str, Any]:
        value = event if isinstance(event, dict) else {}
        event_id = bounded_review_text(value.get("id"), 100)
        event_type = value.get("type")
        if not event_id or event_id in self.processed_ids:
            self.status_text = "重复或无效操作已忽略"
            return self.refresh()
        self.processed_ids.append(event_id)
        try:
            snapshot = payment_country_options(self.page)
            if event_type in {"previous", "next"}:
                delta = -1 if event_type == "previous" else 1
                target_index = snapshot["index"] + delta
                if 0 <= target_index < len(snapshot["options"]):
                    select_payment_country(
                        self.page, snapshot["options"][target_index]["value"]
                    )
                    self.status_text = "国家已切换"
                else:
                    self.status_text = "已到列表边界"
            elif event_type == "save":
                methods = re.split(r"[,，\n]+", str(value.get("methods_text", "")))
                self.state["annotations"][snapshot["current"]] = (
                    normalize_manual_review_annotation(
                        {
                            "has_unique_method": value.get("has_unique_method") is True,
                            "observed_methods": methods,
                            "note": value.get("note"),
                        }
                    )
                )
                self._persist()
                self.status_text = "标记已保存"
            elif event_type == "clear":
                self.state["annotations"].pop(snapshot["current"], None)
                self._persist()
                self.status_text = "标记已清除"
            elif event_type == "export":
                self.export()
                self.status_text = str(self.export_path)
            else:
                self.status_text = "未知操作已忽略"
        except (RuntimeError, ValueError):
            self.status_text = "付款表单未就绪"
        return self.refresh()

    def export(self) -> Path:
        self._persist(self.export_path)
        return self.export_path


def run_manual_review_cycle(
    page: object,
    controller: ManualPaymentCountryController,
    events: collections.deque[dict[str, Any]],
    asset: str,
) -> dict[str, Any]:
    try:
        panel = page.locator("#claude-payment-country-review")
        if panel.count() == 0:
            page.evaluate(asset)
        view = controller.handle(events.popleft()) if events else controller.refresh()
        page.evaluate(
            "state => window.__claudePaymentCountryReview.render(state)",
            view,
        )
        page.wait_for_timeout(500)
        return view
    except PlaywrightError as exc:
        try:
            page.wait_for_timeout(500)
        except PlaywrightError as wait_exc:
            raise RuntimeError("manual review page became unavailable") from wait_exc
        return {"ready": False, "status_text": "页面导航中"}


def manual_payment_country_review(profile_id: str, url: str) -> dict[str, Any]:
    path = profile_dir(profile_id)
    if is_running(path):
        raise RuntimeError("profile is running; close it before manual review")
    asset = MANUAL_REVIEW_ASSET.read_text(encoding="utf-8")
    with profile_lock(path, blocking=False):
        _path, metadata, raw_options = load_profile(profile_id)
        ensure_not_running(path)
        options = sanitized_options(raw_options)
        if options != raw_options:
            write_private_json(path / "launch-options.json", options)
        validate_saved_proxy(options.get("proxy"), metadata.get("proxy"))
        run_state_path = path / "run-state.json"
        write_private_json(
            run_state_path,
            {
                "schema_version": 1,
                "operation": "manual-payment-country-review",
                "profile_id": profile_id,
                "manager_pid": os.getpid(),
                "process_start": process_start_token(os.getpid()),
                "started_at": utc_now(),
            },
        )
        previous_handler = signal.getsignal(signal.SIGTERM)

        def request_close(_signum: int, _frame: object) -> None:
            raise ManagedClose()

        signal.signal(signal.SIGTERM, request_close)
        status = "closed"
        try:
            with Camoufox(from_options=options, persistent_context=True) as context:
                page = context.pages[0] if context.pages else context.new_page()
                events: collections.deque[dict[str, Any]] = collections.deque()

                def receive_event(_source: object, event: object) -> None:
                    if isinstance(event, dict):
                        events.append(event)

                page.expose_binding("__manualPaymentReviewEvent", receive_event)
                page.goto(url, wait_until="commit", timeout=45_000)
                controller = ManualPaymentCountryController(profile_id, page, path)
                while True:
                    run_manual_review_cycle(page, controller, events, asset)
        except (ManagedClose, KeyboardInterrupt):
            pass
        finally:
            signal.signal(signal.SIGTERM, previous_handler)
            run_state_path.unlink(missing_ok=True)
        return {
            "ok": True,
            "profile_id": profile_id,
            "status": status,
            "state_file": "manual-payment-country-review.json",
            "export_file": "manual-payment-country-review-export.json",
        }


def wait_for_manual_review_start(
    path: Path,
    process: subprocess.Popen[bytes],
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("manual payment-country review failed to start")
        state = read_run_state(path)
        if (
            state
            and state.get("operation") == "manual-payment-country-review"
            and state.get("manager_pid") == process.pid
            and managed_process_matches(state)
        ):
            return state
        time.sleep(0.1)
    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)
    raise RuntimeError("manual payment-country review start timed out")


def start_manual_payment_country_review(profile_id: str, url: str) -> dict[str, Any]:
    path = profile_dir(profile_id)
    if is_running(path):
        raise RuntimeError("profile is running; close it before manual review")
    (path / "run-state.json").unlink(missing_ok=True)
    process = subprocess.Popen(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "manual-payment-country-review",
            profile_id,
            "--url",
            url,
            "--foreground-worker",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
    )
    wait_for_manual_review_start(path, process)
    return {
        "ok": True,
        "profile_id": profile_id,
        "status": "running",
        "detached": True,
        "state_file": "manual-payment-country-review.json",
        "export_file": "manual-payment-country-review-export.json",
    }


def wait_for_payment_country_stable(
    page: object,
    expected_country: str,
    *,
    timeout_ms: int = 30_000,
    poll_ms: int = 1_000,
    stable_reads: int = 2,
) -> None:
    if timeout_ms < 0 or poll_ms <= 0 or stable_reads <= 0:
        raise ValueError("country stability wait parameters are invalid")
    attempts = max(1, (timeout_ms + poll_ms - 1) // poll_ms)
    consecutive = 0
    for attempt in range(attempts):
        try:
            locator = find_payment_country_select(page)
            current_country = country_select_state(locator)["value"]
            consecutive = consecutive + 1 if current_country == expected_country else 0
        except Exception:
            consecutive = 0
        if consecutive >= stable_reads:
            return
        if attempt + 1 < attempts:
            page.wait_for_timeout(poll_ms)
    raise RuntimeError("billing country control did not become stable")


def survey_frame_is_relevant(frame: dict[str, Any], *, is_top: bool) -> bool:
    if frame.get("access") != "available":
        return False
    searchable = " ".join(
        str(frame.get(key, "")) for key in ("url", "title", "body_text")
    ).lower()
    if "hcaptcha" in searchable or "recaptcha" in searchable:
        return False
    if is_top:
        return True
    if any(term in searchable for term in ("stripe", "payment", "billing", "address", "tax")):
        return True
    return any(
        any(term in str(control.get(key, "")).lower() for term in ("payment", "billing", "tax"))
        for control in frame.get("controls", [])
        if isinstance(control, dict)
        for key in ("name", "id", "aria-label")
    )


def compact_survey_frame(frame: dict[str, Any]) -> dict[str, Any]:
    controls = frame.get("controls", [])
    compact = {
        "url": sanitize_page_url(frame.get("url", "")),
        "title": sanitize_survey_text(frame.get("title", ""), PAGE_TITLE_LIMIT),
        "access": "available",
        "body_text": sanitize_survey_text(
            frame.get("body_text", ""), SURVEY_FRAME_TEXT_LIMIT
        ),
        "body_text_truncated": bool(frame.get("body_text_truncated"))
        or len(str(frame.get("body_text", ""))) > SURVEY_FRAME_TEXT_LIMIT,
        "controls": sanitize_survey_value(
            controls[:MAX_SURVEY_CONTROLS] if isinstance(controls, list) else []
        ),
        "controls_total": int(frame.get("controls_total", 0)),
    }
    compact["controls_truncated"] = compact["controls_total"] > len(compact["controls"])
    return compact


def sample_payment_country(page: object, expected_country: str) -> dict[str, Any]:
    locator = find_payment_country_select(page)
    selected_country = country_select_state(locator)["value"]
    if selected_country != expected_country:
        raise RuntimeError("billing country did not settle to the requested value")

    raw_frames = list(getattr(page, "frames", []) or [page])
    selected_frames: list[dict[str, Any]] = []
    relevant_total = 0
    for index, frame in enumerate(raw_frames[:MAX_INSPECT_FRAMES]):
        try:
            extracted = extract_frame(frame, text_limit=SURVEY_FRAME_TEXT_LIMIT)
        except Exception:
            continue
        if survey_frame_is_relevant(extracted, is_top=index == 0):
            relevant_total += 1
            if len(selected_frames) < MAX_SURVEY_FRAMES:
                selected_frames.append(compact_survey_frame(extracted))
    top_text = selected_frames[0].get("body_text", "") if selected_frames else ""
    return {
        "selected_country": selected_country,
        "checkout_summary": sanitize_survey_text(top_text, SURVEY_SUMMARY_TEXT_LIMIT),
        "frames": selected_frames,
        "frames_total": relevant_total,
        "frames_truncated": relevant_total > len(selected_frames)
        or len(raw_frames) > MAX_INSPECT_FRAMES,
    }


def survey_payment_countries(
    profile_id: str,
    url: str,
    countries: list[str],
    *,
    initial_wait_ms: int = DEFAULT_SURVEY_INITIAL_WAIT_MS,
    settle_ms: int = DEFAULT_SURVEY_SETTLE_MS,
    manual_ready: bool = False,
    manual_timeout_seconds: int = MAX_MANUAL_READY_SECONDS,
    stop_on_error: bool = False,
) -> dict[str, Any]:
    requested = normalize_countries(countries)
    if not 0 <= initial_wait_ms <= MAX_SURVEY_INITIAL_WAIT_MS:
        raise ValueError(f"initial-wait-ms must be between 0 and {MAX_SURVEY_INITIAL_WAIT_MS}")
    if not 0 <= settle_ms <= MAX_SURVEY_SETTLE_MS:
        raise ValueError(f"settle-ms must be between 0 and {MAX_SURVEY_SETTLE_MS}")
    if manual_ready and not 1 <= manual_timeout_seconds <= MAX_MANUAL_READY_SECONDS:
        raise ValueError(
            f"manual ready timeout must be between 1 and {MAX_MANUAL_READY_SECONDS} seconds"
        )
    path = profile_dir(profile_id)
    if is_running(path):
        raise RuntimeError("profile is running; close it before survey-payment-countries")

    result: dict[str, Any]
    checkpoint_path = path / "last-survey-result.json"
    checkpoint_path.unlink(missing_ok=True)
    write_operation_stage(path, "survey-payment-countries", "starting")
    with manual_survey_state(path, profile_id, manual_ready), profile_lock(path, blocking=False):
        _path, metadata, raw_options = load_profile(profile_id)
        if not manual_ready:
            ensure_not_running(path)
        options = sanitized_options(raw_options)
        validate_saved_proxy(options.get("proxy"), metadata.get("proxy"))
        write_operation_stage(path, "survey-payment-countries", "proxy-validated")
        with Camoufox(from_options=options, persistent_context=True) as context:
            write_operation_stage(path, "survey-payment-countries", "browser-opened")
            pages = list(context.pages)
            page = pages[0] if pages else context.new_page()
            write_operation_stage(path, "survey-payment-countries", "navigation-started")
            page.goto(url, wait_until="commit", timeout=45_000)
            write_operation_stage(path, "survey-payment-countries", "navigation-complete")
            if manual_ready:
                write_operation_stage(
                    path, "survey-payment-countries", "awaiting-manual-ready"
                )
                wait_for_manual_ready(
                    path, page, timeout_seconds=manual_timeout_seconds
                )
                write_operation_stage(
                    path, "survey-payment-countries", "manual-ready"
                )
            page.wait_for_timeout(initial_wait_ms)
            write_operation_stage(path, "survey-payment-countries", "render-wait-complete")
            country_select = find_payment_country_select(page)
            write_operation_stage(path, "survey-payment-countries", "selector-ready")
            original_country = country_select_state(country_select)["value"]
            write_operation_stage(path, "survey-payment-countries", "checkout-ready")
            country_results: list[dict[str, Any]] = []
            current_country = original_country
            for country in requested:
                write_operation_stage(
                    path, "survey-payment-countries", f"surveying-{country}"
                )
                failure_stage = "select-country"
                try:
                    select_payment_country(page, country)
                    current_country = country
                    failure_stage = "settle-country"
                    page.wait_for_timeout(settle_ms)
                    failure_stage = "await-country-stable"
                    wait_for_payment_country_stable(page, country)
                    failure_stage = "sample-country"
                    country_results.append(
                        {"country": country, "status": "ok", **sample_payment_country(page, country)}
                    )
                except Exception as exc:
                    country_results.append(
                        {
                            "country": country,
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "error": "country survey failed",
                            "failure_stage": failure_stage,
                            "failure_code": classify_survey_failure(exc),
                        }
                    )
                    if stop_on_error:
                        break

            try:
                current_country = country_select_state(find_payment_country_select(page))["value"]
                restore_needed = current_country != original_country
            except Exception:
                restore_needed = True
            restore: dict[str, Any] = {"attempted": restore_needed}
            if restore["attempted"]:
                try:
                    select_payment_country(page, original_country)
                    page.wait_for_timeout(settle_ms)
                    wait_for_payment_country_stable(page, original_country)
                    restore["status"] = "ok"
                except Exception as exc:
                    restore.update(
                        {
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "error": "original country restoration failed",
                            "failure_code": classify_survey_failure(exc),
                        }
                    )
            else:
                restore["status"] = "not-needed"
            result = {
                "profile_id": profile_id,
                "url": sanitize_page_url(page.url),
                "countries": country_results,
                "restore": restore,
                "closed": False,
            }
            write_private_json(checkpoint_path, result)
            write_operation_stage(path, "survey-payment-countries", "result-ready")
    result["closed"] = True
    write_private_json(checkpoint_path, result)
    write_operation_stage(path, "survey-payment-countries", "complete")
    return result


def inspect_page(
    profile_id: str,
    url: str | None = None,
    *,
    text_limit: int = PAGE_TEXT_LIMIT,
    wait_ms: int = DEFAULT_INSPECT_WAIT_MS,
) -> dict[str, Any]:
    if not 1 <= text_limit <= PAGE_TEXT_LIMIT:
        raise ValueError(f"text limit must be between 1 and {PAGE_TEXT_LIMIT}")
    if not 0 <= wait_ms <= MAX_INSPECT_WAIT_MS:
        raise ValueError(f"wait-ms must be between 0 and {MAX_INSPECT_WAIT_MS}")
    path = profile_dir(profile_id)
    if is_running(path):
        raise RuntimeError("profile is running; close it before inspect-page")
    with profile_lock(path, blocking=False):
        _path, metadata, raw_options = load_profile(profile_id)
        ensure_not_running(path)
        options = sanitized_options(raw_options)
        validate_saved_proxy(options.get("proxy"), metadata.get("proxy"))
        with Camoufox(from_options=options, persistent_context=True) as context:
            all_pages = list(context.pages)
            pages = [page for page in all_pages if str(getattr(page, "url", "")) != "about:blank"]
            if url:
                page = all_pages[0] if all_pages else context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            elif pages:
                page = pages[-1]
            else:
                raise RuntimeError("no recovered page is available; pass --url")
            page.wait_for_timeout(wait_ms)

            raw_frames = list(getattr(page, "frames", []) or [page])
            frame_results: list[dict[str, Any]] = []
            frame_text_limit = min(text_limit, FRAME_TEXT_LIMIT)
            for frame in raw_frames[:MAX_INSPECT_FRAMES]:
                try:
                    frame_results.append(extract_frame(frame, text_limit=frame_text_limit))
                except Exception:
                    frame_results.append(
                        {
                            "url": sanitize_page_url(getattr(frame, "url", "")),
                            "access": "unavailable",
                        }
                    )

            available = [frame for frame in frame_results if frame.get("access") == "available"]
            combined_text = "\n\n".join(
                str(frame.get("body_text", ""))
                for frame in available
                if frame.get("body_text")
            )
            all_controls = [
                control
                for frame in available
                for control in frame.get("controls", [])
            ]
            controls_total = sum(int(frame.get("controls_total", 0)) for frame in available)
            return {
                "profile_id": profile_id,
                "title": limited_text(page.title(), PAGE_TITLE_LIMIT),
                "url": sanitize_page_url(page.url),
                "body_text": combined_text[:text_limit],
                "body_text_truncated": len(combined_text) > text_limit
                or any(bool(frame.get("body_text_truncated")) for frame in available),
                "controls": all_controls[:MAX_FORM_CONTROLS],
                "controls_total": controls_total,
                "controls_truncated": controls_total > min(len(all_controls), MAX_FORM_CONTROLS),
                "frames": frame_results,
                "frames_total": len(raw_frames),
                "frames_truncated": len(raw_frames) > len(frame_results),
            }


def ensure_not_running(path: Path) -> None:
    state = read_run_state(path)
    if state and managed_process_matches(state):
        raise RuntimeError("profile is already running; close it before continuing")
    if state:
        (path / "run-state.json").unlink(missing_ok=True)


def launch_profile(
    profile_id: str,
    url: str | None = None,
    *,
    wait_ms: int = 3000,
    handoff: bool = False,
) -> dict[str, Any]:
    path = profile_dir(profile_id)
    with profile_lock(path):
        _path, metadata, raw_options = load_profile(profile_id)
        ensure_not_running(path)
        options = sanitized_options(raw_options)
        if options != raw_options:
            write_private_json(path / "launch-options.json", options)
        validate_saved_proxy(options.get("proxy"), metadata.get("proxy"))
        target_url = url or str((metadata.get("target") or {}).get("url") or "https://example.com/")
        if wait_ms < 0 or wait_ms > 60_000:
            raise ValueError("wait-ms must be between 0 and 60000")
        run_state_path = path / "run-state.json"
        try:
            with Camoufox(from_options=options, persistent_context=True) as context:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(target_url, wait_until="domcontentloaded", timeout=45_000)
                if wait_ms:
                    page.wait_for_timeout(wait_ms)
                result = {"title": page.title(), "url": page.url}
                if handoff:
                    state = {
                        "schema_version": 1,
                        "operation": "launch",
                        "profile_id": profile_id,
                        "manager_pid": os.getpid(),
                        "process_start": process_start_token(os.getpid()),
                        "started_at": utc_now(),
                    }
                    write_private_json(run_state_path, state)

                    def request_close(_signum: int, _frame: object) -> None:
                        raise ManagedClose()

                    previous = signal.signal(signal.SIGTERM, request_close)
                    try:
                        while True:
                            time.sleep(3600)
                    except ManagedClose:
                        pass
                    finally:
                        signal.signal(signal.SIGTERM, previous)
                        run_state_path.unlink(missing_ok=True)
        finally:
            if not handoff:
                run_state_path.unlink(missing_ok=True)

        metadata["target"] = result
        metadata["last_launched_at"] = utc_now()
        write_private_json(path / "profile.json", metadata)
        return {
            "ok": True,
            "profile_id": profile_id,
            "fingerprint_id": metadata.get("fingerprint_id"),
            "target_title": result["title"],
            "target_url": result["url"],
            "handoff": handoff,
            "closed": True,
        }


def rotate_proxy(profile_id: str, country: str | None = None) -> dict[str, Any]:
    path = profile_dir(profile_id)
    with profile_lock(path):
        _path, metadata, raw_options = load_profile(profile_id)
        ensure_not_running(path)
        old_proxy = metadata.get("proxy") if isinstance(metadata.get("proxy"), dict) else {}
        current_country = normalize_country(old_proxy.get("country"))
        explicit_country = normalize_country(country)
        if explicit_country is None and current_country is None:
            raise RuntimeError("Profile metadata has no country; pass --country explicitly")
        requested_country = explicit_country or current_country
        proxy, proxy_meta, geo, exit_ip = select_eligible_proxy(
            exclude_exit_id=old_proxy.get("exit_id"),
            country=requested_country,
        )
        options = sanitized_options(raw_options)
        config = decode_config(options.get("env"))
        device_before = device_fingerprint(options)
        generated = build_official_launch_options(
            proxy=proxy,
            exit_ip=exit_ip,
            geo=geo,
            user_data_dir=str(path / "firefox-profile"),
        )
        generated_config = decode_config(generated.get("env"))
        for key in list(config):
            if is_location_key(key):
                config.pop(key)
        config.update(
            {key: value for key, value in generated_config.items() if is_location_key(key)}
        )
        options["env"] = encode_config(config)
        options["proxy"] = proxy
        if device_fingerprint(options) != device_before:
            raise RuntimeError("proxy rotation changed the persisted device fingerprint")
        metadata["proxy"] = proxy_meta
        metadata["rotated_at"] = utc_now()
        write_private_json(path / "launch-options.json", options)
        write_private_json(path / "profile.json", metadata)
        return {
            "ok": True,
            "profile_id": profile_id,
            "fingerprint_id": metadata.get("fingerprint_id"),
            "proxy": proxy_meta,
        }


def set_external_proxy(profile_id: str, config_path: Path) -> dict[str, Any]:
    path = profile_dir(profile_id)
    with profile_lock(path):
        _path, metadata, raw_options = load_profile(profile_id)
        ensure_not_running(path)
        old_proxy = metadata.get("proxy") if isinstance(metadata.get("proxy"), dict) else {}
        current_country = normalize_country(old_proxy.get("country"))
        proxy, proxy_meta = load_external_proxy_config(config_path)
        if current_country and proxy_meta["country"] != current_country:
            raise RuntimeError("external proxy country must match the Profile country")
        exit_ip = check_public_ip(proxy)
        geo = geolocation_config(exit_ip, proxy_meta["country"])
        proxy_meta["exit_id"] = proxy_exit_id(exit_ip)

        options = sanitized_options(raw_options)
        config = decode_config(options.get("env"))
        device_before = device_fingerprint(options)
        generated = build_official_launch_options(
            proxy=proxy,
            exit_ip=exit_ip,
            geo=geo,
            user_data_dir=str(path / "firefox-profile"),
        )
        generated_config = decode_config(generated.get("env"))
        for key in list(config):
            if is_location_key(key):
                config.pop(key)
        config.update(
            {key: value for key, value in generated_config.items() if is_location_key(key)}
        )
        options["env"] = encode_config(config)
        options["proxy"] = proxy
        if device_fingerprint(options) != device_before:
            raise RuntimeError("external proxy update changed the persisted device fingerprint")
        metadata["proxy"] = proxy_meta
        metadata["rotated_at"] = utc_now()
        write_private_json(path / "launch-options.json", options)
        write_private_json(path / "profile.json", metadata)
        return {
            "ok": True,
            "profile_id": profile_id,
            "fingerprint_id": metadata.get("fingerprint_id"),
            "proxy": proxy_meta,
        }


def wait_for_exit(pid: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


def close_profile(profile_id: str) -> dict[str, Any]:
    path = profile_dir(profile_id)
    state_path = path / "run-state.json"
    state = read_run_state(path)
    if not state:
        return {"ok": True, "profile_id": profile_id, "closed": False, "status": "not-running"}
    if not managed_process_matches(state):
        state_path.unlink(missing_ok=True)
        return {"ok": True, "profile_id": profile_id, "closed": False, "status": "stale-state"}
    pid = int(state["manager_pid"])
    os.kill(pid, signal.SIGTERM)
    exited = wait_for_exit(pid)
    if exited:
        state_path.unlink(missing_ok=True)
    return {
        "ok": exited,
        "profile_id": profile_id,
        "closed": exited,
        "status": "closed" if exited else "timeout",
    }


def bootstrap(
    profile_id: str, url: str, country: str | None = None
) -> dict[str, object]:
    final_dir = profile_dir(profile_id, must_exist=False)
    if final_dir.exists():
        raise RuntimeError(f"profile already exists: {profile_id}")
    requested_country = normalize_country(country)
    proxy, proxy_meta, geo, exit_ip = select_eligible_proxy(country=requested_country)
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = Path(tempfile.mkdtemp(prefix=f".{profile_id}-", dir=ROOT))
    os.chmod(staging, 0o700)
    profile_path = staging / "firefox-profile"
    try:
        options = build_official_launch_options(
            proxy=proxy,
            exit_ip=exit_ip,
            geo=geo,
            user_data_dir=str(profile_path),
        )
        fingerprint_id = device_fingerprint(options)
        with Camoufox(from_options=options, persistent_context=True) as context:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(3000)
            result = {"title": page.title(), "url": page.url}

        options["user_data_dir"] = str(final_dir / "firefox-profile")
        write_private_json(staging / "launch-options.json", options)
        write_private_json(
            staging / "profile.json",
            {
                "schema_version": 1,
                "id": profile_id,
                "created_at": utc_now(),
                "engine": "camoufox",
                "fingerprint_id": fingerprint_id,
                "profile_path": str(final_dir / "firefox-profile"),
                "proxy": proxy_meta,
                "target": result,
                "login_allowed": False,
            },
        )
        staging.rename(final_dir)
        return {
            "ok": True,
            "profile_id": profile_id,
            "fingerprint_id": fingerprint_id,
            "country": proxy_meta["country"],
            "target_title": result["title"],
            "target_url": result["url"],
        }
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage isolated persistent Camoufox profiles.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List managed Profiles without exposing proxy addresses.")

    inspect = subparsers.add_parser("inspect", help="Inspect sanitized Profile metadata.")
    inspect.add_argument("profile_id")

    inspect_page_parser = subparsers.add_parser(
        "inspect-page", help="Read visible page text and form metadata without interaction."
    )
    inspect_page_parser.add_argument("profile_id")
    inspect_page_parser.add_argument("--url", help="Navigate before inspection; otherwise use recovery.")
    inspect_page_parser.add_argument(
        "--wait-ms",
        type=int,
        default=DEFAULT_INSPECT_WAIT_MS,
        help="Wait for asynchronous rendering after navigation or recovery (0-30000).",
    )

    survey = subparsers.add_parser(
        "survey-payment-countries",
        help="Read payment methods by changing only Stripe's billing-country select.",
    )
    survey.add_argument("profile_id")
    survey.add_argument("--url", required=True, help="Checkout page to survey.")
    survey.add_argument(
        "--country",
        action="append",
        required=True,
        help="Two-letter ISO billing country; repeat for each country (max 250).",
    )
    survey.add_argument(
        "--initial-wait-ms",
        type=int,
        default=DEFAULT_SURVEY_INITIAL_WAIT_MS,
        help="Initial checkout preparation wait, including manual navigation (0-120000).",
    )
    survey.add_argument(
        "--settle-ms",
        type=int,
        default=DEFAULT_SURVEY_SETTLE_MS,
        help="Bounded wait after each country selection (0-15000).",
    )
    survey.add_argument(
        "--manual-ready",
        action="store_true",
        help="Keep the same visible context open until the ready command is called.",
    )
    survey.add_argument(
        "--manual-timeout-seconds",
        type=int,
        default=MAX_MANUAL_READY_SECONDS,
        help="Maximum manual payment-page preparation time (1-900 seconds).",
    )
    survey.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop the current country batch after the first survey error.",
    )

    manual_review = subparsers.add_parser(
        "manual-payment-country-review",
        help="Open a user-controlled billing-country review panel.",
    )
    manual_review.add_argument("profile_id")
    manual_review.add_argument("--url", default="https://claude.ai/upgrade/max")
    manual_review.add_argument(
        "--foreground-worker",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    create = subparsers.add_parser("bootstrap", help="Create a new managed Profile.")
    create.add_argument("profile_id")
    create.add_argument("--url", default="https://claude.ai/")
    create.add_argument("--country", help="Require a two-letter ISO exit country.")

    launch = subparsers.add_parser("launch", help="Revalidate and launch a managed Profile.")
    launch.add_argument("profile_id")
    launch.add_argument("--url")
    launch.add_argument("--wait-ms", type=int, default=3000)
    launch.add_argument(
        "--handoff",
        action="store_true",
        help="Keep the visible browser open until the matching close command is issued.",
    )

    rotate = subparsers.add_parser(
        "rotate-proxy", help="Select a new validated Claude-eligible proxy."
    )
    rotate.add_argument("profile_id")
    rotate.add_argument(
        "--country",
        help="Explicit exit country; defaults to the Profile's current country.",
    )

    set_proxy = subparsers.add_parser(
        "set-proxy", help="Validate and attach an authenticated external proxy."
    )
    set_proxy.add_argument("profile_id")
    set_proxy.add_argument(
        "--config", required=True, help="Path to a mode-0600 private proxy JSON file."
    )

    close = subparsers.add_parser("close", help="Close only this Profile's managed handoff.")
    close.add_argument("profile_id")

    ready = subparsers.add_parser(
        "ready", help="Continue a managed manual-ready payment survey."
    )
    ready.add_argument("profile_id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "list":
            result: object = list_profiles()
        elif args.command == "inspect":
            result = inspect_profile(args.profile_id)
        elif args.command == "inspect-page":
            result = inspect_page(args.profile_id, args.url, wait_ms=args.wait_ms)
        elif args.command == "survey-payment-countries":
            result = survey_payment_countries(
                args.profile_id,
                args.url,
                args.country,
                initial_wait_ms=args.initial_wait_ms,
                settle_ms=args.settle_ms,
                manual_ready=args.manual_ready,
                manual_timeout_seconds=args.manual_timeout_seconds,
                stop_on_error=args.stop_on_error,
            )
        elif args.command == "manual-payment-country-review":
            if args.foreground_worker:
                result = manual_payment_country_review(args.profile_id, args.url)
            else:
                result = start_manual_payment_country_review(args.profile_id, args.url)
        elif args.command == "bootstrap":
            result = bootstrap(args.profile_id, args.url, country=args.country)
        elif args.command == "launch":
            result = launch_profile(
                args.profile_id,
                args.url,
                wait_ms=args.wait_ms,
                handoff=args.handoff,
            )
        elif args.command == "rotate-proxy":
            result = rotate_proxy(args.profile_id, country=args.country)
        elif args.command == "set-proxy":
            result = set_external_proxy(args.profile_id, Path(args.config))
        elif args.command == "close":
            result = close_profile(args.profile_id)
        elif args.command == "ready":
            result = mark_survey_ready(args.profile_id)
        else:
            raise RuntimeError(f"unsupported command: {args.command}")
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
