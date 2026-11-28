#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor de consistência cruzada e grafo de proveniência (Revisão Hostil v8.0-beta.4).

Prioridade máxima do Beta 4 (Passo 4.4):
Correlaciona valores de uma mesma grandeza entre:
  codigo -> planilha -> tabela -> figura -> texto -> afirmacao_cientifica

Considera legitimamente:
- Conversão automática de unidades compatíveis (via motor_dimensional);
- Arredondamento declarado (casas decimais ou tolerância relativa/absoluta);
- Transformações legítimas (ex.: fração <-> percentual '%').

Identifica a divergência, sua origem provável e os nós afetados (Efeito Dominó).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.common import SCHEMA_VERSION
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.validation import MAX_JSON_PAYLOAD_BYTES, read_bounded_json, require_finite_number, sanitize_for_json
from scripts.engines.motor_dimensional import convert_unit

MOTOR_ID = "motor_consistencia_cruzada"
MOTOR_VERSION = "0.3.0-beta.1"

# Ordem canônica de autoridade da fonte (menor índice = mais próximo do cálculo original)
SOURCE_AUTHORITY_ORDER = {
    "codigo": 0,
    "simulacao": 0,
    "planilha": 1,
    "dataset": 1,
    "tabela": 2,
    "figura": 3,
    "grafico": 3,
    "texto": 4,
    "resumo": 5,
    "conclusao": 5,
}


def _to_reference_unit(value: float, unit: str | None, ref_unit: str | None) -> tuple[float, bool, str | None]:
    if not unit or not ref_unit or unit.strip() == ref_unit.strip():
        return value, True, None
    # Fração <-> percentual
    if unit.strip() == "%" and ref_unit.strip() in ("1", "dimensionless", "frac"):
        return value / 100.0, True, None
    if ref_unit.strip() == "%" and unit.strip() in ("1", "dimensionless", "frac"):
        return value * 100.0, True, None

    conv = convert_unit(value, unit, ref_unit)
    if conv.get("compatible"):
        return float(conv["converted_value"]), True, None
    return value, False, conv.get("error") or f"Unidades incompatíveis: {unit} vs {ref_unit}"


