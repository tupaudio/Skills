# MATRIZ DE TESTES DE ACEITAÇÃO — FASE 7 (`v8.0-beta.7`), REVISÃO 11

**Status:** Especificação de testes (**0/75 executados** — implementação Python suspensa até aprovação da OS)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)

---

## 1. Cenários Herdados (Revisões 1–10)

- **`T-R10-001` a `T-R10-060`:** mantidos integralmente (60 cenários normativos cobrindo JCS, `Fraction`, `MandatoryAxesPlan`, isolamento de pareceres, qualificação probatória, adjudicação mecânica vs interpretativa, âncoras externas e portão de congelamento).

---

## 2. Novos Cenários Obrigatórios da Revisão 11 (`T-R11-061` a `T-R11-075`)

| ID | Achado | Cenário Adversarial / Verificação | Resultado Esperado (Fail-Closed) |
| :--- | :--- | :--- | :--- |
| `T-R11-061` | `ACH-B7-R10-001` | Replay de `signed_store_receipt` antigo e validamente assinado (revisão `r-1` reapresentada como atual). | Rejeição da classificação `ancoragem_externa_independente` / `AnchorVerificationError` por falha na `freshness_proof` (testemunha/log/contador acusa regressão). |
| `T-R11-062` | `ACH-B7-R10-001` | Restauração de snapshot do armazenamento remoto do `MonotonicCheckpointStore` voltando o estado para revisão anterior. | Detectado pela divergência com `freshness_proof` (prova de consistência Merkle falha ou testemunha/contador HW exige revisão maior); bloqueio imediato. |
| `T-R11-063` | `ACH-B7-R10-001` | Perda ou indisponibilidade da testemunha externa independente durante verificação. | Negação obrigatória de `ancoragem_externa_independente`; degradação explícita para `integridade_local_com_ancora_co_localizada` ou `AnchorVerificationError` se ancoragem externa for obrigatória. |
| `T-R11-064` | `ACH-B7-R10-002` | Adulteração de 1 byte em `compatibility_policy_v1.json` após assinatura da política confiável. | Divergência de `compatibility_policy_jcs_sha256` causa `ExecutionBlockedError` antes de qualquer validação de instância. |
| `T-R11-065` | `ACH-B7-R10-002` | Submissão de instância com tripla `(schema_name, instance_schema_version, contract_version)` não listada em `allowed_triples`. | Rejeição imediata pela regra `default_decision: "deny"` (`ExecutionBlockedError`). |
| `T-R11-066` | `ACH-B7-R10-002` | Arquivo `$ref` ausente ou com SHA-256 divergente do declarado em `ref_hashes`. | Bloqueio imediato (`ExecutionBlockedError`), mesmo com `backward_validation: true`. |
| `T-R11-067` | `ACH-B7-R10-003` | Cálculo exato com $m=15$, $n_i \in \{1..15\}$ e $\tilde{W}_{\text{total}}$ não divisor de $15 \times 10^6$ (ex.: primo). | Verificação confirma $D \mid (L \cdot 10^6 \cdot \tilde{W}_{\text{total}})$, $D \le D_{\text{bound}} = 5.4054 \times 10^{21}$ (73 bits) e $N \le 10 \cdot D_{\text{bound}}$ (76 bits), sem exigir $D \mid D_{\text{bound}}$. |
| `T-R11-068` | `ACH-B7-R10-004` | Política candidata `P_k` assinada por chave não presente na raiz nem em `P_{k-1}.authorized_signers`, mas inserida na própria `P_k.authorized_signers` (tentativa de autoautorização). | Rejeição imediata (`PolicyAuthorityError`). |
| `T-R11-069` | `ACH-B7-R10-004` | Política candidata `P_k` assinada por chave delegada válida em `P_{k-1}`, porém com `genTime` do TSA fora de `[not_before_utc, not_after_utc]` ou sem escopo `policy_sign`. | Rejeição imediata (`PolicyAuthorityError`). |
| `T-R11-070` | `ACH-B7-R10-005` | `policy_seq` ou `checkpoint_revision` contendo dígitos Unicode mistos (ex.: `"1٣"`, `"٢"`). | Rejeição na validação de schema e regex Python `\A(0\|[1-9][0-9]{0,31})\Z`. |
| `T-R11-071` | `ACH-B7-R10-005` | `policy_seq` ou `checkpoint_revision` com mais de 32 dígitos ASCII (ex.: 33 dígitos `"1" + "0"*32`). | Rejeição imediata por excesso de comprimento. |
| `T-R11-072` | `ACH-B7-R10-005` | `policy_seq` ou `checkpoint_revision` com zeros à esquerda (`"01"`, `"00"`). | Rejeição imediata pela regex canônica. |
| `T-R11-073` | `ACH-B7-R10-006` | Alteração exclusiva na proveniência lexical da nota (`"8.5"` → `"8.50"`) ou metadado de emissão, preservando conteúdo e valor numérico. | `score_semantic_sha256` permanece **idêntico**, enquanto `score_provenance_sha256` e `parecer_sha256` **alteram obrigatoriamente**. |
| `T-R11-074` | `ACH-B7-R10-007` | (Windows) Reparse point (symlink/junction/mount point) posicionado em componente intermediário ou final do caminho dentro de `root_dir`. | Travessia componente por componente com `NtCreateFile` (segmento único) detecta `FILE_ATTRIBUTE_REPARSE_POINT` no componente afetado e aborta com `PathConfinementError` antes de avançar. |
| `T-R11-075` | `ACH-B7-R10-007` | (POSIX) Subdiretório dentro de `root_dir` que é um mount-point ou bind-mount cruzando fronteira de montagem. | Verificação de `st_dev` / `stx_mnt_id` / `RESOLVE_NO_XDEV` detecta o cruzamento e aborta fail-closed com `PathConfinementError`. |

**Total de cenários especificados:** **75 cenários** (`60` herdados + `15` novos da Revisão 11). Nenhum executado ainda.
