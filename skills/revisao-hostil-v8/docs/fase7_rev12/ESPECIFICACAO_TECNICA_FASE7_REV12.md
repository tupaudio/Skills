# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 12

**Status:** Documentação normativa autossuficiente (**implementação Python NÃO iniciada**; Ordem de Serviço **BLOQUEADA até aprovação externa**)  
**Base obrigatória imutável:** tag `v8.0-beta.6.6`, commit `11e91b6f3d517707326357868cc34ff97ab8327d`  
**Branch documental:** `specification/v8.0-beta.7-rev12`  
**Escopo:** Correção integral dos achados `ACH-B7-R11-001` a `ACH-B7-R11-010`, restaurando integralmente todas as garantias da Revisão 10 e fechando regressões e inconsistências da Revisão 11.

---

## 0. Declaração de Escopo e Preservação da Base

1. Este pacote documental é estritamente normativo. **Nenhum código Python da Fase 7 foi criado ou executado**; nenhum teste de implementação da Fase 7 foi executado (`0/119 executados`).
2. `main`, a tag `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`), `requirements.txt`, `catalogo_agentes.yaml`, `SKILL.md`, os 8 schemas em `references/schemas/` e as branches históricas (`rev10`, `rev11`) permanecem integralmente inalterados.
3. Nenhuma funcionalidade da Fase 8 é antecipada neste documento.

---

## 1. Inventário de Contratos e Migração da Beta 6.6 (`ACH-B7-R11-001`)

1. Os **8 schemas históricos** da Beta 6.6 estão preservados byte a byte em `schemas/legacy-v8.0-beta.6.6/` com SHA-256 físico documentado em `MATRIZ_MIGRACAO_SCHEMAS_BETA66_REV12.md` e `SCHEMA_REGISTRY_FASE7_REV12.json`.
2. **Proibição de versão inventada:** é expressamente proibido atribuir `instance_schema_version = "6.6.0"` a partir do número da release `v8.0-beta.6.6`. Versões não comprovadas por instâncias reais são marcadas como `NAO_VERIFICADO` e bloqueadas pela política `default_decision: "deny"`.
3. **Contratos aninhados:** `schema_achado.json` e `schema_evidencia.json` não possuem `schema_version` própria na instância; herdam a versão do schema-raiz que os referencia.
4. **Separação em `schema_profile.json`:** `profile_version` (versão funcional do perfil) é estritamente separada de `PROFILE_CONTRACT_VERSION = "7.0.0"` (constante do carregador de contrato).
5. **18 contratos canônicos em `schemas/7.0.0/`:**
   - 8 evoluídos da Beta 6.6 (`schema_achado`, `schema_agente` [identifica `agent_opinion`], `schema_evidencia`, `schema_input`, `schema_iteracao`, `schema_motor`, `schema_profile`, `schema_relatorio_final`);
   - 3 adicionais da Rev 10 (`schema_envelope_agente`, `schema_ledger_adjudicacao`, `schema_gatilho_agente`);
   - 7 adicionais independentes (`schema_monotonic_checkpoint_receipt`, `schema_isolation_attestation`, `schema_evidence_qualification`, `schema_campaign_manifest`, `schema_mandatory_axes_plan`, `schema_adversarial_contestation`, `schema_adjudication_record`).
6. Todos os 18 contratos possuem `$id` único `https://revisao-hostil.v8/schemas/7.0.0/<nome-do-schema>`, `$ref` exclusivamente local e versionado, e `additionalProperties: false`.

---

## 2. Protocolo Definitivo do `MonotonicCheckpointStore` (`ACH-B7-R11-002`, `ACH-B7-R11-010`)

Especificação criptográfica completa em `CONTRATOS_CRIPTOGRAFICOS_REV12.md`. Regras normativas:

