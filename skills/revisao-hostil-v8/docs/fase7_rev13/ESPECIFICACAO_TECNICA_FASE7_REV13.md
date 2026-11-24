# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 13

**Status:** Documentação normativa autossuficiente (**implementação Python NÃO iniciada**; Ordem de Serviço **BLOQUEADA até aprovação externa**)  
**Base obrigatória imutável:** tag `v8.0-beta.6.6`, commit `11e91b6f3d517707326357868cc34ff97ab8327d`  
**Branch documental:** `specification/v8.0-beta.7-rev13`  
**Escopo:** Correção integral dos 3 achados P1 da auditoria da Revisão 12 (`ACH-B7-R12-001`, `ACH-B7-R12-002`, `ACH-B7-R12-003`), preservando integralmente todas as garantias consolidadas até a Revisão 12.

---

## 0. Declaração de Escopo e Preservação da Base

1. Este pacote documental é estritamente normativo. **Nenhum código Python da Fase 7 foi criado ou executado**; nenhum teste de implementação da Fase 7 foi executado (`0/128 executados`).
2. `main`, a tag `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`), `requirements.txt`, `catalogo_agentes.yaml`, `SKILL.md`, os 8 schemas em `references/schemas/` e as branches históricas (`rev10`, `rev11`, `rev12`) permanecem integralmente inalterados.
3. Nenhuma funcionalidade da Fase 8 é antecipada neste documento.

---

## 1. Inventário de Contratos e Migração da Beta 6.6

1. Os **8 schemas históricos** da Beta 6.6 estão preservados byte a byte em `schemas/legacy-v8.0-beta.6.6/` com SHA-256 físico documentado em `MATRIZ_MIGRACAO_SCHEMAS_BETA66_REV13.md` e `SCHEMA_REGISTRY_FASE7_REV13.json`.
2. **Proibição de versão inventada:** é proibido atribuir `instance_schema_version = "6.6.0"` a partir do número da release. Versões não comprovadas por instâncias reais são marcadas como `NAO_VERIFICADO` e bloqueadas pela política `default_decision: "deny"`.
3. **Contratos aninhados:** `schema_achado.json` e `schema_evidencia.json` herdam a versão do schema-raiz.
4. **Separação em `schema_profile.json`:** `profile_version` (versão funcional) é separada de `PROFILE_CONTRACT_VERSION = "7.0.0"`.
5. **18 contratos canônicos em `schemas/7.0.0/`** com `$id` único `https://revisao-hostil.v8/schemas/7.0.0/<nome>`, `$ref` exclusivamente local e versionado, e `additionalProperties: false`.

---

## 2. Protocolo Definitivo do `MonotonicCheckpointStore`, Independência Administrativa e Anti-Replay Persistente (`ACH-B7-R12-001`, `ACH-B7-R12-002`)

Especificação criptográfica completa em `CONTRATOS_CRIPTOGRAFICOS_REV13.md`. Regras normativas:

1. **Mecanismo único obrigatório:** Store remoto append-only com CAS atômico + **duas testemunhas externas independentes** (Testemunha A e Testemunha B), com **quórum fixo `2-of-2`** e chaves Ed25519 em formato `public_key_spki_der_b64` (`key_id = lowercase_hex(SHA256(SPKI_DER_BYTES))`).
2. **Prova de Independência Administrativa (`ACH-B7-R12-001`):** a simples diferença entre `key_id` **não** comprova independência. Para conceder `ancoragem_externa_independente`, exige-se dossiê verificável (`administrative_independence_dossier_sha256`) comprovando operadores jurídicos/organizacionais distintos, provedores/domínios distintos, ausência de credenciais administrativas compartilhadas, KMS/HSM e custodiantes separados, e procedimentos independentes de rotação e recuperação (detalhado em `CONTRATOS_CRIPTOGRAFICOS_REV13.md` §3.1.1).
3. **Persistência Transacional e Concorrente de Nonces (`ACH-B7-R12-002`):** o consumo único de nonces de 32 bytes é garantido pela interface persistente `NonceConsumptionStore.consume_once(...)` com persistência transacional, inserção condicional atômica, restrição de unicidade sobre `(protocol_scope, nonce_sha256)`, registro append-only, proteção contra restauração de backup, exclusividade sob concorrência (apenas 1 thread/processo/campanha pode consumir), bloqueio imediato em falha de persistência (`NoncePersistenceError`) e janela de retenção vinculada ao TTL da campanha e margem de clock skew (detalhado em `CONTRATOS_CRIPTOGRAFICOS_REV13.md` §3.4.1).

