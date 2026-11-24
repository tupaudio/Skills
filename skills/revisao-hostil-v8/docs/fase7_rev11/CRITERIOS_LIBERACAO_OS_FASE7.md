# CRITÉRIOS DE LIBERAÇÃO DA ORDEM DE SERVIÇO — FASE 7 (`v8.0-beta.7`), REVISÃO 11

**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Branch documental:** `specification/v8.0-beta.7-rev11`

## 1. Checklist de Consistência Interna da Revisão 11

- [x] **Base congelada preservada:** `main`, `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`), `specification/v8.0-beta.7-rev10`, `requirements.txt`, `catalogo_agentes.yaml` e todos os arquivos Python inalterados.
- [x] **Zero implementação prematura:** nenhum código Python da Fase 7 foi criado ou executado; nenhum dos 75 cenários de teste foi declarado como executado.
- [x] **`ACH-B7-R10-001` (P1) fechado:** schema fechado `signed_store_receipt` + 3 mecanismos verificáveis de `freshness_proof` + degradação fail-closed + cenários `T-R11-061`..`063`.
- [x] **`ACH-B7-R10-002` (P1) fechado:** artefato estruturado `compatibility_policy_v1.json` com schema fechado, `default_decision: "deny"`, autenticação via `compatibility_policy_jcs_sha256`, verificação de `ref_hashes`, semântica formal de `backward_validation` + cenários `T-R11-064`..`066`.
- [x] **`ACH-B7-R10-003` (P2) fechado:** prova corrigida por desigualdade $D \le D_{\text{bound}} = 5.4054 \times 10^{21}$ (73 bits), $N \le 10 \cdot D_{\text{bound}}$ (76 bits), teto operacional 128 bits + cenário `T-R11-067`.
- [x] **`ACH-B7-R10-004` (P2) fechado:** autoridade exclusiva via raiz fixada ou `P_{k-1}.authorized_signers`, proibição explícita de autoautorização, `key_id` + escopo + validade no `genTime` do TSA + cenários `T-R11-068`..`069`.
- [x] **`ACH-B7-R10-005` (P2) fechado:** regex estritamente ASCII `\A(0|[1-9][0-9]{0,31})\Z` (máx. 32 dígitos) + cenários `T-R11-070`..`072`.
- [x] **`ACH-B7-R10-006` (P2) fechado:** fórmula composta explícita de `parecer_sha256` vinculando conteúdo, `score_semantic_sha256` e `score_provenance_sha256` + cenário `T-R11-073`.
- [x] **`ACH-B7-R10-007` (P2) fechado:** regras explícitas de confinamento para Windows (segmento único `NtCreateFile` + inspeção imediata de reparse point) e POSIX (`st_dev` / `stx_mnt_id` / `RESOLVE_NO_XDEV` contra mount-point/bind-mount) + cenários `T-R11-074`..`075`.

## 2. Condição de Liberação da OS

A implementação da Fase 7 (`v8.0-beta.7`) só poderá ser iniciada após parecer formal de aprovação desta Revisão 11 pela banca externa.
