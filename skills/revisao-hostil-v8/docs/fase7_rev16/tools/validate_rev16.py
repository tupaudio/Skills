"""Validador documental deterministico da Revisao 16 (Fase 7 - v8.0-beta.7).

NOTA: Este script e uma ferramenta exclusivamente documental (ACH-B7-R15-004)
para reproducao independente dos artefatos publicados em docs/fase7_rev16/.
NAO constitui implementacao Python de runtime da Fase 7.

Saida: codigo 0 se todas as verificacoes passarem; codigo != 0 em qualquer divergencia.
"""
import base64
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

# Minimal pure-Python RFC 8032 Ed25519 verification (zero external crypto dependencies)
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

def ed25519_verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    if len(sig) != 64 or len(pub) != 32:
        return False
    R = _ed_decode(sig[:32])
    A = _ed_decode(pub)
    S = int.from_bytes(sig[32:], "little")
    if S >= _L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pub + msg).digest(), "little") % _L
    return _ed_encode(_ed_mul(_B, S)) == _ed_encode(_ed_add(R, _ed_mul(A, k)))

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

def jcs_canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def main() -> int:
    rev16 = Path(__file__).resolve().parent.parent
    repo_root = rev16.parent.parent.parent

    # 1. Strict JSON parse + zero placeholders
    json_files = sorted(rev16.rglob("*.json"))
    for jf in json_files:
        strict_parse(jf)
        if "PENDING_" in jf.read_text(encoding="utf-8"):
            raise AssertionError(f"Placeholder encontrado em {jf}")
    print(f"[1] Strict JSON parse + zero placeholders OK ({len(json_files)} JSON files)")

    # 2. Draft 2020-12 schema checks + compatibility policy
    policy = strict_parse(rev16 / "compatibility_policy_v1.json")
    policy_schema = strict_parse(rev16 / "compatibility_policy.schema.json")
    registry = strict_parse(rev16 / "SCHEMA_REGISTRY_FASE7_REV16.json")
    dossier_schema = strict_parse(rev16 / "schemas/7.0.0/schema_administrative_independence_dossier.json")
    receipt_schema = strict_parse(rev16 / "schemas/7.0.0/schema_monotonic_checkpoint_receipt.json")

    for s in (policy_schema, dossier_schema, receipt_schema):
        jsonschema.Draft202012Validator.check_schema(s)
    jsonschema.Draft202012Validator(policy_schema).validate(policy)
    print("[2] Draft 2020-12 schemas + compatibility_policy_v1.json OK")

    # 3. Semantic validation: 19 unique contracts, 1-to-1 registry, disk transitive $ref tree, unique instance versions
    names = [e["schema_name"] for e in policy["entries"]]
    assert len(names) == 19 and len(set(names)) == 19
    assert set(names) == set(registry["canonical_v7_schemas"].keys())

    v7_dir = rev16 / "schemas/7.0.0"
    direct, hashes = {}, {}
    for p in sorted(v7_dir.glob("*.json")):
        raw = p.read_bytes()
        hashes[p.name] = hashlib.sha256(raw).hexdigest()
        direct[p.name] = sorted(set(re.findall(r'"\$ref"\s*:\s*"\./([^"]+)"', raw.decode("utf-8"))))

    def disk_trefs(name):
        vis, st = {}, list(direct[name])
        while st:
            r = st.pop()
            if r not in vis:
                vis[r] = hashes[r]
                for s in direct[r]:
                    if s not in vis:
                        st.append(s)
        return vis

    for e in policy["entries"]:
        sn = e["schema_name"]
        assert e["schema_sha256"] == hashes[sn]
        rnames = [r["ref_schema_name"] for r in e["ref_hashes"]]
        assert len(rnames) == len(set(rnames))
        assert {r["ref_schema_name"]: r["ref_sha256"] for r in e["ref_hashes"]} == disk_trefs(sn)
        ivers = [v["instance_schema_version"] for v in e["allowed_instance_versions"]]
        assert len(ivers) == len(set(ivers))
    print("[3] Semantic policy validation + 19 contracts + 19 transitive $ref OK")

    # 4. Policy JCS digest
    payload = {k: v for k, v in policy.items() if k != "compatibility_policy_jcs_sha256"}
    jcs_digest = hashlib.sha256(jcs_canonical(payload)).hexdigest()
    assert jcs_digest == policy["compatibility_policy_jcs_sha256"]
    print(f"[4] Policy JCS digest OK: {jcs_digest}")

    # 5. Reproducible test vector dossier-tv-001 (Draft 2020-12 + JCS + SHA-256 + Ed25519)
    tv_obj = strict_parse(rev16 / "test_vectors/dossier-tv-001.json")
    tv_jcs = (rev16 / "test_vectors/dossier-tv-001.jcs.txt").read_bytes()
    tv_ver = strict_parse(rev16 / "test_vectors/dossier-tv-001.verification.json")
    jsonschema.Draft202012Validator(dossier_schema).validate(tv_obj)
    tv_payload = {k: v for k, v in tv_obj.items() if k not in {"authority_signature", "dossier_jcs_sha256"}}
    assert jcs_canonical(tv_payload) == tv_jcs
    tv_sha = hashlib.sha256(tv_jcs).hexdigest()
    assert tv_sha == tv_obj["dossier_jcs_sha256"] == tv_ver["dossier_jcs_sha256"]
    spki = base64.b64decode(tv_obj["authority_signature"]["public_key_spki_der_b64"], validate=True)
    assert hashlib.sha256(spki).hexdigest() == tv_obj["authority_signature"]["authority_key_id"]
    raw_pub = spki[12:]  # RFC 8410 Ed25519 SPKI prefix is 12 bytes
    sig = base64.b64decode(tv_obj["authority_signature"]["signature_b64"], validate=True)
    assert ed25519_verify(raw_pub, tv_jcs, sig), "Falha na verificacao Ed25519 do vetor dossier-tv-001!"
    print(f"[5] Test vector dossier-tv-001 verified (Draft 2020-12 + {len(tv_jcs)}B JCS + SHA-256 + Ed25519)")

    # 6. Exact rational math bounds
    L = math.lcm(*range(1, 16))
    D_bound = L * (10**6) * (15 * 1000 * 10**6)
    N_bound = 10 * D_bound
    assert D_bound == 5_405_400_000_000_000_000_000 and D_bound.bit_length() == 73 and N_bound.bit_length() == 76
    print(f"[6] Exact math verified: D_bound={D_bound} (73 bits), N_bound={N_bound} (76 bits)")

    # 7. 154 unique acceptance test IDs
    tm = (rev16 / "MATRIZ_TESTES_ACEITACAO_REV16.md").read_text(encoding="utf-8")
    tids = re.findall(r"^\|\s*`(T-R(?:9-\d{3}-\d{2}|11-\d{3}|12-\d{3}|13-\d{3}|14-\d{3}|15-\d{3}|16-\d{3}))`\s*\|", tm, re.M)
    assert len(tids) == 154 and len(set(tids)) == 154, f"Expected 154 unique IDs, got {len(tids)}"
    print("[7] 154 unique test IDs verified (0/154 executed)")

    print("ALL REV 16 DOCUMENTARY VALIDATIONS PASSED.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
