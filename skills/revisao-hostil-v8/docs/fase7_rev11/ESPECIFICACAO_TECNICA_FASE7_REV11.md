# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 11

**Status:** Documentação normativa (implementação Python **NÃO iniciada**; Ordem de Serviço **aguardando aprovação externa**)  
**Base imutável de referência:** `v8.0-beta.6.6` (commit `11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Branch documental:** `specification/v8.0-beta.7-rev11`  
**Escopo da Revisão 11:** Fechamento integral dos 7 achados da auditoria externa da Revisão 10 (`ACH-B7-R10-001` a `ACH-B7-R10-007`), preservando integralmente a base `v8.0-beta.6.6` e todas as garantias consolidadas nas Revisões 1–10.

---

## 0. Escopo e Declaração de Não-Implementação

1. Este pacote documental especifica os requisitos normativos da Fase 7 (`v8.0-beta.7`).
2. **Nenhum código Python da Fase 7 foi implementado ou executado**; nenhum arquivo da base `v8.0-beta.6.6`, `requirements.txt`, `catalogo_agentes.yaml`, `main` ou tags históricas foi modificado.
3. Os cenários listados em `MATRIZ_TESTES_ACEITACAO_REV11.md` são **especificações de testes de aceitação** a serem implementados e executados somente após a emissão formal da Ordem de Serviço.

---

## 1. Arquitetura da Banca Adversarial (Três Pilares)

1. **Independência dos Pareceres (`parecer_independente`):** cada agente elegível avalia o artefato e suas evidências em contexto isolado de outros pareceres, com registro externo de isolamento e hash de entrada.
2. **Contestação Adversarial (`contestacao_adversarial`):** agentes contestadores recebem pareceres selados e evidências qualificadas, produzindo refutações rastreáveis.
3. **Adjudicação Rastreável (`adjudicacao`):** separa estritamente:
   - **Adjudicação Mecânica:** verificação determinística de hashes, schemas, assinaturas, âncoras, elegibilidade e aritmética exata (`Fraction`).
   - **Adjudicação Interpretativa:** resolução de conflitos de mérito baseada em evidências qualificadas (evidência qualificada não é automaticamente prevalente sem verificação de validade, aplicabilidade, integridade de origem e interpretação).

---

## 2. Política de Confiança, Anti-Rollback e Ancoragem (`ACH-B7-R10-001`, `ACH-B7-R10-004`, `ACH-B7-R10-005`)

Os contratos criptográficos completos constam em `CONTRATOS_CRIPTOGRAFICOS_REV11.md`. Em síntese normativa:

1. **Raiz de Confiança Fixada (`pinned_trust_root`):** chave pública raiz imutável embutida/configurada fora do escopo mutável da campanha.
2. **Modelo Inequívoco de Autoridade, Delegação e Rotação (`ACH-B7-R10-004`):**
   - Uma política candidata `P_k` (`policy_seq = k`) só é aceita se assinada pela **raiz de confiança fixada** OU por uma chave delegada **já autorizada na política aceita imediatamente anterior `P_{k-1}.authorized_signers`** com escopo `policy_sign` e janela `[not_before_utc, not_after_utc]` válida no `genTime` do carimbo TSA verificado.
   - **Autoautorização proibida:** o verificador **NUNCA** consulta `P_k.authorized_signers` para validar a assinatura da própria `P_k`.
   - `signature.key_id` deve corresponder exatamente ao identificador da chave autorizada.
3. **Anti-Rollback Verificável no `MonotonicCheckpointStore` (`ACH-B7-R10-001`):**
   - Cada atualização de checkpoint exige um `signed_store_receipt` de schema fechado assinado pela chave do store fixada na política confiável **MAIS** uma **prova verificável de atualidade/freshness** (co-assinatura de testemunha externa independente, prova de inclusão + consistência em log de transparência append-only, ou cotação atestada de contador monotônico em hardware TPM/HSM/TEE).
   - Se a prova de atualidade falhar, for ausente ou a testemunha estiver indisponível, a campanha **NÃO** pode receber classificação `ancoragem_externa_independente` (degrada para `integridade_local_com_ancora_co_localizada`, ou falha fechada se ancoragem externa for obrigatória).
4. **Identificadores Monotônicos Estritamente ASCII (`ACH-B7-R10-005`):**
   - `policy_seq` e `checkpoint_revision` são strings de inteiros não negativos em dígitos ASCII puros (`0`–`9`), com comprimento máximo de 32 dígitos:
     - Regex Python (com `fullmatch`): `\A(0|[1-9][0-9]{0,31})\Z` (proibido `\d`, que aceita dígitos Unicode como `1٣`).
     - Regex JSON Schema: `^(0|[1-9][0-9]{0,31})(?![\r\n])$`.
   - Rejeita dígitos Unicode, zeros à esquerda (`01`), sinais, espaços/quebras de linha e entradas com mais de 32 dígitos.

---

## 3. Política Estruturada e Executável de Compatibilidade de Schemas (`ACH-B7-R10-002`)

1. A compatibilidade entre versões de instâncias e contratos de schema não é mais apenas tabular em Markdown: é governada pelo artefato estruturado, autenticado e executável `compatibility_policy_v1.json` (detalhado em `MATRIZ_COMPATIBILIDADE_CONTRATOS_REV11.md`).
2. **Default-Deny:** qualquer tripla `(schema_name, instance_schema_version, contract_version)` não enumerada explicitamente em `allowed_triples` é rejeitada com `ExecutionBlockedError`.
3. **Autenticação:** o hash `compatibility_policy_jcs_sha256` (calculado sobre o JCS de `compatibility_policy_v1.json` excluindo o próprio campo de hash) é fixado na `trusted_anchors_policy` assinada e registrado no `campaign_manifest.json`.
4. **Semântica Formal de `backward_validation`:**
   - `backward_validation: false`: exige igualdade exata `instance_schema_version == contract_version` e validação contra o contrato e cadeia `$ref` fixados em `ref_hashes`.
   - `backward_validation: true`: permite `instance_schema_version < contract_version` exclusivamente para a tripla declarada, exigindo validação integral contra o schema `contract_version` (com todos os `$ref` verificados por SHA-256), `additionalProperties: false` e ausência total de coerção implícita.

---

## 4. Aritmética Exata e Prova de Limite Superior `D_bound` (`ACH-B7-R10-003`)

Notas e pesos são serializados como strings decimais com no máximo 6 casas decimais e convertidos exatamente para `fractions.Fraction`.

### 4.1. Domínio de Entrada
- Número de eixos obrigatórios: $1 \le m \le 15$.
- Número de avaliadores por eixo $i$: $1 \le n_i \le 15$.
- Nota individual de cada avaliador: string decimal em $[0, 10]$ com até 6 casas decimais, logo representável como $b_{i,j} / 10^6$ com $b_{i,j} \in \mathbb{Z}$, $0 \le b_{i,j} \le 10^7$.
- Média do eixo $i$: $s_i = \frac{a_i}{10^6 \cdot n_i}$, onde $a_i = \sum_{j=1}^{n_i} b_{i,j} \in \mathbb{Z}_{\ge 0}$ e $0 \le s_i \le 10$.
- Peso do eixo $i$: string decimal em $(0, 1]$ com até 6 casas decimais, logo $w_i = \tilde{w}_i / 10^6$ com $\tilde{w}_i \in \mathbb{Z}$, $1 \le \tilde{w}_i \le 10^6$.
- Soma dos pesos escalada: $\tilde{W}_{\text{total}} = \sum_{i=1}^{m} \tilde{w}_i \in \mathbb{Z}$, com $1 \le \tilde{W}_{\text{total}} \le 15 \times 10^6$.

### 4.2. Prova por Desigualdade (Correção de `ACH-B7-R10-003`)
Seja $L = \operatorname{lcm}(1, 2, \dots, 15) = 360{,}360$. Como $1 \le n_i \le 15$, temos $n_i \mid L$ para todo eixo $i$, de modo que $L / n_i \in \mathbb{Z}_{>0}$. A nota global ponderada é:

$$S = \frac{\sum_{i=1}^{m} w_i s_i}{\sum_{i=1}^{m} w_i} = \frac{\sum_{i=1}^{m} \frac{\tilde{w}_i}{10^6} \cdot \frac{a_i}{10^6 \cdot n_i}}{\frac{\tilde{W}_{\text{total}}}{10^6}} = \frac{\sum_{i=1}^{m} \tilde{w}_i \cdot a_i \cdot (L / n_i)}{L \cdot 10^6 \cdot \tilde{W}_{\text{total}}}$$

Reduzindo $S = N / D$ à forma irredutível ($\gcd(N, D) = 1$, $D > 0$):
1. **Divisibilidade exata (para o $\tilde{W}_{\text{total}}$ da campanha):** $D \mid (L \cdot 10^6 \cdot \tilde{W}_{\text{total}})$. (Observação normativa: **NÃO** se afirma que $D \mid D_{\text{bound}}$, pois $\tilde{W}_{\text{total}}$ varia por campanha e não necessariamente divide $15 \times 10^6$.)
2. **Desigualdade exata (limite superior `D_bound` / `D_limite`):**
   $$D \le L \cdot 10^6 \cdot \tilde{W}_{\text{total}} \le 360{,}360 \times 10^6 \times (15 \times 10^6) = 5{,}405{,}400{,}000{,}000{,}000{,}000{,}000 = 5.4054 \times 10^{21} = D_{\text{bound}}$$
3. **Limites em bits:**
   - $D \le D_{\text{bound}} < 2^{73}$ (máximo de **73 bits**).
   - Como $0 \le S \le 10$, temos $N \le 10 \cdot D \le 10 \cdot D_{\text{bound}} = 5.4054 \times 10^{22} < 2^{76}$ (máximo de **76 bits**).
   - **Teto operacional:** ambos $N$ e $D$ permanecem estritamente abaixo do teto operacional de **128 bits** ($2^{128} - 1$).

---

## 5. Digest Composto do Parecer Completo (`parecer_sha256`) (`ACH-B7-R10-006`)

Para garantir que a separação entre equivalência semântica de pontuação e proveniência lexical não permita adulteração silenciosa de proveniência no parecer selado:

1. `score_semantic_sha256`: SHA-256 do JCS das frações reduzidas `(numerator, denominator)` de notas e pesos. Invariante a representações lexicais equivalentes (ex.: `"8.50"` vs `"8.5"`).
2. `score_provenance_sha256`: SHA-256 do JCS das strings decimais originais exatamente como emitidas pelo agente, acrescidas de metadados de emissão (`agent_id`, `emitted_at_utc`, `input_manifest_sha256`).
3. `parecer_core_jcs_sha256`: SHA-256 do JCS do corpo normativo do parecer (achados, evidências, veredito, justificativas), excluindo `parecer_sha256`.
4. **Fórmula obrigatória de `parecer_sha256`:**
   ```text
   parecer_sha256 = SHA256(
     JCS({
       "schema_version": parecer.schema_version,
       "parecer_core_jcs_sha256": parecer_core_jcs_sha256,
       "score_semantic_sha256": score_semantic_sha256,
       "score_provenance_sha256": score_provenance_sha256
     })
   )
   ```
5. **Propriedade garantida:** alterar apenas a proveniência (ex.: `"8.5"` → `"8.50"` ou metadado de emissão) mantém `score_semantic_sha256` idêntico, mas **altera obrigatoriamente** `score_provenance_sha256` e `parecer_sha256`.

---

## 6. Confinamento de Caminhos por Plataforma (`ACH-B7-R10-007`)

Toda leitura de artefato, evidência ou arquivo de campanha dentro do diretório raiz confiável (`root_dir`) deve ser confinada contra travessia (`..`), symlinks, junctions, mount points e TOCTOU, com leitura por buffer único em memória após validação do descritor/handle aberto.

### 6.1. Regras Normativas para Windows
1. O diretório raiz `root_dir` é aberto primeiro e validado como não sendo um reparse point (`FILE_ATTRIBUTE_REPARSE_POINT == 0`).
2. A travessia é executada **componente por componente**: cada chamada a `NtCreateFile` recebe **exclusivamente um único segmento relativo** (`ObjectName` sem `\` nem `/`, proibido `.` e `..`) ancorado no `HANDLE` já validado do diretório pai (`RootDirectory`), com a flag `FILE_OPEN_REPARSE_POINT`.
3. **Regra explícita:** `FILE_OPEN_REPARSE_POINT` atua apenas sobre o componente final daquela chamada de segmento único e **não** fornece proteção contra ancestrais; por isso, **imediatamente após cada chamada `NtCreateFile`**, o verificador inspeciona os atributos do handle retornado (`GetFileInformationByHandleEx` / `FileBasicInfo`) e **rejeita fail-closed** (`PathConfinementError`) qualquer objeto com `FILE_ATTRIBUTE_REPARSE_POINT` (symlink, junction, volume mount point) **antes** de avançar para o próximo segmento.
4. O conteúdo do arquivo final é lido diretamente do `HANDLE` já validado (buffer único), nunca reabrindo por caminho textual.

### 6.2. Regras Normativas para POSIX (Linux / macOS)
1. O diretório raiz `root_dir` é aberto com `O_RDONLY | O_DIRECTORY | O_CLOEXEC` e seu `(st_dev, st_ino)` (e `stx_mnt_id` via `statx`, quando suportado pelo kernel) é registrado como fronteira de montagem raiz.
2. A travessia é executada **componente por componente** via `openat(parent_fd, segment, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)` (ou `openat2` com `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_XDEV` em Linux 5.6+).
3. **Política explícita de cruzamento de mount-point / bind-mount:** em cada componente aberto, o verificador executa `fstat(fd)` (e `statx` quando disponível) e compara `st_dev` (e `stx_mnt_id` se disponível) com o do `root_dir`. Qualquer divergência de dispositivo ou mount ID (incluindo bind-mounts dentro do mesmo filesystem quando `stx_mnt_id` ou `RESOLVE_NO_XDEV` detectar a fronteira) é **rejeitada fail-closed** (`PathConfinementError`).
4. O arquivo final é lido diretamente do `fd` validado em buffer único.

---

## 7. Portão de Congelamento e Inventário de Schemas

- Mantém integralmente o inventário de **8 schemas existentes evoluídos + 3 novos schemas** da Fase 7, todos governados por `compatibility_policy_v1.json`.
- Nenhuma implementação Python será iniciada antes da aprovação formal desta Revisão 11 e emissão da Ordem de Serviço pela banca externa.
