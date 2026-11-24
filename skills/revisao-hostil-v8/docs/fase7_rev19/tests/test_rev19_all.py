"""Suite pytest independente da Revisao 19 (ACH-B7-R18-001 a ACH-B7-R18-006).

Executa mutacoes negativas independentes fora do validador principal.
"""
import base64
import copy
import hashlib
import platform
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

REV19 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REV19 / "tools"))

import platform_clock as pc
import validate_rev19 as v19


def _load_fixtures():
    hashes, direct, trefs = v19.validate_all_schemas(REV19)
    reg = v19.validate_schema_registry(REV19, hashes, direct, trefs)
    pol = v19.validate_compatibility_policy(REV19, hashes, trefs, reg)
    tb = v19.strict_parse(REV19 / "test_vectors/checkpoint/checkpoint-trust-bundle-tv-001.json")
    dos = v19.strict_parse(REV19 / "test_vectors/dossier/dossier-tv-001.json")
    ver = v19.strict_parse(REV19 / "test_vectors/dossier/dossier-tv-001.verification.json")
    jcs_b = (REV19 / "test_vectors/dossier/dossier-tv-001.jcs.txt").read_bytes()
    rev = v19.strict_parse(REV19 / "test_vectors/trust/revocation-list-tv-001.json")
    rcpt = v19.strict_parse(REV19 / "test_vectors/checkpoint/checkpoint-receipt-tv-001.json")
    now = v19.parse_utc("2026-11-24T12:00:00Z")
    return hashes, trefs, reg, pol, tb, dos, ver, jcs_b, rev, rcpt, now


def _other_spki_b64() -> tuple[str, str]:
    priv = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b"rogue-key").digest())
    spki = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(spki).decode("ascii"), hashlib.sha256(spki).hexdigest()


# --- ACH-B7-R18-001: Trust key binding & 3-way dossier digest ---
def test_trust_key_mutations():
    _, _, _, pol, tb, dos, ver, jcs_b, rev, rcpt, now = _load_fixtures()
    rogue_b64, rogue_kid = _other_spki_b64()
    revoked = v19.validate_dossier(REV19, dos, ver, jcs_b, tb, rev, now)

    for fn in [
        lambda t: t["store_key"].__setitem__("key_id", "0" * 64),
        lambda t: t["store_key"].__setitem__("public_key_spki_der_b64", rogue_b64),
        lambda t: t["witness_keys"]["witness-a"].__setitem__("key_id", "0" * 64),
        lambda t: t["witness_keys"]["witness-a"].__setitem__("public_key_spki_der_b64", rogue_b64),
        lambda t: t["witness_keys"]["witness-b"].__setitem__("key_id", "0" * 64),
        lambda t: t["witness_keys"]["witness-b"].__setitem__("public_key_spki_der_b64", rogue_b64),
    ]:
        bad_tb = copy.deepcopy(tb)
        fn(bad_tb)
        with pytest.raises(v19.ValidationError):
            v19.validate_checkpoint_receipt_global(rcpt, pol, dos, bad_tb, revoked)

    # expected_dossier_sha256 tampered
    bad_tb = copy.deepcopy(tb)
    bad_tb["expected_dossier_sha256"] = "f" * 64
    with pytest.raises(v19.ValidationError):
        v19.validate_dossier(REV19, dos, ver, jcs_b, bad_tb, rev, now)

    # Authority SPKI mismatch in trust bundle
    bad_tb2 = copy.deepcopy(tb)
    aid = dos["authority_signature"]["authority_key_id"]
    bad_tb2["authorized_dossier_authorities"][aid] = rogue_b64
    with pytest.raises(v19.ValidationError):
        v19.validate_dossier(REV19, dos, ver, jcs_b, bad_tb2, rev, now)


# --- ACH-B7-R18-002: Administrative independence, temporal validity & revocation ---
def test_administrative_independence_and_revocation_mutations():
    _, _, _, pol, tb, dos, ver, jcs_b, rev, rcpt, now = _load_fixtures()

    for field in ("legal_entity_id", "administrative_domain", "kms_hsm_id", "key_custodian_id", "operator_key_id"):
        bad_dos = copy.deepcopy(dos)
        bad_dos["domains"][1][field] = bad_dos["domains"][0][field]
        with pytest.raises(v19.ValidationError):
            v19.validate_administrative_independence(bad_dos)

    # Expired & future dossier
    with pytest.raises(v19.ValidationError):
        v19.validate_dossier(REV19, dos, ver, jcs_b, tb, rev, v19.parse_utc("2028-01-01T00:00:00Z"))
    with pytest.raises(v19.ValidationError):
        v19.validate_dossier(REV19, dos, ver, jcs_b, tb, rev, v19.parse_utc("2025-01-01T00:00:00Z"))

    # Revocation list tampered / unauthorized / expired
    bad_rev = copy.deepcopy(rev)
    bad_rev["revocation_list_version"] = "99"
    with pytest.raises(v19.ValidationError):
        v19.validate_revocation_list(bad_rev, tb["authorized_revocation_authorities"], now)

    with pytest.raises(v19.ValidationError):
        v19.parse_utc("2026-11-24T12:00:00")  # missing timezone

    # Revoked store / witness rejected in global checkpoint
    store_kid = tb["store_key"]["key_id"]
    with pytest.raises(v19.ValidationError):
        v19.validate_checkpoint_receipt_global(rcpt, pol, dos, tb, {store_kid})
    wa_kid = tb["witness_keys"]["witness-a"]["key_id"]
    with pytest.raises(v19.ValidationError):
        v19.validate_checkpoint_receipt_global(rcpt, pol, dos, tb, {wa_kid})


# --- ACH-B7-R18-004: Real platform monotonic clock ---
def test_windows_qpc_real_clock():
    if platform.system() != "Windows":
        pytest.skip("Teste especifico de Windows QPC")
    ctx = pc.create_runtime_clock_context("epoch-001")
    t1 = pc.validate_runtime_clock_context(ctx, "epoch-001")
    t2 = pc.validate_runtime_clock_context(ctx, "epoch-001")
    if t2 < t1:
        pytest.fail("Regressao monotonica em QPC")
    with pytest.raises(pc.PlatformClockError):
        pc.validate_runtime_clock_context(ctx, "epoch-002")


def test_linux_monotonic_raw_real_clock():
    if platform.system() != "Linux":
        pytest.skip("BLOQUEADO_AMBIENTE_LINUX: host atual nao e Linux")
    src, ns = pc.read_platform_monotonic_ns()
    if src != "linux_clock_monotonic_raw" or ns < 0:
        pytest.fail("Leitura Linux CLOCK_MONOTONIC_RAW invalida")


# --- ACH-B7-R18-005: Policy & Registry digest reconciliation ---
def test_policy_registry_digest_mismatch():
    hashes, _, reg, _, _, _, _, _, _, _, _ = _load_fixtures()
    _, _, trefs = v19.validate_all_schemas(REV19)
    bad_reg = copy.deepcopy(reg)
    bad_reg["compatibility_policy_jcs_sha256"] = "0" * 64
    with pytest.raises(v19.ValidationError):
        v19.validate_compatibility_policy(REV19, hashes, trefs, bad_reg)
