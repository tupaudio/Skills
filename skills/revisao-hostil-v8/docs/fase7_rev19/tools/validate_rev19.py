"""Validador documental autoverificavel da Revisao 19 (Fase 7 - v8.0-beta.7).

Corrige integralmente ACH-B7-R18-001 a ACH-B7-R18-006:
  - validate_trust_key() para autoridade do dossie, autoridade de revogacao, store e testemunhas
  - 3-way digest check do dossie (dossie, verification.json, trust_bundle.expected_dossier_sha256)
  - validate_administrative_independence() + validate_revocation_list() + parse_utc()
  - validate_monotonic_context_structure() separado de platform_clock.py
  - validate_compatibility_policy(..., registry) reconciliando digest com politica E registry
  - ZERO instrucoes 'assert' (resiste integralmente a 'python -O')
"""
import base64
import hashlib
import importlib.metadata
import json
import math
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_DEPS = {
    "rfc8785": "0.1.4",
    "jcs": "0.3.0",
    "cryptography": "50.0.2",
    "jsonschema": "4.26.0",
    "pytest": "9.2.0",
}

ED25519_SPKI_DER_HEADER = bytes.fromhex("302a300506032b6570032100")


class ValidationError(Exception):
    """Excecao explicita de validacao documental (nunca removida por python -O)."""


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def validate_dependencies() -> dict:
    loaded = {}
    for pkg, expected_ver in EXPECTED_DEPS.items():
        try:
            ver = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ValidationError(f"Dependencia obrigatoria ausente: {pkg}=={expected_ver}") from exc
        require(ver == expected_ver, f"Versao divergente para {pkg}: {ver} != {expected_ver}")
        loaded[pkg] = ver
    return loaded


def strict_parse(path: Path):
    raw_text = path.read_text(encoding="utf-8")
    require("PENDING_" not in raw_text, f"Placeholder proibido em {path}")

    def no_dups(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValidationError(f"Chave JSON duplicada '{k}' em {path}")
            d[k] = v
        return d

    def reject_const(c):
        raise ValidationError(f"Constante JSON invalida '{c}' em {path}")

    return json.loads(raw_text, object_pairs_hook=no_dups, parse_constant=reject_const)


def parse_utc(ts: str) -> datetime:
    """Parsing estrito RFC 3339 / ISO-8601 com timezone obrigatorio e normalizacao UTC."""
    require(isinstance(ts, str) and len(ts) >= 20, f"Timestamp malformado: {ts!r}")
    normalized = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"Timestamp invalido: {ts!r}") from exc
    require(dt.tzinfo is not None, f"Timestamp sem timezone proibido: {ts!r}")
    return dt.astimezone(timezone.utc)


def _check_json_types(obj) -> None:
    if obj is None or isinstance(obj, (bool, int, str)):
        return
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValidationError(f"Valor float nao finito proibido: {obj}")
        return
    if isinstance(obj, list):
        for item in obj:
            _check_json_types(item)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            require(isinstance(k, str), f"Chave nao string proibida: {type(k)}")
            _check_json_types(v)
        return
    raise ValidationError(f"Tipo Python fora do modelo JSON: {type(obj).__name__}")


def jcs_canonical(obj) -> bytes:
    import jcs as jcs_b
    import rfc8785 as jcs_a

    _check_json_types(obj)
    out_a = jcs_a.dumps(obj)
    out_b = jcs_b.canonicalize(obj)
    require(out_a == out_b, f"Divergencia rfc8785 vs jcs: {out_a!r} != {out_b!r}")
    return out_a


def load_ed25519_public_key(spki_der: bytes):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_der_public_key

    require(len(spki_der) == 44, f"SPKI DER Ed25519 deve ter 44 bytes, encontrado {len(spki_der)}")
    require(spki_der.startswith(ED25519_SPKI_DER_HEADER), "Cabecalho ASN.1 DER SPKI Ed25519 invalido")
    try:
        pub = load_der_public_key(spki_der)
    except Exception as exc:
        raise ValidationError(f"Falha ao decodificar SPKI DER: {exc}") from exc
    require(isinstance(pub, Ed25519PublicKey), "Chave nao e Ed25519PublicKey")
    require(pub.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo) == spki_der, "SPKI DER nao canonico")
    return pub


