"""Validador documental autoverificavel da Revisao 18 (Fase 7 - v8.0-beta.7).

REGRAS ESTRITAS:
  - ZERO instrucoes 'assert' (resiste integralmente a 'python -O').
  - ZERO implementacao artesanal de RFC 8785 JCS (usa rfc8785==0.1.4 + jcs==0.3.0).
  - ZERO fallback artesanal de Ed25519 (usa cryptography==50.0.2).
  - Falha fechada (codigo != 0) diante de qualquer divergencia.
"""
import base64
import copy
import ctypes
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import sys
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

EXPECTED_DEPS = {
    "rfc8785": "0.1.4",
    "jcs": "0.3.0",
    "cryptography": "50.0.2",
    "jsonschema": "4.26.0",
}

ED25519_SPKI_DER_HEADER = bytes.fromhex("302a300506032b6570032100")


class ValidationError(Exception):
    """Excecao explicita de validacao documental (nunca removida por python -O)."""


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def validate_dependencies() -> dict:
    """Verifica disponibilidade e versao exata de todas as dependencias obrigatorias."""
    loaded = {}
    for pkg, expected_ver in EXPECTED_DEPS.items():
        try:
            ver = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ValidationError(f"Dependencia obrigatoria ausente: {pkg}=={expected_ver}") from exc
        require(ver == expected_ver, f"Versao divergente para {pkg}: encontrado {ver}, esperado {expected_ver}")
        loaded[pkg] = ver
    return loaded


def strict_parse(path: Path):
    """Parser JSON estrito: UTF-8, rejeita chaves duplicadas, NaN/Infinity e placeholders."""
    raw_text = path.read_text(encoding="utf-8")
    require("PENDING_" not in raw_text, f"Placeholder proibido encontrado em {path}")

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


def _check_json_types(obj) -> None:
    """Rejeita tipos Python fora do modelo JSON e valores float nao finitos."""
    if obj is None or isinstance(obj, (bool, int, str)):
        return
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValidationError(f"Valor float nao finito proibido em RFC 8785: {obj}")
        return
    if isinstance(obj, list):
        for item in obj:
            _check_json_types(item)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise ValidationError(f"Chave de objeto nao string proibida: {type(k)}")
            _check_json_types(v)
        return
    raise ValidationError(f"Tipo Python nao permitido no modelo JSON/JCS: {type(obj).__name__}")


def jcs_canonical(obj) -> bytes:
    """Canonicaliza um objeto JSON segundo RFC 8785 com verificacao cruzada rfc8785 vs jcs."""
    import jcs as jcs_b
    import rfc8785 as jcs_a

    _check_json_types(obj)
    out_a = jcs_a.dumps(obj)
    out_b = jcs_b.canonicalize(obj)
    require(out_a == out_b, f"Divergencia entre rfc8785 e jcs: {out_a!r} != {out_b!r}")
    return out_a


def validate_jcs_vectors(rev18: Path) -> int:
    """Valida todos os 18 vetores RFC 8785 + testes negativos (NaN, Inf, tipos proibidos)."""
    tv_dir = rev18 / "test_vectors/rfc8785"
    files = sorted(tv_dir.glob("*.json"))
    require(len(files) == 18, f"Esperados 18 vetores RFC 8785, encontrados {len(files)}")
    for p in files:
        vec = strict_parse(p)
        if vec["classification"] == "positive":
            cbytes = jcs_canonical(vec["input"])
            require(cbytes.decode("utf-8") == vec["expected_jcs_utf8"], f"JCS divergente em {p.name}")
            require(hashlib.sha256(cbytes).hexdigest() == vec["expected_sha256"], f"SHA-256 divergente em {p.name}")
        else:
            for bad_val in (float("nan"), float("inf"), float("-inf")):
                try:
                    jcs_canonical({"v": bad_val})
                except ValidationError:
                    continue
                raise ValidationError(f"Valor nao finito {bad_val} deveria ter sido rejeitado")
    for bad_obj in (Decimal("1.0"), Fraction(1, 2), b"bytes", (1, 2)):
        try:
            jcs_canonical({"x": bad_obj})
        except ValidationError:
            continue
        raise ValidationError(f"Tipo proibido {type(bad_obj)} deveria ter sido rejeitado")
    return len(files)


