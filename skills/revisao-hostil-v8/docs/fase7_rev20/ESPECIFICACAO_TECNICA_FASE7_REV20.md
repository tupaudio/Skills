# ESPECIFICAÇÃO TÉCNICA — FASE 7 (`v8.0-beta.7`), REVISÃO 20

**Branch de origem:** `specification/v8.0-beta.7-rev19` (`d68ba00f460f93872b0555c74c8dc7461ee96436`)  
**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Escopo:** Correção integral dos achados `ACH-B7-R19-001` a `ACH-B7-R19-006` (runtime da Fase 7 não iniciado; `OS_STATUS = BLOCKED`).

1. **`ACH-B7-R19-001`:** Removido instante UTC fixo; `get_trusted_utc_now()` + `resolve_execution_now_utc(mode="operational")` rejeita injeção de relógio de teste em modo operacional e verifica `finished_utc >= started_utc`.
2. **`ACH-B7-R19-002`:** `validate_dossier_trust_binding()` vincula cada operador do dossiê (`checkpoint_store`, `witness_a`, `witness_b`) à chave efetiva do trust bundle e exige 3 `infrastructure_provider` distintos.
3. **`ACH-B7-R19-003`:** `tools/historical_test_manifest_rev20.json`, `tools/historical_results_rev20.json`, `tests/test_historical_preservation.py` (igualdade de conjuntos Rev17 ⊆ Rev18 ⊆ Rev19 = 199 IDs), `artifact_sha256` obrigatório em `test_results_schema.json`, e matriz gerada exclusivamente de resultados estruturados.
4. **`ACH-B7-R19-004`:** `tools/run_independent_tests.py` executa `pytest --junitxml=reports/pytest-results.xml`, interpreta individualmente `passed`/`failed`/`skipped`/`error`, nunca classifica `skipped` como `PASS`, e falha se teste obrigatório for ignorado na própria plataforma.
5. **`ACH-B7-R19-005`:** `RuntimeClockContext` ampliado com `boot_id` (`/proc/sys/kernel/random/boot_id` + kernel ≥ 5.6 no Linux; `MachineGuid` + `GetTickCount64` no Windows), validando UUID, PID, `boot_id`, `clock_source`, `store_epoch` e monotonicidade.
6. **`ACH-B7-R19-006`:** `validate_revocation_list()` valida `revoked_at <= now_utc`, unicidade semântica de `key_id` (`seen`) e `reason` não vazia.
