# Matriz Executável de Compatibilidade de Contratos — Fase 7 (`v8.0-beta.7`, Revisão 10)

> **Base de referência congelada:** `v8.0-beta.6.6` (`commit 11e91b6f3d517707326357868cc34ff97ab8327d`)  
> **Aviso normativo:** especificação contratual documental (`ACH-B7-R9-002`; não representa implementação executada).

---

## 1. Interface Normativa do Validador

```python
validate_contract(
    instance: dict[str, Any],
    schema_name: str,
    contract_version: str,
    *,
    compatibility_policy: CompatibilityPolicy,
) -> dict[str, Any]
```

**Regras inegociáveis:**
1. `instance_schema_version` (declarado na instância) e `contract_version` (selecionado explicitamente pelo consumidor) são tratados como identidades distintas.
2. A versão do contrato **nunca** é selecionada implicitamente como a mais recente.
3. Toda comparação de versão usa o comparador normativo SemVer 2.0.0 (`compare_semver`).
4. O retorno detalhado integra a proveniência da campanha:
   ```json
   {
     "valid": true,
     "schema_name": "schema_motor.json",
     "instance_schema_version": "1.0.0",
     "contract_version_used": "1.1.0",
     "compatibility_rule": "backward_validation",
     "errors": []
   }
   ```

---

## 2. Tabela de Despacho por Tipo de Documento

| Tipo de documento | Origem da versão da instância | Origem do `contract_version` | Comportamento se versão ausente/desconhecida |
| :--- | :--- | :--- | :--- |
| Parecer de agente (`schema_agente.json`) | Campo obrigatório `schema_version` | Parâmetro explícito `contract_version` | Levanta `SchemaVersionError` |
| Relatório final (`schema_relatorio_final.json`) | Campo obrigatório `schema_version` | Parâmetro explícito `contract_version` | Levanta `SchemaVersionError` |
| Saída de motor (`schema_motor.json`) | Campo obrigatório `schema_version` | Parâmetro explícito `contract_version` | Levanta `SchemaVersionError` |
| Entrada de motor (`schema_input.json`) | Campo obrigatório `schema_version` | Parâmetro explícito `contract_version` | Levanta `SchemaVersionError` |
| Iteração (`schema_iteracao.json`) | Campo obrigatório `schema_version` | Parâmetro explícito `contract_version` | Levanta `SchemaVersionError` |
| Envelope (`schema_envelope_agente.json`) | Campo obrigatório `schema_version` | Parâmetro explícito `contract_version` | Levanta `SchemaVersionError` |
| Ledger (`schema_ledger_adjudicacao.json`) | Campo obrigatório `schema_version` | Parâmetro explícito `contract_version` | Levanta `SchemaVersionError` |
| Gatilho (`schema_gatilho_agente.json`) | Campo obrigatório `schema_version` | Parâmetro explícito `contract_version` | Levanta `SchemaVersionError` |
| Perfil YAML (`schema_profile.json`) | Não possui `schema_version` (`profile_version` é versão do domínio) | Constante explícita `PROFILE_CONTRACT_VERSION = "1.0.0"` | Levanta `SchemaConfigurationError` se contrato não existir |
| Objetos aninhados (`schema_achado.json`, `schema_evidencia.json`) | Sem `schema_version` próprio na instância | `$ref` imutável versionado do contrato-raiz (`1.0.0/...` ou `1.1.0/...`) | Proibido validar isoladamente sem `contract_version` explícito |

---

## 3. Matriz Executável de Compatibilidade por Schema

| Schema | `instance_schema_version` | `contract_version` selecionado | Compatível? | `compatibility_rule` | Campos adicionais / condicionais | Resultado |
| :--- | :---: | :---: | :---: | :--- | :--- | :---: |
| `schema_motor.json` | `1.0.0` | `1.0.0` | Sim | `exact_match` | Apenas árvore `1.0.0` | **PASS** |
| `schema_motor.json` | `1.0.0` | `1.1.0` | Sim | `backward_validation` | Novos campos aninhados opcionais | **PASS** |
| `schema_motor.json` | `1.1.0` | `1.1.0` | Sim | `exact_match` | Aceita `tipo="saida_motor"` e `proveniencia_probatoria` | **PASS** |
| `schema_motor.json` | `1.1.0` | `1.0.0` | **Não** | `rejected_forward_version` | Contrato `1.0.0` congelado não aceita `1.1.0` | **FAIL** |
| `schema_agente.json` | `1.0.0` | `1.0.0` | Sim | `exact_match` | Apenas árvore `1.0.0` | **PASS** |
| `schema_agente.json` | `1.0.0` | `1.1.0` | Sim | `backward_validation` | Campos `1.1.0` não exigidos para instância `1.0.0` | **PASS** |
| `schema_agente.json` | `1.1.0` | `1.1.0` | Sim | `exact_match` | Exige `hash_artefato`, `hash_envelope`, `rodada`, `papel_especifico` | **PASS** |
| `schema_agente.json` | `1.1.0` | `1.0.0` | **Não** | `rejected_forward_version` | Rejeitado | **FAIL** |
| `schema_iteracao.json` | `1.0.0` | `1.0.0` | Sim | `exact_match` | Congelado `1.0.0` | **PASS** |
| `schema_iteracao.json` | `1.0.0` | `1.1.0` | Sim | `backward_validation` | `resumo_adjudicacao` opcional | **PASS** |
| `schema_iteracao.json` | `1.1.0` | `1.1.0` | Sim | `exact_match` | Aceita `resumo_adjudicacao` fechado | **PASS** |
| `schema_iteracao.json` | `1.1.0` | `1.0.0` | **Não** | `rejected_forward_version` | Rejeitado | **FAIL** |
| `schema_relatorio_final.json` | `1.0.0` | `1.0.0` | Sim | `exact_match` | `$ref` → `1.0.0/{achado,iteracao}` | **PASS** |
| `schema_relatorio_final.json` | `1.0.0` | `1.1.0` | Sim | `backward_validation` | Campos de ledger opcionais para `1.0.0` | **PASS** |
| `schema_relatorio_final.json` | `1.1.0` | `1.1.0` | Sim | `exact_match` | `$ref` → `1.1.0/{achado,iteracao}`; exige `ledger_head_sha256` e `ledger_entry_count` | **PASS** |
| `schema_relatorio_final.json` | `1.1.0` | `1.0.0` | **Não** | `rejected_forward_version` | Rejeitado | **FAIL** |
| `schema_input.json` | `1.0.0` | `1.0.0` | Sim | `exact_match` | Inalterado | **PASS** |
| `schema_profile.json` | *(perfil YAML)* | `1.0.0` (`PROFILE_CONTRACT_VERSION`) | Sim | `explicit_loader_contract` | Independente de `profile_version` | **PASS** |
| `schema_envelope_agente.json` | `1.0.0` | `1.0.0` | Sim | `exact_match` | Novo contrato fechado | **PASS** |
| `schema_ledger_adjudicacao.json` | `1.0.0` | `1.0.0` | Sim | `exact_match` | Novo contrato fechado | **PASS** |
| `schema_gatilho_agente.json` | `1.0.0` | `1.0.0` | Sim | `exact_match` | Novo contrato fechado | **PASS** |
| Qualquer schema | `2.0.0` / `1.2.0` / ausente | Qualquer | **Não** | `rejected_unknown_version` | Versões futuras/desconhecidas sempre rejeitadas | **FAIL** |
