# Especificação Técnica Consolidada — Fase 7 (`v8.0-beta.7`, Revisão 10)

> **Base de referência congelada:** `v8.0-beta.6.6` (`commit 11e91b6f3d517707326357868cc34ff97ab8327d`)  
> **Branch documental:** `specification/v8.0-beta.7-rev10`  
> **Aviso normativo obrigatório:** este documento é **especificação técnica documental** e **não representa implementação executada**. Nenhum arquivo de código, contrato da Beta 6.6, `requirements.txt`, catálogo de agentes ou tag histórica foi alterado. A implementação da Fase 7 permanece suspensa até aprovação formal pela banca externa e emissão da Ordem de Serviço.

---

## 0. Escopo e Documentos Complementares da Revisão 10

Esta Revisão 10 consolida a especificação da Fase 7 corrigindo exclusivamente os sete achados da nona auditoria (`ACH-B7-R9-001` a `ACH-B7-R9-007`), sem ampliar escopo funcional nem antecipar componentes da Fase 8 (`motor_integracao`, `motor_meta`, `auditor_meta`, `orchestrator.py`, `SKILL.md` v8.0).

Documentos integrantes do pacote da Revisão 10:
1. `ESPECIFICACAO_TECNICA_FASE7_REV10.md` (este documento — regras normativas, interfaces e erros);
2. `CONTRATOS_CRIPTOGRAFICOS_REV10.md` (política de confiança, assinaturas, `MonotonicCheckpointStore` e RFC 3161);
3. `MATRIZ_COMPATIBILIDADE_CONTRATOS_REV10.md` (separação instância vs contrato, tabela de despacho e `$ref` imutáveis);
4. `MATRIZ_R9_R10.md` (rastreabilidade bidirecional de `ACH-B7-R9-001` a `ACH-B7-R9-007`);
5. `MATRIZ_TESTES_ACEITACAO_REV10.md` (60 cenários positivos, negativos, concorrentes e adversariais);
6. `CRITERIOS_LIBERACAO_OS_FASE7.md` (portão objetivo de aprovação e liberação da Ordem de Serviço).

---

## 1. `ACH-B7-R9-001` (P1) — Checkpoint Anti-Rollback Resistente a Restauração e Concorrência

### 1.1. Ambiguidade eliminada
Na Revisão 9, o checkpoint anti-rollback era descrito como um arquivo JSON local fora do diretório da campanha, vulnerável a restauração silenciosa de backup e a corridas entre campanhas concorrentes.

### 1.2. Regra normativa e interface `MonotonicCheckpointStore`
- Define-se a interface abstrata `MonotonicCheckpointStore` (módulo futuro `scripts/banca/checkpoint_store.py`) com cinco operações obrigatórias:
  - `read_checkpoint() -> CheckpointSnapshot`
  - `compare_and_swap(expected_revision: str, new_state: CheckpointRecord) -> CheckpointSnapshot`
  - `initialize_genesis(genesis_record: CheckpointRecord) -> CheckpointSnapshot`
  - `verify_checkpoint_integrity() -> CheckpointIntegrityReport`
  - `recover_checkpoint(recovery_record: RecoveryAuthorizationRecord) -> CheckpointSnapshot`
- **Mecanismo de referência para `ancoragem_externa_independente`:** armazenamento transacional remoto, *append-only* e independente da campanha, suportando CAS atômico e prova de autenticidade do estado. Alternativa documentada: contador monotônico protegido por hardware (TPM/HSM) com capacidade e integridade verificadas.
- **Proibição explícita:** um arquivo local ou backup restaurável **nunca** pode ser classificado como `ancoragem_externa_independente` (recebe obrigatoriamente `integridade_local_com_ancora_co_localizada`).
- **Contrato do checkpoint:** `last_accepted_policy_seq` (string decimal canônica `\A(0|[1-9]\d*)\Z` para evitar limites inteiros IEEE 754 do JCS), `last_accepted_policy_jcs_sha256`, `root_key_spki_der_sha256`, `checkpoint_revision` (string decimal monotônica), `previous_checkpoint_sha256`, `updated_at_utc` e `checkpoint_integrity_proof`.