def verify_ed25519_signature(spki_der: bytes, msg: bytes, sig: bytes) -> None:
    require(len(sig) == 64, f"Assinatura Ed25519 deve ter 64 bytes, encontrado {len(sig)}")
    pub = load_ed25519_public_key(spki_der)
    try:
        pub.verify(sig, msg)
    except Exception as exc:
        raise ValidationError(f"Assinatura Ed25519 invalida: {exc}") from exc


def validate_trust_key(key_entry: dict, label: str) -> bytes:
    """Valida identidade criptografica de chave de confianca (ACH-B7-R18-001)."""
    require(isinstance(key_entry, dict), f"{label}: entrada de chave invalida")
    require(isinstance(key_entry.get("key_id"), str), f"{label}: key_id ausente")
    require(isinstance(key_entry.get("public_key_spki_der_b64"), str), f"{label}: public_key_spki_der_b64 ausente")
    try:
        spki = base64.b64decode(key_entry["public_key_spki_der_b64"], validate=True)
    except Exception as exc:
        raise ValidationError(f"{label}: SPKI Base64 invalido") from exc
    load_ed25519_public_key(spki)
    calculated_key_id = hashlib.sha256(spki).hexdigest()
    require(calculated_key_id == key_entry["key_id"], f"{label}: key_id nao corresponde a SHA256(SPKI_DER)")
    return spki


def validate_administrative_independence(dossier: dict) -> None:
    """Validacao semantica da independencia administrativa (ACH-B7-R18-002)."""
    domains = dossier["domains"]
    required_roles = {"checkpoint_store", "witness_a", "witness_b"}
    require(len(domains) == 3, "Exigidos exatamente tres dominios")
    by_role = {d["role"]: d for d in domains}
    require(set(by_role.keys()) == required_roles, "Papeis administrativos ausentes, duplicados ou invalidos")
    for field in ("legal_entity_id", "administrative_domain", "kms_hsm_id", "key_custodian_id", "operator_key_id"):
        values = [d[field] for d in domains]
        require(len(set(values)) == 3, f"Independencia administrativa violada: {field}")
    for domain in domains:
        require(domain["no_shared_admin_credentials"] is True, "Credenciais administrativas compartilhadas nao permitidas")
        require(bool(domain["documentary_evidence_sha256"]), "Evidencia documental ausente")
        require(bool(domain["independent_rotation_recovery_ref"]), "Procedimento independente de recuperacao ausente")


def validate_revocation_list(revocation_list: dict, trusted_authorities: dict, now_utc: datetime) -> set[str]:
    """Verifica assinatura, autoridade, validade temporal e revogacoes (ACH-B7-R18-002)."""
    auth_id = revocation_list["authority_key_id"]
    require(auth_id in trusted_authorities, "Autoridade da lista de revogacao nao confiavel")
    authority_spki = validate_trust_key(trusted_authorities[auth_id], "revocation_authority")
    payload = {k: v for k, v in revocation_list.items() if k != "signature_b64"}
    sig = base64.b64decode(revocation_list["signature_b64"], validate=True)
    verify_ed25519_signature(authority_spki, jcs_canonical(payload), sig)
    issued = parse_utc(revocation_list["issued_at_utc"])
    expires = parse_utc(revocation_list["valid_until_utc"])
    require(issued <= now_utc <= expires, "Lista de revogacao expirada ou futura")
    return {item["key_id"] for item in revocation_list["revoked_keys"]}


