#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auditor estrutural e forense modular para manuscritos científicos e técnicos.
(Revisão Hostil v8.0-beta.2 — Core estabilizado)

Separação modular (Passo 2.4):
- Extração de conteúdo (TXT, MD, TEX, RST, DOCX, PDF)
- Extração de equações
- Extração de tabelas
- Extração de referências e citações
- Leitura de metadados forenses
- Detecção de pistas genéricas (DEF-A01 corrigido: 100% casa corretamente)
- Aplicação desacoplada de regras de domínio (injetáveis via perfil YAML)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.common import SCHEMA_VERSION
from scripts.common.citation import (
    CROSS_REF_PROSE_RE,
    extract_latex_citations,
    extract_latex_refs_and_labels,
)
from scripts.common.evidence import create_evidence, create_finding, utc_now_iso
from scripts.common.provenance import sha256_file
from scripts.common.units import extract_numbers_with_units
from scripts.common.validation import sanitize_for_json, validate_safe_file_path

MOTOR_ID = "auditor_estrutural"
MOTOR_VERSION = "8.0.0-beta.2"

# --- Regras Genéricas Universais (independentes de disciplina) ---
GENERIC_ABSOLUTE_CLAIMS: list[tuple[str, str]] = [
    (
        r"(?<!\w)(?:100\s*%|100\s*por\s*cento|100\s*percent)(?=$|[\s,.;:)!?\]\}])",
        "Verificar se a afirmação de totalidade (100%) é estritamente suportada pelos dados ou exige condição de contorno.",
    ),
    (
        r"\b(elimina[çc][ãa]o\s+total|complete\s+elimination|perp[ée]tu[oa]s?|perpetual|ininterrupt[oa]s?|uninterrupted)\b",
        "Verificar se a condição extrema se sustenta em todo o domínio operacional.",
    ),
    (
        r"\b(never|always|permanently|entirely|nunca|jamais|sempre|permanentemente|integralmente)\b",
        "Verificar escopo, condições de contorno e incerteza da afirmação absoluta.",
    ),
    (
        r"\b([óo]timo\s+global|global\s+optimum|proves?\s+mathematically|comprova\s+matematicamente|"
        r"prova\s+definitiva|unequivocally\s+proves)\b",
        "Verificar se há demonstração formal de convexidade/otimalidade global e hipóteses comprovadas.",
    ),
    (
        r"\b(superior\s+a\s+todas|outperforms\s+all|definitive|incontestable|incontest[áa]vel|"
        r"sem\s+qualquer\s+limita[çc][ãa]o)\b",
        "Verificar se comparadores, baselines e métricas sustentam uma conclusão tão abrangente.",
    ),
]

GENERIC_EPISTEMIC_OVERCLAIMS: list[tuple[str, str]] = [
    (
        r"\b(comprov\w*|comprovam|comprova|comprovando|comprovado)\b",
        "Modéstia epistêmica: modelos/simulações não 'comprovam' verdades absolutas. Calibrar para 'demonstram a viabilidade', 'evidenciam' ou 'indicam'.",
    ),
    (
        r"\b(proves?\s+(?:that|the)|proving\s+(?:that|the)|proof\s+of)\b",
        "Epistemic modesty: simulations/models do not 'prove' physical reality. Calibrate to 'demonstrate', 'indicate' or 'corroborate'.",
    ),
    (
        r"\b(eliminat\w*|elimina[çc][ãa]o\s+de|eliminando|eliminou)\b",
        "Afirmação absoluta de eliminação: preferir 'mitigar', 'reduzir' ou 'conter' salvo prova formal.",
    ),
    (
        r"\b(strictly\s+(?:stable|invariance|preserves|zero)|perfectly\s+(?:stable|invariance)|flawless\w*)\b",
        "Linguagem dogmática: calibrar para 'asymptotically stable', 'robust' ou 'consistent'.",
    ),
    (
        r"\b(mathematically\s+guaranteed|guarantees?\s+that|garante\s+que|garantem\s+que)\b",
        "Garantia excessiva sem teorema fechado no texto: preferir 'converges in accordance with' ou 'under nominal conditions'.",
    ),
]

