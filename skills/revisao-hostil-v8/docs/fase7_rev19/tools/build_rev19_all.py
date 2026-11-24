"""Gerador deterministico dos artefatos documentais da Revisao 19 (Fase 7 - v8.0-beta.7)."""
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

REV19 = Path(__file__).resolve().parent.parent
REPO = REV19.parent.parent.parent.parent
LEGACY_SRC = REPO / "skills/revisao-hostil-v8/references/schemas"
REV18_DIR = REPO / "skills/revisao-hostil-v8/docs/fase7_rev18"

LEGACY_DST = REV19 / "schemas/legacy-v8.0-beta.6.6"
V7_DST = REV19 / "schemas/7.0.0"
TV_RFC8785 = REV19 / "test_vectors/rfc8785"
TV_ED25519 = REV19 / "test_vectors/ed25519"
TV_CHECKPOINT = REV19 / "test_vectors/checkpoint"
TV_DOSSIER = REV19 / "test_vectors/dossier"
TV_TRUST = REV19 / "test_vectors/trust"

for d in (LEGACY_DST, V7_DST, TV_RFC8785, TV_ED25519, TV_CHECKPOINT, TV_DOSSIER, TV_TRUST, REV19 / "reports", REV19 / "tests"):
    d.mkdir(parents=True, exist_ok=True)

