"""Suite pytest independente da Revisao 20 (ACH-B7-R19-001 a ACH-B7-R19-006)."""
import base64
import copy
import hashlib
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REV20 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REV20 / "tools"))

import platform_clock as pc
import validate_rev20 as v20


def _load_fixtures():
    hashes, direct, trefs = v20.validate_all_schemas(REV20)
    reg = v20.validate_schema_registry(REV20, hashes, direct, trefs)
    pol = v20.validate_compatibility_policy(REV20, hashes, trefs, reg)
    tb = v20.strict_parse(REV20 / "test_vectors/checkpoint/checkpoint-trust-bundle-tv-001.json")
    dos = v20.strict_parse(REV20 / "test_vectors/dossier/dossier-tv-001.json")
    ver = v20.strict_parse(REV20 / "test_vectors/dossier/dossier-tv-001.verification.json")
    jcs_b = (REV20 / "test_vectors/dossier/dossier-tv-001.jcs.txt").read_bytes()
    rev = v20.strict_parse(REV20 / "test_vectors/trust/revocation-list-tv-001.json")
    rcpt = v20.strict_parse(REV20 / "test_vectors/checkpoint/checkpoint-receipt-tv-001.json")
    return pol, tb, dos, ver, jcs_b, rev, rcpt


def _sign_rev_list(payload: dict) -> dict:
    seed = hashlib.sha256(b"revisao-hostil-v8-fase7-rev19-revocation-authority-tv").digest()
    priv = Ed25519PrivateKey.from_private_bytes(seed)
    out = dict(payload)
    out["signature_b64"] = base64.b64encode(priv.sign(v20.jcs_canonical(payload))).decode("ascii")
    return out


# --- ACH-B7-R19-001: Real UTC clock & operational mode guard ---
def test_trusted_utc_clock_and_operational_guard():
    now, src = v20.resolve_execution_now_utc(mode="operational")
    if now.tzinfo is None or src != "system_utc_realtime":
        pytest.fail("Relogio operacional invalido")
    with pytest.raises(v20.ValidationError):
        v20.resolve_execution_now_utc(mode="operational", test_clock=lambda: datetime(2026, 11, 24, tzinfo=timezone.utc))
    with pytest.raises(v20.ValidationError):
        v20.resolve_execution_now_utc(mode="test", test_clock=lambda: datetime(2026, 11, 24))  # naive clock


# --- ACH-B7-R19-002: Dossier operator trust binding & 3 distinct providers ---
def test_dossier_trust_binding_and_providers():
    _, tb, dos, _, _, _, _ = _load_fixtures()
    v20.validate_dossier_trust_binding(dos, tb)

    for idx in (0, 1, 2):
        bad = copy.deepcopy(dos)
        bad["domains"][idx]["operator_key_id"] = "0" * 64
        with pytest.raises(v20.ValidationError):
            v20.validate_dossier_trust_binding(bad, tb)

    bad_prov = copy.deepcopy(dos)
    bad_prov["domains"][1]["infrastructure_provider"] = bad_prov["domains"][0]["infrastructure_provider"]
    with pytest.raises(v20.ValidationError):
        v20.validate_dossier_trust_binding(bad_prov, tb)


# --- ACH-B7-R19-005: RuntimeClockContext with boot_id, PID, UUID, epoch ---
def test_windows_qpc_lifecycle_with_boot_id():
    if platform.system() != "Windows":
        pytest.skip("Teste especifico de Windows QPC")
    ctx = pc.create_runtime_clock_context("epoch-001")
    t1 = pc.validate_runtime_clock_context(ctx, "epoch-001", expected_context_id=ctx.clock_context_id)
    t2 = pc.validate_runtime_clock_context(ctx, "epoch-001", expected_context_id=ctx.clock_context_id)
    if t2 < t1:
        pytest.fail("Regressao monotonica QPC")
    with pytest.raises(pc.PlatformClockError):
        pc.validate_runtime_clock_context(ctx, "epoch-002")
    with pytest.raises(pc.PlatformClockError):
        pc.validate_runtime_clock_context(ctx, "epoch-001", current_pid=ctx.pid + 1)
    with pytest.raises(pc.PlatformClockError):
        pc.validate_runtime_clock_context(ctx, "epoch-001", current_boot_id="windows-boot:different")


def test_linux_monotonic_raw_lifecycle_with_boot_id():
    if platform.system() != "Linux":
        pytest.skip("BLOQUEADO_AMBIENTE_LINUX: host atual nao e Linux")
    ctx = pc.create_runtime_clock_context("epoch-001")
    pc.validate_runtime_clock_context(ctx, "epoch-001", expected_context_id=ctx.clock_context_id)


# --- ACH-B7-R19-006: Individual revocation entry validation (future date, duplicate, empty reason) ---
def test_revocation_list_individual_entries():
    _, tb, _, _, _, rev, _ = _load_fixtures()
    now = v20.get_trusted_utc_now()
    base_payload = {k: v for k, v in rev.items() if k != "signature_b64"}
    store_kid = tb["store_key"]["key_id"]

    # Valid 1-entry revocation
    p1 = copy.deepcopy(base_payload)
    p1["revoked_keys"] = [{"key_id": store_kid, "revoked_at_utc": "2026-11-24T01:00:00Z", "reason": "compromised"}]
    revoked = v20.validate_revocation_list(_sign_rev_list(p1), tb["authorized_revocation_authorities"], now)
    if store_kid not in revoked:
        pytest.fail("Chave revogada nao retornada")

    # Future revocation date rejected
    p_fut = copy.deepcopy(base_payload)
    p_fut["revoked_keys"] = [{"key_id": store_kid, "revoked_at_utc": "2027-01-01T00:00:00Z", "reason": "future"}]
    with pytest.raises(v20.ValidationError):
        v20.validate_revocation_list(_sign_rev_list(p_fut), tb["authorized_revocation_authorities"], now)

    # Duplicate key_id rejected
    p_dup = copy.deepcopy(base_payload)
    p_dup["revoked_keys"] = [
        {"key_id": store_kid, "revoked_at_utc": "2026-11-24T01:00:00Z", "reason": "r1"},
        {"key_id": store_kid, "revoked_at_utc": "2026-11-24T02:00:00Z", "reason": "r2"},
    ]
    with pytest.raises(v20.ValidationError):
        v20.validate_revocation_list(_sign_rev_list(p_dup), tb["authorized_revocation_authorities"], now)

    # Empty reason rejected
    p_empty = copy.deepcopy(base_payload)
    p_empty["revoked_keys"] = [{"key_id": store_kid, "revoked_at_utc": "2026-11-24T01:00:00Z", "reason": "   "}]
    with pytest.raises(v20.ValidationError):
        v20.validate_revocation_list(_sign_rev_list(p_empty), tb["authorized_revocation_authorities"], now)
