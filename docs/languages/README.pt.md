# Strata LLM Console — Português

[English](README.en.md) · [Español](README.es.md) · [Português](README.pt.md) · [Français](README.fr.md) · [Deutsch](README.de.md)

O inglês é o idioma inicial e a documentação de referência do Strata LLM Console. O usuário pode trocar o idioma no cabeçalho ou em Preferências.

## Origem do motor

Esta consola é uma camada operacional para o [motor oficial de inferência Strata](https://github.com/Niko1221/Strata). O repositório de origem é `https://github.com/Niko1221/Strata.git`. A consola administra catálogo, parâmetros, ciclo de vida, exposição de rede, observabilidade e atualizações.

## Áreas principais

- **Operar** — cadastrar, selecionar, carregar, descarregar, parar e remover modelos do catálogo; editar parâmetros; analisar memória e contexto.
- **Observar** — consultar VRAM/RAM, desempenho histórico, rastreamentos, raciocínio emitido pelo motor, ferramentas, tokens, latência e erros.
- **Conectar** — manter a API local, ativar LAN explicitamente, configurar Bearer/CORS e usar túnel criptografado.
- **Sistema** — verificar a versão do Strata, procurar atualizações, detectar backends e personalizar a interface.

## API

- Gateway OpenAI: `http://127.0.0.1:8090/v1`
- API de controle: `http://127.0.0.1:8090/api`
- O acesso remoto exige `Authorization: Bearer <console-token>`.
- O endereço padrão é loopback; LAN e CORS exigem ativação explícita.

## Otimizador

Combina memória real de GPU/RAM, contexto solicitado, quantização KV, cache de especialistas, configurações MTP/lookup, configuração atual, histórico e margens de risco. Retorna recomendação, alternativas e confiança. A análise estática é identificada honestamente e não é apresentada como benchmark.

## Telegram

O bot com lista permitida controla status, seleção de modelos, parada, descarga, confirmações, rastreamentos, erros, otimização, conexão e atualizações do Strata. Novos chats começam em inglês e podem escolher outro idioma.

## Capturas

![Navegação agrupada](../screenshots/models-grouped-en-final2.png)
![Desempenho](../screenshots/performance.png)
![Rastreamentos](../screenshots/traces-errors.png)
![Conexão](../screenshots/connection-final.png)
![Preferências](../screenshots/preferences-latest.png)
![Parâmetros](../screenshots/parameters.png)
![Otimizador](../screenshots/optimizer-analysis.png)
![Atualizações](../screenshots/update.png)
![Túnel](../screenshots/tunnel.png)
![Cadastro de modelo](../screenshots/add.png)
![Atividade](../screenshots/activity.png)

## Segurança do repositório

Tokens, arquivos de ambiente, rastreamentos, logs, GGUF, packs, binários e caminhos específicos do computador ficam fora do Git. Remover um modelo do catálogo nunca apaga seus arquivos originais.