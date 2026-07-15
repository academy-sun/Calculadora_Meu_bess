# Campo Desenvolvedor Ploomes — Spike (Fase 0)

Passos manuais para validar a integração embed dentro de um negócio de teste no Ploomes.

## Pré-requisitos

- Módulo CPQ contratado e habilitado (✓ confirmado na conta)
- Acesso de administrador no Ploomes
- Frontend deployado com a rota `/embed/ploomes` (Vercel)

## Passo 1 — Criar campo de teste

Crie um campo customizado no **Negócio** do tipo *texto*, chamado `MeuBESS Teste`.
Anote a **FieldKey** dele (ex.: `deal_9FA0C1...`). Vamos escrever nele via postMessage.

## Passo 2 — Criar o campo desenvolvedor

Crie um campo do tipo **Desenvolvedor** no formulário do Negócio com o conteúdo abaixo.

> O objetivo do spike é **descobrir a superfície de API real** do sandbox
> (como ler o ID do negócio, como escrever noutro campo). O snippet é
> diagnóstico: mostra na tela o que encontrou e loga tudo no console.

```html
<div id="mb-root" style="font-family: sans-serif; font-size: 13px;">
  <div id="mb-diag" style="padding:8px; background:#f5f5f5; border-radius:6px; margin-bottom:8px;">
    Carregando diagnóstico…
  </div>
  <div id="mb-frame"></div>
</div>

<script>
  var EMBED_URL = 'https://calculadora-meu-bess.vercel.app/embed/ploomes';
  var diag = document.getElementById('mb-diag');
  var lines = [];

  function log(label, value) {
    lines.push('<b>' + label + ':</b> ' + String(value));
    diag.innerHTML = lines.join('<br>');
    try { console.log('[MeuBESS spike]', label, value); } catch (e) {}
  }

  // ── Diagnóstico: o que o sandbox expõe? ────────────────────────────
  log('typeof PloomesServer', typeof PloomesServer);
  log('typeof PloomesDocument', typeof PloomesDocument);
  log('typeof Ploomes', typeof Ploomes);
  log('location.href', location.href);

  // Chaves globais não-padrão (ajuda a descobrir a API do sandbox)
  try {
    var std = ['window','self','document','location','navigator','top','parent','frames','history','screen','console','alert'];
    var custom = Object.getOwnPropertyNames(window).filter(function (k) {
      return std.indexOf(k) === -1 && !/^(on|webkit|chrome|inner|outer|screen|scroll|page|dev|client)/i.test(k);
    }).slice(0, 40);
    log('globals (amostra)', custom.join(', '));
  } catch (e) { log('globals', 'erro: ' + e.message); }

  // ── Tenta descobrir o ID do negócio ────────────────────────────────
  var dealId = null;
  try {
    // hipótese 1: query string do próprio iframe do campo
    var m = location.search.match(/[?&](DealId|dealId|Id|id)=(\d+)/);
    if (m) dealId = m[2];
  } catch (e) {}
  try {
    // hipótese 2: contexto exposto pelo sandbox
    if (!dealId && typeof Ploomes !== 'undefined' && Ploomes && Ploomes.EntityId) dealId = Ploomes.EntityId;
  } catch (e) {}
  log('deal_id descoberto', dealId || 'NÃO ENCONTRADO — verificar globals acima');

  // ── Monta o iframe da nossa plataforma ─────────────────────────────
  var iframe = document.createElement('iframe');
  iframe.src = EMBED_URL + '?deal_id=' + encodeURIComponent(dealId || 'desconhecido');
  iframe.style.cssText = 'width:100%; height:420px; border:1px solid #ddd; border-radius:8px;';
  document.getElementById('mb-frame').appendChild(iframe);

  // ── Escuta o retorno da nossa página ───────────────────────────────
  window.addEventListener('message', function (e) {
    if (!e.data || e.data.type !== 'meubess:test') return;
    log('postMessage RECEBIDO', JSON.stringify(e.data));

    // ACK de volta para a página embed (prova de canal bidirecional)
    try { iframe.contentWindow.postMessage({ type: 'ploomes:ack', ok: true }, '*'); } catch (err) {}

    // Tentativa de escrever no campo de teste — A API EXATA É O QUE O SPIKE
    // PRECISA DESCOBRIR. Tentativas comuns (descomentar/ajustar conforme o
    // que o diagnóstico de globals mostrar):
    //
    // 1) via PloomesServer (se expuser método de update de campo):
    //    PloomesServer.patch('Deals(' + dealId + ')', {
    //      OtherProperties: [{ FieldKey: 'deal_XXXX', StringValue: e.data.valor_teste }]
    //    });
    //
    // 2) via API de campo do próprio componente (se existir setValue/save):
    //    Field.setValue(e.data.valor_teste);
    try {
      if (typeof PloomesServer !== 'undefined') {
        log('PloomesServer métodos', Object.getOwnPropertyNames(PloomesServer.__proto__ || PloomesServer).join(', '));
      }
    } catch (err) { log('PloomesServer introspect', 'erro: ' + err.message); }
  });
</script>
```

## Passo 3 — Executar o teste

1. Abra um negócio de teste no Ploomes (na web, não no app mobile).
2. O bloco de diagnóstico deve listar o que o sandbox expõe e o `deal_id` descoberto.
3. Dentro do iframe, a página MeuBESS deve carregar mostrando o `deal_id`.
   - Se o iframe ficar em branco → problema de `frame-ancestors` (ver `frontend/vercel.json`).
4. Clique **"Testar retorno (postMessage)"** na página MeuBESS.
5. O diagnóstico deve mostrar `postMessage RECEBIDO` e a página deve mostrar o ACK.
6. Anote a saída de `globals (amostra)` e `PloomesServer métodos` — é com isso que
   escrevemos a versão definitiva (leitura do deal id + escrita nos campos).

## Critério go/no-go

| Verificação | Resultado esperado |
|---|---|
| Página MeuBESS renderiza no iframe | ✅ frame-ancestors ok |
| `deal_id` chega na página | ✅ (ou descobrimos a fonte certa nos globals) |
| postMessage embed → campo dev | ✅ diagnóstico mostra a mensagem |
| ACK campo dev → embed | ✅ página mostra o ACK |
| Escrita num campo do formulário | descobrir API (PloomesServer/Field) |

**Fallback se o iframe for bloqueado:** o campo desenvolvedor abre a página em
nova aba (`window.open`) e o write-back fica 100% no backend via API Ploomes
(`POST /ploomes/pushback`), sem postMessage.