EQUATION_CANDIDATE_RE = re.compile(
    r"(=|≈|≤|≥|±|×|\\frac|\\sum|\\int|\\partial|\\nabla|"
    r"\\begin\{equation\*?\}|\\begin\{align\*?\}|\\begin\{eqnarray\*?\}|"
    r"\\\[|\\\(|\\begin\{math\}|\$[^$]+\$)"
)

FLOATING_ENV_RE = re.compile(
    r"(\\begin\{(figure|table|figure\*|table\*|quadro)\}|\\begin\{tabularx?\}|^\[(Tabela|Figura)\s+\d+)",
    re.IGNORECASE,
)

QUANTITATIVE_COMPARISON_RE = re.compile(
    r"(increase|decrease|reduction|gain|improvement|saving|ganho|redu[çc][ãa]o|"
    r"aument|dimin|economia|melhoria|superior|inferior|vs\.?|versus)",
    re.IGNORECASE,
)

LATEX_OR_MD_LEAK_IN_DOCX_RE = re.compile(
    r"(\\(?:frac|sum|int|sqrt|alpha|beta|gamma|delta|eta|theta|lambda|mu|pi|rho|sigma|tau|omega|"
    r"cdot|times|leq|geq|approx|neq|infty|partial|nabla|mathcal|mathbb|mathrm|textbf|textit)\b|"
    r"\$[^$\n]+\$|\*\*[^*\n]+\*\*)"
)

# Regras específicas de domínio desacopladas (migrarão para references/profiles/*.yaml na Fase 6)
ENGINEERING_DOMAIN_RULES: list[dict[str, str]] = [
    {
        "category": "power_energy_confusion",
        "portao": "G03",
        "pattern": (
            r"\b(\d+(?:[.,]\d+)?)\s*(W|kW|MW|GW)\b.*?\b(\d+(?:[.,]\d+)?)\s*(Wh|kWh|MWh|GWh)\b|"
            r"\b(energia|energy|capacidade|capacity)\s+(?:de\s+|of\s+)?\d+(?:[.,]\d+)?\s*(W|kW|MW|GW)\b|"
            r"\b(pot[êe]ncia|power|consumo\s+instant[âa]neo)\s+(?:de\s+|of\s+)?\d+(?:[.,]\d+)?\s*(Wh|kWh|MWh|GWh)\b"
        ),
        "prompt": "Possível coexistência ou confusão entre potência (W/kW/MW) e energia (Wh/kWh/MWh). Verificar integração temporal e unidades.",
    },
    {
        "category": "method_review",
        "portao": "G02",
        "pattern": r"\b(Lyapunov|Riccati|DARE|Hurwitz|MPC|KKT|AHP|Saaty|TOPSIS|Stefan-Boltzmann|Arrhenius|Weibull)\b",
        "prompt": "Termo técnico crítico detectado: conferir hipóteses, condições de contorno e fechamento numérico no motor correspondente.",
    },
    {
        "category": "absolute_claim_domain",
        "portao": "G01",
        "pattern": r"\b(zero\s+eclipse|eclipse\s+zero|isot[ée]rmic[oa]\s+perfeit[oa])\b",
        "prompt": "Condição física extrema de engenharia detectada: testar solstícios, falhas e transientes.",
    },
]


