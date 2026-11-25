#!/usr/bin/env python3
"""Montagem, preenchimento e geracao em lote de prompts v0.2 (bracos A e C).

Apenas biblioteca padrao. Nenhuma validacao usa assert (comportamento identico
sob python -O).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

UTF8_BOM = b"\xef\xbb\xbf"
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
BLOCK_NAMES = (
    "bloco1_cabecalho.txt",
    "bloco2_metodo_A.txt",
    "bloco3_metodo_C.txt",
    "bloco4_saida.txt",
)


class PromptBuildError(ValueError):
    """Erro de validacao na montagem ou preenchimento de prompts."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text_strict_no_bom(path: Path) -> str:
    if not path.is_file():
        raise PromptBuildError(f"Arquivo nao encontrado: {path}")
    raw = path.read_bytes()
    if raw.startswith(UTF8_BOM):
        raise PromptBuildError(f"Arquivo contem UTF-8 BOM (proibido): {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptBuildError(f"Arquivo nao e UTF-8 valido: {path}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_text_lf_no_bom(path: Path, text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    data = normalized.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)


def is_inside_git_repo(path: Path) -> bool:
    cur = path.resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".git").exists():
            return True
    return False


def _validate_pos_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PromptBuildError(f"Parametro '{name}' deve ser inteiro >= 1 (recebido: {value!r})")
    return value


def build_models(dir_blocos: Path, dir_saida: Path) -> Dict[str, str]:
    blocks: Dict[str, str] = {}
    hashes: Dict[str, str] = {}
    for bname in BLOCK_NAMES:
        bpath = dir_blocos / bname
        text = read_text_strict_no_bom(bpath)
        blocks[bname] = text.rstrip("\n")
        hashes[bname] = sha256_bytes((blocks[bname] + "\n").encode("utf-8"))

    modelo_a = f"{blocks['bloco1_cabecalho.txt']}\n\n{blocks['bloco2_metodo_A.txt']}\n\n{blocks['bloco4_saida.txt']}\n"
    modelo_c = f"{blocks['bloco1_cabecalho.txt']}\n\n{blocks['bloco3_metodo_C.txt']}\n\n{blocks['bloco4_saida.txt']}\n"

    out_a = dir_saida / "revisor_A_v0.2.txt"
    out_c = dir_saida / "revisor_C_v0.2.txt"
    hashes["revisor_A_v0.2.txt"] = write_text_lf_no_bom(out_a, modelo_a)
    hashes["revisor_C_v0.2.txt"] = write_text_lf_no_bom(out_c, modelo_c)
    return hashes


def fill_template_text(template: str, pairs: Sequence[Tuple[str, str]]) -> str:
    expected_keys = set(PLACEHOLDER_RE.findall(template))
    provided: Dict[str, str] = {}
    for key, val in pairs:
        if not key:
            raise PromptBuildError("Chave vazia em fill")
        if key in provided:
            raise PromptBuildError(f"Chave repetida: {key}")
        if key not in expected_keys:
            raise PromptBuildError(f"Chave desconhecida: {key}")
        if "{{" in val or "\n" in val or "\r" in val:
            raise PromptBuildError(f"Valor invalido para '{key}' (contem '{{{{' ou quebra de linha)")
        provided[key] = val

    missing = sorted(expected_keys - set(provided.keys()))
    if missing:
        raise PromptBuildError(f"Chaves faltando: {', '.join(missing)}")

    result = PLACEHOLDER_RE.sub(lambda m: provided[m.group(1)], template)
    if "{{" in result:
        raise PromptBuildError("Placeholder residual '{{' encontrado apos substituicao")
    return result


def fill_file(modelo_path: Path, saida_path: Path, kv_args: Sequence[str]) -> str:
    template = read_text_strict_no_bom(modelo_path)
    pairs: List[Tuple[str, str]] = []
    for item in kv_args:
        if "=" not in item:
            raise PromptBuildError(f"Argumento invalido (esperado CHAVE=VALOR): {item!r}")
        k, v = item.split("=", 1)
        pairs.append((k, v))
    filled = fill_template_text(template, pairs)
    return write_text_lf_no_bom(saida_path, filled)