def check_quantity_consistency(
    quantity_id: str,
    observations: list[dict[str, Any]],
    *,
    rel_tolerance: float = 0.005,
    abs_tolerance: float = 1e-4,
) -> dict[str, Any]:
    """Constrói grafo de proveniência para uma grandeza e audita divergências entre fontes."""
    if len(observations) < 2:
        raise ValueError(f"Grandeza '{quantity_id}' requer pelo menos 2 observações para comparação cruzada.")

    accepted_types = list(SOURCE_AUTHORITY_ORDER.keys())
    normalized_observations: list[dict[str, Any]] = []
    for idx, obs in enumerate(observations, start=1):
        if not isinstance(obs, dict):
            raise ValueError(
                f"Observação {idx} da grandeza '{quantity_id}' inválida: esperado dict, recebido {type(obs).__name__}."
            )
        st = obs.get("source_type")
        if not isinstance(st, str):
            raise ValueError(
                f"Observação {idx} da grandeza '{quantity_id}' possui source_type inválido: {st!r}. "
                f"Para grandezas com 2 ou mais observações, source_type deve ser string reconhecida entre: {accepted_types}."
            )
        st_clean = st.strip().lower()
        if st_clean not in SOURCE_AUTHORITY_ORDER:
            raise ValueError(
                f"Observação {idx} da grandeza '{quantity_id}' possui source_type desconhecido: {st!r}. "
                f"Tipos aceitos: {accepted_types}."
            )
        obs_copy = dict(obs)
        obs_copy["source_type"] = st_clean
        normalized_observations.append(obs_copy)

    observations = normalized_observations

    # Mapeia autoridade para cada observação
    # Fontes conhecidas: codigo/simulacao(0) > planilha/dataset(1) > tabela(2) > figura/grafico(3) > texto(4) > resumo/conclusao(5)
    ranks = [SOURCE_AUTHORITY_ORDER[o["source_type"]] for o in observations]
    min_rank = min(ranks)
    count_min = ranks.count(min_rank)
    has_unique_anchor = (count_min == 1)

    if has_unique_anchor:
        # Hierarquia assimétrica válida: âncora estritamente dominante
        anchor_idx = ranks.index(min_rank)
        anchor = observations[anchor_idx]
        other_obs = [obs for i, obs in enumerate(observations) if i != anchor_idx]

        anchor_val = require_finite_number(anchor["value"], f"{quantity_id}.anchor.value")
        anchor_unit = anchor.get("unit")

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        divergences: list[dict[str, Any]] = []

        anchor_node_id = f"{quantity_id}:{anchor.get('object_id') or anchor.get('location') or 'root'}"
        nodes.append(
            {
                "node_id": anchor_node_id,
                "role": "anchor",
                "source_type": anchor.get("source_type"),
                "location": anchor.get("location"),
                "object_id": anchor.get("object_id"),
                "raw_value": anchor_val,
                "unit": anchor_unit,
                "normalized_value": anchor_val,
            }
        )

        for idx, obs in enumerate(other_obs, start=1):
            val = require_finite_number(obs["value"], f"{quantity_id}.obs[{idx}].value")
            unit = obs.get("unit")
            norm_val, unit_ok, unit_err = _to_reference_unit(val, unit, anchor_unit)
            node_id = f"{quantity_id}:{obs.get('object_id') or obs.get('location') or f'n{idx}'}"

            decimals = obs.get("decimals")
            round_tol = 0.5 * (10.0 ** (-int(decimals))) if decimals is not None else 0.0
            eff_abs_tol = max(abs_tolerance, round_tol)

            abs_err = abs(norm_val - anchor_val)
            rel_err = abs_err / abs(anchor_val) if abs(anchor_val) > 1e-12 else (0.0 if abs_err <= eff_abs_tol else float("inf"))
            consistent = bool(unit_ok and (abs_err <= eff_abs_tol or rel_err <= rel_tolerance))

            nodes.append(
                {
                    "node_id": node_id,
                    "role": "representation",
                    "source_type": obs.get("source_type"),
                    "location": obs.get("location"),
                    "object_id": obs.get("object_id"),
                    "raw_value": val,
                    "unit": unit,
                    "normalized_value": norm_val if unit_ok else None,
                }
            )
            edges.append(
                {
                    "from": anchor_node_id,
                    "to": node_id,
                    "consistent": consistent,
                    "abs_error": abs_err if unit_ok else None,
                    "rel_error_pct": rel_err * 100.0 if unit_ok and rel_err != float("inf") else None,
                }
            )

            if not consistent:
                divergences.append(
                    {
                        "type": "asymmetric",
                        "quantity_id": quantity_id,
                        "anchor_source": anchor.get("source_type"),
                        "anchor_location": anchor.get("location"),
                        "anchor_value": anchor_val,
                        "anchor_unit": anchor_unit,
                        "divergent_source": obs.get("source_type"),
                        "divergent_location": obs.get("location"),
                        "divergent_object_id": obs.get("object_id"),
                        "divergent_value": val,
                        "divergent_unit": unit,
                        "normalized_divergent_value": norm_val if unit_ok else None,
                        "reason": unit_err or f"Divergência numérica: {norm_val:g} vs referência {anchor_val:g} ({anchor_unit or 'adim.'}).",
                    }
                )

        return {
            "operation": "check_quantity_consistency",
            "quantity_id": quantity_id,
            "anchor": {"source_type": anchor.get("source_type"), "location": anchor.get("location"), "value": anchor_val, "unit": anchor_unit},
            "graph": {"nodes": nodes, "edges": edges},
            "divergences": divergences,
            "consistent": len(divergences) == 0,
            "status": "ok" if not divergences else "discrepancy_detected",
        }

    # Caso Paritário / Empate de Autoridade: Simétrico e Invariante à Ordem
    # Ordena canonicamente as observações por location, object_id e valor bruto
    canonical_obs = sorted(
        observations,
        key=lambda o: (
            str(o.get("location") or ""),
            str(o.get("object_id") or ""),
            str(o.get("source_type") or ""),
            float(o.get("value") or 0.0),
        ),
    )

    # Converte todas para a unidade da primeira observação canônica (ou mantém nativo)
    base_unit = canonical_obs[0].get("unit")
    norm_values: list[tuple[float, bool, str | None]] = []
    for obs in canonical_obs:
        v = require_finite_number(obs["value"], f"{quantity_id}.obs.value")
        u = obs.get("unit")
        nv, ok, err = _to_reference_unit(v, u, base_unit)
        norm_values.append((nv, ok, err))

    # Agrupa observações por valor normalizado (dentro da tolerância)
    groups: list[dict[str, Any]] = []
    for obs, (nv, ok, err) in zip(canonical_obs, norm_values):
        val_raw = obs["value"]
        loc = obs.get("location") or "desconhecido"
        unit = obs.get("unit")
        st = obs.get("source_type")

        placed = False
        if ok:
            for g in groups:
                rep_val = g["normalized_value"]
                abs_err = abs(nv - rep_val)
                rel_err = abs_err / abs(rep_val) if abs(rep_val) > 1e-12 else abs_err
                if abs_err <= abs_tolerance or rel_err <= rel_tolerance:
                    g["occurrences"].append({"location": loc, "raw_value": val_raw, "unit": unit, "source_type": st})
                    placed = True
                    break
        if not placed:
            groups.append(
                {
                    "normalized_value": nv if ok else None,
                    "unit_ok": ok,
                    "unit_error": err,
                    "occurrences": [{"location": loc, "raw_value": val_raw, "unit": unit, "source_type": st}],
                }
            )

    nodes = []
    for idx, obs in enumerate(canonical_obs, start=1):
        nid = f"{quantity_id}:{obs.get('object_id') or obs.get('location') or f'n{idx}'}"
        nodes.append(
            {
                "node_id": nid,
                "role": "peer",
                "source_type": obs.get("source_type"),
                "location": obs.get("location"),
                "object_id": obs.get("object_id"),
                "raw_value": obs["value"],
                "unit": obs.get("unit"),
            }
        )

    divergences = []
    if len(groups) > 1:
        # Existe divergência entre pares paritários
        group_summaries = []
        for g in groups:
            locs = sorted(set(str(occ["location"]) for occ in g["occurrences"]))
            val_str = f"{g['normalized_value']:g} ({base_unit or 'adim.'})" if g["unit_ok"] else f"unidade_invalida ({g['unit_error']})"
            group_summaries.append(f"valor {val_str} em [{', '.join(locs)}]")

        all_locs = sorted(set(str(o.get("location") or "desconhecido") for o in canonical_obs))
        divergences.append(
            {
                "type": "symmetric_peer_conflict",
                "quantity_id": quantity_id,
                "locations": all_locs,
                "groups": groups,
                "reason": f"Divergência entre fontes paritárias para a mesma grandeza '{quantity_id}': " + "; ".join(group_summaries) + ".",
            }
        )

    return {
        "operation": "check_quantity_consistency",
        "quantity_id": quantity_id,
        "anchor": None,
        "graph": {"nodes": nodes, "edges": []},
        "divergences": divergences,
        "consistent": len(divergences) == 0,
        "status": "ok" if not divergences else "discrepancy_detected",
    }