def validate_dossier(
    rev19: Path,
    dossier: dict,
    ver: dict,
    jcs_bytes: bytes,
    trust_bundle: dict,
    revocation_list: dict,
    now_utc: datetime,
) -> set[str]:
    """Valida dossie completo: schema, independencia, 3 digests, autoridade, janela temporal e revogacoes."""
    import jsonschema

    dossier_schema = strict_parse(rev19 / "schemas/7.0.0/schema_administrative_independence_dossier.json")
    jsonschema.Draft202012Validator(dossier_schema).validate(dossier)
    validate_administrative_independence(dossier)

    payload = {k: v for k, v in dossier.items() if k not in {"authority_signature", "dossier_jcs_sha256"}}
    calc_jcs = jcs_canonical(payload)
    require(calc_jcs == jcs_bytes, "Bytes JCS do dossie divergem de .jcs.txt")
    require(len(calc_jcs) == ver["jcs_byte_length"], "jcs_byte_length diverge")
    calc_sha = hashlib.sha256(calc_jcs).hexdigest()

    require(calc_sha == dossier["dossier_jcs_sha256"], "Digest do dossie diverge do proprio dossie")
    require(calc_sha == ver["dossier_jcs_sha256"], "Digest do dossie diverge de verification.json")
    require(calc_sha == trust_bundle["expected_dossier_sha256"], "Digest do dossie diverge do trust bundle")

    auth = dossier["authority_signature"]
    spki = validate_trust_key(
        {"key_id": auth["authority_key_id"], "public_key_spki_der_b64": auth["public_key_spki_der_b64"]},
        "dossier_authority",
    )
    authorized = trust_bundle["authorized_dossier_authorities"]
    require(auth["authority_key_id"] in authorized, "Autoridade do dossie nao autorizada")
    require(authorized[auth["authority_key_id"]] == auth["public_key_spki_der_b64"], "SPKI da autoridade diverge do trust bundle")

    sig = base64.b64decode(auth["signature_b64"], validate=True)
    verify_ed25519_signature(spki, calc_jcs, sig)

    vf = parse_utc(dossier["valid_from_utc"])
    issued = parse_utc(dossier["issued_at_utc"])
    vu = parse_utc(dossier["valid_until_utc"])
    require(vf <= issued <= vu, "Janela temporal inconsistente no dossie")
    require(vf <= now_utc <= vu, "Dossie expirado ou ainda nao valido")

    rev_schema = strict_parse(rev19 / "schemas/7.0.0/schema_revocation_list.json")
    jsonschema.Draft202012Validator(rev_schema).validate(revocation_list)
    revoked_keys = validate_revocation_list(revocation_list, trust_bundle["authorized_revocation_authorities"], now_utc)
    require(auth["authority_key_id"] not in revoked_keys, "Autoridade do dossie revogada")
    for dom in dossier["domains"]:
        require(dom["operator_key_id"] not in revoked_keys, f"Operador {dom['role']} revogado")
    return revoked_keys


def validate_process_clock_context_id(value: str) -> None:
    require(isinstance(value, str) and len(value) == 36, f"UUIDv4 invalido: {value!r}")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError(f"UUID malformado: {value!r}") from exc
    require(parsed.version == 4 and parsed.variant == uuid.RFC_4122 and str(parsed) == value, f"UUIDv4 nao canonico: {value!r}")


def validate_monotonic_context_structure(ctx: dict) -> None:
    """Validacao estritamente estrutural do contexto monotonico (ACH-B7-R18-004)."""
    require(ctx["clock_source"] in {"linux_clock_monotonic_raw", "windows_query_performance_counter"}, "clock_source invalido")
    require(ctx["unit"] == "nanoseconds", "unit deve ser nanoseconds")
    require(isinstance(ctx["deadline_ns"], int) and ctx["deadline_ns"] >= 0, "deadline_ns invalido")
    validate_process_clock_context_id(ctx["clock_context_id"])
    require(isinstance(ctx.get("store_epoch"), str) and len(ctx["store_epoch"]) > 0, "store_epoch ausente")