SHA256_PATTERN = r"^[0-9a-f]{64}(?![\r\n])$"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical_dual(obj) -> bytes:
    a = jcs_a.dumps(obj)
    b = jcs_b.canonicalize(obj)
    if a != b:
        raise RuntimeError(f"Divergencia rfc8785 vs jcs: {a!r} != {b!r}")
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

    # 2. Copy 19 v7.0.0 schemas from Rev18 + create 20th schema: schema_revocation_list.json (ACH-B7-R18-002)
    for src in sorted((REV18_DIR / "schemas/7.0.0").glob("*.json")):
        shutil.copyfile(src, V7_DST / src.name)

    revocation_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://revisao-hostil.v8/schemas/7.0.0/schema_revocation_list.json",
        "title": "Lista Assinada de Revogacao de Chaves (Fase 7 - Rev 19)",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "revocation_list_version", "issued_at_utc", "valid_until_utc",
            "authority_key_id", "revoked_keys", "signature_algorithm", "signature_b64"
        ],
        "properties": {
            "revocation_list_version": {"type": "string", "pattern": r"^(0|[1-9][0-9]{0,31})(?![\r\n])$"},
            "issued_at_utc": {"type": "string", "format": "date-time"},
            "valid_until_utc": {"type": "string", "format": "date-time"},
            "authority_key_id": {"type": "string", "pattern": SHA256_PATTERN},
            "revoked_keys": {
                "type": "array",
                "uniqueItems": True,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["key_id", "revoked_at_utc", "reason"],
                    "properties": {
                        "key_id": {"type": "string", "pattern": SHA256_PATTERN},
                        "revoked_at_utc": {"type": "string", "format": "date-time"},
                        "reason": {"type": "string", "minLength": 1},
                    },
                },
            },
            "signature_algorithm": {"type": "string", "const": "Ed25519"},
            "signature_b64": {"type": "string", "minLength": 86, "maxLength": 88},
        },
    }
    (V7_DST / "schema_revocation_list.json").write_bytes((json.dumps(revocation_schema, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    # 3. Update compatibility_policy.schema.json for 20 canonical contracts
    cs = json.loads((REV18_DIR / "compatibility_policy.schema.json").read_text(encoding="utf-8"))
    cs["title"] = "Schema Fechado da Politica de Compatibilidade (Fase 7 - Rev 19)"
    cs["properties"]["entries"]["minItems"] = 20
    cs["properties"]["entries"]["maxItems"] = 20
    (REV19 / "compatibility_policy.schema.json").write_bytes((json.dumps(cs, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    # 4. Recompute physical hashes and transitive refs for all 20 schemas
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
    (REV19 / "compatibility_policy_v1.json").write_bytes((json.dumps(policy_full, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

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
    (REV19 / "SCHEMA_REGISTRY_FASE7_REV19.json").write_bytes((json.dumps(registry, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    # 5. Copy RFC 8785, Ed25519, Dossier vectors from Rev 18
    for sub, dst in [("test_vectors/rfc8785", TV_RFC8785), ("test_vectors/ed25519", TV_ED25519), ("test_vectors/dossier", TV_DOSSIER)]:
        for src in sorted((REV18_DIR / sub).glob("*")):
            shutil.copyfile(src, dst / src.name)

    # 6. Build signed revocation-list-tv-001.json (ACH-B7-R18-002)
    rev_priv, _, _, rev_spki_b64, rev_kid = make_test_key(b"revisao-hostil-v8-fase7-rev19-revocation-authority-tv")
    rev_payload = {
        "revocation_list_version": "1",
        "issued_at_utc": "2026-11-24T00:00:00Z",
        "valid_until_utc": "2027-11-24T00:00:00Z",
        "authority_key_id": rev_kid,
        "revoked_keys": [],
        "signature_algorithm": "Ed25519",
    }
    rev_full = dict(rev_payload)
    rev_full["signature_b64"] = base64.b64encode(rev_priv.sign(canonical_dual(rev_payload))).decode("ascii")
    (TV_TRUST / "revocation-list-tv-001.json").write_bytes((json.dumps(rev_full, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    # 7. Rebuild checkpoint-receipt-tv-001.json with new policy_jcs_sha256 and revocation authority in trust bundle
    store_priv, _, _, store_spki_b64, store_kid = make_test_key(b"revisao-hostil-v8-fase7-rev18-store-tv")
    wa_priv, _, _, wa_spki_b64, wa_kid = make_test_key(b"revisao-hostil-v8-fase7-rev18-witness-a-tv")
    wb_priv, _, _, wb_spki_b64, wb_kid = make_test_key(b"revisao-hostil-v8-fase7-rev18-witness-b-tv")
    _, _, _, auth_spki_b64, auth_kid = make_test_key(b"revisao-hostil-v8-fase7-rev18-dossier-authority-tv")
    dossier_obj = json.loads((TV_DOSSIER / "dossier-tv-001.json").read_text(encoding="utf-8"))
    dossier_sha = dossier_obj["dossier_jcs_sha256"]

    ssr_payload = {
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
    ssr_jcs = canonical_dual(ssr_payload)
    ssr_sha = sha256_bytes(ssr_jcs)
    ssr_full = dict(ssr_payload)
    ssr_full["signature_b64"] = base64.b64encode(store_priv.sign(ssr_jcs)).decode("ascii")

    nonce_a, nonce_b = bytes([0x11] * 32), bytes([0x22] * 32)
    wa_payload = {
        "protocol": "checkpoint_freshness_assertion_v1",
        "witness_id": "witness-a",
        "witness_key_id": wa_kid,
        "store_id": "store-prod-01",
        "namespace": "revisao-hostil-v8",
        "policy_seq": "10",
        "checkpoint_revision": "10",
        "checkpoint_sha256": "a" * 64,
        "receipt_sha256": ssr_sha,
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
        "receipt_sha256": ssr_sha,
        "challenge_nonce_b64": base64.b64encode(nonce_b).decode("ascii"),
        "issued_at_utc": "2026-11-24T06:00:01Z",
        "signature_algorithm": "Ed25519",
    }
    wb_full = dict(wb_payload)
    wb_full["signature_b64"] = base64.b64encode(wb_priv.sign(canonical_dual(wb_payload))).decode("ascii")

    checkpoint_tv = {
        "schema_version": "7.0.0",
        "administrative_independence_dossier_sha256": dossier_sha,
        "signed_store_receipt": ssr_full,
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
                    "clock_context_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
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
                    "clock_context_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
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
        "authorized_revocation_authorities": {
            rev_kid: {"key_id": rev_kid, "public_key_spki_der_b64": rev_spki_b64}
        },
        "store_key": {"key_id": store_kid, "public_key_spki_der_b64": store_spki_b64},
        "witness_keys": {
            "witness-a": {"key_id": wa_kid, "public_key_spki_der_b64": wa_spki_b64},
            "witness-b": {"key_id": wb_kid, "public_key_spki_der_b64": wb_spki_b64},
        },
    }, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    print("SUCCESS Rev19 build complete.")
    print(f"compatibility_policy_jcs_sha256={policy_jcs_sha256}")


if __name__ == "__main__":
    main()
