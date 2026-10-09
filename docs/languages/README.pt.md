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

![Navegação agrupada](../screenshots/en/01-models.png)
![Desempenho](../screenshots/en/02-performance.png)
![Rastreamentos](../screenshots/en/03-traces.png)
![Conexão](../screenshots/en/04-connection.png)
![Preferências](../screenshots/en/05-preferences.png)
![Parâmetros](../screenshots/en/06-parameters.png)
![Otimizador](../screenshots/en/07-optimizer-evaluation.png)
![Atualizações](../screenshots/en/08-updates.png)
![Túnel](../screenshots/en/09-tunnel.png)
![Cadastro de modelo](../screenshots/en/10-registration.png)
![Atividade](../screenshots/en/11-activity.png)

## Instalação no Linux

Após publicar uma versão, instale o pacote Linux para o usuário com:

```bash
curl -fsSL https://github.com/monrroyag/strata-llm-console/releases/latest/download/install-linux.sh | bash
```

O instalador verifica SHA-256, instala em `~/.local/share/strata-llm-console`, cria o comando em `~/.local/bin` e registra um serviço systemd de usuário quando disponível.

## Segurança do repositório

Tokens, arquivos de ambiente, rastreamentos, logs, GGUF, packs, binários e caminhos específicos do computador ficam fora do Git. Remover um modelo do catálogo nunca apaga seus arquivos originais.