def validate_checkpoint_receipt_global(
    receipt: dict,
    policy: dict,
    dossier: dict,
    trust_bundle: dict,
    revoked_keys: set[str],
) -> None:
    """Reconciliacao semantica global do checkpoint com validate_trust_key() (ACH-B7-R18-001/002/003)."""
    ssr = receipt["signed_store_receipt"]
    wa = receipt["witness_assertions"]
    ncr = receipt["nonce_consumption_receipts"]

    require(len(wa) == 2 and len(ncr) == 2, "Exigidas 2 testemunhas e 2 recibos de nonce")
    require(receipt["administrative_independence_dossier_sha256"] == dossier["dossier_jcs_sha256"], "Hash do dossie diverge")
    require(ssr["policy_jcs_sha256"] == policy["compatibility_policy_jcs_sha256"], "policy_jcs_sha256 diverge")

    store_key = trust_bundle["store_key"]
    store_spki = validate_trust_key(store_key, "checkpoint_store")
    require(ssr["store_key_id"] == store_key["key_id"], "store_key_id nao autorizado")
    require(store_key["key_id"] not in revoked_keys, "Chave do store revogada")

    ssr_payload = {k: v for k, v in ssr.items() if k != "signature_b64"}
    ssr_jcs = jcs_canonical(ssr_payload)
    ssr_sha = hashlib.sha256(ssr_jcs).hexdigest()
    verify_ed25519_signature(store_spki, ssr_jcs, base64.b64decode(ssr["signature_b64"], validate=True))

    w_ids = [w["witness_id"] for w in wa]
    r_ids = [r["witness_id"] for r in ncr]
    require(len(set(w_ids)) == 2 and set(w_ids) == set(r_ids) == set(trust_bundle["witness_keys"].keys()), "Bijeccao de testemunhas falhou")
    require(len(set(r["nonce_sha256"] for r in ncr)) == 2, "nonce_sha256 duplicado")

    by_wid = {r["witness_id"]: r for r in ncr}
    for w in wa:
        wid = w["witness_id"]
        r = by_wid[wid]
        expected_wkey = trust_bundle["witness_keys"][wid]
        w_spki = validate_trust_key(expected_wkey, f"witness:{wid}")
        require(w["witness_key_id"] == expected_wkey["key_id"], f"witness_key_id nao autorizado para {wid}")
        require(expected_wkey["key_id"] not in revoked_keys, f"Testemunha {wid} revogada")
        require(w["store_id"] == ssr["store_id"], "store_id diverge")
        require(w["namespace"] == ssr["namespace"], "namespace diverge")
        require(w["policy_seq"] == ssr["policy_seq"], "policy_seq diverge")
        require(w["checkpoint_revision"] == ssr["new_revision"], "checkpoint_revision diverge")
        require(w["checkpoint_sha256"] == ssr["new_checkpoint_sha256"], "checkpoint_sha256 diverge")
        require(w["receipt_sha256"] == ssr_sha, "receipt_sha256 diverge")

        w_payload = {k: v for k, v in w.items() if k != "signature_b64"}
        verify_ed25519_signature(w_spki, jcs_canonical(w_payload), base64.b64decode(w["signature_b64"], validate=True))

        require(r["bound_witness_key_id"] == w["witness_key_id"], "bound_witness_key_id diverge")
        nonce_bytes = base64.b64decode(w["challenge_nonce_b64"], validate=True)
        require(len(nonce_bytes) == 32, "Nonce deve ter 32 bytes")
        require(r["nonce_sha256"] == hashlib.sha256(nonce_bytes).hexdigest(), "nonce_sha256 diverge")
        require(r["campaign_id"] == trust_bundle["campaign_id"], "campaign_id diverge")
        require(r["protocol_scope"] == trust_bundle["protocol_scope"], "protocol_scope diverge")
        require(r["store_epoch"] == r["expires_at_monotonic_context"]["store_epoch"], "store_epoch diverge")
        require(isinstance(r["persisted_tx_id"], str) and len(r["persisted_tx_id"]) > 0, "persisted_tx_id ausente")
        validate_monotonic_context_structure(r["expires_at_monotonic_context"])


def validate_all_schemas(rev19: Path) -> tuple[dict, dict, dict]:
    import jsonschema
    v7_dir = rev19 / "schemas/7.0.0"
    files = sorted(v7_dir.glob("*.json"))
    require(len(files) == 20, f"Esperados 20 schemas, encontrados {len(files)}")
    ids_seen, hashes, direct = set(), {}, {}
    for p in files:
        raw = p.read_bytes()
        hashes[p.name] = hashlib.sha256(raw).hexdigest()
        obj = strict_parse(p)
        jsonschema.Draft202012Validator.check_schema(obj)
        sid = obj.get("$id")
        require(bool(sid) and sid not in ids_seen, f"$id ausente ou duplicado em {p.name}")
        ids_seen.add(sid)
        refs = re.findall(r'"\$ref"\s*:\s*"([^"]+)"', raw.decode("utf-8"))
        for r in refs:
            require(r.startswith("./") and "/" not in r[2:], f"$ref proibido '{r}' em {p.name}")
        direct[p.name] = sorted(set(r[2:] for r in refs))

    trefs_map = {}
    for sn in hashes:
        vis, on_stack = {}, set()
        def dfs(node):
            on_stack.add(node)
            for nxt in direct[node]:
                require(nxt not in on_stack, f"Ciclo de $ref detectado em {nxt}")
                if nxt not in vis:
                    vis[nxt] = hashes[nxt]
                    dfs(nxt)
            on_stack.remove(node)
        dfs(sn)
        trefs_map[sn] = dict(sorted(vis.items()))
    return hashes, direct, trefs_map


