"""Evidências, achados, máquina de estados (10 estados) e pontuação unificada (0–10)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .validation import require_finite_number

ESTADOS_ACHADO = (
    "ABERTO",
    "EM_ANALISE",
    "CONFIRMADO",
    "NAO_VERIFICADO",
    "PATCH_PROPOSTO",
    "PATCH_APROVADO",
    "PATCH_APLICADO",
    "FECHADO",
    "REJEITADO",
    "FORA_DE_ESCOPO",
)

GRAVIDADES_ACHADO = ("CRITICO", "MAIOR", "MODERADO", "MENOR", "INFORMATIVO")
CONFIANCAS_ACHADO = ("ALTA", "MEDIA", "BAIXA", "TRIAGEM")

TRANSICOES_VALIDAS: dict[str, set[str]] = {
    "ABERTO": {"EM_ANALISE", "CONFIRMADO", "NAO_VERIFICADO", "REJEITADO", "FORA_DE_ESCOPO"},
    "EM_ANALISE": {"CONFIRMADO", "NAO_VERIFICADO", "REJEITADO", "FORA_DE_ESCOPO"},
    "NAO_VERIFICADO": {"EM_ANALISE", "CONFIRMADO", "REJEITADO", "FORA_DE_ESCOPO"},
    "CONFIRMADO": {"PATCH_PROPOSTO", "REJEITADO", "FORA_DE_ESCOPO"},
    "PATCH_PROPOSTO": {"PATCH_APROVADO", "CONFIRMADO", "REJEITADO"},
    "PATCH_APROVADO": {"PATCH_APLICADO", "PATCH_PROPOSTO"},
    "PATCH_APLICADO": {"FECHADO", "CONFIRMADO"},
    "FECHADO": {"ABERTO"},
    "REJEITADO": {"EM_ANALISE"},
    "FORA_DE_ESCOPO": {"EM_ANALISE"},
}

ESTADOS_ABERTOS = {
    "ABERTO",
    "EM_ANALISE",
    "CONFIRMADO",
    "NAO_VERIFICADO",
    "PATCH_PROPOSTO",
    "PATCH_APROVADO",
    "PATCH_APLICADO",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_evidence(
    evidencia_id: str,
    tipo: str,
    origem_arquivo: str,
    localizacao: str,
    conteudo: str,
    *,
    hash_arquivo: str | None = None,
    objeto_id: str | None = None,
    valor_observado: Any = None,
    valor_calculado: Any = None,
    tolerancia: float | None = None,
    motor_origem: str | None = None,
) -> dict[str, Any]:
    return {
        "evidencia_id": evidencia_id,
        "tipo": tipo,
        "origem_arquivo": origem_arquivo,
        "hash_arquivo": hash_arquivo,
        "localizacao": localizacao,
        "objeto_id": objeto_id,
        "conteudo": conteudo[:1000] if conteudo else "<vazio>",
        "valor_observado": valor_observado,
        "valor_calculado": valor_calculado,
        "tolerancia": tolerancia,
        "motor_origem": motor_origem,
        "timestamp": utc_now_iso(),
    }


def create_finding(
    finding_id: str,
    titulo: str,
    categoria: str,
    gravidade: str,
    confianca: str,
    localizacao: str,
    descricao: str,
    evidencias: list[dict[str, Any]],
    *,
    estado: str = "ABERTO",
    portao: str | None = None,
    impacto: str | None = None,
    acao_recomendada: str | None = None,
    origem_componente: str | None = None,
) -> dict[str, Any]:
    if gravidade not in GRAVIDADES_ACHADO:
        raise ValueError(f"Gravidade inválida: {gravidade}")
    if confianca not in CONFIANCAS_ACHADO:
        raise ValueError(f"Confiança inválida: {confianca}")
    if estado not in ESTADOS_ACHADO:
        raise ValueError(f"Estado inválido: {estado}")

    return {
        "id": finding_id,
        "titulo": titulo,
        "categoria": categoria,
        "portao": portao,
        "gravidade": gravidade,
        "confianca": confianca,
        "estado": estado,
        "localizacao": localizacao,
        "descricao": descricao,
        "impacto": impacto,
        "acao_recomendada": acao_recomendada,
        "origem_componente": origem_componente,
        "evidencias": evidencias,
        "historico_estados": [
            {
                "de": None,
                "para": estado,
                "motivo": "Criação inicial do achado",
                "reauditado": False,
                "timestamp": utc_now_iso(),
            }
        ],
    }


def transition_finding_state(
    finding: dict[str, Any],
    novo_estado: str,
    motivo: str,
    *,
    reauditado: bool = False,
) -> dict[str, Any]:
    """Aplica transição formal de estado. Fechamento exige PATCH_APLICADO + reauditado=True."""
    estado_atual = finding["estado"]
    if novo_estado not in ESTADOS_ACHADO:
        raise ValueError(f"Estado destino inválido: {novo_estado}")

    permitidos = TRANSICOES_VALIDAS.get(estado_atual, set())
    if novo_estado not in permitidos:
        raise ValueError(
            f"Transição inválida de '{estado_atual}' para '{novo_estado}'. "
            f"Permitidos: {sorted(permitidos)}"
        )

    if novo_estado == "FECHADO" and not reauditado:
        raise ValueError(
            "Um achado não pode ir para FECHADO sem reauditoria comprovada (reauditado=True)."
        )

    finding["estado"] = novo_estado
    finding.setdefault("historico_estados", []).append(
        {
            "de": estado_atual,
            "para": novo_estado,
            "motivo": motivo,
            "reauditado": reauditado,
            "timestamp": utc_now_iso(),
        }
    )
    return finding


def normalize_score(nota_0_10: float, incluir_escala_100: bool = True) -> dict[str, float | None]:
    """Unifica pontuação na escala canônica 0–10 com exibição opcional em 0–100 (rejeita NaN/Inf)."""
    val = require_finite_number(nota_0_10, name="nota_0_10")
    if val < 0.0 or val > 10.0:
        raise ValueError(f"Nota fora do intervalo canônico [0, 10]: {val}")
    val_round = round(val, 2)
    return {
        "nota_0_10": val_round,
        "nota_0_100": round(val_round * 10.0, 1) if incluir_escala_100 else None,
    }


def evaluate_freeze_gate(
    nota_global_0_10: float,
    notas_por_eixo: dict[str, float],
    achados: list[dict[str, Any]],
    regressao_aprovada: bool,
) -> dict[str, Any]:
    """Avalia o critério de congelamento da v8.0 (>=9.5 global, >=8.5/eixo, 0 críticos/maiores abertos).
    Rejeita explicitamente qualquer nota NaN, Inf ou fora de [0, 10] antes das comparações (ACH-001).
    """
    nota_global = require_finite_number(nota_global_0_10, name="nota_global_0_10")
    if nota_global < 0.0 or nota_global > 10.0:
        raise ValueError(f"nota_global_0_10 fora do intervalo [0, 10]: {nota_global}")

    eixos_validados: dict[str, float] = {}
    for eixo, raw_val in notas_por_eixo.items():
        v = require_finite_number(raw_val, name=f"notas_por_eixo.{eixo}")
        if v < 0.0 or v > 10.0:
            raise ValueError(f"Nota do eixo '{eixo}' fora do intervalo [0, 10]: {v}")
        eixos_validados[eixo] = v

    criticos_abertos = sum(
        1 for a in achados if a["gravidade"] == "CRITICO" and a["estado"] in ESTADOS_ABERTOS
    )
    maiores_abertos = sum(
        1 for a in achados if a["gravidade"] == "MAIOR" and a["estado"] in ESTADOS_ABERTOS
    )
    nao_verificados_criticos = sum(
        1
        for a in achados
        if a["gravidade"] == "CRITICO" and a["estado"] == "NAO_VERIFICADO"
    )
    eixos_abaixo = {k: v for k, v in eixos_validados.items() if v < 8.5}

    bloqueios: list[str] = []
    if nota_global < 9.5:
        bloqueios.append(f"Nota global {nota_global:.2f} < 9.50")
    if eixos_abaixo:
        bloqueios.append(f"Eixos abaixo de 8.50: {eixos_abaixo}")
    if criticos_abertos > 0:
        bloqueios.append(f"{criticos_abertos} achado(s) CRÍTICO(S) em aberto")
    if maiores_abertos > 0:
        bloqueios.append(f"{maiores_abertos} achado(s) MAIOR(ES) em aberto")
    if nao_verificados_criticos > 0:
        bloqueios.append(f"{nao_verificados_criticos} achado(s) CRÍTICO(S) NAO_VERIFICADO")
    if not regressao_aprovada:
        bloqueios.append("Regressão final não aprovada")

    return {
        "pode_congelar": len(bloqueios) == 0,
        "bloqueios": bloqueios,
        "criticos_abertos": criticos_abertos,
        "maiores_abertos": maiores_abertos,
        "nao_verificados_criticos": nao_verificados_criticos,
    }
