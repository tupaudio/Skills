# MATRIZ E POLÍTICA EXECUTÁVEL DE COMPATIBILIDADE DE CONTRATOS — FASE 7 (`v8.0-beta.7`), REVISÃO 11

**Status:** Documentação normativa (sem implementação Python)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Achado endereçado:** `ACH-B7-R10-002` (P1)

---

## 1. Artefato Estruturado, Autenticado e Executável (`compatibility_policy_v1.json`)

Na Revisão 11, a compatibilidade de schemas deixa de ser apenas descritiva em Markdown e passa a ser governada pelo artefato JSON estruturado `compatibility_policy_v1.json` (presente neste diretório como modelo normativo; na execução da Fase 7, os placeholders `PENDING_PHASE7_OS_FREEZE` serão substituídos pelos SHA-256 reais dos arquivos `.schema.json` congelados na OS).

### 1.1. Schema Fechado da Política de Compatibilidade (`additionalProperties: false`)
```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["policy_version", "policy_status", "baseline_tag", "baseline_commit", "default_decision", "allowed_triples"],
  "properties": {
    "policy_version": { "type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+(?![\\r\\n])$" },
    "policy_status": { "type": "string", "enum": ["normative_specification_template", "frozen_executable"] },
    "baseline_tag": { "type": "string", "minLength": 1 },
    "baseline_commit": { "type": "string", "pattern": "^[0-9a-f]{40}(?![\\r\\n])$" },
    "default_decision": { "type": "string", "const": "deny" },
    "allowed_triples": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["schema_name", "instance_schema_version", "contract_version", "backward_validation", "ref_hashes"],
        "properties": {
          "schema_name": { "type": "string", "minLength": 1 },
          "instance_schema_version": { "type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+(?![\\r\\n])$" },
          "contract_version": { "type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+(?![\\r\\n])$" },
          "backward_validation": { "type": "boolean" },
          "ref_hashes": {
            "type": "object",
            "additionalProperties": { "type": "string", "minLength": 1 }
          }
        }
      }
    }
  }
}
```

### 1.2. Regra Default-Deny e Autenticação
1. **Default-Deny:** qualquer tripla `(schema_name, instance_schema_version, contract_version)` ausente de `allowed_triples` é **rejeitada imediatamente** com `ExecutionBlockedError`.
2. **Autenticação Criptográfica:** o hash `compatibility_policy_jcs_sha256 = SHA256(JCS(compatibility_policy_v1.json))` é fixado na `trusted_anchors_policy` assinada e registrado no `campaign_manifest.json`. Qualquer adulteração da matriz invalida a assinatura da política confiável e bloqueia a execução.
3. **Verificação da Cadeia `$ref`:** antes de validar qualquer instância, o validador verifica o SHA-256 de todos os schemas referenciados em `ref_hashes`. Um `$ref` ausente ou com hash divergente causa bloqueio imediato (`ExecutionBlockedError`).

---

## 2. Semântica Formal de `backward_validation`

- **`backward_validation: false`:** exige `instance_schema_version == contract_version`. A instância é validada estritamente contra o contrato `contract_version` e sua cadeia `$ref` fixada.
- **`backward_validation: true`:** permite `instance_schema_version < contract_version` **exclusivamente** para a tripla listada em `allowed_triples`, sob três condições cumulativas:
  1. Validação integral contra o schema `contract_version` (com todos os `$ref` verificados por SHA-256);
  2. `additionalProperties: false` respeitado (nenhum campo desconhecido ou legado não mapeado é tolerado);
  3. Nenhuma coerção implícita de tipos ou preenchimento silencioso de defaults obrigatórios.

---

## 3. Inventário Consolidado (8 Schemas Evoluídos + 3 Novos)

Todos os 8 schemas existentes da `v8.0-beta.6.6` evoluídos para `7.0.0` (com compatibilidade explícita somente onde `backward_validation: true` em `compatibility_policy_v1.json`) e os 3 novos schemas da Fase 7 (`monotonic_checkpoint_receipt`, `isolation_attestation`, `evidence_qualification`) obedecem estritamente à regra default-deny acima.
