# Matriz de Testes de Aceitação — Fase 7 (`v8.0-beta.7`, Revisão 10)

> **Base de referência congelada:** `v8.0-beta.6.6` (`commit 11e91b6f3d517707326357868cc34ff97ab8327d`)  
> **Aviso normativo:** especificação de testes de aceitação (60 cenários obrigatórios); **nenhum teste da Fase 7 foi implementado ou executado ainda**.

---

## 1. `ACH-B7-R9-001` — Checkpoint Anti-Rollback e Concorrência (10 cenários)

| ID | Cenário | Entrada / Condição | Comportamento Esperado Inequívoco |
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

---

## 2. `ACH-B7-R9-002` — Separação Instância vs Contrato (8 cenários)

| ID | Cenário | Entrada / Condição | Comportamento Esperado Inequívoco |
| :--- | :--- | :--- | :--- |
| `T-R9-002-01` | Instância `1.0.0` vs contrato `1.0.0` | `schema_motor.json`, instância `1.0.0`, `contract_version="1.0.0"` | `valid=True`, `compatibility_rule="exact_match"`. |
| `T-R9-002-02` | Instância `1.0.0` vs contrato `1.1.0` | `schema_motor.json`, instância `1.0.0`, `contract_version="1.1.0"` | `valid=True`, `compatibility_rule="backward_validation"`, `contract_version_used="1.1.0"`. |
| `T-R9-002-03` | Instância `1.1.0` vs contrato `1.1.0` | `schema_motor.json` com `tipo="saida_motor"`, `contract_version="1.1.0"` | `valid=True`, `compatibility_rule="exact_match"`. |
| `T-R9-002-04` | Instância `1.1.0` vs contrato `1.0.0` | `schema_motor.json` `1.1.0`, `contract_version="1.0.0"` | `valid=False` / `SchemaValidationError`, `compatibility_rule="rejected_forward_version"`. |
| `T-R9-002-05` | Instância com versão desconhecida | `schema_version="0.9.9"` | Rejeitada (`SchemaVersionError`), `compatibility_rule="rejected_unknown_version"`. |
| `T-R9-002-06` | Instância com versão futura | `schema_version="2.0.0"` | Rejeitada (`SchemaVersionError`), sem fallback silencioso. |
| `T-R9-002-07` | Perfil YAML com `profile_version != PROFILE_CONTRACT_VERSION` | Perfil com `profile_version="2.3.1"` validado por `PROFILE_CONTRACT_VERSION="1.0.0"` | `valid=True`, `contract_version_used="1.0.0"`, `compatibility_rule="explicit_loader_contract"`. |
| `T-R9-002-08` | Ausência de `schema_version` em documento que a exige | Parecer de agente sem campo `schema_version` | Rejeitado (`SchemaVersionError`), nunca seleciona versão mais recente implicitamente. |

---

## 3. `ACH-B7-R9-003` — Assinatura Criptográfica e Prova Temporal da Política (10 cenários)

| ID | Cenário | Entrada / Condição | Comportamento Esperado Inequívoco |
| :--- | :--- | :--- | :--- |
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

---

## 4. `ACH-B7-R9-004` — Identidade Semântica vs Proveniência da Nota (6 cenários)

| ID | Cenário | Entrada / Condição | Comportamento Esperado Inequívoco |
| :--- | :--- | :--- | :--- |
| `T-R9-004-01` | Equivalência lexical | Entradas `"9.5"` e `"9.50"` | Ambas normalizam para `"9.500000"` e produzem o **mesmo** `score_semantic_sha256`. |
| `T-R9-004-02` | Proveniências distintas | Entradas `"9.5"` e `"9.50"` | `score_provenance_sha256` distintos, preservando `valor_original_informado` intacto. |
| `T-R9-004-03` | Precisão excedente | `"9.5000001"` (7 casas decimais) | Rejeitada (`ExcessiveDecimalPrecisionError`), sem arredondar nem truncar. |
| `T-R9-004-04` | Forma canônica exata | `"9.500000"` | Aceita, `nota_decimal == "9.500000"`. |
| `T-R9-004-05` | Alteração da nota normalizada | `"9.500000"` → `"9.500001"` | `score_semantic_sha256` muda obrigatoriamente. |
| `T-R9-004-06` | Alteração exclusiva da proveniência | Mesmo `score_payload`, `timestamp_utc` diferente na proveniência | `score_provenance_sha256` muda; `score_semantic_sha256` permanece idêntico. |

---

## 5. `ACH-B7-R9-005` — Reconstrução do Interpretador Python (6 cenários)

| ID | Cenário | Entrada / Condição | Comportamento Esperado Inequívoco |
| :--- | :--- | :--- | :--- |
| `T-R9-005-01` | Python com instalador/artefato e hash verificados | `python_artifact_sha256` válido + 100% pacotes com hashes | `python_environment_reconstructible == True`. |
| `T-R9-005-02` | Python sem artefato de origem | `python_artifact_sha256 == None` | `python_environment_reconstructible == False` e `campaign_environment_reconstructible == False`. |
| `T-R9-005-03` | Versão correta com artefato divergente | `python_version` confere, mas `python_artifact_sha256` diverge | Rejeição de integridade (`EnvironmentArtifactMismatchError`). |
| `T-R9-005-04` | Build customizado incompleto | Build-from-source sem `compiler_version` ou `python_build_flags` | `python_environment_reconstructible == False` com limitação registrada. |
| `T-R9-005-05` | Pacotes 100% verificados, interpretador não verificável | Todos wheels verificados, mas interpretador sem origem | `python_environment_reconstructible == False`. |
| `T-R9-005-06` | Ambiente integralmente reconstruível | Python + pacotes + runtime nativo + configurações verificados | `python_environment_reconstructible == True`, `native_runtime_reconstructible == True`, `campaign_environment_reconstructible == True`. |

---

## 6. `ACH-B7-R9-006` — Confinamento Windows e POSIX por Handles/Descritores (10 cenários)

| ID | Cenário | Entrada / Condição | Comportamento Esperado Inequívoco |
| :--- | :--- | :--- | :--- |
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

---

## 7. `ACH-B7-R9-007` — Limites Racionais Matematicamente Derivados (10 cenários)

| ID | Cenário | Entrada / Condição | Comportamento Esperado Inequívoco |
| :--- | :--- | :--- | :--- |
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
