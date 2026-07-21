# Script do campo desenvolvedor "MeuBESS BESS — Calculadora" (v3)

Cole o conteúdo abaixo no campo desenvolvedor `MeuBESS BESS — Calculadora`
(`quote_15BBB0B5-5B33-4C28-BB87-AC7EBD45A294`), substituindo a versão anterior.

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
    cidade: 'quote_5C6A4269-9DC8-412D-AF05-FF686E5EE40A',
    estrutura: 'quote_EBCA6669-E2BF-4413-A1DD-DB502E5373BA',
    potencia: 'quote_75B0AB94-48A6-4FDE-A67B-F09D333CA822',

    kit_descricao: 'quote_8F8080A1-FDF9-4759-BA50-E7A05B8B8F97',
    kit_valor: 'quote_5ABAA79B-230A-4411-8CD2-AFC1E7320D55',
    frete_valor: 'quote_DE6DB76E-330B-42CC-AA12-F7F2C5BB47AD',
    frete_modalidade: 'quote_11FB5869-986E-44DD-92D3-AC9AF25233B3',
    total_geral: 'quote_9C8BDB19-3BD3-47E8-8B0C-E6C454248220',
    itens_kit: 'quote_F026D026-5B7F-44CC-9B98-32635D1A58B5',
  };

  var ESTRUTURA_MAP_RAW = {
    'Telhado Cerâmico': 'tile_ceramic',
    'Telhado Fibrocimento Terça Madeira': 'tile_fiber_wood',
    'Telhado Fibrocimento Terça Metálica': 'tile_fiber_metal',
    'Telhado Metálico Ondulado': 'tile_metal_long',
    'Telhado Metálico Mini Trilho - 0,55m - baixo(2cm)': 'tile_metal_mini',
    'Telhado Metálico Mini Trilho Longo - 2,40m - baixo(2cm)': 'tile_metal_mini',
    'Telhado Metálico Mini Trilho - 0,55m - alto(10cm)': 'tile_metal_mini_high',
    'Telhado Metálico Mini Trilho Longo - 2,40m - alto(10cm)': 'tile_metal_mini_high',
    'Telhado Zipado': 'tile_zipped',
    'Laje em Retrato': 'slab_portrait',
    'Especial Solo Pratyc': 'ground_pratyc',
    'Solo Fixo Pratyc': 'ground_pratyc',
    'Solo Fixo': 'ground_pratyc'
  };

  function normalizarTexto(s) {
    if (!s) return '';
    return s.replace(/\s+/g, ' ').trim().toLowerCase();
  }

  var ESTRUTURA_MAP = {};
  for (var k in ESTRUTURA_MAP_RAW) {
    if (ESTRUTURA_MAP_RAW.hasOwnProperty(k)) ESTRUTURA_MAP[normalizarTexto(k)] = ESTRUTURA_MAP_RAW[k];
  }

  function log() {
    try { console.log.apply(console, ['[MeuBESS]'].concat([].slice.call(arguments))); } catch (e) {}
  }

  // ── Leitura (com fallback de seletor para campos de opções) ────────────────
  function readField(key) {
    try {
      var el = PloomesDocument.querySelector("input[name='" + key + "']")
        || PloomesDocument.querySelector("select[name='" + key + "']")
        || PloomesDocument.querySelector("[name='" + key + "']");
      if (!el) { log('leitura: elemento não encontrado', key); return null; }
      if (el.tagName === 'SELECT') {
        var opt = el.options[el.selectedIndex];
        return opt ? opt.text : el.value;
      }
      return el.value != null ? el.value : el.textContent;
    } catch (e) {
      log('erro lendo campo', key, e.message);
      return null;
    }
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

  function writeField(key, value) {
    var achado = localizarElementoEscrita(key);
    if (!achado) { log('escrita: campo não encontrado', key); return; }
    var strVal = value == null ? '' : String(value);
    try {
      if (achado.tipo === 'contenteditable') {
        achado.el.focus();
        achado.el.innerHTML = '';
        achado.el.textContent = strVal;
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
  function extrairUF(cidadeRaw) {
    if (!cidadeRaw) return '';
    var m = cidadeRaw.match(/-\s*([A-Za-z]{2})\s*$/);
    return m ? m[1].toUpperCase() : '';
  }

  function mapEstrutura(estruturaRaw) {
    if (!estruturaRaw) return '';
    return ESTRUTURA_MAP[normalizarTexto(estruturaRaw)] || '';
  }

  function mostrarDiagnostico(ctx) {
    var diag = document.getElementById('mb-diag');
    diag.style.display = 'block';
    diag.innerHTML =
      '<b>Lido da proposta:</b> ' +
      'Potência = <code>' + (ctx.kwp || '—') + '</code> · ' +
      'Cidade = <code>' + (ctx.cidade || '—') + '</code> → UF <b>' + (ctx.uf || '?') + '</b> · ' +
      'Estrutura = <code>' + (ctx.estrutura || '—') + '</code> → <b>' + (ctx.fixingType || 'sem mapeamento') + '</b>';
  }

  function puxarValores() {
    var ctx = {
      kwp: readField(FIELD_KEYS.potencia),
      cidade: readField(FIELD_KEYS.cidade),
      estrutura: readField(FIELD_KEYS.estrutura),
    };
    ctx.uf = extrairUF(ctx.cidade);
    ctx.fixingType = mapEstrutura(ctx.estrutura);
    log('contexto lido', ctx);
    mostrarDiagnostico(ctx);

    var iframe = document.getElementById('mb-iframe');
    if (iframe.contentWindow) {
      iframe.contentWindow.postMessage({
        type: 'ploomes:context',
        kwp: ctx.kwp,
        uf: ctx.uf,
        fixing_type: ctx.fixingType,
      }, '*');
    }
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
      writeField(FIELD_KEYS.itens_kit, d.itens_texto);

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

  document.getElementById('mb-pull').addEventListener('click', puxarValores);
  document.getElementById('mb-iframe').src = EMBED_BASE + '?perfil=consultor';
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