1. **Mecanismo único obrigatório:** Store remoto append-only com CAS atômico + **duas testemunhas externas independentes** (Testemunha A e Testemunha B), com **quórum fixo `2-of-2`**. Alternativas de testemunha única, log de transparência primário ou TPM/HSM/TEE estão eliminadas.
2. **Três domínios administrativos independentes:** chaves Ed25519 distintas para Store, Testemunha A e Testemunha B, todas fixadas na política confiável em formato único `public_key_spki_der_b64` com `key_id = lowercase_hex(SHA256(SPKI_DER_BYTES))`.
3. **Desafio-resposta com nonce de 32 bytes:** o verificador gera nonce CSPRNG de 32 bytes (Base64 estrito), consulta A e B, valida assinaturas, nonce, concordância total (`checkpoint_revision`, `checkpoint_sha256`, `policy_seq`, `receipt_sha256`), monotonia, ausência de equivocação (`CheckpointEquivocationError`), prazo máximo de **30 segundos** por relógio monotônico local e consumo único do nonce.
4. **Falha e degradação:** quórum `1-of-2`, indisponibilidade de A ou B, replay de recibo antigo ou restauração de snapshot impedem `ancoragem_externa_independente` (`AnchorVerificationError` quando obrigatória, ou degradação explícita para `integridade_local_com_ancora_co_localizada`).
5. **Recuperação:** exige autorização assinada pela raiz fixada, justificativa, operador, estado anterior/novo, recibo do store, confirmação das duas testemunhas e evento append-only. Reset automático para sequência zero é proibido.

---

## 3. Confinamento Estrito de Arquivos por Plataforma (`ACH-B7-R11-003`)

### 3.1. Plataformas Oficialmente Suportadas
- **Windows NTFS**
- **Linux kernel 5.6 ou superior** (com suporte a `openat2` + `RESOLVE_NO_XDEV`)
- **macOS, BSD, Linux sem `openat2` compatível ou outras plataformas:** **NÃO** são suportadas para confinamento estrito nesta fase; devem levantar `UnsafePlatformPathError` (proibido fallback textual com `Path.resolve()`).

### 3.2. Regras Obrigatórias — Windows NTFS
1. Entrada da rotina: lista de segmentos relativos já separados (nunca caminho absoluto livre).
2. Rejeitar imediatamente: UNC (`\\servidor\share`), prefixos `\\?\` e `\\.\`, Alternate Data Streams (`:stream`), dois pontos em qualquer segmento, segmentos vazios, `.`, `..`, `/` ou `\` internos, nomes terminados em ponto ou espaço, e nomes reservados de dispositivos Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`).
3. Validar a raiz e sua cadeia de abertura sem atravessar reparse points.
4. Travessia componente por componente com `NtCreateFile`: um único segmento relativo por chamada, `RootDirectory` = handle validado do pai, flag `FILE_OPEN_REPARSE_POINT`, opção de diretório para intermediários e não-diretório para o destino final.
5. Após cada abertura: consultar `FileBasicInfo`, rejeitar `FILE_ATTRIBUTE_REPARSE_POINT`, confirmar volume, confirmar identidade via `FILE_ID_INFO` e manter o handle aberto até o término da leitura.
6. **Hard links:** no arquivo final, exigir `NumberOfLinks == 1`; caso contrário levantar `HardLinkPolicyError`.

### 3.3. Regras Obrigatórias — Linux (kernel ≥ 5.6)
1. Utilizar `openat2` com `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV` sobre descritores encadeados.
2. Validar via `fstat` e `statx`: arquivo final regular (`S_ISREG`), `st_dev` e `stx_mnt_id` compatíveis com a raiz (bloqueando mount points e bind mounts; não usar apenas `st_dev` para autorizar bind mounts), sem symlinks nem magic links.
3. **Hard links:** exigir `st_nlink == 1`; caso contrário levantar `HardLinkPolicyError`.
4. Ausência de suporte a `openat2` + `RESOLVE_NO_XDEV` falha fechado com `UnsafePlatformPathError`.

### 3.4. Integridade de Leitura (Buffer Único Imutável)
O arquivo é aberto pelo descritor/handle validado, lido integralmente pelo mesmo handle para um único buffer imutável em memória, hasheado (SHA-256) e decodificado a partir desse mesmo buffer — nunca reaberto por caminho textual.

---

## 4. Domínio de Pesos e Prova Matemática Exata de `D_bound` (`ACH-B7-R11-004`, `ACH-B7-R11-005`)

