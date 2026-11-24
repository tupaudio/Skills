"""Gera MATRIZ_TESTES_ACEITACAO_REV18.md preservando os 164 IDs historicos + 30 novos (194 total)."""
from pathlib import Path

REV18 = Path(__file__).resolve().parent.parent
REV17_TM = REV18.parent / "fase7_rev17/MATRIZ_TESTES_ACEITACAO_REV17.md"
OUT_TM = REV18 / "MATRIZ_TESTES_ACEITACAO_REV18.md"

rev17_txt = REV17_TM.read_text(encoding="utf-8")

new_rows = [
    ("T-R18-165", "ACH-B7-R17-001", "Vetores oficiais RFC 8785 (ordenacao UTF-16 + numeros)", "test_vectors/rfc8785/v01..v18", "100% concordancia rfc8785==0.1.4 e jcs==0.3.0", "EXECUTADO_DOC", "PASS"),
    ("T-R18-166", "ACH-B7-R17-001", "Rejeicao de NaN, Infinity e -Infinity em jcs_canonical()", "float('nan'), float('inf'), float('-inf')", "ValidationError explicito", "EXECUTADO_DOC", "PASS"),
    ("T-R18-167", "ACH-B7-R17-001", "Rejeicao de tipos Python fora do modelo JSON (Decimal, Fraction, bytes, tuple)", "Decimal('1.0'), Fraction(1,2), b'a', (1,)", "ValidationError explicito", "EXECUTADO_DOC", "PASS"),
    ("T-R18-168", "ACH-B7-R17-001", "Divergencia entre rfc8785 e jcs ou dependencia ausente/versao incorreta", "validate_dependencies() + dual check", "Falha fechada codigo != 0", "EXECUTADO_DOC", "PASS"),
    ("T-R18-169", "ACH-B7-R17-002", "Vetor oficial RFC 8032 Section 7.1 TEST 1 via cryptography", "test_vectors/ed25519/rfc8032-tv1.json", "Assinatura Ed25519 valida sem fallback artesanal", "EXECUTADO_DOC", "PASS"),
    ("T-R18-170", "ACH-B7-R17-002", "SPKI DER vazio, truncado, com bytes excedentes ou OID diferente de Ed25519", "Mutacoes DER em load_ed25519_public_key()", "Rejeicao explicita (ValidationError)", "EXECUTADO_DOC", "PASS"),
    ("T-R18-171", "ACH-B7-R17-002", "Assinatura Ed25519 com 63 bytes, 65 bytes ou 1 bit alterado", "Mutacoes de assinatura", "Rejeicao explicita (ValidationError)", "EXECUTADO_DOC", "PASS"),
    ("T-R18-172", "ACH-B7-R17-002", "Chave valida nao autorizada na politica de confianca ou authority_key_id divergente", "Chave fora de authorized_dossier_authorities", "Rejeicao explicita (ValidationError)", "EXECUTADO_DOC", "PASS"),
    ("T-R18-173", "ACH-B7-R17-003", "Reconciliacao semantica global positiva de checkpoint-receipt-tv-001.json", "Recibo + trust bundle + dossie + politica", "Todas as 14 relacoes + assinaturas Ed25519 aprovadas", "EXECUTADO_DOC", "PASS"),
    ("T-R18-174", "ACH-B7-R17-003", "Mutacoes negativas: store_id, namespace, policy_seq, new_revision ou new_checkpoint_sha256 divergentes", "5 mutacoes independentes", "Todas rejeitadas sem efeitos colaterais", "EXECUTADO_DOC", "PASS"),
    ("T-R18-175", "ACH-B7-R17-003", "Mutacao negativa: receipt_sha256 divergente ou assinatura de signed_store_receipt invalida", "2 mutacoes independentes", "Rejeicao explicita (ValidationError)", "EXECUTADO_DOC", "PASS"),
    ("T-R18-176", "ACH-B7-R17-003", "Mutacoes negativas: testemunha sem recibo, recibo sem testemunha, chave divergente", "3 mutacoes independentes", "Rejeicao explicita (ValidationError)", "EXECUTADO_DOC", "PASS"),
    ("T-R18-177", "ACH-B7-R17-003", "Mutacoes negativas: nonce divergente, nonce duplicado, Base64 invalido", "3 mutacoes independentes", "Rejeicao explicita (ValidationError)", "EXECUTADO_DOC", "PASS"),
    ("T-R18-178", "ACH-B7-R17-003", "Mutacoes negativas: campaign_id, protocol_scope, store_epoch ou persisted_tx_id invalidos", "4 mutacoes independentes", "Rejeicao explicita (ValidationError)", "EXECUTADO_DOC", "PASS"),
    ("T-R18-179", "ACH-B7-R17-003", "Mutacao negativa: administrative_independence_dossier_sha256 divergente do dossie", "Hash divergente no recibo", "Rejeicao explicita (ValidationError)", "EXECUTADO_DOC", "PASS"),
    ("T-R18-180", "ACH-B7-R17-004", "UUIDv4 canonico em minusculas aceito para Linux e Windows", "f47ac10b-58cc-4372-a567-0e02b2c3d479", "Aprovado por schema e validate_process_clock_context_id()", "EXECUTADO_DOC", "PASS"),
    ("T-R18-181", "ACH-B7-R17-004", "Rejeicao de string arbitraria, UUID v1, v3, v5, maiusculas, variante incorreta, truncado", "8 mutacoes negativas UUID", "Todas rejeitadas (ValidationError)", "EXECUTADO_DOC", "PASS"),
    ("T-R18-182", "ACH-B7-R17-004", "Invalidacao por mudanca de clock_context_id, clock_source ou store_epoch (runtime)", "Reinicializacao / troca de epoca", "Invalidacao imediata do prazo pendente", "NAO_EXECUTADO_RUNTIME", "PENDENTE_OS"),
    ("T-R18-183", "ACH-B7-R17-004", "Execucao real de conversao de ticks Windows QPC (QueryPerformanceCounter)", "Ambiente Windows 11 local", "Conversao inteira exata sem float", "EXECUTADO_DOC", "PASS"),
    ("T-R18-184", "ACH-B7-R17-004", "Execucao real de CLOCK_MONOTONIC_RAW em kernel Linux >= 5.6", "Requer ambiente Linux (host atual e Windows)", "Conversao inteira exata", "BLOQUEADO_AMBIENTE_LINUX", "BLOQUEADO"),
    ("T-R18-185", "ACH-B7-R17-005", "Cobertura 100% dos 18 vetores RFC 8785 nas duas implementacoes independentes", "reports/COBERTURA_RFC8785_REV18.md", "18/18 PASS em rfc8785 e jcs", "EXECUTADO_DOC", "PASS"),
    ("T-R18-186", "ACH-B7-R17-005", "Validacao integral de todos os 19 schemas Draft 2020-12 e unicidade de $id", "schemas/7.0.0/*.json", "19/19 aprovados sem ciclos nem $ref externos", "EXECUTADO_DOC", "PASS"),
    ("T-R18-187", "ACH-B7-R17-005", "Reconciliacao integral de Registry e politica de compatibilidade", "SCHEMA_REGISTRY + compatibility_policy_v1", "19 contratos e 19 $ref transitivos conferidos", "EXECUTADO_DOC", "PASS"),
    ("T-R18-188", "ACH-B7-R17-005", "Execucao de validate_rev18.py sob python -O (otimizacao sem asserts)", "python -O tools/validate_rev18.py", "Zero asserts no validador; codigo de saida 0", "EXECUTADO_DOC", "PASS"),
    ("T-R18-189", "ACH-B7-R17-005", "Preservacao historica: 164 IDs anteriores, 8 schemas legados, Rev17 e Beta 6.6 intactos", "validate_historical_preservation()", "Zero alteracoes historicas", "EXECUTADO_DOC", "PASS"),
    ("T-R18-190", "ACH-B7-R17-001", "Rejeicao de chaves JSON duplicadas em strict_parse()", "Objeto com chave repetida", "ValidationError explicito", "EXECUTADO_DOC", "PASS"),
    ("T-R18-191", "ACH-B7-R17-001", "Rejeicao de bytes JCS esperados ou SHA-256 adulterados em vetor", "Mutacao de vetor RFC 8785", "ValidationError explicito", "EXECUTADO_DOC", "PASS"),
    ("T-R18-192", "ACH-B7-R17-002", "Assinatura de dossie sobre pre-imagem alterada ou digest alterado", "Mutacao de pre-imagem do dossie", "ValidationError explicito", "EXECUTADO_DOC", "PASS"),
    ("T-R18-193", "ACH-B7-R17-003", "Verificacao de assinatura Ed25519 das duas witness_assertions no recibo", "Assinatura adulterada em witness_a ou witness_b", "ValidationError explicito", "EXECUTADO_DOC", "PASS"),
    ("T-R18-194", "ACH-B7-R17-005", "Auditoria interna hostil sem falsos positivos, sem asserts e sem fallbacks", "reports/RELATORIO_AUDITORIA_INTERNA_REV18.md", "Zero P1/P2 documentais abertos", "EXECUTADO_DOC", "PASS"),
]