def run_batch(plano_path: Path, dir_saida: Path, dir_blocos: Path | None = None) -> Dict[str, object]:
    if is_inside_git_repo(dir_saida):
        raise PromptBuildError(f"Recusado: dir_saida esta dentro de repositorio git: {dir_saida}")

    if not plano_path.is_file():
        raise PromptBuildError(f"Plano nao encontrado: {plano_path}")
    plan = json.loads(plano_path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise PromptBuildError("Plano JSON deve ser um objeto")

    if "max_linhas" not in plan or "max_achados" not in plan:
        raise PromptBuildError("Plano deve definir 'max_linhas' e 'max_achados' explicitamente")
    max_linhas = _validate_pos_int("max_linhas", plan["max_linhas"])
    max_achados = _validate_pos_int("max_achados", plan["max_achados"])

    if "ordem_seed" not in plan or isinstance(plan["ordem_seed"], bool) or not isinstance(plan["ordem_seed"], int):
        raise PromptBuildError("Plano deve definir 'ordem_seed' como inteiro")
    ordem_seed = plan["ordem_seed"]

    execucoes = plan.get("execucoes")
    if not isinstance(execucoes, list) or not execucoes:
        raise PromptBuildError("Plano deve conter lista nao vazia 'execucoes'")

    # Validate A/C pairing for every (doc_id, modelo, rodada)
    pairs_seen: Dict[Tuple[str, str, int], set] = {}
    for ex in execucoes:
        if not isinstance(ex, dict):
            raise PromptBuildError("Cada item de execucoes deve ser um objeto")
        for req in ("doc_id", "arquivo_numerado", "modelo", "sessao", "braco", "rodada"):
            if req not in ex:
                raise PromptBuildError(f"Campo obrigatorio ausente em execucao: {req}")
        braco = ex["braco"]
        if braco not in ("A", "C"):
            raise PromptBuildError(f"Braco invalido (esperado 'A' ou 'C'): {braco!r}")
        rodada = _validate_pos_int("rodada", ex["rodada"])
        key = (str(ex["doc_id"]), str(ex["modelo"]), rodada)
        pairs_seen.setdefault(key, set()).add(braco)

    incomplete = [k for k, arms in pairs_seen.items() if arms != {"A", "C"}]
    if incomplete:
        raise PromptBuildError(f"Pares A/C incompletos: {incomplete}")

    if dir_blocos is None:
        dir_blocos = Path(__file__).resolve().parent / "revisor_v0.2"

    dir_saida.mkdir(parents=True, exist_ok=True)
    # Build base models in memory/temp inside dir_saida/_modelos_base
    modelos_dir = dir_saida / "_modelos_base"
    base_hashes = build_models(dir_blocos, modelos_dir)
    base_texts = {
        "A": read_text_strict_no_bom(modelos_dir / "revisor_A_v0.2.txt"),
        "C": read_text_strict_no_bom(modelos_dir / "revisor_C_v0.2.txt"),
    }

    indices = list(range(len(execucoes)))
    rng = random.Random(ordem_seed)
    rng.shuffle(indices)
    order_pos = {orig_i: pos + 1 for pos, orig_i in enumerate(indices)}

    indice_entries: List[Dict[str, object]] = []
    for orig_i, ex in enumerate(execucoes):
        num_path = Path(str(ex["arquivo_numerado"]))
        if not num_path.is_file():
            raise PromptBuildError(f"Arquivo numerado nao encontrado: {num_path}")
        doc_sha = sha256_file(num_path)
        braco = str(ex["braco"])
        doc_id = str(ex["doc_id"])
        modelo = str(ex["modelo"])
        sessao = str(ex["sessao"])
        rodada = int(ex["rodada"])

        filled = fill_template_text(
            base_texts[braco],
            [
                ("DOC_ID", doc_id),
                ("DOC_SHA256", doc_sha),
                ("MODELO", modelo),
                ("SESSAO", sessao),
                ("MAX_LINHAS", str(max_linhas)),
                ("MAX_ACHADOS", str(max_achados)),
            ],
        )
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{doc_id}_{braco}_r{rodada}_{sessao}.txt")
        out_prompt = dir_saida / safe_name
        prompt_sha = write_text_lf_no_bom(out_prompt, filled)

        indice_entries.append({
            "doc_id": doc_id,
            "braco": braco,
            "rodada": rodada,
            "modelo": modelo,
            "sessao": sessao,
            "arquivo_prompt": safe_name,
            "sha256_prompt": prompt_sha,
            "sha256_modelo_base": base_hashes[f"revisor_{braco}_v0.2.txt"],
            "sha256_arquivo_numerado": doc_sha,
            "posicao_ordem": order_pos[orig_i],
        })

    indice_entries.sort(key=lambda e: int(e["posicao_ordem"]))
    indice_obj: Dict[str, object] = {
        "ordem_seed": ordem_seed,
        "max_linhas": max_linhas,
        "max_achados": max_achados,
        "execucoes": indice_entries,
    }
    indice_path = dir_saida / "INDICE.json"
    indice_bytes = (json.dumps(indice_obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    indice_path.write_bytes(indice_bytes)
    return indice_obj


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Uso: montar_prompts.py <build|fill|batch> ...", file=sys.stderr)
        return 2
    cmd = args[0]
    try:
        if cmd == "build":
            if len(args) != 3:
                raise PromptBuildError("Uso: build <dir_blocos> <dir_saida>")
            hashes = build_models(Path(args[1]), Path(args[2]))
            for k, v in hashes.items():
                print(f"{k}: {v}")
            return 0
        if cmd == "fill":
            if len(args) < 4:
                raise PromptBuildError("Uso: fill <modelo.txt> <saida.txt> CHAVE=VALOR ...")
            h = fill_file(Path(args[1]), Path(args[2]), args[3:])
            print(f"{args[2]}: {h}")
            return 0
        if cmd == "batch":
            if len(args) not in (3, 4):
                raise PromptBuildError("Uso: batch <plano.json> <dir_saida> [dir_blocos]")
            db = Path(args[3]) if len(args) == 4 else None
            idx = run_batch(Path(args[1]), Path(args[2]), dir_blocos=db)
            print(f"INDICE.json: {len(idx['execucoes'])} execucoes")
            return 0
        raise PromptBuildError(f"Subcomando desconhecido: {cmd}")
    except PromptBuildError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