### 1.3. Máquina de aceitação e tratamento de concorrência
- **Caso A (`candidate.policy_seq < checkpoint.policy_seq`):** levanta `PolicyRollbackError` imediatamente.
- **Caso B (`candidate.policy_seq == checkpoint.policy_seq`):** aceita somente se `candidate.policy_jcs_sha256 == checkpoint.last_accepted_policy_jcs_sha256` (operação idempotente, sem mutar checkpoint); hash divergente levanta `PolicyEquivocationError`.
- **Caso C (`candidate.policy_seq == checkpoint.policy_seq + 1`):** aceita somente se `candidate.prev_policy_sha256 == checkpoint.last_accepted_policy_jcs_sha256`; após validação criptográfica e temporal, executa `compare_and_swap(expected_revision, new_state)`.
- **Caso D (`candidate.policy_seq > checkpoint.policy_seq + 1`):** rejeitado por padrão (`PolicySequenceGapError`), salvo apresentação de cadeia intermediária completa, autenticada e contínua sem lacunas.
- **Concorrência / falha CAS:** se `compare_and_swap` falhar por revisão obsoleta (`CheckpointConflictError`), o processo relê o estado, revalida a política candidata contra o novo estado e reinicia a avaliação — nunca sobrescreve o checkpoint mais recente.
- **Indisponibilidade / timeout / perda:** modo *fail-closed* (`CheckpointUnavailableError` bloqueia `ancoragem_externa_independente`). Recuperação extraordinária exige autorização assinada fora de banda, registro de auditoria e nova ancoragem confiável; é proibido reinicializar automaticamente em sequência `0` ou restaurar backups antigos.

---

## 2. `ACH-B7-R9-002` (P1) — Separação entre Versão da Instância e Versão do Contrato

### 2.1. Ambiguidade eliminada
Na Revisão 9, a seleção automática por `schema_version` da instância contradizia a matriz que permite validar uma instância `1.0.0` contra o contrato `1.1.0`.

### 2.2. Regra normativa e interface
- Separam-se formalmente:
  - `instance_schema_version`: versão declarada pelo produtor na instância;
  - `contract_version`: versão congelada do contrato solicitada explicitamente pelo consumidor.
- Interface normativa em `scripts/common/schema_validator.py`:
  ```python
  validate_contract(
      instance: dict[str, Any],
      schema_name: str,
      contract_version: str,
      *,
      compatibility_policy: CompatibilityPolicy,
  ) -> ValidationResult
  ```
- **Fluxo obrigatório:** (1) exigir versão declarada na instância (exceto perfis YAML, despachados por `PROFILE_CONTRACT_VERSION = "1.0.0"`); (2) validar SemVer 2.0.0 estrito; (3) consultar a matriz executável de compatibilidade (`MATRIZ_COMPATIBILIDADE_CONTRATOS_REV10.md`); (4) carregar exclusivamente o schema congelado de `references/schemas/<contract_version>/<schema_name>`; (5) validar e retornar resultado estruturado com `valid`, `schema_name`, `instance_schema_version`, `contract_version_used`, `compatibility_rule` e `errors`.
- **Proibição:** a versão do contrato nunca é escolhida implicitamente como "a mais recente".

---

## 3. `ACH-B7-R9-003` (P2) — Contrato Criptográfico e Temporal da Assinatura da Política

- Especificação detalhada em `CONTRATOS_CRIPTOGRAFICOS_REV10.md`.
- **Estrutura fechada de `policy_signature`:** `algorithm`, `key_id`, `signature_encoding`, `signature_b64`, `signed_payload_sha256`, `timestamp_token_ref`.
- **Algoritmo normativo inicial:** `Ed25519` (chave pública em SPKI DER; `key_id = SHA256(spki_der)`; assinatura de 64 bytes em Base64 estrito sem padding inválido). Suporte opcional a `ECDSA-P256-SHA256` exige curva P-256 explícita, assinatura ASN.1 DER estrita e chave SPKI DER validada.
- **Bytes assinados (zero circularidade):** exclusivamente os bytes UTF-8 de `JCS(trusted_anchors_policy_payload_v1)`, excluindo `policy_jcs_sha256`, `policy_signature` e `timestamp_token_ref`.
- **Prova temporal obrigatória:** token RFC 3161 carimbando `SHA256(signature_bytes)` (com OID SHA-256 `2.16.840.1.101.3.4.2.1`, assinatura CMS válida, extensão crítica `id-kp-timeStamping`, cadeia X.509, política TSA e revogação verificadas). A janela de validade da política é avaliada exclusivamente com `genTime`, nunca com relógio local.

---

## 4. `ACH-B7-R9-004` (P2) — Separação entre Identidade Semântica da Nota e Proveniência da Entrada

- **Duas estruturas fechadas distintas:**
  1. `score_payload`: `{"nota_decimal": "9.500000", "peso_decimal": "1.000000"}` — usado exclusivamente para conversão em `Fraction`, canonicalização JCS e `score_semantic_sha256 = SHA256(JCS(score_payload))`.
  2. `score_input_provenance`: `{valor_original_informado, formato_recebido, origem, timestamp_utc, resultado_normalizacao, agente_id}` — possui digest próprio `score_provenance_sha256 = SHA256(JCS(score_input_provenance))`.
- **Regras:** entradas com 0 a 6 casas decimais (`"9.5"`, `"9.50"`, `"9.500000"`) normalizam para `"9.500000"` produzindo o **mesmo** `score_semantic_sha256`, preservando `score_provenance_sha256` distintos. Entradas com `> 6` casas decimais (`"9.5000001"`), `float`, `bool`, `NaN` ou `Infinity` são rejeitadas (`ExcessiveDecimalPrecisionError` / `InvalidScoreInputError`), sem arredondamento nem truncamento.

