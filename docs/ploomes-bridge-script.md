# Script do campo desenvolvedor "MeuBESS BESS — Calculadora" (v5)

Cole o conteúdo abaixo no campo desenvolvedor `MeuBESS BESS — Calculadora`
(`quote_15BBB0B5-5B33-4C28-BB87-AC7EBD45A294`), substituindo a versão anterior.

## Mudanças da v5 (2026-08-05)

1. **Lê os campos de TEXTO, não os de opção.** `Cidade da proposta`
   (`quote_53F02E1F…`) e `Estrutura Requisição` (`quote_AB306D98…`) são TypeId 1
   — texto simples, que o `input[name=…]` entrega direto. Os campos de opção
   (`Cidade`, `Estrutura`) ficam como fallback. Isso contorna de vez o problema
   do TypeId 7, em que o input carrega o id da opção e não o texto.
2. **O bridge não traduz mais nada.** Ele manda o texto cru (`cidade`,
   `estrutura`) e o de:para passou para dentro da ferramenta
   (`frontend/src/lib/ploomesContext.ts`). Cada conta de CRM escreve a estrutura
   de um jeito; ajustar o de:para agora é deploy do embed, não recolar script em
   cada conta. O `ploomesContext` aceita tanto o valor canônico
   (`tile_ceramic`) quanto os rótulos do CRM, e tem heurística por palavra-chave
   para variações não catalogadas.
3. **Conferência de escrita.** Depois de escrever, o bridge relê cada campo e
   mostra no painel o que ficou gravado. O campo `Itens do Kit` é o motivo:
   ele vinha saindo vazio sem nenhum erro visível, então agora o script diz se
   a escrita pegou ou não, e qual estratégia usou.

## Mudanças da v4 (após 3º teste real, 2026-07-31)

1. **Leitura de campos de opção (TypeId 7).** `Cidade` e `Estrutura` são campos
   de opção com tabela de opções; `Potência adequada (kWp)` é decimal. Só o
   decimal vinha — confirmado pela API: na proposta 601430438 a `Cidade` está
   gravada como `IntegerValue=607844285` + `ObjectValueName='LONDRINA-PR'`.
   O `input[name=…]` desses campos carrega o **id**, não o texto. O leitor agora
   detecta id numérico e cai para o texto visível do container.
2. **Diagnóstico detalhado.** O painel passa a mostrar *por qual estratégia*
   cada campo foi lido e, quando falha, despeja todos os elementos que casam
   com aquele `name` (tag, tipo, value, texto). É essa informação que fecha o
   ajuste do seletor sem precisar de mais um ciclo de teste.
3. **`Itens do Kit` escrito como HTML.** O campo é multilinha e só renderiza
   HTML — texto puro saía vazio. O embed agora manda `itens_html` (`<ul><li>`)
   e o bridge escreve com `innerHTML`.

## ⚠️ Perfil temporário: `admin` (2026-07-22)

O script está fixo em `?perfil=admin` só para validar o fluxo completo
(catálogo sem filtro por view) enquanto testamos a integração ponta a ponta.
**Não é o estado final** — hoje o perfil é um parâmetro de URL, então
qualquer um que descubra o endereço do embed pode trocar `?perfil=consultor`
por `?perfil=admin` e ver preço/produtos restritos. Aceitável para o piloto
interno, não para produção multi-conta.

## Modelo multi-conta (planejado, não implementado)

Decisão: cada base de CRM (cada integrador/empresa que usar essa integração)
vai ter sua própria API key, cadastrada na plataforma MeuBESS com o perfil
já embutido no servidor — o parâmetro `?perfil=` da URL deixa de valer.

Fluxo alvo:
1. Cadastro do integrador na plataforma MeuBESS gera um token com o perfil
   desejado (integrador/consultor/admin) associado no banco.
2. Esse token é colado no script do campo desenvolvedor daquela conta
   Ploomes (troca a `X-API-Key` usada nas chamadas ao embed/backend).