def run_motor(payload: Any, *, run_id: str | None = None, artefato_alvo: str | None = None) -> dict[str, Any]:
    inner = payload["payload"] if isinstance(payload, dict) and "payload" in payload and "motor_id" in payload else payload
    quantities = inner.get("quantities") if isinstance(inner, dict) and "quantities" in inner else [inner]

    results: list[dict[str, Any]] = []
    achados: list[dict[str, Any]] = []
    ach_seq = 0
    for idx, q in enumerate(quantities, start=1):
        if not isinstance(q, dict):
            results.append(
                {
                    "quantity_id": f"Q_{idx:03d}",
                    "success": False,
                    "status": "error",
                    "error": f"Item de quantidade inválido no índice {idx}: esperado objeto/dicionário, recebido {type(q).__name__}.",
                }
            )
            continue

        qid = str(q.get("quantity_id") or q.get("id") or f"Q_{idx:03d}")
        try:
            res = check_quantity_consistency(
                qid,
                q["observations"],
                rel_tolerance=q.get("rel_tolerance", 0.005),
                abs_tolerance=q.get("abs_tolerance", 1e-4),
            )
            res["success"] = True
            results.append(res)
            for div in res["divergences"]:
                ach_seq += 1
                if div.get("type") == "symmetric_peer_conflict":
                    # Conflito simétrico de fontes paritárias (sem âncora)
                    locs_str = ", ".join(div["locations"])
                    ev = create_evidence(
                        f"EV-XCS-{ach_seq:03d}",
                        "numerica",
                        artefato_alvo or "grafo_consistencia",
                        locs_str,
                        div["reason"],
                        objeto_id=None,
                        valor_observado=None,
                        valor_calculado=None,
                        motor_origem=MOTOR_ID,
                    )
                    achados.append(
                        create_finding(
                            f"ACH-XCS-{ach_seq:03d}",
                            f"Inconsistência interna paritária em '{qid}'",
                            "divergencia_consistencia_cruzada",
                            "MAIOR",
                            "ALTA",
                            locs_str,
                            div["reason"],
                            [ev],
                            estado="NAO_VERIFICADO",
                            portao="G05",
                            impacto=f"Valores divergentes reportados em diferentes locais ({locs_str}) sem hierarquia ou autoridade que defina a fonte primária.",
                            acao_recomendada=f"Esclarecer a discrepância entre as localizações [{locs_str}] ou declarar a transformação/relação entre os valores reportados.",
                            origem_componente=MOTOR_ID,
                        )
                    )
                else:
                    # Divergência assimétrica contra âncora hierárquica dominante
                    ev = create_evidence(
                        f"EV-XCS-{ach_seq:03d}",
                        "numerica",
                        artefato_alvo or "grafo_consistencia",
                        f"{div['anchor_location']} <-> {div['divergent_location']}",
                        div["reason"],
                        objeto_id=div.get("divergent_object_id"),
                        valor_observado=div["divergent_value"],
                        valor_calculado=div["anchor_value"],
                        motor_origem=MOTOR_ID,
                    )
                    achados.append(
                        create_finding(
                            f"ACH-XCS-{ach_seq:03d}",
                            f"Divergência cruzada em '{qid}' ({div['anchor_source']} vs {div['divergent_source']})",
                            "divergencia_consistencia_cruzada",
                            "CRITICO",
                            "ALTA",
                            f"{div['divergent_location']}",
                            div["reason"],
                            [ev],
                            estado="CONFIRMADO",
                            portao="G05",
                            impacto=f"Quebra de rastreabilidade entre {div['anchor_source']} e {div['divergent_source']} (Efeito Dominó).",
                            acao_recomendada=f"Alinhar '{div['divergent_location']}' com a fonte primária '{div['anchor_location']}' ou documentar a transformação.",
                            origem_componente=MOTOR_ID,
                        )
                    )
        except Exception as err:
            results.append({"quantity_id": qid, "success": False, "status": "error", "error": str(err)})

    failed = sum(1 for r in results if not r.get("success"))
    status = "ERRO_VALIDACAO" if failed == len(results) else ("PARCIAL" if failed > 0 else ("COM_ACHADOS" if achados else "OK"))
    return sanitize_for_json(
        {
            "schema_version": SCHEMA_VERSION,
            "motor_id": MOTOR_ID,
            "motor_version": MOTOR_VERSION,
            "run_id": run_id,
            "deterministico": True,
            "status": status,
            "timestamp": utc_now_iso(),
            "artefato_alvo": artefato_alvo,
            "hash_artefato": None,
            "metricas": {
                "total_grandezas": len(results),
                "sucesso": len(results) - failed,
                "falhas": failed,
                "total_achados": len(achados),
            },
            "resultados": {"quantities": results},
            "achados": achados,
            "limitacoes": [
                "A comparação considera conversão de unidades compatíveis e arredondamento declarado; transformações não lineares entre etapas devem ser explicitadas."
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Motor de consistência cruzada (Revisão Hostil v8.0-beta.4).")
    parser.add_argument("--input", "-i", help="Arquivo JSON de entrada (se omitido, lê de stdin).")
    parser.add_argument("--out", "-o", help="Arquivo JSON de saída (se omitido, imprime em stdout).")
    parser.add_argument("--run-id", help="Identificador opcional da campanha.")
    args = parser.parse_args()

    try:
        source = args.input if args.input else sys.stdin
        req, artefato = read_bounded_json(source, max_bytes=MAX_JSON_PAYLOAD_BYTES)
        out = run_motor(req, run_id=args.run_id, artefato_alvo=artefato)
        text = json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
        else:
            print(text)
        if isinstance(out, dict) and out.get("status") == "ERRO_VALIDACAO":
            sys.exit(1)
    except Exception as error:
        err_out = json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "motor_id": MOTOR_ID,
                "motor_version": MOTOR_VERSION,
                "deterministico": True,
                "status": "ERRO_EXECUCAO",
                "timestamp": utc_now_iso(),
                "resultados": {"error_type": type(error).__name__, "error": str(error)},
                "achados": [],
                "limitacoes": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        if args.out:
            Path(args.out).write_text(err_out, encoding="utf-8")
        print(err_out)
        sys.exit(1)

if __name__ == "__main__":
    main()