---

## 3. Confinamento Estrito de Arquivos por Plataforma

1. **Plataformas suportadas:** estritamente **Windows NTFS** e **Linux kernel ≥ 5.6** (`openat2` com `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV`). macOS, BSD ou Linux sem `openat2` seguro levantam `UnsafePlatformPathError` (proibido fallback `Path.resolve()`).
2. **Windows NTFS:** lista de segmentos já separados; bloqueio de UNC, `\\?\`, `\\.\`, ADS (`:stream`), `.`, `..`, nomes reservados; `NtCreateFile` de segmento único com `FILE_OPEN_REPARSE_POINT`, verificação imediata de `FileBasicInfo`, volume e `FILE_ID_INFO`; `NumberOfLinks == 1` (`HardLinkPolicyError`).
3. **Linux ≥ 5.6:** descritores encadeados, `fstat`/`statx` (`S_ISREG`, `st_dev` e `stx_mnt_id` compatíveis com a raiz, bloqueio de bind mounts), `st_nlink == 1` (`HardLinkPolicyError`).
4. **Buffer único imutável:** abertura, leitura, hash SHA-256 e decodificação sobre o mesmo descritor/handle validado.

---

## 4. Domínio de Pesos e Prova Matemática Exata de `D_bound`

- **Domínio:** $1 \le m \le 15$ eixos, $1 \le n_i \le 15$ avaliadores/eixo, notas em $[0, 10]$ e pesos em **$(0, 1000]$** com até 6 casas decimais em `Fraction` (sem `float`, sem normalização automática).
- $L = \operatorname{lcm}(1, \dots, 15) = 360{,}360$; $\tilde{W}_{\text{total}} \le 15 \times 1000 \times 10^6 = 1.5 \times 10^{10}$.
- $D \mid (L \cdot 10^6 \cdot \tilde{W}_{\text{total}}) \implies D \le D_{\text{bound}} = 5.4054 \times 10^{21}$ (**73 bits**); $N \le N_{\text{bound}} = 5.4054 \times 10^{22}$ (**76 bits**); teto operacional de **128 bits** (`RationalCapacityExceededError`).

---

## 5. Política Executável de Compatibilidade, Validador Semântico e SemVer Estável (`ACH-B7-R12-003`)

1. **Validação Estrutural (`compatibility_policy.schema.json`):** Draft 2020-12, `additionalProperties: false` em todos os níveis, `"entries": {"minItems": 18, "maxItems": 18, "uniqueItems": true}`, `"uniqueItems": true` em `ref_hashes` e `allowed_instance_versions`.
2. **Validação Semântica Obrigatória (a validação do JSON Schema isoladamente NÃO comprova integridade semântica):** antes de aceitar `policy_status == "frozen_executable"`, o carregador `load_compatibility_policy()` deve executar obrigatoriamente:
   - Unicidade de `schema_name` entre as exatamente 18 entradas;
   - Unicidade de `ref_schema_name` dentro de cada `ref_hashes`;
   - Correspondência exata 1-para-1 entre o conjunto de `schema_name` das 18 entradas e `SCHEMA_REGISTRY_FASE7_REV13.json` (rejeitar schemas desconhecidos, ausentes ou duplicados);
   - Extração independente da árvore transitiva real de `$ref` a partir dos arquivos físicos em disco e comparação exata com `ref_hashes` (rejeitar referências extras, ausentes, duplicadas ou com caminhos divergentes);
   - Verificação de que cada `schema_sha256` e `ref_sha256` corresponde aos bytes físicos em disco (`^[0-9a-f]{64}$`, zero placeholders);
   - Verificação do digest `compatibility_policy_jcs_sha256` e assinatura pela raiz confiável;
   - Parser JSON estrito (UTF-8 válido, rejeição de chaves duplicadas, `NaN`, `Infinity`, `-Infinity`, dados trailing).
3. **SemVer estável estrito:** `MAJOR.MINOR.PATCH` (`^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})(?![\r\n])$`), comparador numérico `compare_semver_stable()` (`1.10.0 > 1.9.0`), sem `packaging.Version`.
