#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auditor estrutural e forense para manuscritos científicos em TXT, Markdown, LaTeX, DOCX e PDF.
(Skill: revisao-hostil v6.0)

O script:
- extrai texto preservando a localização estrutural (parágrafos, linhas, páginas e tabelas);
- em arquivos DOCX, audita metadados internos (anonimato Double-Blind), objetos matemáticos
  nativos OMML (m:oMath / m:oMathPara) e vazamentos de código LaTeX/Markdown cru;
- localiza trechos candidatos a equações, números com unidades, comparações quantitativas,
  alegações absolutas/hiperbólicas, termos matemáticos/metodológicos, referências cruzadas,
  ambientes flutuantes e possíveis confusões entre potência e energia;
- gera pistas estruturadas de revisão com referência precisa de localização;
- não declara que uma equação ou afirmação é falsa sem verificação pelo motor_matematico.py.

Dependências opcionais:
    python-docx para DOCX
    pypdf para PDF
"""

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")


ABSOLUTE_CLAIMS = [
    (
        r"\b(100\s*%|100\s*por\s*cento|100\s*percent)\b",
        "Verificar se a afirmação de totalidade (100%) é estritamente suportada pelos dados ou se requer condição de contorno.",
    ),
    (
        r"\b(zero\s+eclipse|eclipse\s+zero|elimina[çc][ãa]o\s+total|complete\s+elimination|"
        r"perp[ée]tu[oa]s?|perpetual|ininterrupt[oa]s?|uninterrupted|isot[ée]rmic[oa]\s+perfeit[oa])\b",
        "Verificar se a condição física extrema se sustenta em todo o domínio operacional e sazonal (ex.: solstícios, falhas, transientes).",
    ),
    (
        r"\b(never|always|permanently|entirely|nunca|jamais|sempre|permanentemente|integralmente)\b",
        "Verificar escopo, condições de contorno e incerteza da afirmação absoluta.",
    ),
    (
        r"\b([óo]timo\s+global|global\s+optimum|proves?\s+mathematically|comprova\s+matematicamente|"
        r"prova\s+definitiva|unequivocally\s+proves)\b",
        "Verificar se há demonstração formal de convexidade/otimalidade global e se todas as hipóteses foram comprovadas.",
    ),
    (
        r"\b(superior\s+a\s+todas|outperforms\s+all|definitive|incontestable|incontest[áa]vel|"
        r"sem\s+qualquer\s+limita[çc][ãa]o)\b",
        "Verificar se comparadores, baselines e métricas sustentam uma conclusão tão abrangente.",
    ),
]

EPISTEMIC_OVERCLAIMS = [
    (
        r"\b(comprov\w*|comprovam|comprova|comprovando|comprovado)\b",
        "Modéstia epistêmica: modelos computacionais e simulações não 'comprovam' verdades absolutas. Substituir por 'demonstram a viabilidade', 'evidenciam', 'indicam' ou 'sustentam'.",
    ),
    (
        r"\b(proves?\s+(?:that|the)|proving\s+(?:that|the)|proof\s+of)\b",
        "Epistemic modesty: simulations and numerical models do not 'prove' physical reality. Calibrate to 'demonstrate the feasibility', 'indicate', 'corroborate', or 'substantiate'.",
    ),
    (
        r"\b(eliminat\w*|elimina[çc][ãa]o\s+de|eliminando|eliminou)\b",
        "Afirmação absoluta de eliminação: sistemas de engenharia mitigam, contêm ou reduzem gargalos/degradação; raramente eliminam completamente. Calibrar para 'mitigate', 'alleviate' ou 'reduce'.",
    ),
    (
        r"\b(strictly\s+(?:stable|invariance|preserves|zero)|perfectly\s+(?:stable|invariance)|flawless\w*)\b",
        "Linguagem dogmática: evitar advérbios absolutistas em modelos numéricos. Calibrar para 'asymptotically stable', 'consistent', 'robust' ou 'contained'.",
    ),
    (
        r"\b(mathematically\s+guaranteed|guarantees?\s+that|garante\s+que|garantem\s+que)\b",
        "Garantia excessiva: a menos que haja teorema analítico formal com hipóteses fechadas no próprio texto, substitua por 'converges in accordance with standard theory' ou 'ensures under nominal conditions'.",
    ),
    (
        r"\b(destroying|preclude[sd]?|precluding|destruindo)\b",
        "Linguagem hiperbólica: termos excessivamente dramáticos. Substituir por 'severely threatening', 'exceeding reliability limits' ou 'mitigate risk of'.",
    ),
    (
        r"\b(established\s+a|establishes\s+a|estabelece\s+um|estabeleceu\s+um)\b",
        "Assertividade excessiva: 'established a framework' soa pretensioso para revisores. Calibrar para 'presented a framework', 'proposed a framework' ou 'investigated'.",
    ),
    (
        r"\b(develop\s+a\s+fully|develops\s+a\s+fully)\b",
        "Modéstia acadêmica: 'develop a fully...' soa dogmático. Preferir 'propose a decentralized consensus formulation...' ou 'formulate a distributed scheme'.",
    ),
]



MATH_TERMS = [
    (
        r"\b(theorem|teorema|proof|prova|lemma|lema|corol[áa]rio|corollary)\b",
        "Conferir hipóteses declaradas, rigor da demonstração e correspondência exata entre premissas e conclusão.",
    ),
    (
        r"\b(stability|estabilidade|Lyapunov|Riccati|DARE|eigenvalue|autovalor|autovetor|eigenvector|Hurwitz)\b",
        "Conferir definições formais, condições matemáticas e se os autovalores/funções de Lyapunov foram efetivamente calculados.",
    ),
    (
        r"\b(optimization|otimiza[çc][ãa]o|MPC|feasibility|factibilidade|constraint|restri[çc][ãa]o|Karush|KKT)\b",
        "Conferir domínio, restrições de estado/controle, condições iniciais e evidência de factibilidade recursiva.",
    ),
    (
        r"\b(AHP|Saaty|weighted\s+sum|soma\s+ponderada|Pareto|multi-criteria|multicrit[ée]rio|TOPSIS)\b",
        "Conferir matriz de comparação par a par, autovetor principal, lambda_max, CI, CR, normalização e soma dos pesos.",
    ),
    (
        r"\b(energy\s+balance|balan[çc]o\s+energ[ée]tico|balan[çc]o\s+de\s+pot[êe]ncia|conservation|"
        r"conserva[çc][ãa]o|mass\s+balance|balan[çc]o\s+de\s+massa|Stefan-Boltzmann|Arrhenius|Weibull)\b",
        "Conferir fechamento numérico do balanço, conservação de massa/energia, acoplamento térmico e constantes físicas.",
    ),
]

EQUATION_CANDIDATE = re.compile(
    r"(=|≈|≤|≥|±|×|\\frac|\\sum|\\int|\\partial|\\nabla|"
    r"\\begin\{equation\*?\}|\\begin\{align\*?\}|\\begin\{eqnarray\*?\}|"
    r"\\\[|\\\(|\\begin\{math\}|\$[^$]+\$)"
)

# Unidades compostas e específicas primeiro; unidades de 1 letra exigem limite estrito e não podem preceder palavras comuns
UNITS_MULTI = (
    r"°[CFK]|kg/m³|kg/m3|g/cm³|g/cm3|g/cm²|g/cm2|kg/kW|W/kg|Wh/kg|W/m²|W/m2|N/m²|"
    r"J/\(kg[·\*\.]K\)|W/\(m[·\*\.]K\)|W/\(m²[·\*\.]K⁴\)|"
    r"ms|μs|us|ns|ps|min|Hz|kHz|MHz|GHz|THz|"
    r"kW|MW|GW|TW|Wh|kWh|MWh|GWh|kJ|MJ|GJ|eV|keV|MeV|GeV|"
    r"kg|mg|μg|km|cm|mm|nm|μm|um|"
    r"m/s²|m/s2|m/s|km/s|km/h|kg/s|kN|MN|"
    r"Pa|kPa|MPa|GPa|bar|mbar|atm|"
    r"kV|mV|mA|μA|Ah|mAh|kΩ|MΩ|Ohm|μF|nF|pF|mH|μH|"
    r"dBi|dBm|dBc|dB|ppm|ppb|"
    r"TB/day|TB/dia|GB/s|Gbps|Mbps|kbps|KiB|MiB|GiB|TiB|KB|MB|GB|TB|PB|"
    r"N[·\.]m|J/kg|m²/s|m2/s|m²|m2|m³|m3|cm²|cm2|cm³|cm3|mm²|mm2|"
    r"rad/s|rad|sr|cd|lm|lx|Bq|Gy|Sv|krad|Mrad"
)

UNITS_SINGLE = r"%|[KJWAVNΩ]|(?<![a-zA-Z])[smgthL](?![a-zA-Z])"

NUMBER_WITH_UNIT = re.compile(
    r"(?<![a-zA-Z0-9_])[+-]?\d+(?:[.,]\d+)?\s*(?:" + UNITS_MULTI + r"|" + UNITS_SINGLE + r")(?=$|[\s,.;:)!?\]\}])"
)

CROSS_REFERENCE = re.compile(
    r"(\\ref\{|\\cite\{|\\citep\{|\\citet\{|\\citeonline\{|\\eqref\{|\\label\{|"
    r"\b(?:Equa[çc][ãa]o|Equation|Eq\.|Tabela|Table|Figura|Figure|Fig\.|Se[çc][ãa]o|Section)\s+\d+)",
    re.IGNORECASE,
)

FLOATING_ENVIRONMENT = re.compile(
    r"(\\begin\{(figure|table|figure\*|table\*|quadro)\}|\\begin\{tabularx?\}|"
    r"^\[(Tabela|Figura)\s+\d+)",
    re.IGNORECASE,
)

POWER_ENERGY_CONFUSION = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(W|kW|MW|GW)\b.*?\b(\d+(?:[.,]\d+)?)\s*(Wh|kWh|MWh|GWh)\b|"
    r"\b(energia|energy|capacidade|capacity)\s+(?:de\s+|of\s+)?\d+(?:[.,]\d+)?\s*(W|kW|MW|GW)\b|"
    r"\b(pot[êe]ncia|power|consumo\s+instant[âa]neo)\s+(?:de\s+|of\s+)?\d+(?:[.,]\d+)?\s*(Wh|kWh|MWh|GWh)\b",
    re.IGNORECASE,
)

LATEX_OR_MD_LEAK_IN_DOCX = re.compile(
    r"(\\(?:frac|sum|int|sqrt|alpha|beta|gamma|delta|eta|theta|lambda|mu|pi|rho|sigma|tau|omega|"
    r"cdot|times|leq|geq|approx|neq|infty|partial|nabla|mathcal|mathbb|mathrm|textbf|textit)\b|"
    r"\$[^$\n]+\$|\*\*[^*\n]+\*\*)"
)


def extract_docx_structured(path):
    """
    Extrai texto de arquivos DOCX preservando a ordem real entre parágrafos e tabelas,
    além de realizar auditoria forense nos metadados e nos objetos matemáticos OMML.
    """
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

    docx_forensics = {
        "metadata": {
            "author": cp.author or "",
            "last_modified_by": cp.last_modified_by or "",
            "title": cp.title or "",
            "subject": cp.subject or "",
        },
        "anonymity_warning": bool((cp.author and cp.author.strip()) or (cp.last_modified_by and cp.last_modified_by.strip())),
        "omml_display_equations": 0,
        "omml_inline_or_total_math": 0,
        "table_count": len(document.tables),
        "paragraph_count": len(document.paragraphs),
    }

    xml_str = document._element.xml
    docx_forensics["omml_display_equations"] = len(re.findall(r"<m:oMathPara\b", xml_str))
    docx_forensics["omml_inline_or_total_math"] = len(re.findall(r"<m:oMath\b", xml_str))

    lines = []
    p_idx = 0
    t_idx = 0

    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            p_idx += 1
            para = Paragraph(child, document)
            p_xml = child.xml
            has_omml = "<m:oMath" in p_xml
            text = para.text.strip()
            if text or has_omml:
                omml_tag = " [EQUAÇÃO_OMML_NATIVA]" if has_omml else ""
                lines.append((f"Parágrafo {p_idx}", f"{text}{omml_tag}".strip(), "paragraph"))
        elif isinstance(child, CT_Tbl):
            t_idx += 1
            table = Table(child, document)
            for r_idx, row in enumerate(table.rows, start=1):
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                row_text = " | ".join(cells)
                if any(cells):
                    lines.append((f"Tabela {t_idx}, Linha {r_idx}", f"[Tabela {t_idx}] {row_text}", "table"))

    return lines, docx_forensics


def extract_content(path):
    """Retorna lista de tuplas (localizacao, texto, tipo_bloco) e dicionário de metadados extras."""
    suffix = path.suffix.lower()

    if suffix in {".txt", ".md", ".tex", ".rst"}:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        lines = [
            (f"linha {i}", line.strip(), "text")
            for i, line in enumerate(raw_text.splitlines(), start=1)
            if line.strip()
        ]
        return lines, suffix.lstrip("."), None

    if suffix == ".docx":
        lines, docx_forensics = extract_docx_structured(path)
        return lines, "docx", docx_forensics

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise RuntimeError("Para ler PDF, instale pypdf (pip install pypdf).") from error

        reader = PdfReader(str(path))
        lines = []
        for page_idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            for line_idx, raw_line in enumerate(page_text.splitlines(), start=1):
                clean = raw_line.strip()
                if clean:
                    lines.append((f"Página {page_idx}, linha {line_idx}", clean, "pdf"))
        pdf_meta = {
            "page_count": len(reader.pages),
            "metadata": {k: str(v) for k, v in (reader.metadata or {}).items()} if reader.metadata else {},
        }
        return lines, "pdf", pdf_meta

    raise ValueError(f"Formato não suportado: {suffix}")


def add_finding(findings, category, location, text, prompt, confidence="triage"):
    findings.append({
        "category": category,
        "location": location,
        "excerpt": text[:500],
        "review_prompt": prompt,
        "status": "requer_verificacao",
        "confidence": confidence,
    })


def audit_structured_lines(lines, source_type, extra_forensics=None):
    findings = []

    # Se for DOCX, registra achados forenses de metadados e estrutura
    if source_type == "docx" and extra_forensics:
        meta = extra_forensics.get("metadata", {})
        if extra_forensics.get("anonymity_warning"):
            add_finding(
                findings,
                "double_blind_violation",
                "Metadados Internos (core_properties)",
                f"author='{meta.get('author')}', last_modified_by='{meta.get('last_modified_by')}'",
                "Se o manuscrito for para submissão Double-Blind (avaliação cega), remova os nomes dos autores das propriedades internas do arquivo DOCX.",
                confidence="high",
            )

    for location, line, block_type in lines:
        if not line:
            continue

        # Vazamento de LaTeX ou Markdown em DOCX
        if source_type == "docx" and LATEX_OR_MD_LEAK_IN_DOCX.search(line):
            add_finding(
                findings,
                "formatting_leak",
                location,
                line,
                "Detectado resíduo de código LaTeX ($) ou Markdown (**) visível em arquivo DOCX. Converter para equação nativa OMML ou formatação Word.",
                confidence="high",
            )

        if EQUATION_CANDIDATE.search(line) or "[EQUAÇÃO_OMML_NATIVA]" in line:
            add_finding(
                findings,
                "equation_candidate",
                location,
                line,
                "Substituir os parâmetros numéricos declarados no texto nesta equação via motor_matematico.py e confrontar com o valor reportado.",
            )

        for pattern, prompt in ABSOLUTE_CLAIMS:
            if re.search(pattern, line, re.IGNORECASE):
                add_finding(
                    findings,
                    "absolute_claim",
                    location,
                    line,
                    prompt,
                )

        for pattern, prompt in EPISTEMIC_OVERCLAIMS:
            if re.search(pattern, line, re.IGNORECASE):
                add_finding(
                    findings,
                    "epistemic_overclaim",
                    location,
                    line,
                    prompt,
                )


        for pattern, prompt in MATH_TERMS:
            if re.search(pattern, line, re.IGNORECASE):
                add_finding(
                    findings,
                    "method_review",
                    location,
                    line,
                    prompt,
                )

        units = NUMBER_WITH_UNIT.findall(line)
        if len(units) >= 2 and re.search(
            r"(increase|decrease|reduction|gain|improvement|saving|ganho|redu[çc][ãa]o|aument|dimin|economia|melhoria|superior|inferior|vs\.?|versus)",
            line,
            re.IGNORECASE,
        ):
            add_finding(
                findings,
                "quantitative_comparison",
                location,
                line,
                "Recalcular a comparação percentual/relativa no motor_matematico.py e verificar denominador, unidade, arredondamento e valor de referência.",
            )

        if CROSS_REFERENCE.search(line):
            add_finding(
                findings,
                "cross_reference",
                location,
                line,
                "Verificar se a referência cruzada ou citação está resolvida (bijeção 1:1), pertinente e consistente com os dados.",
            )

        if FLOATING_ENVIRONMENT.search(line) or block_type == "table":
            if block_type != "table" or "Linha 1" in location:
                add_finding(
                    findings,
                    "floating_environment",
                    location,
                    line,
                    "Verificar legenda, unidades, soma das linhas/colunas, fonte dos dados, escala e correspondência exata com o texto.",
                )

        if POWER_ENERGY_CONFUSION.search(line):
            add_finding(
                findings,
                "power_energy_confusion",
                location,
                line,
                "Possível coexistência ou confusão entre potência (W/kW/MW) e energia (Wh/kWh/MWh). Verificar integração temporal e unidades.",
            )

    # Contagem por categoria para facilitar o resumo executivo
    category_counts = {}
    for f in findings:
        cat = f["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    report = {
        "finding_count": len(findings),
        "category_counts": category_counts,
        "forensics": extra_forensics,
        "findings": findings,
        "limitations": [
            "A extração automática pode perder equações em imagens ou objetos gráficos vetoriais.",
            "Em equações OMML nativas do Word sem texto linearizado, inspecione o XML ou o texto adjacente para extrair a fórmula exata.",
            "Os itens de triagem são pistas para verificação pelo agente e pelo motor_matematico.py, não vereditos finais.",
        ],
    }
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Auditor estrutural e forense para manuscritos científicos (TXT, MD, TEX, DOCX, PDF)."
    )
    parser.add_argument("manuscript", help="Caminho do arquivo TXT, MD, TEX, DOCX ou PDF.")
    parser.add_argument("--out", help="Caminho opcional para salvar o relatório JSON.")
    args = parser.parse_args()

    path = Path(args.manuscript)
    if not path.exists():
        error_json = json.dumps(
            {"success": False, "error": f"Arquivo não encontrado: {path}"},
            ensure_ascii=False,
            indent=2,
        )
        print(error_json)
        sys.exit(1)

    lines, source_type, extra_forensics = extract_content(path)
    report = audit_structured_lines(lines, source_type, extra_forensics)
    report["source_file"] = path.name
    report["source_path"] = str(path.resolve())
    report["source_type"] = source_type

    serialized = json.dumps(report, ensure_ascii=False, indent=2)

    if args.out:
        Path(args.out).write_text(serialized, encoding="utf-8")
        print(f"Relatório salvo com sucesso em: {args.out} ({report['finding_count']} pistas localizadas)")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