# =========================================================================
# 1. EXTRATORES DE CONTEÚDO E METADADOS
# =========================================================================
def extract_docx_structured(path: Path) -> tuple[list[tuple[str, str, str]], dict[str, Any]]:
    try:
        import docx
        from docx.oxml.table import CT_Tbl
        from docx.oxml.text.paragraph import CT_P
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as error:
        raise RuntimeError("Para ler DOCX, instale python-docx (pip install python-docx).") from error

    document = docx.Document(str(path))
    cp = document.core_properties
    xml_str = document._element.xml

    forensics = {
        "metadata": {
            "author": cp.author or "",
            "last_modified_by": cp.last_modified_by or "",
            "title": cp.title or "",
            "subject": cp.subject or "",
        },
        "anonymity_warning": bool(
            (cp.author and cp.author.strip()) or (cp.last_modified_by and cp.last_modified_by.strip())
        ),
        "omml_display_equations": len(re.findall(r"<m:oMathPara\b", xml_str)),
        "omml_inline_or_total_math": len(re.findall(r"<m:oMath\b", xml_str)),
        "table_count": len(document.tables),
        "paragraph_count": len(document.paragraphs),
    }

    lines: list[tuple[str, str, str]] = []
    p_idx = 0
    t_idx = 0
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            p_idx += 1
            para = Paragraph(child, document)
            has_omml = "<m:oMath" in child.xml
            text = para.text.strip()
            if text or has_omml:
                omml_tag = " [EQUAÇÃO_OMML_NATIVA]" if has_omml else ""
                lines.append((f"Parágrafo {p_idx}", f"{text}{omml_tag}".strip(), "paragraph"))
        elif isinstance(child, CT_Tbl):
            t_idx += 1
            table = Table(child, document)
            for r_idx, row in enumerate(table.rows, start=1):
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                if any(cells):
                    lines.append((f"Tabela {t_idx}, Linha {r_idx}", f"[Tabela {t_idx}] " + " | ".join(cells), "table"))

    return lines, forensics


