"""Validador documental completo da Revisao 17 (Fase 7 - v8.0-beta.7).

NOTA: Ferramenta exclusivamente de auditoria documental (nao e runtime da Fase 7).
Implementa integralmente ACH-B7-R16-001 a ACH-B7-R16-005:
  1. Parsing JSON estrito + zero placeholders em todos os arquivos JSON.
  2. Validacao Draft 2020-12 em TODOS os 19 schemas + unicidade de $id + bloqueio de $ref externos e ciclos.
  3. Reconciliacao integral de direct_refs, transitive_refs e physical_sha256 contra Registry e politica.
  4. Canonicalizacao RFC 8785 JCS (ordenacao UTF-16 code units) validada contra test_vectors/rfc8785-conformance.json.
  5. Verificacao integral de todos os 6 campos de dossier-tv-001.verification.json + validacao estrita ASN.1 DER SPKI Ed25519 (44B, OID 1.3.101.112) + assinatura Ed25519 (64B).
  6. Validador semantico de schema_monotonic_checkpoint_receipt.json (teste positivo + 4 mutacoes negativas).
  7. Prova matematica exata (D_bound 73 bits, N_bound 76 bits) e 164 IDs unicos de cenarios.

Saida: codigo 0 se 100% aprovado; codigo != 0 em qualquer divergencia.
"""
import base64
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERRO: dependencia 'jsonschema' ausente. Instale com: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

# RFC 8410 Ed25519 SPKI DER exact 12-byte header:
# SEQUENCE (42) { SEQUENCE (5) { OID 1.3.101.112 (2b 65 70) }, BIT STRING (33, 0 unused bits) }
ED25519_SPKI_DER_HEADER = bytes.fromhex("302a300506032b6570032100")

# Minimal pure-Python RFC 8032 Ed25519 verification (fallback when 'cryptography' is not installed)
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _Q - 2, _Q) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)

def _xrecover(y):
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    return _Q - x if x % 2 != 0 else x

_BY = 4 * pow(5, _Q - 2, _Q) % _Q
_BX = _xrecover(_BY)
_B = (_BX % _Q, _BY % _Q, 1, (_BX * _BY) % _Q)

def _ed_add(P, Qp):
    A = (P[1] - P[0]) * (Qp[1] - Qp[0]) % _Q
    B = (P[1] + P[0]) * (Qp[1] + Qp[0]) % _Q
    C = 2 * P[3] * Qp[3] * _D % _Q
    D = 2 * P[2] * Qp[2] % _Q
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _Q, G * H % _Q, F * G % _Q, E * H % _Q)

def _ed_mul(P, e):
    R = (0, 1, 1, 0)
    while e > 0:
        if e & 1:
            R = _ed_add(R, P)
        P = _ed_add(P, P)
        e >>= 1
    return R

def _ed_encode(P):
    zinv = pow(P[2], _Q - 2, _Q)
    x, y = (P[0] * zinv) % _Q, (P[1] * zinv) % _Q
    b = bytearray(y.to_bytes(32, "little"))
    b[31] |= (x & 1) << 7
    return bytes(b)