rev18_txt = rev17_txt.replace(
    "# MATRIZ DE TESTES DE ACEITAÇÃO — FASE 7 (`v8.0-beta.7`), REVISÃO 17",
    "# MATRIZ DE TESTES DE ACEITAÇÃO — FASE 7 (`v8.0-beta.7`), REVISÃO 18"
).replace(
    "**0/164 executados**", "**28/194 executados (documentais/validador), 165/194 não executados (runtime Fase 7 suspenso), 1/194 bloqueado por ambiente (Linux)**"
).replace(
    "+ `10` novos cenários da Revisão 17 (`T-R17-155`..`164`) = **164 cenários especificados**.",
    "+ `10` cenários da Revisão 17 (`T-R17-155`..`164`) + `30` novos cenários da Revisão 18 (`T-R18-165`..`194`) = **194 cenários especificados**."
).replace(
    "**Total consolidado:** `164` cenários especificados (`0/164 executados`).",
    "---\n\n## 9. Novos Cenários da Revisão 18 (`30` cenários — `T-R18-165` a `T-R18-194`)\n\n"
    "| ID | Achado / Requisito | Cenário | Entrada / Pré-condição | Resultado Esperado | Classificação | Status |\n"
    "| :--- | :--- | :--- | :--- | :--- | :--- | :---: |\n"
    + "\n".join(f"| `{r[0]}` | `{r[1]}` | {r[2]} | {r[3]} | {r[4]} | `{r[5]}` | `{r[6]}` |" for r in new_rows)
    + "\n\n---\n\n**Total consolidado:** `194` cenários especificados (`28` documentais executados via `validate_rev18.py`, `165` de runtime não executados, `1` bloqueado por ambiente Linux)."
)

OUT_TM.write_text(rev18_txt, encoding="utf-8")
print(f"Wrote {OUT_TM.name} with 164 historical + {len(new_rows)} new = {164 + len(new_rows)} scenarios.")