---

## 5. `ACH-B7-R9-005` (P2) — Reconstrução do Próprio Interpretador Python

- `environment_lock.json` passa a exigir metadados verificáveis do próprio interpretador: `python_distribution_origin`, `python_artifact_filename`, `python_artifact_sha256`, `python_version`, `python_implementation`, `python_build_id`, `python_build_flags`, `python_abi_tag`, `architecture`, `installer_name`, `installer_version` e `base_image_digest` (quando aplicável). Para builds a partir do código-fonte, exige também hash do source release, compilador/versão, configuração/flags, dependências de build e imagem de construção.
- **Critério estrito:** `python_environment_reconstructible = true` **somente** quando (1) artefato do interpretador disponível, (2) `python_artifact_sha256` verificado, (3) versão e ABI exatas, (4) 100% das distribuições diretas/transitivas identificadas e (5) 100% dos artefatos verificáveis.
- Mantêm-se separadas `native_runtime_reconstructible` e `campaign_environment_reconstructible` (verdadeira apenas quando todas as camadas relevantes forem reconstruíveis).

---

## 6. `ACH-B7-R9-006` (P2) — Confinamento Windows por Identidade de Handles

- Adaptadores separados sob contrato único (`scripts/common/safe_io.py`):
  - **Adaptador POSIX:** `openat` componente a componente com `O_DIRECTORY | O_NOFOLLOW`, `fstat` (`S_ISREG`) e leitura + SHA-256 sobre o mesmo `fd`.
  - **Adaptador Windows:** (1) abertura do handle da raiz com validação de volume e identidade (`FILE_ID_INFO` / `GetFileInformationByHandle`); (2) traversal relativo componente a componente via **`NtCreateFile`** com `RootDirectory` + `FILE_OPEN_REPARSE_POINT` (sem seguir reparse points em nenhum ancestral!); (3) verificação de atributos/tags (rejeitando symlinks, junctions, mount points); (4) verificação de volume e `nNumberOfLinks == 1` (rejeitando hard links múltiplos quando exclusividade for exigida); (5) rejeição explícita de caminhos UNC (`\\server\share`), prefixos `\\?\`, Alternate Data Streams (`:stream`), nomes com pontos/espaços finais ou mudança de volume; (6) leitura e cálculo de SHA-256 diretamente sobre o mesmo handle validado.
- **Proibição de fallback inseguro:** se a implementação segura por handles/descritores não estiver disponível na plataforma, o comportamento obrigatório é **falhar fechado** (`UnsafePlatformPathError`), nunca recorrer a `Path.resolve()` + comparação textual de prefixos.

---

## 7. `ACH-B7-R9-007` (P2) — Limites Racionais Matematicamente Derivados

### 7.1. Limites operacionais fixados para a Fase 7
- Máximo de **15 agentes avaliadores** (Adjudicador excluído da contagem);
- Máximo de **15 eixos** e **15 avaliações por eixo**;
- Notas $s \in [0, 10]$; pesos $w \in (0, 1000]$; precisão máxima de **6 casas decimais** (denominador inicial divide $10^6$).

### 7.2. Demonstração formal (verificada independentemente em Python)
- Média de um eixo com $m_e \in \{1, \dots, 15\}$ avaliadores tem denominador que divide $m_e \cdot 10^6$.
- Seja $L = \operatorname{lcm}(1, 2, \dots, 15) = 360\,360$.
- A soma ponderada $\sum w_e \cdot S_e$ tem denominador que divide $L \cdot 10^{12} = 3{,}6036 \times 10^{17}$ (59 bits).
- A soma dos pesos é $\frac{W_{\text{total}}}{10^6}$ com $W_{\text{total}} \le 15 \cdot 1000 \cdot 10^6 = 1{,}5 \times 10^{10}$.
- Logo, o denominador da nota global $S_{\text{global}}$ divide:
  $$D_{\max} = L \cdot 10^6 \cdot W_{\text{total}} = 360\,360 \cdot 10^6 \cdot (15 \cdot 1000 \cdot 10^6) = 5\,405\,400\,000\,000\,000\,000\,000 = 5{,}4054 \times 10^{21}$$
- **Verificação de largura em bits:**
  - $D_{\max}.\text{bit\_length()} = 73 \le 128$;
  - $N_{\max} = 10 \cdot D_{\max} = 5{,}4054 \times 10^{22} \implies N_{\max}.\text{bit\_length()} = 76 \le 128$.
- **Novo limite operacional:** revoga-se `10**12` e adota-se `numerator.bit_length() <= 128` e `denominator.bit_length() <= 128` em `round_fraction_half_even()` e operações racionais. Exceder esse teto por expansão de configuração levanta `RationalCapacityExceededError` (erro de capacidade, não dado inválido). Nenhuma etapa de cálculo utiliza `float`.