def extract_pdf_structured(path: Path) -> tuple[list[tuple[str, str, str]], dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("Para ler PDF, instale pypdf (pip install pypdf).") from error

    reader = PdfReader(str(path))
    lines: list[tuple[str, str, str]] = []
    for page_idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        for line_idx, raw_line in enumerate(page_text.splitlines(), start=1):
            clean = raw_line.strip()
            if clean:
                lines.append((f"Página {page_idx}, linha {line_idx}", clean, "pdf"))

    meta = {
        "page_count": len(reader.pages),
        "metadata": {k: str(v) for k, v in (reader.metadata or {}).items()} if reader.metadata else {},
    }
    return lines, meta


def extract_text_structured(path: Path) -> tuple[list[tuple[str, str, str]], dict[str, Any]]:
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    lines = [
        (f"linha {i}", line.strip(), "text")
        for i, line in enumerate(raw_text.splitlines(), start=1)
        if line.strip()
    ]
    return lines, {"line_count": len(raw_text.splitlines()), "non_empty_lines": len(lines)}


def extract_content(path: Path) -> tuple[list[tuple[str, str, str]], str, dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".tex", ".rst"}:
        lines, meta = extract_text_structured(path)
        return lines, suffix.lstrip("."), meta
    if suffix == ".docx":
        lines, forensics = extract_docx_structured(path)
        return lines, "docx", forensics
    if suffix == ".pdf":
        lines, meta = extract_pdf_structured(path)
        return lines, "pdf", meta
    raise ValueError(f"Formato não suportado: {suffix}")


# =========================================================================
# 2. EXTRATORES ESTRUTURADOS (EQUAÇÕES, TABELAS, REFERÊNCIAS)
# =========================================================================
def extract_equations(lines: list[tuple[str, str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for loc, line, _ in lines:
        if EQUATION_CANDIDATE_RE.search(line) or "[EQUAÇÃO_OMML_NATIVA]" in line:
            out.append({"location": loc, "excerpt": line[:400]})
    return out


def extract_tables(lines: list[tuple[str, str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for loc, line, block_type in lines:
        if block_type == "table" and "Linha 1" in loc:
            out.append({"location": loc, "header_excerpt": line[:400]})
        elif block_type != "table" and FLOATING_ENV_RE.search(line):
            out.append({"location": loc, "header_excerpt": line[:400]})
    return out


def extract_references(lines: list[tuple[str, str, str]]) -> dict[str, Any]:
    full_text = "\n".join(line for _, line, _ in lines)
    latex_cites = sorted(set(extract_latex_citations(full_text)))
    refs_labels = extract_latex_refs_and_labels(full_text)
    prose_refs = [
        {"location": loc, "match": m.group(0)}
        for loc, line, _ in lines
        for m in CROSS_REF_PROSE_RE.finditer(line)
    ]
    return {
        "latex_citations": latex_cites,
        "latex_refs": sorted(set(refs_labels["refs"])),
        "latex_labels": sorted(set(refs_labels["labels"])),
        "prose_cross_references": prose_refs,
    }


# =========================================================================
# 3. DETECÇÃO DE PISTAS GENÉRICAS E REGRAS DE DOMÍNIO
# =========================================================================
def _make_cue_finding(
    seq: int,
    category: str,
    portao: str,
    gravidade: str,
    confianca: str,
    location: str,
    excerpt: str,
    prompt: str,
    source_file: str,
    file_hash: str | None,
) -> dict[str, Any]:
    ev = create_evidence(
        f"EV-AUD-{seq:04d}",
        "metadado" if category == "double_blind_violation" else "textual",
        source_file,
        location,
        excerpt[:500],
        hash_arquivo=file_hash,
        motor_origem=MOTOR_ID,
    )
    return create_finding(
        f"ACH-AUD-{seq:04d}",
        f"Pista de triagem ({category}) em {location}",
        category,
        gravidade,
        confianca,
        location,
        prompt,
        [ev],
        estado="ABERTO",
        portao=portao,
        acao_recomendada=prompt,
        origem_componente=MOTOR_ID,
    )


def detect_cues(
    lines: list[tuple[str, str, str]],
    source_type: str,
    source_file: str,
    file_hash: str | None,
    metadata: dict[str, Any],
    domain_rules: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    achados: list[dict[str, Any]] = []
    seq = 0

    def push(cat: str, portao: str, grav: str, conf: str, loc: str, exc: str, prompt: str) -> None:
        nonlocal seq
        seq += 1
        achados.append(
            _make_cue_finding(seq, cat, portao, grav, conf, loc, exc, prompt, source_file, file_hash)
        )

    if source_type == "docx" and metadata.get("anonymity_warning"):
        meta = metadata.get("metadata", {})
        push(
            "double_blind_violation",
            "G10",
            "CRITICO",
            "ALTA",
            "Metadados Internos (core_properties)",
            f"author='{meta.get('author')}', last_modified_by='{meta.get('last_modified_by')}'",
            "Remover autoria das propriedades internas do DOCX em submissões Double-Blind.",
        )

    for location, line, block_type in lines:
        if source_type == "docx" and LATEX_OR_MD_LEAK_IN_DOCX_RE.search(line):
            push(
                "formatting_leak",
                "G09",
                "MODERADO",
                "ALTA",
                location,
                line,
                "Resíduo de código LaTeX/Markdown detectado em DOCX. Converter para OMML ou formatação nativa.",
            )

        if EQUATION_CANDIDATE_RE.search(line) or "[EQUAÇÃO_OMML_NATIVA]" in line:
            push(
                "equation_candidate",
                "G03",
                "INFORMATIVO",
                "TRIAGEM",
                location,
                line,
                "Extrair parâmetros numéricos declarados e testar via motor_matematico.py.",
            )

        for pattern, prompt in GENERIC_ABSOLUTE_CLAIMS:
            if re.search(pattern, line, re.IGNORECASE):
                push("absolute_claim", "G01", "MODERADO", "TRIAGEM", location, line, prompt)

        for pattern, prompt in GENERIC_EPISTEMIC_OVERCLAIMS:
            if re.search(pattern, line, re.IGNORECASE):
                push("epistemic_overclaim", "G01", "MENOR", "TRIAGEM", location, line, prompt)

        units = extract_numbers_with_units(line)
        if len(units) >= 2 and QUANTITATIVE_COMPARISON_RE.search(line):
            push(
                "quantitative_comparison",
                "G05",
                "INFORMATIVO",
                "TRIAGEM",
                location,
                line,
                "Recalcular comparação percentual/relativa e conferir denominador, unidade e arredondamento.",
            )

        if CROSS_REF_PROSE_RE.search(line) or "\\cite" in line or "\\ref{" in line:
            push(
                "cross_reference",
                "G07",
                "INFORMATIVO",
                "TRIAGEM",
                location,
                line,
                "Conferir bijeção 1:1 e correspondência exata com figura/tabela/equação citada.",
            )

        if (FLOATING_ENV_RE.search(line) and block_type != "table") or (
            block_type == "table" and "Linha 1" in location
        ):
            push(
                "floating_environment",
                "G09",
                "INFORMATIVO",
                "TRIAGEM",
                location,
                line,
                "Verificar legenda, unidades, totais e consistência cruzada com o texto.",
            )

        for rule in domain_rules or []:
            if re.search(rule["pattern"], line, re.IGNORECASE):
                push(
                    rule["category"],
                    rule.get("portao", "G02"),
                    rule.get("gravidade", "MODERADO"),
                    "TRIAGEM",
                    location,
                    line,
                    rule["prompt"],
                )

    return achados


def run_auditor(
    manuscript_path: str | Path,
    *,
    run_id: str | None = None,
    domain_rules: list[dict[str, str]] | None = None,
    include_engineering_preset: bool = False,
) -> dict[str, Any]:
    """Executa o auditor estrutural e devolve saída padronizada conforme schema_motor.json."""
    resolved = validate_safe_file_path(manuscript_path)
    file_hash = sha256_file(resolved)
    lines, source_type, metadata = extract_content(resolved)

    active_rules = list(domain_rules or [])
    if include_engineering_preset:
        active_rules.extend(ENGINEERING_DOMAIN_RULES)

    equations = extract_equations(lines)
    tables = extract_tables(lines)
    references = extract_references(lines)
    achados = detect_cues(lines, source_type, resolved.name, file_hash, metadata, active_rules)

    category_counts: dict[str, int] = {}
    for a in achados:
        cat = a["categoria"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return sanitize_for_json(
        {
            "schema_version": SCHEMA_VERSION,
            "motor_id": MOTOR_ID,
            "motor_version": MOTOR_VERSION,
            "run_id": run_id,
            "deterministico": True,
            "status": "COM_ACHADOS" if achados else "OK",
            "timestamp": utc_now_iso(),
            "artefato_alvo": str(resolved),
            "hash_artefato": file_hash,
            "metricas": {
                "total_linhas_estruturadas": len(lines),
                "total_equacoes_candidatas": len(equations),
                "total_tabelas_flutuantes": len(tables),
                "total_achados": len(achados),
                "contagem_por_categoria": category_counts,
            },
            "resultados": {
                "source_file": resolved.name,
                "source_type": source_type,
                "metadata": metadata,
                "equations": equations,
                "tables": tables,
                "references": references,
            },
            "achados": achados,
            "limitacoes": [
                "A extração automática pode não ler equações rasterizadas em imagens.",
                "Itens de triagem são pistas localizadas para verificação pelos motores e agentes, não vereditos finais.",
            ],
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auditor estrutural e forense modular (Revisão Hostil v8.0-beta.2)."
    )
    parser.add_argument("manuscript", help="Caminho do arquivo TXT, MD, TEX, RST, DOCX ou PDF.")
    parser.add_argument("--out", help="Caminho opcional para salvar o relatório JSON.")
    parser.add_argument("--run-id", help="Identificador opcional da campanha.")
    parser.add_argument(
        "--engineering-preset",
        action="store_true",
        help="Ativa regras de domínio de engenharia (compatibilidade v6.0 até a Fase 6).",
    )
    args = parser.parse_args()

    try:
        report = run_auditor(
            args.manuscript,
            run_id=args.run_id,
            include_engineering_preset=args.engineering_preset,
        )
        serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(serialized, encoding="utf-8")
            print(
                f"Relatório salvo em: {args.out} "
                f"({report['metricas']['total_achados']} pistas localizadas)"
            )
        else:
            print(serialized)
    except Exception as error:
        print(json.dumps({"status": "ERRO_EXECUCAO", "error": str(error)}, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
