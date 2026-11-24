"""Gerador deterministico dos artefatos documentais da Revisao 18 (Fase 7 - v8.0-beta.7).

Utiliza exclusivamente bibliotecas consolidadas:
  - rfc8785==0.1.4 (Implementacao A de RFC 8785 JCS)
  - jcs==0.3.0 (Implementacao B independente de RFC 8785 JCS)
  - cryptography==50.0.2 (Ed25519 + SPKI DER)
  - jsonschema==4.26.0 (Draft 2020-12)
"""
import base64
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import jcs as jcs_b
import rfc8785 as jcs_a
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

REV18 = Path(__file__).resolve().parent.parent
REPO = REV18.parent.parent.parent.parent
LEGACY_SRC = REPO / "skills/revisao-hostil-v8/references/schemas"
REV17_DIR = REPO / "skills/revisao-hostil-v8/docs/fase7_rev17"

LEGACY_DST = REV18 / "schemas/legacy-v8.0-beta.6.6"
V7_DST = REV18 / "schemas/7.0.0"
TV_RFC8785 = REV18 / "test_vectors/rfc8785"
TV_ED25519 = REV18 / "test_vectors/ed25519"
TV_CHECKPOINT = REV18 / "test_vectors/checkpoint"
TV_DOSSIER = REV18 / "test_vectors/dossier"

for d in (LEGACY_DST, V7_DST, TV_RFC8785, TV_ED25519, TV_CHECKPOINT, TV_DOSSIER, REV18 / "reports"):
    d.mkdir(parents=True, exist_ok=True)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical_dual(obj) -> bytes:
    a = jcs_a.dumps(obj)
    b = jcs_b.canonicalize(obj)
    if a != b:
        raise RuntimeError(f"Divergencia entre rfc8785 e jcs: {a!r} != {b!r}")
    return a


def make_test_key(label: bytes):
    seed = hashlib.sha256(label).digest()
    priv = Ed25519PrivateKey.from_private_bytes(seed)
    pub = priv.public_key()
    spki = pub.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return priv, pub, spki, base64.b64encode(spki).decode("ascii"), sha256_bytes(spki)