3. Backend resolve o perfil pela própria key (`API_KEY_EMBED` deixa de ser
   uma única key global — vira uma tabela `ploomes_accounts` ou similar,
   key → perfil → talvez PLOOMES_FIELD_MAP por conta), ignorando qualquer
   `perfil` vindo da URL/query.

Isso também resolve a limitação atual de `PLOOMES_FIELD_MAP` ser uma env
única — cada conta pode ter suas próprias FieldKeys.

**Não implementado ainda** — fica como próximo passo estrutural depois que
o fluxo atual (perfil admin fixo) estiver validado.

## Mudanças da v3 (após 2º teste real, 2026-07-21)

1. **Sem mais retry/espera de 8s.** O modelo agora é sob demanda: um botão
   grande **"⟳ Puxar valores da proposta"** lê os campos na hora do clique e
   envia para o iframe via `postMessage` — sem recarregar o iframe, então as
   cargas já digitadas são preservadas. O consultor preenche a proposta no
   ritmo dele e puxa os valores quando quiser. No load, o bridge também envia
   automaticamente assim que o iframe avisa que está pronto (`meubess:ready`).
2. **Painel de diagnóstico visível** no widget: a cada "puxar valores", mostra
   o que foi lido (cru) e o que foi mapeado (UF, fixing_type) — não precisa
   mais de console para depurar cidade/estrutura.
3. **Leitura com fallback**: tenta `input[name=...]`, depois
   `select[name=...]`, depois qualquer `[name=...]` — cobre variações do DOM
   do Ploomes para campos de opções.
4. **Escrita de moeda corrigida**: o embed agora envia os valores também como
   string decimal pt-BR (`"62822,49"`), e o bridge usa essa string nos campos
   moeda — elimina o bug do float impreciso que virava
   `62.822.249.999.999,99`. Escrita agora faz focus → limpa → escreve → blur,
   com native setter (React) — corrige também o reaplicar que só atualizava a
   descrição.

## Fluxo

```
[Consultor preenche a proposta: Cidade, Estrutura, Potência adequada…]
        │
        ▼ clica "⟳ Puxar valores da proposta"  (ou automático no load)
Bridge lê os 3 campos → mostra diagnóstico → postMessage 'ploomes:context'
        │
        ▼
Iframe MeuBESS atualiza kWp / UF do frete / estrutura (sem perder as cargas)
        │
        ▼ consultor adiciona cargas, busca kits, clica "Aplicar à proposta"
Iframe → postMessage 'meubess:saved' → bridge escreve nos 6 campos novos
```

## Mapeamento Estrutura → fixing_type

> **Desde a v5 este de:para não está mais no script.** Ele vive em
> `frontend/src/lib/ploomesContext.ts` e é exercitado por
> `ploomesContext.test.ts`. A tabela abaixo fica como referência do que o
> Ploomes escreve. Além destes rótulos, o normalizador aceita o valor canônico
> direto (o caso do campo `Estrutura Requisição`) e tem heurística por
> palavra-chave — "Cobertura em telha ceramica portuguesa" cai em
> `tile_ceramic`. Quando não reconhece, devolve vazio em vez de chutar.

| Ploomes | fixing_type |
|---|---|
| Telhado Cerâmico | `tile_ceramic` |
| Telhado Fibrocimento Terça Madeira | `tile_fiber_wood` |
| Telhado Fibrocimento Terça Metálica | `tile_fiber_metal` |
| Telhado Metálico Ondulado | `tile_metal_long` |
| Telhado Metálico Mini Trilho (0,55m/2,40m) baixo | `tile_metal_mini` |
| Telhado Metálico Mini Trilho (0,55m/2,40m) alto | `tile_metal_mini_high` |
| Telhado Zipado | `tile_zipped` |
| Laje em Retrato | `slab_portrait` |
| Especial Solo Pratyc / Solo Fixo Pratyc / Solo Fixo | `ground_pratyc` |
| Micro Metal, Telhado Shingle | *(sem mapeamento — ignorados)* |