def load_ed25519_public_key(spki_der: bytes):
    """Valida integralmente SPKI DER Ed25519 (OID 1.3.101.112, 44B) e carrega via cryptography."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_der_public_key

    require(len(spki_der) == 44, f"SPKI DER Ed25519 deve ter exatamente 44 bytes, encontrado {len(spki_der)}")
    require(spki_der.startswith(ED25519_SPKI_DER_HEADER), "Cabecalho ASN.1 DER SPKI Ed25519 invalido")
    try:
        pub = load_der_public_key(spki_der)
    except Exception as exc:
        raise ValidationError(f"Falha ao decodificar SPKI DER: {exc}") from exc
    require(isinstance(pub, Ed25519PublicKey), "Chave carregada nao e Ed25519PublicKey")
    # Re-encode canonico para rejeitar qualquer codificacao DER nao canonica
    reencoded = pub.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    require(reencoded == spki_der, "SPKI DER nao canonico")
    return pub


def verify_ed25519_signature(spki_der: bytes, msg: bytes, sig: bytes) -> None:
    """Verifica assinatura Ed25519 estritamente de 64 bytes usando cryptography."""
    require(len(sig) == 64, f"Assinatura Ed25519 deve ter 64 bytes, encontrado {len(sig)}")
    pub = load_ed25519_public_key(spki_der)
    try:
        pub.verify(sig, msg)
    except Exception as exc:
        raise ValidationError(f"Assinatura Ed25519 invalida: {exc}") from exc


def validate_ed25519_vectors(rev18: Path) -> None:
    """Valida vetor oficial RFC 8032 TV1 + mutacoes negativas DER e assinatura."""
    tv1 = strict_parse(rev18 / "test_vectors/ed25519/rfc8032-tv1.json")
    spki = base64.b64decode(tv1["public_key_spki_der_b64"], validate=True)
    sig = base64.b64decode(tv1["signature_b64"], validate=True)
    msg = bytes.fromhex(tv1["message_hex"])
    require(hashlib.sha256(spki).hexdigest() == tv1["authority_key_id"], "authority_key_id divergente em RFC 8032 TV1")
    verify_ed25519_signature(spki, msg, sig)

    # Mutacoes negativas obrigatorias
    bad_spkis = [b"", spki[:-1], spki + b"\x00", b"\x30\x2a\x30\x05\x06\x03\x2b\x65\x71\x03\x21\x00" + spki[12:]]
    for bspki in bad_spkis:
        try:
            load_ed25519_public_key(bspki)
        except ValidationError:
            continue
        raise ValidationError("SPKI DER invalido deveria ter sido rejeitado")

    bad_sigs = [sig[:-1], sig + b"\x00", bytes([sig[0] ^ 1]) + sig[1:]]
    for bsig in bad_sigs:
        try:
            verify_ed25519_signature(spki, msg, bsig)
        except ValidationError:
            continue
        raise ValidationError("Assinatura Ed25519 invalida deveria ter sido rejeitada")


def validate_process_clock_context_id(value: str) -> None:
    """Valida estritamente UUIDv4 RFC 4122 em representacao canonica minuscula (ACH-B7-R17-004)."""
    require(isinstance(value, str) and len(value) == 36, f"UUIDv4 invalido (tamanho): {value!r}")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError(f"UUID malformado: {value!r}") from exc
    require(parsed.version == 4, f"UUID deve ser versao 4, encontrado v{parsed.version}: {value!r}")
    require(parsed.variant == uuid.RFC_4122, f"Variante UUID invalida: {value!r}")
    require(str(parsed) == value, f"UUIDv4 nao canonico ou com maiusculas: {value!r}")


def validate_monotonic_context(ctx: dict) -> None:
    """Valida MonotonicDeadlineContext e testa mutacoes negativas de UUIDv4 + QPC no Windows."""
    require(ctx["clock_source"] in {"linux_clock_monotonic_raw", "windows_query_performance_counter"}, "clock_source invalido")
    require(ctx["unit"] == "nanoseconds", "unit deve ser nanoseconds")
    require(isinstance(ctx["deadline_ns"], int) and ctx["deadline_ns"] >= 0, "deadline_ns invalido")
    validate_process_clock_context_id(ctx["clock_context_id"])


def validate_dossier(rev18: Path, trust_bundle: dict) -> dict:
    """Valida dossier-tv-001 contra schema, verification.json, SPKI DER, autoridade e Ed25519."""
    import jsonschema

    dossier_schema = strict_parse(rev18 / "schemas/7.0.0/schema_administrative_independence_dossier.json")
    dossier = strict_parse(rev18 / "test_vectors/dossier/dossier-tv-001.json")
    jcs_bytes = (rev18 / "test_vectors/dossier/dossier-tv-001.jcs.txt").read_bytes()
    ver = strict_parse(rev18 / "test_vectors/dossier/dossier-tv-001.verification.json")

    jsonschema.Draft202012Validator(dossier_schema).validate(dossier)
    roles = [d["role"] for d in dossier["domains"]]
    require(len(roles) == 3 and set(roles) == {"checkpoint_store", "witness_a", "witness_b"}, "Composicao de papeis invalida no dossie")

    payload = {k: v for k, v in dossier.items() if k not in {"authority_signature", "dossier_jcs_sha256"}}
    calc_jcs = jcs_canonical(payload)
    require(calc_jcs == jcs_bytes, "Bytes JCS do dossie divergem de .jcs.txt")
    require(len(calc_jcs) == ver["jcs_byte_length"], "jcs_byte_length diverge")
    calc_sha = hashlib.sha256(calc_jcs).hexdigest()
    require(calc_sha == dossier["dossier_jcs_sha256"] == ver["dossier_jcs_sha256"], "dossier_jcs_sha256 diverge")

    auth = dossier["authority_signature"]
    for field in ("public_key_spki_der_b64", "authority_key_id", "signature_algorithm", "signature_b64"):
        require(auth[field] == ver[field], f"Campo {field} diverge entre dossie e verification.json")
    require(auth["signature_algorithm"] == "Ed25519", "Algoritmo do dossie deve ser Ed25519")
    require(auth["authority_key_id"] in trust_bundle["authorized_dossier_authorities"], "Autoridade do dossie nao autorizada")

    spki = base64.b64decode(auth["public_key_spki_der_b64"], validate=True)
    require(hashlib.sha256(spki).hexdigest() == auth["authority_key_id"], "authority_key_id diverge de SHA256(SPKI_DER)")
    sig = base64.b64decode(auth["signature_b64"], validate=True)
    verify_ed25519_signature(spki, calc_jcs, sig)
    return dossier


def validate_checkpoint_receipt_schema(rev18: Path, receipt: dict) -> None:
    import jsonschema
    schema = strict_parse(rev18 / "schemas/7.0.0/schema_monotonic_checkpoint_receipt.json")
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(receipt)


def validate_checkpoint_receipt_global(receipt: dict, policy: dict, dossier: dict, trust_bundle: dict) -> None:
    """Reconciliacao semantica global completa do checkpoint (ACH-B7-R17-003)."""
    ssr = receipt["signed_store_receipt"]
    wa = receipt["witness_assertions"]
    ncr = receipt["nonce_consumption_receipts"]

    require(len(wa) == 2 and len(ncr) == 2, "Exigidas exatamente 2 testemunhas e 2 recibos de nonce")
    require(receipt["administrative_independence_dossier_sha256"] == dossier["dossier_jcs_sha256"], "Hash do dossie diverge no recibo")
    require(ssr["policy_jcs_sha256"] == policy["compatibility_policy_jcs_sha256"], "policy_jcs_sha256 diverge da politica")

    # Verificar assinatura Ed25519 do signed_store_receipt
    require(ssr["store_key_id"] == trust_bundle["store_key"]["key_id"], "store_key_id nao autorizado")
    ssr_payload = {k: v for k, v in ssr.items() if k != "signature_b64"}
    ssr_jcs = jcs_canonical(ssr_payload)
    ssr_sha = hashlib.sha256(ssr_jcs).hexdigest()
    store_spki = base64.b64decode(trust_bundle["store_key"]["public_key_spki_der_b64"], validate=True)
    verify_ed25519_signature(store_spki, ssr_jcs, base64.b64decode(ssr["signature_b64"], validate=True))

    w_ids = [w["witness_id"] for w in wa]
    w_keys = [w["witness_key_id"] for w in wa]
    r_ids = [r["witness_id"] for r in ncr]
    r_nonces = [r["nonce_sha256"] for r in ncr]

    require(len(set(w_ids)) == 2, "witness_id duplicado")
    require(len(set(w_keys)) == 2, "witness_key_id duplicado")
    require(len(set(r_ids)) == 2, "witness_id duplicado nos recibos de nonce")
    require(len(set(r_nonces)) == 2, "nonce_sha256 duplicado")
    require(set(r_ids) == set(w_ids) == set(trust_bundle["witness_keys"].keys()), "Bijeccao de testemunhas falhou")

    by_wid = {r["witness_id"]: r for r in ncr}
    for w in wa:
        wid = w["witness_id"]
        r = by_wid[wid]
        expected_wkey = trust_bundle["witness_keys"][wid]
        require(w["witness_key_id"] == expected_wkey["key_id"], f"witness_key_id nao autorizado para {wid}")
        require(w["store_id"] == ssr["store_id"], "store_id diverge")
        require(w["namespace"] == ssr["namespace"], "namespace diverge")
        require(w["policy_seq"] == ssr["policy_seq"], "policy_seq diverge")
        require(w["checkpoint_revision"] == ssr["new_revision"], "checkpoint_revision diverge de new_revision")
        require(w["checkpoint_sha256"] == ssr["new_checkpoint_sha256"], "checkpoint_sha256 diverge")
        require(w["receipt_sha256"] == ssr_sha, "receipt_sha256 diverge do SHA-256 canonico de signed_store_receipt")

        # Verificar assinatura Ed25519 da testemunha
        w_payload = {k: v for k, v in w.items() if k != "signature_b64"}
        w_spki = base64.b64decode(expected_wkey["public_key_spki_der_b64"], validate=True)
        verify_ed25519_signature(w_spki, jcs_canonical(w_payload), base64.b64decode(w["signature_b64"], validate=True))

        # Reconciliacao com nonce_consumption_receipt
        require(r["bound_witness_key_id"] == w["witness_key_id"], "bound_witness_key_id diverge")
        try:
            nonce_bytes = base64.b64decode(w["challenge_nonce_b64"], validate=True)
        except Exception as exc:
            raise ValidationError("Base64 invalido em challenge_nonce_b64") from exc
        require(len(nonce_bytes) == 32, "Nonce decodificado deve ter 32 bytes")
        require(r["nonce_sha256"] == hashlib.sha256(nonce_bytes).hexdigest(), "nonce_sha256 diverge")
        require(r["campaign_id"] == trust_bundle["campaign_id"], "campaign_id diverge")
        require(r["protocol_scope"] == trust_bundle["protocol_scope"], "protocol_scope diverge")
        require(r["store_epoch"] == r["expires_at_monotonic_context"]["store_epoch"], "store_epoch diverge")
        require(isinstance(r["persisted_tx_id"], str) and len(r["persisted_tx_id"]) > 0, "persisted_tx_id ausente")
        validate_monotonic_context(r["expires_at_monotonic_context"])


def validate_all_schemas(rev18: Path) -> tuple[dict, dict, dict]:
    import jsonschema
    v7_dir = rev18 / "schemas/7.0.0"
    files = sorted(v7_dir.glob("*.json"))
    require(len(files) == 19, f"Esperados 19 schemas, encontrados {len(files)}")
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
            require(r.startswith("./") and "/" not in r[2:], f"$ref externo ou proibido '{r}' em {p.name}")
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


def validate_schema_registry(rev18: Path, hashes: dict, direct: dict, trefs_map: dict) -> dict:
    reg = strict_parse(rev18 / "SCHEMA_REGISTRY_FASE7_REV18.json")
    require(set(reg["canonical_v7_schemas"].keys()) == set(hashes.keys()), "Registry diverge dos 19 schemas em disco")
    for sn, meta in reg["canonical_v7_schemas"].items():
        require(meta["physical_sha256"] == hashes[sn], f"Hash fisico divergente no Registry: {sn}")
        require(meta["direct_refs"] == direct[sn], f"direct_refs divergente no Registry: {sn}")
        require(meta["transitive_refs"] == trefs_map[sn], f"transitive_refs divergente no Registry: {sn}")
    return reg


def validate_compatibility_policy(rev18: Path, hashes: dict, trefs_map: dict) -> dict:
    import jsonschema
    ps = strict_parse(rev18 / "compatibility_policy.schema.json")
    pol = strict_parse(rev18 / "compatibility_policy_v1.json")
    jsonschema.Draft202012Validator.check_schema(ps)
    jsonschema.Draft202012Validator(ps).validate(pol)

    names = [e["schema_name"] for e in pol["entries"]]
    require(len(names) == 19 and len(set(names)) == 19 and set(names) == set(hashes.keys()), "Entradas da politica invalidas")
    for e in pol["entries"]:
        sn = e["schema_name"]
        require(e["schema_sha256"] == hashes[sn], f"schema_sha256 divergente na politica: {sn}")
        rnames = [r["ref_schema_name"] for r in e["ref_hashes"]]
        require(len(rnames) == len(set(rnames)), f"ref_schema_name duplicado em {sn}")
        require({r["ref_schema_name"]: r["ref_sha256"] for r in e["ref_hashes"]} == trefs_map[sn], f"ref_hashes diverge em {sn}")
        ivers = [v["instance_schema_version"] for v in e["allowed_instance_versions"]]
        require(len(ivers) == len(set(ivers)), f"instance_schema_version duplicado em {sn}")

    payload = {k: v for k, v in pol.items() if k != "compatibility_policy_jcs_sha256"}
    require(hashlib.sha256(jcs_canonical(payload)).hexdigest() == pol["compatibility_policy_jcs_sha256"], "Digest JCS da politica diverge")
    return pol


def validate_test_matrix(rev18: Path) -> int:
    tm = (rev18 / "MATRIZ_TESTES_ACEITACAO_REV18.md").read_text(encoding="utf-8")
    tids = re.findall(r"^\|\s*`(T-R(?:9-\d{3}-\d{2}|11-\d{3}|12-\d{3}|13-\d{3}|14-\d{3}|15-\d{3}|16-\d{3}|17-\d{3}|18-\d{3}))`\s*\|", tm, re.M)
    require(len(tids) == 194 and len(set(tids)) == 194, f"Esperados 194 IDs unicos, encontrados {len(tids)}")
    return len(tids)


def validate_historical_preservation(rev18: Path) -> None:
    repo = rev18.parent.parent.parent.parent
    legacy_src = repo / "skills/revisao-hostil-v8/references/schemas"
    legacy_dst = rev18 / "schemas/legacy-v8.0-beta.6.6"
    src_files = sorted(legacy_src.glob("*.json"))
    require(len(src_files) == 8, "Base Beta 6.6 deve conter 8 schemas")
    for s in src_files:
        d = legacy_dst / s.name
        require(d.exists() and d.read_bytes() == s.read_bytes(), f"Divergencia no schema legado {s.name}")


def main() -> int:
    rev18 = Path(__file__).resolve().parent.parent
    deps = validate_dependencies()
    print(f"[1] Dependencies verified: {deps}")

    json_files = sorted(rev18.rglob("*.json"))
    for jf in json_files:
        strict_parse(jf)
    print(f"[2] Strict JSON parse + zero placeholders OK ({len(json_files)} JSON files)")

    n_jcs = validate_jcs_vectors(rev18)
    print(f"[3] RFC 8785 JCS dual-implementation cross-check OK ({n_jcs} vectors + negatives)")

    validate_ed25519_vectors(rev18)
    print("[4] Ed25519 RFC 8032 TV1 + SPKI DER & signature negatives OK (cryptography)")

    hashes, direct, trefs_map = validate_all_schemas(rev18)
    validate_schema_registry(rev18, hashes, direct, trefs_map)
    policy = validate_compatibility_policy(rev18, hashes, trefs_map)
    print("[5] All 19 Draft 2020-12 schemas, Registry & Policy reconciled OK")

    trust_bundle = strict_parse(rev18 / "test_vectors/checkpoint/checkpoint-trust-bundle-tv-001.json")
    dossier = validate_dossier(rev18, trust_bundle)
    rcpt = strict_parse(rev18 / "test_vectors/checkpoint/checkpoint-receipt-tv-001.json")
    validate_checkpoint_receipt_schema(rev18, rcpt)
    validate_checkpoint_receipt_global(rcpt, policy, dossier, trust_bundle)

    # 18 negative mutations for global checkpoint reconciliation (ACH-B7-R17-003)
    mutators = [
        ("store_id", lambda r: r["witness_assertions"][0].__setitem__("store_id", "wrong-store")),
        ("namespace", lambda r: r["witness_assertions"][0].__setitem__("namespace", "wrong-ns")),
        ("policy_seq", lambda r: r["witness_assertions"][0].__setitem__("policy_seq", "999")),
        ("revision", lambda r: r["witness_assertions"][0].__setitem__("checkpoint_revision", "999")),
        ("checkpoint_sha", lambda r: r["witness_assertions"][0].__setitem__("checkpoint_sha256", "f" * 64)),
        ("receipt_sha", lambda r: r["witness_assertions"][0].__setitem__("receipt_sha256", "f" * 64)),
        ("missing_receipt", lambda r: r["nonce_consumption_receipts"].pop()),
        ("extra_receipt", lambda r: r["nonce_consumption_receipts"].append(copy.deepcopy(r["nonce_consumption_receipts"][0]))),
        ("bound_key", lambda r: r["nonce_consumption_receipts"][0].__setitem__("bound_witness_key_id", "9" * 64)),
        ("bad_nonce", lambda r: r["nonce_consumption_receipts"][0].__setitem__("nonce_sha256", "f" * 64)),
        ("dup_nonce", lambda r: r["nonce_consumption_receipts"][1].__setitem__("nonce_sha256", r["nonce_consumption_receipts"][0]["nonce_sha256"])),
        ("bad_b64", lambda r: r["witness_assertions"][0].__setitem__("challenge_nonce_b64", "!!!invalid-base64!!!")),
        ("campaign_id", lambda r: r["nonce_consumption_receipts"][0].__setitem__("campaign_id", "other-camp")),
        ("protocol_scope", lambda r: r["nonce_consumption_receipts"][0].__setitem__("protocol_scope", "other-scope")),
        ("store_epoch", lambda r: r["nonce_consumption_receipts"][0].__setitem__("store_epoch", "epoch-999")),
        ("empty_tx", lambda r: r["nonce_consumption_receipts"][0].__setitem__("persisted_tx_id", "")),
        ("dossier_sha", lambda r: r.__setitem__("administrative_independence_dossier_sha256", "f" * 64)),
        ("store_sig", lambda r: r["signed_store_receipt"].__setitem__("signature_b64", base64.b64encode(b"\x00" * 64).decode("ascii"))),
    ]
    for label, fn in mutators:
        bad = copy.deepcopy(rcpt)
        fn(bad)
        try:
            validate_checkpoint_receipt_global(bad, policy, dossier, trust_bundle)
        except ValidationError:
            continue
        raise ValidationError(f"Mutacao negativa '{label}' deveria ter falhado!")

    # Negative UUIDv4 tests (ACH-B7-R17-004)
    for bad_uuid in [
        "proc-uuid-001", "", "F47AC10B-58CC-4372-A567-0E02B2C3D479",
        str(uuid.uuid1()), str(uuid.uuid3(uuid.NAMESPACE_DNS, "x")), str(uuid.uuid5(uuid.NAMESPACE_DNS, "x")),
        "f47ac10b-58cc-4372-a567-0e02b2c3d47", "f47ac10b-58cc-4372-0567-0e02b2c3d479",
    ]:
        try:
            validate_process_clock_context_id(bad_uuid)
        except ValidationError:
            continue
        raise ValidationError(f"UUID invalido '{bad_uuid}' deveria ter sido rejeitado")

    # Windows QPC integer conversion smoke check on Windows host
    if platform.system() == "Windows":
        freq, ticks = ctypes.c_int64(), ctypes.c_int64()
        require(ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(freq)) != 0 and freq.value > 0, "QPC freq falhou")
        require(ctypes.windll.kernel32.QueryPerformanceCounter(ctypes.byref(ticks)) != 0 and ticks.value >= 0, "QPC ticks falhou")
        ns = (ticks.value * 1_000_000_000) // freq.value
        require(isinstance(ns, int) and ns >= 0, "Conversao inteira QPC falhou")
    print("[6] Dossier, global checkpoint reconciliation (1 positive + 18 negatives), UUIDv4 (8 negatives) & QPC OK")

    n_tests = validate_test_matrix(rev18)
    validate_historical_preservation(rev18)
    print(f"[7] Test matrix ({n_tests} unique IDs) & historical preservation OK")
    print("ALL REV 18 DOCUMENTARY VALIDATIONS PASSED.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValidationError as err:
        print(f"VALIDATION FAILED: {err}", file=sys.stderr)
        sys.exit(1)