def validate_schema_registry(rev19: Path, hashes: dict, direct: dict, trefs_map: dict) -> dict:
    reg = strict_parse(rev19 / "SCHEMA_REGISTRY_FASE7_REV19.json")
    require(set(reg["canonical_v7_schemas"].keys()) == set(hashes.keys()), "Registry diverge dos 20 schemas")
    for sn, meta in reg["canonical_v7_schemas"].items():
        require(meta["physical_sha256"] == hashes[sn], f"Hash divergente no Registry: {sn}")
        require(meta["direct_refs"] == direct[sn], f"direct_refs divergente: {sn}")
        require(meta["transitive_refs"] == trefs_map[sn], f"transitive_refs divergente: {sn}")
    return reg


def validate_compatibility_policy(rev19: Path, hashes: dict, trefs_map: dict, registry: dict) -> dict:
    """Reconcilia politica e digest com o Registry (ACH-B7-R18-005)."""
    import jsonschema
    ps = strict_parse(rev19 / "compatibility_policy.schema.json")
    pol = strict_parse(rev19 / "compatibility_policy_v1.json")
    jsonschema.Draft202012Validator.check_schema(ps)
    jsonschema.Draft202012Validator(ps).validate(pol)

    names = [e["schema_name"] for e in pol["entries"]]
    require(len(names) == 20 and len(set(names)) == 20 and set(names) == set(hashes.keys()), "Entradas da politica invalidas")
    for e in pol["entries"]:
        sn = e["schema_name"]
        require(e["schema_sha256"] == hashes[sn], f"schema_sha256 divergente: {sn}")
        rnames = [r["ref_schema_name"] for r in e["ref_hashes"]]
        require(len(rnames) == len(set(rnames)), f"ref_schema_name duplicado em {sn}")
        require({r["ref_schema_name"]: r["ref_sha256"] for r in e["ref_hashes"]} == trefs_map[sn], f"ref_hashes diverge em {sn}")
        ivers = [v["instance_schema_version"] for v in e["allowed_instance_versions"]]
        require(len(ivers) == len(set(ivers)), f"instance_schema_version duplicado em {sn}")

    payload = {k: v for k, v in pol.items() if k != "compatibility_policy_jcs_sha256"}
    calculated_digest = hashlib.sha256(jcs_canonical(payload)).hexdigest()
    require(calculated_digest == pol["compatibility_policy_jcs_sha256"], "Digest calculado diverge da politica")
    require(calculated_digest == registry["compatibility_policy_jcs_sha256"], "Digest calculado diverge do Registry")
    return pol


def main() -> int:
    rev19 = Path(__file__).resolve().parent.parent
    deps = validate_dependencies()
    print(f"[1] Dependencies verified: {deps}")

    json_files = sorted(rev19.rglob("*.json"))
    for jf in json_files:
        strict_parse(jf)
    print(f"[2] Strict JSON parse + zero placeholders OK ({len(json_files)} JSON files)")

    hashes, direct, trefs_map = validate_all_schemas(rev19)
    registry = validate_schema_registry(rev19, hashes, direct, trefs_map)
    policy = validate_compatibility_policy(rev19, hashes, trefs_map, registry)
    print("[3] All 20 Draft 2020-12 schemas, Registry & Policy digest reconciled OK")

    trust_bundle = strict_parse(rev19 / "test_vectors/checkpoint/checkpoint-trust-bundle-tv-001.json")
    dossier = strict_parse(rev19 / "test_vectors/dossier/dossier-tv-001.json")
    ver = strict_parse(rev19 / "test_vectors/dossier/dossier-tv-001.verification.json")
    jcs_bytes = (rev19 / "test_vectors/dossier/dossier-tv-001.jcs.txt").read_bytes()
    rev_list = strict_parse(rev19 / "test_vectors/trust/revocation-list-tv-001.json")
    now_utc = parse_utc("2026-11-24T12:00:00Z")

    revoked_keys = validate_dossier(rev19, dossier, ver, jcs_bytes, trust_bundle, rev_list, now_utc)
    rcpt = strict_parse(rev19 / "test_vectors/checkpoint/checkpoint-receipt-tv-001.json")
    validate_checkpoint_receipt_global(rcpt, policy, dossier, trust_bundle, revoked_keys)
    print("[4] Dossier, administrative independence, revocation list & global checkpoint reconciliation OK")

    print("ALL REV 19 VALIDATOR CHECKS PASSED.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValidationError as err:
        print(f"VALIDATION FAILED: {err}", file=sys.stderr)
        sys.exit(1)