## Script

```html
<div id="mb-widget" style="font-family: sans-serif;">
  <button id="mb-pull" type="button"
    style="width:100%; margin-bottom:8px; padding:12px; font-size:15px; font-weight:700; color:#fff; background:#0d7a5f; border:none; border-radius:8px; cursor:pointer;">
    ⟳ Puxar valores da proposta
  </button>
  <div id="mb-diag" style="display:none; margin-bottom:8px; padding:8px 10px; background:#f4f6f5; border:1px solid #dde; border-radius:6px; font-size:12px; color:#444;"></div>
  <iframe id="mb-iframe" style="width:100%; height:900px; border:1px solid #ddd; border-radius:8px;"></iframe>
</div>

<script>
(function () {
  var EMBED_BASE = 'https://calculadora-meu-bess.vercel.app/embed/ploomes';

  var FIELD_KEYS = {
    // ENTRADA — texto primeiro (TypeId 1, o input entrega o valor direto);
    // os campos de opção (TypeId 7) ficam como fallback.
    cidade_texto: 'quote_53F02E1F-BFDC-4E72-8A23-6579F5F398DE',
    cidade: 'quote_5C6A4269-9DC8-412D-AF05-FF686E5EE40A',
    estrutura_texto: 'quote_AB306D98-5217-4349-B346-F676C425622C',
    estrutura_texto_alt: 'quote_87A55C82-A2FF-4733-8B09-E6EF0078FA01',
    estrutura: 'quote_EBCA6669-E2BF-4413-A1DD-DB502E5373BA',
    potencia: 'quote_75B0AB94-48A6-4FDE-A67B-F09D333CA822',

    kit_descricao: 'quote_8F8080A1-FDF9-4759-BA50-E7A05B8B8F97',
    kit_valor: 'quote_5ABAA79B-230A-4411-8CD2-AFC1E7320D55',
    frete_valor: 'quote_DE6DB76E-330B-42CC-AA12-F7F2C5BB47AD',
    frete_modalidade: 'quote_11FB5869-986E-44DD-92D3-AC9AF25233B3',
    total_geral: 'quote_9C8BDB19-3BD3-47E8-8B0C-E6C454248220',
    itens_kit: 'quote_F026D026-5B7F-44CC-9B98-32635D1A58B5',
  };

  // Sem tabela de de:para aqui de propósito — a tradução Estrutura →
  // fixing_type e Cidade → UF mora no embed (frontend/src/lib/ploomesContext.ts),
  // para não precisar recolar este script quando uma conta escrever diferente.

  function log() {
    try { console.log.apply(console, ['[MeuBESS]'].concat([].slice.call(arguments))); } catch (e) {}
  }

  // ── Leitura ────────────────────────────────────────────────────────────────
  // Campos de opção (TypeId 7 — Cidade, Estrutura) guardam o ID da opção no
  // input; o texto ("LONDRINA-PR") fica num elemento de exibição ao lado.
  // Campos decimais (Potência) trazem o valor direto. Daí a cascata abaixo.
  function ehIdDeOpcao(v) {
    return /^\d{6,}$/.test(String(v == null ? '' : v).trim());
  }

  function textoVisivelProximo(el) {
    var node = el;
    for (var i = 0; i < 5 && node; i++) {
      node = node.parentElement;
      if (!node) break;
      var txt = (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim();
      if (txt && txt.length > 0 && txt.length < 120) return txt;
    }
    return '';
  }

  // Devolve { valor, via } — 'via' alimenta o painel de diagnóstico.
  function readField(key) {
    try {
      var todos = [].slice.call(PloomesDocument.querySelectorAll("[name='" + key + "']"));
      if (!todos.length) return { valor: null, via: 'nenhum elemento com esse name' };

      // 1) <select> nativo: o texto da opção selecionada
      for (var i = 0; i < todos.length; i++) {
        if (todos[i].tagName === 'SELECT') {
          var opt = todos[i].options[todos[i].selectedIndex];
          if (opt && opt.text) return { valor: opt.text, via: 'select' };
        }
      }
      // 2) qualquer elemento cujo value já seja texto (não um id de opção)
      for (var j = 0; j < todos.length; j++) {
        var v = todos[j].value;
        if (v && !ehIdDeOpcao(v)) return { valor: v, via: todos[j].tagName.toLowerCase() + '.value' };
      }
      // 3) só sobrou id de opção → pega o texto exibido ao lado
      for (var k = 0; k < todos.length; k++) {
        if (ehIdDeOpcao(todos[k].value)) {
          var txt = textoVisivelProximo(todos[k]);
          if (txt) return { valor: txt, via: 'texto ao lado (id ' + todos[k].value + ')' };
          return { valor: null, via: 'só o id ' + todos[k].value + ', sem texto legível' };
        }
      }
      // 4) último recurso: textContent do primeiro
      var tc = (todos[0].textContent || '').trim();
      if (tc) return { valor: tc, via: 'textContent' };
      return { valor: null, via: 'encontrado mas vazio' };
    } catch (e) {
      log('erro lendo campo', key, e.message);
      return { valor: null, via: 'erro: ' + e.message };
    }
  }

  // Despeja tudo que casa com um name — usado quando a leitura falha.
  function dumpCampo(key) {
    var els = [].slice.call(PloomesDocument.querySelectorAll("[name='" + key + "']"));
    if (!els.length) return 'nenhum elemento com name=' + key;
    return els.map(function (el, i) {
      return '#' + i + ' <' + el.tagName.toLowerCase() + '>' +
        ' type=' + (el.type || '-') +
        ' value=' + JSON.stringify(el.value == null ? null : String(el.value).slice(0, 40)) +
        ' texto=' + JSON.stringify((el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40));
    }).join(' | ');
  }

  // ── Escrita (native setter p/ inputs controlados por React) ────────────────
  function setValorNativo(el, value) {
    var proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    var descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
    if (descriptor && descriptor.set) descriptor.set.call(el, value);
    else el.value = value;
  }

  function dispararEventos(el) {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function localizarElementoEscrita(key) {
    var el = PloomesDocument.querySelector("input[name='" + key + "']");
    if (el) return { el: el, tipo: 'input' };
    el = PloomesDocument.querySelector("textarea[name='" + key + "']");
    if (el) return { el: el, tipo: 'textarea' };
    el = PloomesDocument.querySelector("[data-field-key='" + key + "'] [contenteditable='true']")
      || PloomesDocument.querySelector("[name='" + key + "'] [contenteditable='true']");
    if (el) return { el: el, tipo: 'contenteditable' };
    return null;
  }

  // ehHtml=true → o conteúdo é markup e precisa ir como innerHTML. O campo
  // "Itens do Kit" é multilinha e só renderiza HTML; com texto puro fica vazio.
  function writeField(key, value, ehHtml) {
    var achado = localizarElementoEscrita(key);
    if (!achado) { log('escrita: campo não encontrado', key); return; }
    var strVal = value == null ? '' : String(value);
    try {
      if (achado.tipo === 'contenteditable') {
        achado.el.focus();
        achado.el.innerHTML = '';
        if (ehHtml) achado.el.innerHTML = strVal;
        else achado.el.textContent = strVal;
        dispararEventos(achado.el);
        achado.el.blur();
      } else {
        achado.el.focus();
        setValorNativo(achado.el, '');
        dispararEventos(achado.el);
        setValorNativo(achado.el, strVal);
        dispararEventos(achado.el);
        achado.el.blur();
      }
      log('escrito', key, '(' + achado.tipo + ')', '=', strVal);
    } catch (e) {
      log('erro escrevendo campo', key, e.message);
    }
  }

  // ── Contexto da proposta → iframe ──────────────────────────────────────────
  // Tenta uma lista de campos em ordem e devolve o primeiro com valor.
  function readPrimeiro(chaves) {
    for (var i = 0; i < chaves.length; i++) {
      var r = readField(chaves[i]);
      if (r.valor != null && String(r.valor).trim() !== '') {
        r.via = r.via + ' [' + chaves[i].slice(6, 14) + ']';
        return r;
      }
    }
    return { valor: null, via: 'vazio em todos os campos tentados' };
  }

  function mostrarDiagnostico(ctx) {
    var diag = document.getElementById('mb-diag');
    diag.style.display = 'block';
    var linhas = [
      '<b>Lido da proposta:</b>',
      'Potência = <code>' + (ctx.kwp || '—') + '</code> <i>(' + ctx.viaKwp + ')</i>',
      'Cidade = <code>' + (ctx.cidade || '—') + '</code> <i>(' + ctx.viaCidade + ')</i>',
      'Estrutura = <code>' + (ctx.estrutura || '—') + '</code> <i>(' + ctx.viaEstrutura + ')</i>'
    ];
    // Quando algo não veio, mostra o DOM cru — é o que permite corrigir o
    // seletor sem mais um ciclo de teste. A tradução acontece no iframe.
    if (!ctx.cidade) linhas.push('<br><b>DOM Cidade (texto):</b> <code>' + dumpCampo(FIELD_KEYS.cidade_texto) + '</code>');
    if (!ctx.estrutura) linhas.push('<br><b>DOM Estrutura (texto):</b> <code>' + dumpCampo(FIELD_KEYS.estrutura_texto) + '</code>');
    diag.innerHTML = linhas.join(' · ');
  }

  function puxarValores() {
    var rKwp = readField(FIELD_KEYS.potencia);
    var rCidade = readPrimeiro([FIELD_KEYS.cidade_texto, FIELD_KEYS.cidade]);
    var rEstrutura = readPrimeiro([
      FIELD_KEYS.estrutura_texto, FIELD_KEYS.estrutura_texto_alt, FIELD_KEYS.estrutura,
    ]);
    var ctx = {
      kwp: rKwp.valor, viaKwp: rKwp.via,
      cidade: rCidade.valor, viaCidade: rCidade.via,
      estrutura: rEstrutura.valor, viaEstrutura: rEstrutura.via,
    };
    log('contexto lido', ctx);
    mostrarDiagnostico(ctx);

    var iframe = document.getElementById('mb-iframe');
    if (iframe.contentWindow) {
      // Texto cru: quem traduz é o embed (ploomesContext.ts).
      iframe.contentWindow.postMessage({
        type: 'ploomes:context',
        kwp: ctx.kwp,
        cidade: ctx.cidade,
        estrutura: ctx.estrutura,
      }, '*');
    }
  }

  // Relê os campos depois de escrever. O "Itens do Kit" saía vazio sem erro
  // nenhum no console; sem esta conferência não dá para saber se o problema é
  // a escrita, o elemento encontrado ou o próprio Ploomes descartando o valor.
  function conferirEscrita(d) {
    var esperado = {
      kit_descricao: d.kit_descricao,
      kit_valor: d.kit_preco_str || d.kit_preco,
      frete_valor: d.frete_valor_str || d.frete_valor,
      frete_modalidade: d.frete_descricao,
      total_geral: d.total_geral_str || d.total_geral,
      itens_kit: d.itens_html || d.itens_texto,
    };
    var linhas = ['<b>Conferência da escrita:</b>'];
    for (var nome in esperado) {
      if (!esperado.hasOwnProperty(nome)) continue;
      var key = FIELD_KEYS[nome];
      var achado = localizarElementoEscrita(key);
      if (!achado) { linhas.push(nome + ': <b>campo não encontrado no DOM</b>'); continue; }
      var atual = achado.tipo === 'contenteditable'
        ? (achado.el.innerHTML || '')
        : (achado.el.value || '');
      var tamEsperado = String(esperado[nome] == null ? '' : esperado[nome]).length;
      var ok = String(atual).trim().length > 0;
      linhas.push(nome + ': ' + (ok ? '✓' : '✗ VAZIO') +
        ' <i>(' + achado.tipo + ', gravado ' + String(atual).length +
        ' de ' + tamEsperado + ' chars)</i>');
    }
    // dump do elemento do multilinha, que é o problemático
    linhas.push('<br><b>DOM Itens do Kit:</b> <code>' + dumpCampo(FIELD_KEYS.itens_kit) + '</code>');
    var diag = document.getElementById('mb-diag');
    diag.style.display = 'block';
    diag.innerHTML = linhas.join(' · ');
  }

  // ── Retorno do iframe → campos da proposta ─────────────────────────────────
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d || typeof d !== 'object') return;

    if (d.type === 'meubess:ready') {
      // iframe montou — envia o contexto automaticamente
      puxarValores();
      return;
    }

    if (d.type === 'meubess:saved') {
      log('resultado recebido', d);
      writeField(FIELD_KEYS.kit_descricao, d.kit_descricao);
      writeField(FIELD_KEYS.kit_valor, d.kit_preco_str || d.kit_preco);
      writeField(FIELD_KEYS.frete_valor, d.frete_valor_str || d.frete_valor);
      writeField(FIELD_KEYS.frete_modalidade, d.frete_descricao);
      writeField(FIELD_KEYS.total_geral, d.total_geral_str || d.total_geral);
      // multilinha: só renderiza HTML
      writeField(FIELD_KEYS.itens_kit, d.itens_html || d.itens_texto, !!d.itens_html);
      conferirEscrita(d);

      var btn = document.getElementById('mb-pull');
      var original = btn.innerHTML;
      btn.innerHTML = '✓ Campos da proposta atualizados';
      btn.style.background = '#0a5c47';
      setTimeout(function () {
        btn.innerHTML = original;
        btn.style.background = '#0d7a5f';
      }, 3000);
    }
  });

  // TEMPORÁRIO — perfil fixo em 'admin' para validar o funcionamento e a
  // passagem de dados de ponta a ponta (catálogo completo, sem filtro por
  // view). Antes de ir para produção multi-conta, trocar para perfil por
  // API key no backend (ver "Modelo multi-conta" no topo do doc).
  document.getElementById('mb-pull').addEventListener('click', puxarValores);
  document.getElementById('mb-iframe').src = EMBED_BASE + '?perfil=admin';
})();
</script>
```

## Teste

1. Abra uma proposta de teste (template 60032074), preencha Cidade, Estrutura
   e Potência adequada.
2. Clique **"⟳ Puxar valores da proposta"** — o painel de diagnóstico mostra o
   que foi lido e mapeado; o iframe atualiza kWp/UF/estrutura sem perder o que
   já estava digitado. Se Cidade/Estrutura aparecerem como `—` no diagnóstico,
   me mande print do painel — é a informação exata que preciso para ajustar o
   seletor de leitura.
3. Adicione cargas (o catálogo agora carrega), busque kits, clique
   **"Aplicar à proposta"** num kit.
4. Confira os 6 campos. Depois clique "Aplicar" em OUTRO kit e confirme que
   TODOS os campos trocaram (não só a descrição).
5. Os campos moeda devem mostrar valores plausíveis (ex. `62.822,49`), sem
   dígitos fantasma.

## Diferenças embed × calculadora completa (intencional)

O embed é uma versão focada no fluxo da proposta: o kWp vem pronto do
Ploomes (não recalcula por consumo/HSP/PR como a página interna), e não há
histórico de cotações. A tabela de cargas agora tem os mesmos subtotais
(Pn/Pp/E + TOTAIS) da versão completa.