def main() -> None:
    # 1. Copy 8 legacy schemas byte-for-byte
    legacy_meta = {}
    for src in sorted(LEGACY_SRC.glob("*.json")):
        dst = LEGACY_DST / src.name
        shutil.copyfile(src, dst)
        raw = dst.read_bytes()
        if raw != src.read_bytes():
            raise RuntimeError(f"Falha copia byte a byte: {src.name}")
        legacy_meta[src.name] = {
            "physical_sha256": sha256_bytes(raw),
            "git_blob_sha": subprocess.check_output(["git", "hash-object", str(src)], cwd=REPO, text=True).strip(),
        }

    # 2. Copy 19 v7.0.0 schemas from Rev17 and apply ACH-B7-R17-004 (clock_context_id format: uuid)
    for src in sorted((REV17_DIR / "schemas/7.0.0").glob("*.json")):
        content = src.read_bytes()
        if src.name == "schema_monotonic_checkpoint_receipt.json":
            obj = json.loads(content.decode("utf-8"))
            ctx_props = obj["properties"]["nonce_consumption_receipts"]["items"]["properties"]["expires_at_monotonic_context"]["properties"]
            ctx_props["clock_context_id"] = {"type": "string", "format": "uuid"}
            content = (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        (V7_DST / src.name).write_bytes(content)

    # 3. Copy and update compatibility_policy.schema.json
    cs = json.loads((REV17_DIR / "compatibility_policy.schema.json").read_text(encoding="utf-8"))
    cs["title"] = "Schema Fechado da Politica de Compatibilidade (Fase 7 - Rev 18)"
    (REV18 / "compatibility_policy.schema.json").write_bytes((json.dumps(cs, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    # 4. Recompute physical hashes and transitive refs for all 19 schemas
    v7_hashes, v7_direct_refs = {}, {}
    for p in sorted(V7_DST.glob("*.json")):
        raw = p.read_bytes()
        v7_hashes[p.name] = sha256_bytes(raw)
        v7_direct_refs[p.name] = sorted(set(re.findall(r'"\$ref"\s*:\s*"\./([^"]+)"', raw.decode("utf-8"))))

    def transitive_refs(name: str) -> dict:
        vis, st = {}, list(v7_direct_refs[name])
        while st:
            r = st.pop()
            if r not in vis:
                vis[r] = v7_hashes[r]
                for s in v7_direct_refs[r]:
                    if s not in vis:
                        st.append(s)
        return dict(sorted(vis.items()))

    entries, total_trefs = [], 0
    for name in sorted(v7_hashes.keys()):
        trefs = transitive_refs(name)
        total_trefs += len(trefs)
        ref_list = [{"ref_schema_name": r, "ref_path": f"schemas/7.0.0/{r}", "ref_sha256": h} for r, h in trefs.items()]
        src_kind = (
            "inherited_from_root_schema" if name in {"schema_achado.json", "schema_evidencia.json"}
            else "loader_constant_PROFILE_CONTRACT_VERSION" if name == "schema_profile.json"
            else "instance_schema_version_field"
        )
        entries.append({
            "schema_name": name,
            "schema_path": f"schemas/7.0.0/{name}",
            "contract_version": "7.0.0",
            "schema_sha256": v7_hashes[name],
            "ref_hashes": ref_list,
            "instance_version_source": src_kind,
            "allowed_instance_versions": [
                {"instance_schema_version": "7.0.0", "evidence_status": "COMPROVADO_FASE7", "backward_validation": False}
            ],
            "backward_validation": False,
        })

    policy_payload = {
        "policy_version": "1.0.0",
        "policy_status": "normative_specification_template",
        "baseline_tag": "v8.0-beta.6.6",
        "baseline_commit": "11e91b6f3d517707326357868cc34ff97ab8327d",
        "default_decision": "deny",
        "entries": entries,
    }
    policy_jcs_sha256 = sha256_bytes(canonical_dual(policy_payload))
    policy_full = dict(policy_payload)
    policy_full["compatibility_policy_jcs_sha256"] = policy_jcs_sha256
    (REV18 / "compatibility_policy_v1.json").write_bytes((json.dumps(policy_full, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    registry = {
        "registry_version": "1.0.0",
        "baseline_tag": "v8.0-beta.6.6",
        "baseline_commit": "11e91b6f3d517707326357868cc34ff97ab8327d",
        "total_canonical_contracts": len(v7_hashes),
        "legacy_contracts_preserved": len(legacy_meta),
        "total_transitive_refs": total_trefs,
        "compatibility_policy_jcs_sha256": policy_jcs_sha256,
        "legacy_schemas": {
            name: {
                "source_path": f"skills/revisao-hostil-v8/references/schemas/{name}",
                "preserved_copy_path": f"schemas/legacy-v8.0-beta.6.6/{name}",
                "physical_sha256": meta["physical_sha256"],
                "git_blob_sha": meta["git_blob_sha"],
            }
            for name, meta in sorted(legacy_meta.items())
        },
        "canonical_v7_schemas": {
            name: {
                "id": f"https://revisao-hostil.v8/schemas/7.0.0/{name}",
                "path": f"schemas/7.0.0/{name}",
                "contract_version": "7.0.0",
                "physical_sha256": v7_hashes[name],
                "direct_refs": v7_direct_refs[name],
                "transitive_refs": transitive_refs(name),
            }
            for name in sorted(v7_hashes.keys())
        },
    }
    (REV18 / "SCHEMA_REGISTRY_FASE7_REV18.json").write_bytes((json.dumps(registry, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    # 5. Build 18 individual RFC 8785 test vectors (ACH-B7-R17-001 & 005)
    rfc8785_specs = [
        ("v01_official_sorting", {"\r": "Carriage Return", "1": "One string", "\u0080": "Control", "\ufb33": "Hebrew Letter Dalet With Dagesh", "\ud83d\ude00" if False else "\U0001f600": "Emoji: Grinning Face"}, "official_rfc8785", "RFC 8785 Section 3.2.3", "positive"),
        ("v02_ascii_sorting", {"z": 1, "a": 2, "M": 3, "0": 4}, "project_rev18", "RFC 8785 Section 3.2.3", "positive"),
        ("v03_utf16_bmp", {"\u00e9": 1, "\u0065\u0301": 2, "\u20ac": 3}, "project_rev18", "RFC 8785 Section 3.2.3", "positive"),
        ("v04_utf16_supplementary", {"\U00010000": "linear_b", "\ue000": "pua", "\U0001f680": "rocket"}, "project_rev18", "RFC 8785 Section 3.2.3", "positive"),
        ("v05_u1f600_vs_ufb33", {"\ufb33": "bmp", "\U0001f600": "surrogate"}, "official_rfc8785", "RFC 8785 Section 3.2.3", "positive"),
        ("v06_escapes_control", {"s": "quote:\" slash:\\ nl:\n tab:\t ctrl:\u0001"}, "project_rev18", "RFC 8785 Section 3.2.2.2", "positive"),
        ("v07_unicode_no_nfc", {"nfc": "\u00e9", "nfd": "e\u0301"}, "project_rev18", "RFC 8785 Section 3.2.2.2", "positive"),
        ("v08_zero", {"v": 0}, "official_rfc8785", "RFC 8785 Section 3.2.2.3", "positive"),
        ("v09_neg_zero", {"v": -0.0}, "official_rfc8785", "RFC 8785 Section 3.2.2.3", "positive"),
        ("v10_1e_minus_6", {"v": 1e-6}, "official_rfc8785", "RFC 8785 Appendix B", "positive"),
        ("v11_1e_minus_7", {"v": 1e-7}, "official_rfc8785", "RFC 8785 Appendix B", "positive"),
        ("v12_1e20", {"v": 1e20}, "official_rfc8785", "RFC 8785 Appendix B", "positive"),
        ("v13_1e21", {"v": 1e21}, "official_rfc8785", "RFC 8785 Appendix B", "positive"),
        ("v14_boundary_floats", {"max": 1e30, "min": -1e30, "small": 5e-324}, "official_rfc8785", "RFC 8785 Appendix B", "positive"),
        ("v15_ieee754_rounding", {"v1": 333333333.33333329, "v2": 4.50, "v3": 2e-3}, "official_rfc8785", "RFC 8785 Appendix B", "positive"),
        ("v16_non_finite_negative", {"raw_note": "NaN and Infinity must be rejected at runtime"}, "project_rev18", "RFC 8785 Section 3.2.2.3", "negative"),
        ("v17_large_int_safe_bound", {"safe_max": 9007199254740991, "safe_min": -9007199254740991}, "project_rev18", "RFC 8785 Section 3.2.2.3 / I-JSON", "positive"),
        ("v18_nested_mixed", {"arr": [True, False, None, {"b": 1, "a": [0, -0.0, "x"]}]}, "project_rev18", "RFC 8785 Section 3.2", "positive"),
    ]
    for name, inp, origin, ref, cls in rfc8785_specs:
        if cls == "positive":
            cbytes = canonical_dual(inp)
            vec = {
                "name": name,
                "input": inp,
                "expected_jcs_utf8": cbytes.decode("utf-8"),
                "expected_sha256": sha256_bytes(cbytes),
                "origin": origin,
                "normative_ref": ref,
                "classification": cls,
            }
        else:
            vec = {
                "name": name,
                "input_description": "float('nan'), float('inf'), float('-inf')",
                "expected_error": "ValueError",
                "origin": origin,
                "normative_ref": ref,
                "classification": cls,
            }
        (TV_RFC8785 / f"{name}.json").write_bytes((json.dumps(vec, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    # 6. Build Ed25519 official RFC 8032 TV1 vector
    rfc8032_pub_hex = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
    rfc8032_sig_hex = (
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    rfc8032_spki = bytes.fromhex("302a300506032b6570032100" + rfc8032_pub_hex)
    (TV_ED25519 / "rfc8032-tv1.json").write_bytes((json.dumps({
        "name": "rfc8032_section_7_1_test1",
        "normative_ref": "RFC 8032 Section 7.1 TEST 1",
        "message_hex": "",
        "public_key_spki_der_b64": base64.b64encode(rfc8032_spki).decode("ascii"),
        "authority_key_id": sha256_bytes(rfc8032_spki),
        "signature_b64": base64.b64encode(bytes.fromhex(rfc8032_sig_hex)).decode("ascii"),
        "signature_algorithm": "Ed25519",
    }, indent=2) + "\n").encode("utf-8"))

    # 7. Build signed dossier-tv-001 with cryptography Ed25519
    auth_priv, _, auth_spki, auth_spki_b64, auth_kid = make_test_key(b"revisao-hostil-v8-fase7-rev18-dossier-authority-tv")
    store_priv, _, store_spki, store_spki_b64, store_kid = make_test_key(b"revisao-hostil-v8-fase7-rev18-store-tv")
    wa_priv, _, wa_spki, wa_spki_b64, wa_kid = make_test_key(b"revisao-hostil-v8-fase7-rev18-witness-a-tv")
    wb_priv, _, wb_spki, wb_spki_b64, wb_kid = make_test_key(b"revisao-hostil-v8-fase7-rev18-witness-b-tv")

    dossier_payload = {
        "dossier_id": "dossier-tv-001",
        "issued_at_utc": "2026-11-24T00:00:00Z",
        "revocation_list_ref": "revocation-list-v1",
        "schema_version": "7.0.0",
        "scope": "administrative_independence_2of2_checkpoint",
        "valid_from_utc": "2026-11-24T00:00:00Z",
        "valid_until_utc": "2027-11-24T00:00:00Z",
        "domains": [
            {
                "administrative_domain": "store.org-a.example",
                "documentary_evidence_sha256": "a" * 64,
                "independent_rotation_recovery_ref": "runbook-store-v1",
                "infrastructure_provider": "provider-a",
                "key_custodian_id": "custodian-a",
                "kms_hsm_id": "kms-a-01",
                "legal_entity_id": "LEI-ORG-A",
                "legal_entity_name": "Org A Ltda",
                "no_shared_admin_credentials": True,
                "operator_key_id": store_kid,
                "role": "checkpoint_store",
            },
            {
                "administrative_domain": "witness-a.org-b.example",
                "documentary_evidence_sha256": "b" * 64,
                "independent_rotation_recovery_ref": "runbook-wa-v1",
                "infrastructure_provider": "provider-b",
                "key_custodian_id": "custodian-b",
                "kms_hsm_id": "kms-b-01",
                "legal_entity_id": "LEI-ORG-B",
                "legal_entity_name": "Org B S.A.",
                "no_shared_admin_credentials": True,
                "operator_key_id": wa_kid,
                "role": "witness_a",
            },
            {
                "administrative_domain": "witness-b.org-c.example",
                "documentary_evidence_sha256": "c" * 64,
                "independent_rotation_recovery_ref": "runbook-wb-v1",
                "infrastructure_provider": "provider-c",
                "key_custodian_id": "custodian-c",
                "kms_hsm_id": "kms-c-01",
                "legal_entity_id": "LEI-ORG-C",
                "legal_entity_name": "Org C Corp",
                "no_shared_admin_credentials": True,
                "operator_key_id": wb_kid,
                "role": "witness_b",
            },
        ],
    }
    dossier_jcs = canonical_dual(dossier_payload)
    dossier_sha = sha256_bytes(dossier_jcs)
    dossier_sig_b64 = base64.b64encode(auth_priv.sign(dossier_jcs)).decode("ascii")
    dossier_full = dict(dossier_payload)
    dossier_full["authority_signature"] = {
        "authority_id": "independent-audit-authority-tv",
        "signer_id": "auditor-tv-01",
        "authority_key_id": auth_kid,
        "public_key_spki_der_b64": auth_spki_b64,
        "signature_algorithm": "Ed25519",
        "signature_b64": dossier_sig_b64,
    }
    dossier_full["dossier_jcs_sha256"] = dossier_sha

    (TV_DOSSIER / "dossier-tv-001.json").write_bytes((json.dumps(dossier_full, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    (TV_DOSSIER / "dossier-tv-001.jcs.txt").write_bytes(dossier_jcs)
    (TV_DOSSIER / "dossier-tv-001.verification.json").write_bytes((json.dumps({
        "test_vector_id": "dossier-tv-001",
        "jcs_byte_length": len(dossier_jcs),
        "dossier_jcs_sha256": dossier_sha,
        "authority_key_id": auth_kid,
        "public_key_spki_der_b64": auth_spki_b64,
        "signature_algorithm": "Ed25519",
        "signature_b64": dossier_sig_b64,
    }, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    # 8. Build fully signed checkpoint-receipt-tv-001.json (REAL Ed25519 signatures + valid UUIDv4!)
    store_receipt_payload = {
        "protocol": "signed_store_receipt_v1",
        "store_id": "store-prod-01",
        "namespace": "revisao-hostil-v8",
        "previous_revision": "9",
        "new_revision": "10",
        "previous_checkpoint_sha256": "0" * 64,
        "new_checkpoint_sha256": "a" * 64,
        "policy_seq": "10",
        "policy_jcs_sha256": policy_jcs_sha256,
        "receipt_timestamp_utc": "2026-11-24T06:00:00Z",
        "store_key_id": store_kid,
        "signature_algorithm": "Ed25519",
    }
    store_receipt_jcs = canonical_dual(store_receipt_payload)
    store_receipt_sha = sha256_bytes(store_receipt_jcs)
    store_receipt_full = dict(store_receipt_payload)
    store_receipt_full["signature_b64"] = base64.b64encode(store_priv.sign(store_receipt_jcs)).decode("ascii")

    nonce_a = bytes([0x11] * 32)
    nonce_b = bytes([0x22] * 32)
    wa_payload = {
        "protocol": "checkpoint_freshness_assertion_v1",
        "witness_id": "witness-a",
        "witness_key_id": wa_kid,
        "store_id": "store-prod-01",
        "namespace": "revisao-hostil-v8",
        "policy_seq": "10",
        "checkpoint_revision": "10",
        "checkpoint_sha256": "a" * 64,
        "receipt_sha256": store_receipt_sha,
        "challenge_nonce_b64": base64.b64encode(nonce_a).decode("ascii"),
        "issued_at_utc": "2026-11-24T06:00:01Z",
        "signature_algorithm": "Ed25519",
    }
    wa_full = dict(wa_payload)
    wa_full["signature_b64"] = base64.b64encode(wa_priv.sign(canonical_dual(wa_payload))).decode("ascii")

    wb_payload = {
        "protocol": "checkpoint_freshness_assertion_v1",
        "witness_id": "witness-b",
        "witness_key_id": wb_kid,
        "store_id": "store-prod-01",
        "namespace": "revisao-hostil-v8",
        "policy_seq": "10",
        "checkpoint_revision": "10",
        "checkpoint_sha256": "a" * 64,
        "receipt_sha256": store_receipt_sha,
        "challenge_nonce_b64": base64.b64encode(nonce_b).decode("ascii"),
        "issued_at_utc": "2026-11-24T06:00:01Z",
        "signature_algorithm": "Ed25519",
    }
    wb_full = dict(wb_payload)
    wb_full["signature_b64"] = base64.b64encode(wb_priv.sign(canonical_dual(wb_payload))).decode("ascii")

    # Valid RFC 4122 UUIDv4 lowercase strings (ACH-B7-R17-004)
    uuid4_linux = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    uuid4_win = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"

    checkpoint_tv = {
        "schema_version": "7.0.0",
        "administrative_independence_dossier_sha256": dossier_sha,
        "signed_store_receipt": store_receipt_full,
        "witness_assertions": [wa_full, wb_full],
        "nonce_consumption_receipts": [
            {
                "nonce_sha256": sha256_bytes(nonce_a),
                "protocol_scope": "checkpoint_freshness_assertion_v1",
                "campaign_id": "camp-tv-001",
                "witness_id": "witness-a",
                "bound_witness_key_id": wa_kid,
                "store_epoch": "epoch-001",
                "persisted_tx_id": "tx-0001",
                "expires_at_monotonic_context": {
                    "clock_source": "linux_clock_monotonic_raw",
                    "unit": "nanoseconds",
                    "clock_context_id": uuid4_linux,
                    "store_epoch": "epoch-001",
                    "deadline_ns": 30000000000,
                },
            },
            {
                "nonce_sha256": sha256_bytes(nonce_b),
                "protocol_scope": "checkpoint_freshness_assertion_v1",
                "campaign_id": "camp-tv-001",
                "witness_id": "witness-b",
                "bound_witness_key_id": wb_kid,
                "store_epoch": "epoch-001",
                "persisted_tx_id": "tx-0002",
                "expires_at_monotonic_context": {
                    "clock_source": "windows_query_performance_counter",
                    "unit": "nanoseconds",
                    "clock_context_id": uuid4_win,
                    "store_epoch": "epoch-001",
                    "deadline_ns": 30000000000,
                },
            },
        ],
    }
    (TV_CHECKPOINT / "checkpoint-receipt-tv-001.json").write_bytes((json.dumps(checkpoint_tv, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    (TV_CHECKPOINT / "checkpoint-trust-bundle-tv-001.json").write_bytes((json.dumps({
        "campaign_id": "camp-tv-001",
        "protocol_scope": "checkpoint_freshness_assertion_v1",
        "expected_dossier_sha256": dossier_sha,
        "authorized_dossier_authorities": {auth_kid: auth_spki_b64},
        "store_key": {"key_id": store_kid, "public_key_spki_der_b64": store_spki_b64},
        "witness_keys": {
            "witness-a": {"key_id": wa_kid, "public_key_spki_der_b64": wa_spki_b64},
            "witness-b": {"key_id": wb_kid, "public_key_spki_der_b64": wb_spki_b64},
        },
    }, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    print("SUCCESS Rev18 build complete.")
    print(f"compatibility_policy_jcs_sha256={policy_jcs_sha256}")
    print(f"dossier_jcs_sha256={dossier_sha}")


if __name__ == "__main__":
    main()