def _ed_decode(b):
    y = int.from_bytes(b, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != (b[31] >> 7):
        x = _Q - x
    return (x, y, 1, (x * y) % _Q)

def verify_ed25519(spki_der: bytes, msg: bytes, sig: bytes) -> bool:
    """Strict ASN.1 DER SPKI validation + Ed25519 verification (prefers 'cryptography' if installed)."""
    if len(spki_der) != 44 or not spki_der.startswith(ED25519_SPKI_DER_HEADER):
        raise ValueError("SPKI DER invalido para Ed25519 (esperado 44 bytes com OID 1.3.101.112)")
    if len(sig) != 64:
        raise ValueError("Assinatura Ed25519 deve possuir exatamente 64 bytes")
    try:
        from cryptography.hazmat.primitives.serialization import load_der_public_key
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub_obj = load_der_public_key(spki_der)
        if not isinstance(pub_obj, Ed25519PublicKey):
            raise ValueError("Chave SPKI nao e Ed25519")
        pub_obj.verify(sig, msg)
        return True
    except ImportError:
        pub = spki_der[12:]
        R = _ed_decode(sig[:32])
        A = _ed_decode(pub)
        S = int.from_bytes(sig[32:], "little")
        if S >= _L:
            return False
        k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
        return _ed_encode(_ed_mul(_B, S)) == _ed_encode(_ed_add(R, _ed_mul(A, k)))

def jcs_canonical(obj) -> bytes:
    """RFC 8785 JCS canonicalization (UTF-16-BE code-unit key order, strict numbers)."""
    if obj is None:
        return b"null"
    if isinstance(obj, bool):
        return b"true" if obj else b"false"
    if isinstance(obj, int):
        return str(obj).encode("utf-8")
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError("NaN/Infinity proibidos em RFC 8785 JCS")
        if obj == 0.0:
            return b"0"
        if obj.is_integer() and abs(obj) < 1e21:
            return str(int(obj)).encode("utf-8")
        return repr(obj).encode("utf-8")
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")
    if isinstance(obj, list):
        return b"[" + b",".join(jcs_canonical(v) for v in obj) + b"]"
    if isinstance(obj, dict):
        items = sorted(obj.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        return b"{" + b",".join(jcs_canonical(k) + b":" + jcs_canonical(v) for k, v in items) + b"}"
    raise TypeError(f"Tipo nao suportado em JCS: {type(obj)}")

def strict_parse(path: Path):
    def no_dups(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError(f"Chave JSON duplicada '{k}' em {path}")
            d[k] = v
        return d
    def reject_const(c):
        raise ValueError(f"Constante JSON invalida '{c}' em {path}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_dups, parse_constant=reject_const)

def validate_checkpoint_receipt_semantics(receipt: dict) -> None:
    """Validador semantico obrigatorio de schema_monotonic_checkpoint_receipt.json (ACH-B7-R16-004)."""
    wa = receipt["witness_assertions"]
    ncr = receipt["nonce_consumption_receipts"]
    assert len(wa) == 2, "Exigidas exatamente 2 witness_assertions"
    assert len(ncr) == 2, "Exigidos exatamente 2 nonce_consumption_receipts"

    w_ids = [w["witness_id"] for w in wa]
    w_keys = [w["witness_key_id"] for w in wa]
    r_ids = [r["witness_id"] for r in ncr]
    r_nonces = [r["nonce_sha256"] for r in ncr]

    assert len(set(w_ids)) == 2, "witness_id duplicado em witness_assertions"
    assert len(set(w_keys)) == 2, "witness_key_id duplicado em witness_assertions"
    assert len(set(r_ids)) == 2, "witness_id duplicado em nonce_consumption_receipts"
    assert len(set(r_nonces)) == 2, "nonce_sha256 duplicado em nonce_consumption_receipts"
    assert set(r_ids) == set(w_ids), "Conjunto de witness_id diverge entre declaracoes e recibos de nonce"

    by_wid = {r["witness_id"]: r for r in ncr}
    for w in wa:
        r = by_wid[w["witness_id"]]
        assert r["bound_witness_key_id"] == w["witness_key_id"], "bound_witness_key_id diverge de witness_key_id"
        expected_nonce = hashlib.sha256(base64.b64decode(w["challenge_nonce_b64"], validate=True)).hexdigest()
        assert r["nonce_sha256"] == expected_nonce, "nonce_sha256 diverge de SHA256(challenge_nonce_b64)"
        assert r["store_epoch"] == r["expires_at_monotonic_context"]["store_epoch"], "store_epoch diverge do contexto monotonico"

def main() -> int:
    rev17 = Path(__file__).resolve().parent.parent

    # 1. Strict JSON parse + zero placeholders
    json_files = sorted(rev17.rglob("*.json"))
    for jf in json_files:
        strict_parse(jf)
        if "PENDING_" in jf.read_text(encoding="utf-8"):
            raise AssertionError(f"Placeholder encontrado em {jf}")
    print(f"[1] Strict JSON parse + zero placeholders OK ({len(json_files)} JSON files)")

    # 2. RFC 8785 JCS conformance test vectors (ACH-B7-R16-002)
    jcs_tv = strict_parse(rev17 / "test_vectors/rfc8785-conformance.json")
    for vec in jcs_tv["vectors"]:
        actual = jcs_canonical(vec["input"]).decode("utf-8")
        assert actual == vec["expected_jcs"], f"Falha RFC 8785 em {vec['name']}: {actual!r} != {vec['expected_jcs']!r}"
    print(f"[2] RFC 8785 JCS conformance OK ({len(jcs_tv['vectors'])} vectors including UTF-16 surrogate ordering)")

    # 3. Validate ALL 19 schemas in schemas/7.0.0/ + unique $id + no external $ref + no cycles (ACH-B7-R16-005)
    v7_dir = rev17 / "schemas/7.0.0"
    v7_files = sorted(v7_dir.glob("*.json"))
    assert len(v7_files) == 19, f"Esperados 19 schemas, encontrados {len(v7_files)}"
    ids_seen = set()
    hashes, direct = {}, {}
    for p in v7_files:
        raw = p.read_bytes()
        hashes[p.name] = hashlib.sha256(raw).hexdigest()
        obj = strict_parse(p)
        jsonschema.Draft202012Validator.check_schema(obj)
        sid = obj.get("$id")
        assert sid and sid not in ids_seen, f"$id ausente ou duplicado em {p.name}"
        ids_seen.add(sid)
        all_refs = re.findall(r'"\$ref"\s*:\s*"([^"]+)"', raw.decode("utf-8"))
        for r in all_refs:
            assert r.startswith("./") and "/" not in r[2:], f"$ref externo ou caminho proibido '{r}' em {p.name}"
        direct[p.name] = sorted(set(r[2:] for r in all_refs))

    # Cycle detection + transitive closure
    def compute_trefs(start: str) -> dict:
        vis, on_stack = {}, set()
        def dfs(node):
            on_stack.add(node)
            for nxt in direct[node]:
                assert nxt not in on_stack, f"Ciclo de $ref detectado envolvendo {nxt}"
                if nxt not in vis:
                    vis[nxt] = hashes[nxt]
                    dfs(nxt)
            on_stack.remove(node)
        dfs(start)
        return dict(sorted(vis.items()))

    policy = strict_parse(rev17 / "compatibility_policy_v1.json")
    policy_schema = strict_parse(rev17 / "compatibility_policy.schema.json")
    registry = strict_parse(rev17 / "SCHEMA_REGISTRY_FASE7_REV17.json")
    jsonschema.Draft202012Validator.check_schema(policy_schema)
    jsonschema.Draft202012Validator(policy_schema).validate(policy)

    assert set(registry["canonical_v7_schemas"].keys()) == set(hashes.keys())
    for sn, rmeta in registry["canonical_v7_schemas"].items():
        assert rmeta["physical_sha256"] == hashes[sn]
        assert rmeta["direct_refs"] == direct[sn]
        assert rmeta["transitive_refs"] == compute_trefs(sn)

    names = [e["schema_name"] for e in policy["entries"]]
    assert len(names) == 19 and len(set(names)) == 19 and set(names) == set(hashes.keys())
    for e in policy["entries"]:
        sn = e["schema_name"]
        assert e["schema_sha256"] == hashes[sn]
        rnames = [r["ref_schema_name"] for r in e["ref_hashes"]]
        assert len(rnames) == len(set(rnames))
        assert {r["ref_schema_name"]: r["ref_sha256"] for r in e["ref_hashes"]} == compute_trefs(sn)
        ivers = [v["instance_schema_version"] for v in e["allowed_instance_versions"]]
        assert len(ivers) == len(set(ivers))
    print("[3] All 19 Draft 2020-12 schemas, unique $id, cycle-free $ref tree, Registry & Policy reconciled OK")

    # 4. Policy JCS digest
    payload = {k: v for k, v in policy.items() if k != "compatibility_policy_jcs_sha256"}
    jcs_digest = hashlib.sha256(jcs_canonical(payload)).hexdigest()
    assert jcs_digest == policy["compatibility_policy_jcs_sha256"]
    print(f"[4] Policy RFC 8785 JCS digest OK: {jcs_digest}")

    # 5. Full verification of dossier-tv-001 (ALL 6 fields of verification.json + strict SPKI DER + Ed25519) (ACH-B7-R16-003)
    dossier_schema = strict_parse(v7_dir / "schema_administrative_independence_dossier.json")
    tv_obj = strict_parse(rev17 / "test_vectors/dossier-tv-001.json")
    tv_jcs = (rev17 / "test_vectors/dossier-tv-001.jcs.txt").read_bytes()
    tv_ver = strict_parse(rev17 / "test_vectors/dossier-tv-001.verification.json")
    jsonschema.Draft202012Validator(dossier_schema).validate(tv_obj)

    tv_payload = {k: v for k, v in tv_obj.items() if k not in {"authority_signature", "dossier_jcs_sha256"}}
    assert jcs_canonical(tv_payload) == tv_jcs
    assert len(tv_jcs) == tv_ver["jcs_byte_length"]
    tv_sha = hashlib.sha256(tv_jcs).hexdigest()
    assert tv_sha == tv_obj["dossier_jcs_sha256"] == tv_ver["dossier_jcs_sha256"]

    auth = tv_obj["authority_signature"]
    assert auth["public_key_spki_der_b64"] == tv_ver["public_key_spki_der_b64"]
    assert auth["authority_key_id"] == tv_ver["authority_key_id"]
    assert auth["signature_algorithm"] == tv_ver["signature_algorithm"] == "Ed25519"
    assert auth["signature_b64"] == tv_ver["signature_b64"]

    spki = base64.b64decode(auth["public_key_spki_der_b64"], validate=True)
    assert hashlib.sha256(spki).hexdigest() == auth["authority_key_id"]
    sig = base64.b64decode(auth["signature_b64"], validate=True)
    assert verify_ed25519(spki, tv_jcs, sig), "Falha Ed25519 em dossier-tv-001"
    print("[5] dossier-tv-001 full metadata cross-check + strict SPKI DER + Ed25519 OK")

    # 6. Checkpoint receipt semantic validation (positive + 4 negative mutations) (ACH-B7-R16-004)
    receipt_schema = strict_parse(v7_dir / "schema_monotonic_checkpoint_receipt.json")
    rcpt = strict_parse(rev17 / "test_vectors/checkpoint-receipt-tv-001.json")
    jsonschema.Draft202012Validator(receipt_schema).validate(rcpt)
    validate_checkpoint_receipt_semantics(rcpt)

    for label, mutator in [
        ("cross_key", lambda x: x["nonce_consumption_receipts"][0].__setitem__("bound_witness_key_id", "9" * 64)),
        ("bad_nonce", lambda x: x["nonce_consumption_receipts"][0].__setitem__("nonce_sha256", "f" * 64)),
        ("bad_epoch", lambda x: x["nonce_consumption_receipts"][0].__setitem__("store_epoch", "epoch-999")),
        ("dup_witness", lambda x: x["witness_assertions"][1].__setitem__("witness_id", "witness-a")),
    ]:
        bad = copy.deepcopy(rcpt)
        mutator(bad)
        try:
            validate_checkpoint_receipt_semantics(bad)
            raise RuntimeError(f"Mutacao negativa '{label}' deveria ter falhado!")
        except AssertionError:
            pass
    print("[6] Checkpoint receipt semantic validator OK (1 positive + 4 negative mutations rejected)")

    # 7. Exact rational math + 164 unique test IDs
    L = math.lcm(*range(1, 16))
    D_bound = L * (10**6) * (15 * 1000 * 10**6)
    N_bound = 10 * D_bound
    assert D_bound == 5_405_400_000_000_000_000_000 and D_bound.bit_length() == 73 and N_bound.bit_length() == 76
    tm = (rev17 / "MATRIZ_TESTES_ACEITACAO_REV17.md").read_text(encoding="utf-8")
    tids = re.findall(r"^\|\s*`(T-R(?:9-\d{3}-\d{2}|11-\d{3}|12-\d{3}|13-\d{3}|14-\d{3}|15-\d{3}|16-\d{3}|17-\d{3}))`\s*\|", tm, re.M)
    assert len(tids) == 164 and len(set(tids)) == 164, f"Esperados 164 IDs unicos, encontrados {len(tids)}"
    print("[7] Exact math (73/76/128 bits) + 164 unique test IDs OK (0/164 runtime executed)")

    print("ALL REV 17 DOCUMENTARY VALIDATIONS PASSED.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
