# Relatórios de Execução (Histórico)

Os arquivos desta pasta são relatórios históricos gerados na `v8.0-beta.6.6` (**178 testes**, **82,73% de cobertura**).

Eles **não refletem** a versão atual (`v8.1.0-beta.2`, com suíte atualizada e CI em Ubuntu/Windows) e são mantidos apenas como registro histórico.

## Saneamento posterior à geração

- Os arquivos foram **saneados depois de gerados**: caminhos locais foram trocados por `<USER_HOME>`, `<REPO_ROOT>` e `<WORKSPACE>`.
- Os hashes em `run_manifest.json` e nos `homologacao_*.md` são os dos arquivos originais e não conferem com os atuais; os `SHA256SUMS` da raiz e de `00_diagnostico` foram regenerados ao final desta versão.
- Trata-se de registro histórico, **não reproduzível**.
