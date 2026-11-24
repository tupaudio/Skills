# MATRIZ DE MIGRAÇÃO DOS SCHEMAS DA BETA 6.6 → FASE 7 (`7.0.0`), REVISÃO 15

**Base imutável:** `v8.0-beta.6.6` (`11e91b6f3d517707326357868cc34ff97ab8327d`)  
**Status:** 8 schemas legados preservados byte a byte + **19 contratos canônicos `7.0.0`**

| `schema_name` | `source_path` | `legacy_contract_version` | `instance_schema_versions_observed` | `physical_sha256` | `git_blob_sha` | `schema_version_field` | `has_refs` | `migration_status` |
| :--- | :--- | :---: | :---: | :--- | :--- | :---: | :---: | :--- |
| `schema_achado.json` | `references/schemas/schema_achado.json` | N/A (aninhado) | Herdada do raiz | `d702dc69c9693beb368444161a6575745c33893feadda8ef8bcdded936c34568` | `8be020e84cda1fd89f928d0462172b516dfed8d5` | Não (aninhado) | Sim (`schema_evidencia.json`) | Evoluído → `schemas/7.0.0/schema_achado.json` |
| `schema_agente.json` | `references/schemas/schema_agente.json` | `NAO_VERIFICADO` | `NAO_VERIFICADO` | `58fcf4bc2bdae8f7bcc5a8e427479edeed0af81508787ff509600599ae34e240` | `db04f77b18f5c2377d34391002f126ada95f74e8` | Sim (`schema_version`) | Sim (`schema_achado.json`) | Evoluído → `schemas/7.0.0/schema_agente.json` (`agent_opinion`) |
| `schema_evidencia.json` | `references/schemas/schema_evidencia.json` | N/A (aninhado) | Herdada do raiz | `0156b3516edb48826efd54c1fe18f324bf4e3219a4d7ef71f5a106abc5d9dcef` | `88fbc55fa3966f6a8a988950ef438b8a32522041` | Não (aninhado) | Não | Evoluído → `schemas/7.0.0/schema_evidencia.json` |
| `schema_input.json` | `references/schemas/schema_input.json` | `NAO_VERIFICADO` | `NAO_VERIFICADO` | `0861afd1027463bc4cb223bae942e7cff446e8227786fd0a58b6a6be72314b44` | `afa3e81e5d704171a8c1c5353d8c9692e543ccdc` | Sim (`schema_version`) | Não | Evoluído → `schemas/7.0.0/schema_input.json` |
| `schema_iteracao.json` | `references/schemas/schema_iteracao.json` | `NAO_VERIFICADO` | `NAO_VERIFICADO` | `8e12f2cd018408094c5c42fc03f4164f2405d9954f2fde167156cb99cd2ea047` | `3cd517708c58d7beff17edd89a9448e09665fd51` | Sim (`schema_version`) | Não | Evoluído → `schemas/7.0.0/schema_iteracao.json` |
| `schema_motor.json` | `references/schemas/schema_motor.json` | `NAO_VERIFICADO` | `NAO_VERIFICADO` | `f572842db73e1ef4a4d582535324a59d05197abd62113460e92f785b3683d51f` | `f0b822313da8fa1429ab9e39e62745f3e514bb9b` | Sim (`schema_version`) | Sim (`schema_achado.json`) | Evoluído → `schemas/7.0.0/schema_motor.json` |
| `schema_profile.json` | `references/schemas/schema_profile.json` | `PROFILE_CONTRACT_VERSION` | Separado de `profile_version` | `733ade10fb72109f74b8a389ebaa567c4e1541b1a64aa7f40f81085a166ffdd3` | `51dc96e09e28c8ad792c3ae660cdb3f3eba9d1e7` | Não (`profile_version`) | Não | Evoluído → `schemas/7.0.0/schema_profile.json` |
| `schema_relatorio_final.json` | `references/schemas/schema_relatorio_final.json` | `NAO_VERIFICADO` | `NAO_VERIFICADO` | `a2a2b1290aafeea97333796fe70645f68ebec4f0cd8fb0d8f2d1d6eb0d8a52d1` | `d186307123af07b561005b768bb5003738520703` | Sim (`schema_version`) | Sim (`schema_achado.json`, `schema_iteracao.json`) | Evoluído → `schemas/7.0.0/schema_relatorio_final.json` |

Todos os 19 contratos canônicos `7.0.0` constam em `SCHEMA_REGISTRY_FASE7_REV15.json`.