1. **Domínio restaurado da Revisão 10 (mandatório):**
   - Máximo de **15 eixos** ($1 \le m \le 15$);
   - Máximo de **15 avaliadores por eixo** ($1 \le n_i \le 15$);
   - Notas em $[0, 10]$ como string decimal com até 6 casas decimais;
   - **Pesos no domínio $(0, 1000]$** (`0 < w_i <= 1000`) como string decimal com até 6 casas decimais (ex.: `"0.000001"`, `"1.000000"`, `"999.999999"`, `"1000.000000"`). Rejeitar `"0"`, negativos, `"1000.000001"`, >6 casas decimais, `float`, `NaN`, `Infinity`. Proibida normalização automática ou divisão por 1000.
2. **Prova exata com `Fraction` (sem `float`):**
   - $L = \operatorname{lcm}(1, \dots, 15) = 360{,}360$.
   - Cada peso $w_i = \tilde{w}_i / 10^6$ com $1 \le \tilde{w}_i \le 1000 \times 10^6 = 10^9$.
   - Soma escalada: $\tilde{W}_{\text{total}} = \sum_{i=1}^{m} \tilde{w}_i \le 15 \times 1000 \times 10^6 = 1.5 \times 10^{10}$.
   - Média do eixo $i$: $s_i = a_i / (10^6 \cdot n_i)$ com $n_i \mid L$.
   - Nota global ponderada:
     $$S = \frac{\sum_{i=1}^{m} \tilde{w}_i \cdot a_i \cdot (L / n_i)}{L \cdot 10^6 \cdot \tilde{W}_{\text{total}}}$$
   - Reduzindo $S = N/D$ ($\gcd(N, D) = 1$, $D > 0$):
     $$D \mid (L \cdot 10^6 \cdot \tilde{W}_{\text{total}}) \implies D \le L \cdot 10^6 \cdot \tilde{W}_{\text{total}} \le 360{,}360 \times 10^6 \times 1.5 \times 10^{10} = 5.4054 \times 10^{21} = D_{\text{bound}}$$
   - Numerador máximo ($S \le 10$):
     $$N \le 10 \cdot D \le 10 \cdot D_{\text{bound}} = 5.4054 \times 10^{22} = N_{\text{bound}}$$
   - **Comprimentos em bits:** $D_{\text{bound}}$ possui **73 bits**; $N_{\text{bound}}$ possui **76 bits**.
   - **Teto operacional:** **128 bits** para numerador e denominador, verificado antes e depois das operações racionais relevantes (`RationalCapacityExceededError`).

---

## 5. Política Executável de Compatibilidade e SemVer Estável Estrito (`ACH-B7-R11-006`, `ACH-B7-R11-007`)

1. **Política de compatibilidade:** regida por `compatibility_policy.schema.json` (Draft 2020-12, `additionalProperties: false` em todos os níveis) e `compatibility_policy_v1.json`.
   - `policy_status`: `"normative_specification_template"` (documental, **rejeitado** por `load_compatibility_policy()`) ou `"frozen_executable"` (exige hashes SHA-256 físicos válidos para schema-raiz e todos os `$ref` transitivos, zero placeholders, e assinatura real pela raiz confiável).
   - `compatibility_policy_jcs_sha256` = SHA-256 de `UTF8(JCS(política excluindo compatibility_policy_jcs_sha256))`, vinculado à política confiável assinada e ao `schema_campaign_manifest.json`.
   - **Parser JSON estrito:** UTF-8 válido, rejeição de chaves duplicadas, `NaN`, `Infinity`, `-Infinity` e dados após o objeto JSON.
2. **SemVer estável estrito (`MAJOR.MINOR.PATCH`):**
   - Regex Python (`re.fullmatch`): `\A(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\Z`.
   - Regex JSON Schema: `^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})(?![\r\n])$`.
   - Rejeita zeros à esquerda (`01.0.0`, `1.00.0`, `1.0.00`), versões incompletas (`1.0`, `1`), pré-lançamentos (`1.0.0-alpha`), metadados de build (`1.0.0+build`) e excesso de comprimento.
   - Comparador obrigatório `compare_semver_stable()` retorna `-1`, `0` ou `1` comparando os três inteiros numericamente (`1.10.0 > 1.9.0`), sem usar `packaging.Version`.
