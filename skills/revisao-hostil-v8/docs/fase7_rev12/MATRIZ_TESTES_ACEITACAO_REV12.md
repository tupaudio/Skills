# MATRIZ DE TESTES DE ACEITAÇÃO — FASE 7 (`v8.0-beta.7`), REVISÃO 12

**Status:** Especificação de testes (**0/119 executados** — implementação Python suspensa até aprovação formal da OS)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Composição:** `60` cenários originais da Revisão 10 (IDs `T-R9-*` preservados) + `15` cenários da Revisão 11 (`T-R11-061`..`075`) + `44` novos cenários da Revisão 12 (`T-R12-076`..`119`) = **119 cenários especificados**.

---

## 1. Cenários Originais da Revisão 10 (`60` cenários — IDs preservados)

| ID | Cenário | Entrada / Pré-condição | Resultado Esperado |
| :--- | :--- | :--- | :--- |
| `T-R9-001-01` | Rollback de política 13 → 12 | Checkpoint em `policy_seq="13"`; candidata `policy_seq="12"` legitimamente assinada | Levanta `PolicyRollbackError`; checkpoint permanece em `"13"`. |
| `T-R9-001-02` | Restauração de checkpoint 12 após avanço para 13 | Store remoto em revisão 14 (`seq="13"`); tentativa de apresentar backup local de revisão 13 (`seq="12"`) | `verify_checkpoint_integrity()` / `read_checkpoint()` rejeita backup restaurado; proibido `ancoragem_externa_independente`. |
| `T-R9-001-03` | Duas campanhas concorrentes avançando `13 → 14` | Campanha A e Campanha B leem `rev="14"` simultaneamente e executam `compare_and_swap("14", ...)` | Exatamente uma vence e avança para `rev="15"`; a outra recebe `CheckpointConflictError`, relê e reavalia sem sobrescrever. |
| `T-R9-001-04` | Falha explícita de `compare_and_swap` | `expected_revision="10"` quando store está em `"11"` | Levanta `CheckpointConflictError`; estado do store permanece inalterado. |
| `T-R9-001-05` | Interrupção durante atualização | Falha simulada antes do commit no store | Store mantém estado anterior íntegro; reexecução idempotente conclui transição limpa sem corrupção. |
| `T-R9-001-06` | Recuperação após perda do armazenamento | `recover_checkpoint()` sem autorização assinada fora de banda vs com autorização válida | Sem autorização: `UnauthorizedRecoveryError` (proibido reset automático para `seq="0"`); com autorização válida: registra evento de auditoria e nova âncora. |
| `T-R9-001-07` | Checkpoint inacessível / timeout | Store remoto retorna timeout ou erro de conexão | Levanta `CheckpointUnavailableError`; garantia rebaixada fail-closed (nunca concede `ancoragem_externa_independente`). |
| `T-R9-001-08` | Mesma sequência com hash idêntico | `candidate.policy_seq == "13"` e `policy_jcs_sha256 == checkpoint.last_accepted_policy_jcs_sha256` | Aceito de forma idempotente; `checkpoint_revision` não é incrementada. |
| `T-R9-001-09` | Mesma sequência com hash diferente | `candidate.policy_seq == "13"` e `policy_jcs_sha256 != checkpoint.last_accepted_policy_jcs_sha256` | Levanta `PolicyEquivocationError`; política rejeitada. |
| `T-R9-001-10` | Salto de sequência sem cadeia intermediária | Checkpoint em `"13"`; candidata `"15"` sem política `"14"` | Levanta `PolicySequenceGapError`; aceita somente se cadeia `14 → 15` completa e autenticada for fornecida. |
| `T-R9-002-01` | Instância `1.0.0` vs contrato `1.0.0` | `schema_motor.json`, instância `1.0.0`, `contract_version="1.0.0"` | `valid=True`, `compatibility_rule="exact_match"`. |
| `T-R9-002-02` | Instância `1.0.0` vs contrato `1.1.0` | `schema_motor.json`, instância `1.0.0`, `contract_version="1.1.0"` | `valid=True`, `compatibility_rule="backward_validation"`, `contract_version_used="1.1.0"`. |
| `T-R9-002-03` | Instância `1.1.0` vs contrato `1.1.0` | `schema_motor.json` com `tipo="saida_motor"`, `contract_version="1.1.0"` | `valid=True`, `compatibility_rule="exact_match"`. |
| `T-R9-002-04` | Instância `1.1.0` vs contrato `1.0.0` | `schema_motor.json` `1.1.0`, `contract_version="1.0.0"` | `valid=False` / `SchemaValidationError`, `compatibility_rule="rejected_forward_version"`. |
| `T-R9-002-05` | Instância com versão desconhecida | `schema_version="0.9.9"` | Rejeitada (`SchemaVersionError`), `compatibility_rule="rejected_unknown_version"`. |
| `T-R9-002-06` | Instância com versão futura | `schema_version="2.0.0"` | Rejeitada (`SchemaVersionError`), sem fallback silencioso. |
| `T-R9-002-07` | Perfil YAML com `profile_version != PROFILE_CONTRACT_VERSION` | Perfil com `profile_version="2.3.1"` validado por `PROFILE_CONTRACT_VERSION="1.0.0"` | `valid=True`, `contract_version_used="1.0.0"`, `compatibility_rule="explicit_loader_contract"`. |
| `T-R9-002-08` | Ausência de `schema_version` em documento que a exige | Parecer de agente sem campo `schema_version` | Rejeitado (`SchemaVersionError`), nunca seleciona versão mais recente implicitamente. |
| `T-R9-003-01` | Chave não autorizada | Assinatura Ed25519 válida de chave fora de `pinned_trust_root` | Rejeitada (`UntrustedSignerError`). |
| `T-R9-003-02` | Algoritmo divergente | `algorithm="Ed25519"` com chave/assinatura ECDSA-P256 | Rejeitada (`AlgorithmMismatchError`). |
| `T-R9-003-03` | Base64 inválido | `signature_b64` com caracteres inválidos ou padding incorreto | Rejeitada (`InvalidSignatureEncodingError`). |
| `T-R9-003-04` | Assinatura truncada | Ed25519 com 63 bytes | Rejeitada (`InvalidSignatureLengthError`). |
| `T-R9-003-05` | Digest incorreto | `signed_payload_sha256` diferente de `SHA256(JCS(payload))` | Rejeitada (`PayloadDigestMismatchError`). |
| `T-R9-003-06` | Token temporal de outra assinatura | RFC 3161 válido, porém carimbando `SHA256(outra_assinatura)` | Rejeitada (`TimestampBindingError`). |
| `T-R9-003-07` | Certificado TSA ou raiz expirado | `genTime` fora da janela `[not_before, not_after]` | Rejeitada (`CertificateExpiredError`). |
| `T-R9-003-08` | Chave revogada | Revogação histórica anterior ou igual a `genTime` | Rejeitada (`KeyRevokedError`). |
| `T-R9-003-09` | Política fora da janela de validade | `genTime > expires_at_utc` ou `genTime < valid_from_utc` | Rejeitada (`PolicyExpiredError`). |
| `T-R9-003-10` | Política adulterada após assinatura | 1 byte alterado em `allowed_remotes` | Falha de assinatura (`SignatureVerificationError`). |
| `T-R9-004-01` | Equivalência lexical | Entradas `"9.5"` e `"9.50"` | Ambas normalizam para `"9.500000"` e produzem o **mesmo** `score_semantic_sha256`. |
| `T-R9-004-02` | Proveniências distintas | Entradas `"9.5"` e `"9.50"` | `score_provenance_sha256` distintos, preservando `valor_original_informado` intacto. |
| `T-R9-004-03` | Precisão excedente | `"9.5000001"` (7 casas decimais) | Rejeitada (`ExcessiveDecimalPrecisionError`), sem arredondar nem truncar. |
| `T-R9-004-04` | Forma canônica exata | `"9.500000"` | Aceita, `nota_decimal == "9.500000"`. |
| `T-R9-004-05` | Alteração da nota normalizada | `"9.500000"` → `"9.500001"` | `score_semantic_sha256` muda obrigatoriamente. |
| `T-R9-004-06` | Alteração exclusiva da proveniência | Mesmo `score_payload`, `timestamp_utc` diferente na proveniência | `score_provenance_sha256` muda; `score_semantic_sha256` permanece idêntico. |
| `T-R9-005-01` | Python com instalador/artefato e hash verificados | `python_artifact_sha256` válido + 100% pacotes com hashes | `python_environment_reconstructible == True`. |
| `T-R9-005-02` | Python sem artefato de origem | `python_artifact_sha256 == None` | `python_environment_reconstructible == False` e `campaign_environment_reconstructible == False`. |
| `T-R9-005-03` | Versão correta com artefato divergente | `python_version` confere, mas `python_artifact_sha256` diverge | Rejeição de integridade (`EnvironmentArtifactMismatchError`). |
| `T-R9-005-04` | Build customizado incompleto | Build-from-source sem `compiler_version` ou `python_build_flags` | `python_environment_reconstructible == False` com limitação registrada. |
| `T-R9-005-05` | Pacotes 100% verificados, interpretador não verificável | Todos wheels verificados, mas interpretador sem origem | `python_environment_reconstructible == False`. |
| `T-R9-005-06` | Ambiente integralmente reconstruível | Python + pacotes + runtime nativo + configurações verificados | `python_environment_reconstructible == True`, `native_runtime_reconstructible == True`, `campaign_environment_reconstructible == True`. |
| `T-R9-006-01` | Symlink dentro da raiz apontando para fora | `campaign_root/ev.json -> ../externo.json` | Rejeitado na abertura (`O_NOFOLLOW` / `FILE_OPEN_REPARSE_POINT`). |
| `T-R9-006-02` | Junction NTFS apontando para fora | Diretório junction na cadeia de `campaign_root` | Rejeitado por detecção de reparse point no traversal de handles. |
| `T-R9-006-03` | Substituição de diretório durante o acesso | Subdiretório trocado concorrentemente por link | Traversal por `dir_fd` / `RootDirectory` bloqueia acesso fora da raiz. |
| `T-R9-006-04` | Reparse point na cadeia ancestral | `campaign_root/sub_link/ev.json` | Rejeitado antes de alcançar `ev.json`. |
| `T-R9-006-05` | Hard link com múltiplas referências | Arquivo com `nNumberOfLinks > 1` sob política de exclusividade | Rejeitado (`HardLinkPolicyError`). |
| `T-R9-006-06` | Alternate Data Stream (Windows) | `ev.json:oculto` | Rejeitado (`UnsafePathSyntaxError`). |
| `T-R9-006-07` | Caminho UNC ou `\\?\` | `\\servidor\share\ev.json` ou `\\?\C:\...` | Rejeitado (`UnsafePathSyntaxError`). |
| `T-R9-006-08` | Prefixo textual semelhante | Raiz `C:\campanha` vs alvo `C:\campanha_atacante\ev.json` | Rejeitado por identidade de volume/handle (nunca comparação textual de prefixo). |
| `T-R9-006-09` | Corrida entre validação e abertura | Arquivo trocado em disco após checagem prévia | Leitura e SHA-256 sobre o mesmo handle; conteúdo divergente levanta `IntegrityTamperError`. |
| `T-R9-006-10` | Arquivo regular válido dentro da raiz | `campaign_root/evidencias/motor_01.json` regular | Aberto, hasheado e decodificado a partir do mesmo buffer com sucesso. |
| `T-R9-007-01` | Denominador superior a `10**12` | Agregação válida de 15 eixos com denominadores coprimos resultando em $D > 10^{12}$ | Calculado exatamente sem rejeição arbitrária (`D.bit_length() <= 128`). |
| `T-R9-007-02` | 15 agentes avaliadores | Capacidade máxima de avaliadores (excluindo Adjudicador) | Agregação exata em `Fraction`, `0` erro de capacidade. |
| `T-R9-007-03` | 15 eixos simultâneos | Capacidade máxima de eixos com pesos variados | `S_global` exato em `Fraction`, `D <= 5.4054e21`. |
| `T-R9-007-04` | Pesos próximos ao máximo permitido | Pesos `999.999999` e `1000.000000` | Calculado exatamente sem overflow. |
| `T-R9-007-05` | Notas com 6 casas decimais | Notas `9.499999` vs `9.500000` | `9.499999 < Fraction(19, 2)` bloqueia; `9.500000 >= Fraction(19, 2)` aprova. |
| `T-R9-007-06` | Agregação com múltiplos agentes por eixo | 15 agentes no mesmo eixo sem conflito ($\max - \min \le 1$) | Média racional exata em `Fraction`. |
| `T-R9-007-07` | Conflito intra-eixo | Agentes no mesmo eixo com $\max - \min > 1$ (ex.: `9.800000` e `8.400000`) | Regra conservadora $S_e = \min = \text{Fraction}(84, 10) < 8{,}5$ bloqueia e registra divergência. |
| `T-R9-007-08` | Frações próximas ao limite de 128 bits | Numerador/denominador com 128 bits exatos | Aceito em `round_fraction_half_even()`. |
| `T-R9-007-09` | Entrada acima da capacidade | 16 avaliadores ou `bit_length() > 128` | Levanta `RationalCapacityExceededError` (erro de capacidade, não dado inválido). |
| `T-R9-007-10` | Repetibilidade sob permutações | Permutações exaustivas ($n \le 6$) e 200 permutações determinísticas ($n = 15$) | Representação canônica `"num/den"` e decisão booleana idênticas em 100% das permutações. |

---

## 2. Cenários da Revisão 11 (`15` cenários — `T-R11-061` a `T-R11-075`)

| ID | Achado de Origem | Cenário / Entrada | Pré-condição | Resultado / Erro Esperado |
| :--- | :--- | :--- | :--- | :--- |
| `T-R11-061` | `ACH-B7-R10-001` / `ACH-B7-R11-002` | Replay de `signed_store_receipt_v1` antigo validamente assinado | Store + Testemunhas A e B ativas | Rejeição por `freshness_proof` / `AnchorVerificationError` |
| `T-R11-062` | `ACH-B7-R10-001` / `ACH-B7-R11-002` | Restauração de snapshot do store remoto para revisão anterior | Testemunhas A e B com revisão maior | Bloqueio imediato (`AnchorVerificationError`) |
| `T-R11-063` | `ACH-B7-R10-001` / `ACH-B7-R11-002` | Indisponibilidade de testemunha externa na verificação | Ancoragem externa exigida vs opcional | Negação de `ancoragem_externa_independente`; `AnchorVerificationError` ou degradação explícita |
| `T-R11-064` | `ACH-B7-R10-002` / `ACH-B7-R11-006` | Adulteração de 1 byte em `compatibility_policy_v1.json` | Política assinada na trust policy | Divergência de `compatibility_policy_jcs_sha256` → `ExecutionBlockedError` |
| `T-R11-065` | `ACH-B7-R10-002` / `ACH-B7-R11-006` | Tripla `(schema_name, instance_schema_version, contract_version)` ausente da política | `default_decision: deny` | Rejeição imediata (`ExecutionBlockedError`) |
| `T-R11-066` | `ACH-B7-R10-002` / `ACH-B7-R11-006` | Arquivo `$ref` ausente ou com SHA-256 divergente de `ref_hashes` | Política congelada | Bloqueio imediato (`ExecutionBlockedError`) |
| `T-R11-067` | `ACH-B7-R10-003` / `ACH-B7-R11-005` | Agregação exata com $\tilde{W}_{total}$ não divisor de $15 \times 1000 \times 10^6$ | $m=15, n_i \le 15, w_i \in (0,1000]$ | $D \mid L \cdot 10^6 \cdot \tilde{W}_{total}$ e $D \le D_{bound} = 5.4054 \times 10^{21}$ |
| `T-R11-068` | `ACH-B7-R10-004` | Autoautorização: política `P_k` assinada por chave presente apenas na própria `P_k.authorized_signers` | `P_{k-1}` aceita | Rejeição imediata (`PolicyAuthorityError`) |
| `T-R11-069` | `ACH-B7-R10-004` | Chave delegada válida em `P_{k-1}` usada fora da janela `[not_before, not_after]` no `genTime` TSA ou sem escopo `policy_sign` | Carimbo TSA verificado | Rejeição imediata (`PolicyAuthorityError`) |
| `T-R11-070` | `ACH-B7-R10-005` | `policy_seq` ou `checkpoint_revision` com dígitos Unicode mistos (`1٣`, `٢`) | Regex ASCII estrito | Rejeição na validação (`SchemaValidationError`) |
| `T-R11-071` | `ACH-B7-R10-005` | `policy_seq` ou `checkpoint_revision` com >32 dígitos ASCII | Limite máximo 32 dígitos | Rejeição imediata (`SchemaValidationError`) |
| `T-R11-072` | `ACH-B7-R10-005` | `policy_seq` ou `checkpoint_revision` com zeros à esquerda (`01`, `00`) | Regex canônica | Rejeição imediata (`SchemaValidationError`) |
| `T-R11-073` | `ACH-B7-R10-006` | Alteração exclusiva de proveniência (`8.5` → `8.50`) mantendo conteúdo e valor | Parecer selado | `score_semantic_sha256` igual; `score_provenance_sha256` e `parecer_sha256` mudam |
| `T-R11-074` | `ACH-B7-R10-007` / `ACH-B7-R11-003` | (Windows) Reparse point em componente intermediário ou final | `NtCreateFile` segmento único | Detecção de `FILE_ATTRIBUTE_REPARSE_POINT` → `PathConfinementError` |
| `T-R11-075` | `ACH-B7-R10-007` / `ACH-B7-R11-003` | (Linux) Cruzamento de mount-point ou bind-mount dentro de `root_dir` | `openat2` + `RESOLVE_NO_XDEV` | Bloqueio fail-closed (`PathConfinementError`) |

---

## 3. Novos Cenários da Revisão 12 (`44` cenários — `T-R12-076` a `T-R12-119`)

| ID | Achado / Requisito | Cenário | Entrada / Pré-condição | Resultado Esperado (Critério de Aprovação) | Erro Esperado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `T-R12-076` | `ACH-B7-R11-001` | Presença integral dos oito schemas históricos da Beta 6.6 | Diretório `schemas/legacy-v8.0-beta.6.6/` | 8 arquivos idênticos byte a byte e SHA-256 conferido | Nenhum |
| `T-R12-077` | `ACH-B7-R11-001` | Rejeição de versão de instância inventada a partir do número da release (`6.6.0`) | Instância com `schema_version="6.6.0"` | Rejeição por `default_decision: deny` | `ExecutionBlockedError` |
| `T-R12-078` | `ACH-B7-R11-001` | Herança de versão dos schemas aninhados (`schema_achado`, `schema_evidencia`) | Instância raiz `7.0.0` contendo achado/evidência sem `schema_version` própria | Validado herdando versão do raiz; rejeitado se inventar `schema_version` | `SchemaValidationError` se campo extra |
| `T-R12-079` | `ACH-B7-R11-001` | Separação entre `profile_version` e versão do contrato (`PROFILE_CONTRACT_VERSION`) | Perfil com `profile_version="2.1.0"` sob contrato `7.0.0` | Carregado usando `PROFILE_CONTRACT_VERSION="7.0.0"` sem confundir versões | Nenhum |
| `T-R12-080` | `ACH-B7-R11-001` | Ausência de migração implícita entre tipos semanticamente diferentes | Tentativa de validar `evidence_qualification` como `schema_evidencia` ou `adjudication_record` como `schema_ledger_adjudicacao` | Rejeição imediata por contrato fechado | `SchemaValidationError` |
| `T-R12-081` | `ACH-B7-R11-001` | Hash do schema-raiz obrigatório na política | Entrada de política sem `schema_sha256` | Rejeição contra `compatibility_policy.schema.json` | `SchemaValidationError` |
| `T-R12-082` | `ACH-B7-R11-001` | Cobertura integral de todos os `$ref` transitivos | Schema com `$ref` de 2º nível sem hash em `ref_hashes` | Bloqueio na carga da política | `ExecutionBlockedError` |
| `T-R12-083` | `ACH-B7-R11-002` | Replay de nonce de testemunha | Reutilização de `challenge_nonce_b64` já consumido | Rejeição imediata pelo verificador e testemunha | `AnchorVerificationError` |
| `T-R12-084` | `ACH-B7-R11-002` | Replay de recibo antigo validamente assinado | Recibo `rev=9` apresentado quando testemunhas registram `rev=10` | Rejeição por divergência de revisão | `AnchorVerificationError` |
| `T-R12-085` | `ACH-B7-R11-002` | Testemunha com revisão inferior ao maior estado conhecido | Testemunha A retorna `rev=9` após estado aceito `rev=10` | Bloqueio de regressão monotônica | `AnchorVerificationError` |
| `T-R12-086` | `ACH-B7-R11-002` | Duas testemunhas com hashes divergentes para a mesma revisão | Testemunha A e B retornam `checkpoint_sha256` distintos | Detecção de equivocação | `CheckpointEquivocationError` |
| `T-R12-087` | `ACH-B7-R11-002` | Indisponibilidade da testemunha A | A timeout > 30s monotônicos; B responde | Quórum `1-of-2` negado | `AnchorVerificationError` |
| `T-R12-088` | `ACH-B7-R11-002` | Indisponibilidade da testemunha B | B timeout > 30s monotônicos; A responde | Quórum `1-of-2` negado | `AnchorVerificationError` |
| `T-R12-089` | `ACH-B7-R11-002` | Degradação indevida para ancoragem independente | Falha em testemunha tentando manter `ancoragem_externa_independente` | Classificação bloqueada; exige degradação explícita ou erro | `AnchorVerificationError` |
| `T-R12-090` | `ACH-B7-R11-003` | Hard link POSIX com `st_nlink > 1` | Arquivo Linux com 2 links | Rejeitado pela política de exclusividade | `HardLinkPolicyError` |
| `T-R12-091` | `ACH-B7-R11-003` | Hard link Windows com `NumberOfLinks > 1` | Arquivo NTFS com 2 links | Rejeitado pela política de exclusividade | `HardLinkPolicyError` |
| `T-R12-092` | `ACH-B7-R11-003` | Alternate Data Stream (Windows) | Segmento `ev.json:stream` | Rejeitado na validação de sintaxe de segmento | `UnsafePathSyntaxError` |
| `T-R12-093` | `ACH-B7-R11-003` | Caminho UNC e prefixos de dispositivo | `\\srv\share\f`, `\\?\C:\f`, `\\.\CON` | Rejeitado antes de qualquer syscall | `UnsafePathSyntaxError` |
| `T-R12-094` | `ACH-B7-R11-003` | Diretório raiz contendo reparse point | `root_dir` ou ancestral da raiz é junction/symlink | Rejeitado na validação da raiz | `PathConfinementError` |
| `T-R12-095` | `ACH-B7-R11-003` | Bind mount Linux dentro da raiz | Bind mount no mesmo `st_dev` com `stx_mnt_id` distinto | Bloqueado por `openat2(RESOLVE_NO_XDEV)` + `statx` | `PathConfinementError` |
| `T-R12-096` | `ACH-B7-R11-003` | Linux sem suporte `openat2` seguro (ou macOS/BSD) | Plataforma sem `openat2` + `RESOLVE_NO_XDEV` | Falha fechada sem fallback `Path.resolve()` | `UnsafePlatformPathError` |
| `T-R12-097` | `ACH-B7-R11-003` | Arquivo final não regular (FIFO, socket, diretório, device) | Destino final com `not S_ISREG` | Rejeitado imediatamente após abertura | `PathConfinementError` |
| `T-R12-098` | `ACH-B7-R11-003` | Reparse point em ancestral Windows | Componente intermediário é junction NTFS | Detectado via `FileBasicInfo` antes de avançar | `PathConfinementError` |
| `T-R12-099` | `ACH-B7-R11-003` | Alteração concorrente do arquivo durante a leitura (TOCTOU) | Arquivo substituído em disco após abertura do handle | Leitura, hash e decode executados sobre buffer único imutável do handle original | Nenhum (isolado de TOCTOU) |
| `T-R12-100` | `ACH-B7-R11-004` | Peso `999.999999` aceito | Peso decimal `"999.999999"` no domínio `(0, 1000]` | Aceito e convertido exatamente para `Fraction` | Nenhum |
| `T-R12-101` | `ACH-B7-R11-004` | Peso `1000.000000` aceito | Peso decimal `"1000.000000"` no domínio `(0, 1000]` | Aceito e convertido exatamente para `Fraction(1000, 1)` | Nenhum |
| `T-R12-102` | `ACH-B7-R11-004` | Peso acima de 1000 rejeitado | Peso decimal `"1000.000001"` | Rejeitado pelo schema e validador numérico | `SchemaValidationError` |
| `T-R12-103` | `ACH-B7-R11-005` | Verificação de `D_bound` com pesos máximos | 15 eixos com pesos até `1000.000000` e 15 avaliadores | $D \le 5.4054 \times 10^{21}$ e `D.bit_length() <= 73 <= 128` | Nenhum |
| `T-R12-104` | `ACH-B7-R11-005` | Verificação de `N_bound` com notas máximas | 15 eixos com notas `10.000000` e pesos máximos | $N \le 5.4054 \times 10^{22}$ e `N.bit_length() <= 76 <= 128` | Nenhum |
| `T-R12-105` | `ACH-B7-R11-006` | Política template rejeitada na carga operacional | `policy_status == "normative_specification_template"` | `load_compatibility_policy()` rejeita imediatamente | `ExecutionBlockedError` |
| `T-R12-106` | `ACH-B7-R11-006` | Política executável com placeholder rejeitada | `policy_status == "frozen_executable"` com `PENDING_*` | Rejeitada por regex `^[0-9a-f]{64}$` | `SchemaValidationError` |
| `T-R12-107` | `ACH-B7-R11-006` | Schema-raiz sem hash rejeitado | Entrada sem `schema_sha256` ou hash divergente do disco | Bloqueio imediato | `ExecutionBlockedError` |
| `T-R12-108` | `ACH-B7-R11-006` | Referência transitiva sem hash rejeitada | Schema com `$ref` indireto ausente de `ref_hashes` | Bloqueio imediato | `ExecutionBlockedError` |
| `T-R12-109` | `ACH-B7-R11-006` | JSON com chave duplicada ou `$ref` remoto rejeitado | Payload JSON com chave repetida ou `$ref: https://...` | Rejeitado pelo parser estrito / validador de `$ref` | `ExecutionBlockedError` |
| `T-R12-110` | `ACH-B7-R11-007` | SemVer com zero à esquerda em MAJOR rejeitado (`01.0.0`) | `contract_version="01.0.0"` | Rejeitado em Python e JSON Schema | `SchemaValidationError` |
| `T-R12-111` | `ACH-B7-R11-007` | SemVer com zero à esquerda em MINOR rejeitado (`1.00.0`) | `contract_version="1.00.0"` | Rejeitado em Python e JSON Schema | `SchemaValidationError` |
| `T-R12-112` | `ACH-B7-R11-007` | SemVer com pré-lançamento ou build rejeitado em contrato estável | `1.0.0-alpha`, `1.0.0+build` | Rejeitado em Python e JSON Schema | `SchemaValidationError` |
| `T-R12-113` | `ACH-B7-R11-007` | Versão de comprimento excessivo rejeitada | Componente com >10 dígitos ASCII | Rejeitado pelo limite de comprimento | `SchemaValidationError` |
| `T-R12-114` | `ACH-B7-R11-007` | Comparação numérica `1.10.0 > 1.9.0` | `compare_semver_stable("1.10.0", "1.9.0")` | Retorna `1` (nunca ordem lexicográfica) | Nenhum |
| `T-R12-115` | `ACH-B7-R11-008` | Preservação dos 60 identificadores históricos da Rev 10 | Auditoria da matriz Rev 12 vs Rev 10 | Todos os 60 IDs `T-R9-*` presentes sem renumeração | Nenhum |
| `T-R12-116` | `ACH-B7-R11-008` | Ausência de cenários duplicados ou sem origem | Auditoria dos 119 IDs da matriz Rev 12 | 119 IDs únicos, todos ligados a requisito e achado | Nenhum |
| `T-R12-117` | `ACH-B7-R11-009` | Existência de achado P1 aberto bloqueia OS | Portão de liberação com P1 > 0 | `OS_STATUS = BLOCKED` | `ExecutionBlockedError` |
| `T-R12-118` | `ACH-B7-R11-009` | Existência de achado P2 aberto bloqueia OS | Portão de liberação com P2 > 0 | `OS_STATUS = BLOCKED` | `ExecutionBlockedError` |
| `T-R12-119` | `ACH-B7-R11-010` | Inconsistência de encoding SPKI DER e `key_id` rejeitada | Chave `public_key_spki_der_b64` com `key_id != SHA256(SPKI_DER)` ou mismatch Ed25519/ECDSA | Rejeição imediata na validação criptográfica | `KeyEncodingError` |

---

**Total consolidado:** `119` cenários especificados (`0/119 executados`).
