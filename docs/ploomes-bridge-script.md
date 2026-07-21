# Script do campo desenvolvedor "MeuBESS BESS — Calculadora"

Cole o conteúdo abaixo no campo desenvolvedor `MeuBESS BESS — Calculadora`
(`quote_15BBB0B5-5B33-4C28-BB87-AC7EBD45A294`), no template de proposta
**60032074**, logo após o campo "Potência adequada (kWp)".

## O que o script faz

1. Lê, via `PloomesDocument`, os 3 campos que **já existem** na proposta:
   Cidade, Estrutura, Potência adequada (kWp).
2. Converte Cidade → UF (a opção vem no formato `"NOME-UF"`, ex.
   `"LONDRINA-PR"` — extrai os 2 últimos caracteres) e Estrutura → o
   `fixing_type` interno da calculadora (tabela de-para, validada com o time).
3. Monta o iframe da calculadora (`/embed/ploomes`) já com esses valores na
   query string — nada de API/`deal_id` aqui, tudo em tempo real, mesmo com a
   proposta ainda não salva.
4. Escuta `postMessage` vindo do iframe (`meubess:saved`) e escreve o
   resultado nos 6 campos novos usando `setAttribute` + `dispatchEvent`
   (mesma técnica usada na integração existente do template duplicado —
   engana o Ploomes fazendo-o achar que o vendedor digitou ali).
5. Botão **"↻ Recarregar com valores atuais"**: se o vendedor mudar
   kWp/Cidade/Estrutura depois que o widget já carregou, ele força o iframe a
   reconstruir com os valores novos — evita o bug observado na integração
   antiga (buscar de novo depois de mudar os campos "trava").

## Mapeamento Estrutura → fixing_type

Baseado nas opções reais da conta (12 de 15 mapeadas; ver observações):

| Ploomes | fixing_type |
|---|---|
| Telhado Cerâmico | `tile_ceramic` |
| Telhado Fibrocimento Terça Madeira | `tile_fiber_wood` |
| Telhado Fibrocimento Terça Metálica | `tile_fiber_metal` |
| Telhado Metálico Ondulado | `tile_metal_long` |
| Telhado Metálico Mini Trilho - 0,55m - baixo(2cm) | `tile_metal_mini` |
| Telhado Metálico Mini Trilho Longo - 2,40m - baixo(2cm) | `tile_metal_mini` |
| Telhado Metálico Mini Trilho - 0,55m - alto(10cm) | `tile_metal_mini_high` |
| Telhado Metálico Mini Trilho Longo - 2,40m - alto(10cm) | `tile_metal_mini_high` |
| Telhado Zipado | `tile_zipped` |
| Laje em Retrato | `slab_portrait` |
| Especial Solo Pratyc | `ground_pratyc` |
| Solo Fixo Pratyc | `ground_pratyc` |

**Não mapeados (confirmado com o usuário em 2026-07-21):**
- **Micro Metal** — não aplicável (estrutura para microinversor); sem FV com armazenamento nesse caso, o script ignora e não passa `fixing_type`.
- **Solo Fixo** (sem "Pratyc") — tratado como `ground_pratyc` por aproximação (situação incomum; ajustar depois se necessário).
- **Telhado Shingle** — sem correspondência ainda na calculadora; o script ignora e não passa `fixing_type` (fica sem estrutura selecionada — o vendedor escolhe manualmente dentro do embed se precisar).

## Script

```html
<div id="mb-widget" style="font-family: sans-serif;">
  <div id="mb-toolbar" style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
    <span style="font-size:12px; color:#888;">MeuBESS — Dimensionamento de Armazenamento (BESS)</span>
    <button id="mb-reload" type="button" style="font-size:11px; padding:4px 10px; border-radius:6px; border:1px solid #ccc; background:#f5f5f5; cursor:pointer;">↻ Recarregar com valores atuais</button>
  </div>
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

  // Estrutura Ploomes -> fixing_type da calculadora MeuBESS.
  // 'Micro Metal' (microinversor) e 'Telhado Shingle' ficam de fora de propósito —
  // sem correspondência hoje; 'Solo Fixo' aproximado para ground_pratyc.
  var ESTRUTURA_MAP = {
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

  function log() {
    try { console.log.apply(console, ['[MeuBESS]'].concat([].slice.call(arguments))); } catch (e) {}
  }

  function readField(key) {
    try {
      var el = PloomesDocument.querySelector("input[name='" + key + "']");
      return el ? el.value : null;
    } catch (e) {
      log('erro lendo campo', key, e.message);
      return null;
    }
  }

  function writeField(key, value) {
    try {
      var el = PloomesDocument.querySelector("input[name='" + key + "']");
      if (!el) { log('campo não encontrado para escrita:', key); return; }
      el.setAttribute('value', value == null ? '' : String(value));
      el.dispatchEvent(new InputEvent('input', { bubbles: true }));
    } catch (e) {
      log('erro escrevendo campo', key, e.message);
    }
  }

  function extrairUF(cidadeRaw) {
    if (!cidadeRaw) return '';
    var m = cidadeRaw.match(/-([A-Z]{2})\s*$/);
    return m ? m[1] : '';
  }

  function mapEstrutura(estruturaRaw) {
    if (!estruturaRaw) return '';
    return ESTRUTURA_MAP[estruturaRaw.trim()] || '';
  }

  function montarIframeSrc() {
    var kwp = readField(FIELD_KEYS.potencia);
    var cidade = readField(FIELD_KEYS.cidade);
    var estrutura = readField(FIELD_KEYS.estrutura);
    var uf = extrairUF(cidade);
    var fixingType = mapEstrutura(estrutura);

    var params = [];
    if (kwp) params.push('kwp=' + encodeURIComponent(kwp));
    if (uf) params.push('uf=' + encodeURIComponent(uf));
    if (fixingType) params.push('fixing_type=' + encodeURIComponent(fixingType));
    params.push('perfil=consultor');

    log('prefill', { kwp: kwp, cidade: cidade, uf: uf, estrutura: estrutura, fixingType: fixingType });
    return EMBED_BASE + '?' + params.join('&');
  }

  function carregarIframe() {
    var iframe = document.getElementById('mb-iframe');
    iframe.src = montarIframeSrc();
  }

  window.addEventListener('message', function (e) {
    if (!e.data || e.data.type !== 'meubess:saved') return;
    var d = e.data;
    log('resultado recebido', d);

    writeField(FIELD_KEYS.kit_descricao, d.kit_descricao);
    writeField(FIELD_KEYS.kit_valor, d.kit_preco);
    writeField(FIELD_KEYS.frete_valor, d.frete_valor);
    writeField(FIELD_KEYS.frete_modalidade, d.frete_descricao);
    writeField(FIELD_KEYS.total_geral, d.total_geral);
    writeField(FIELD_KEYS.itens_kit, d.itens_texto);

    var btn = document.getElementById('mb-reload');
    var original = btn.innerHTML;
    var originalBg = btn.style.background;
    btn.innerHTML = '✓ Campos atualizados';
    btn.style.background = '#d4f4dd';
    setTimeout(function () {
      btn.innerHTML = original;
      btn.style.background = originalBg;
    }, 3000);
  });

  document.getElementById('mb-reload').addEventListener('click', carregarIframe);
  carregarIframe();
})();
</script>
```

## Teste após colar

1. Abra uma proposta de teste com o template 60032074, preencha Cidade,
   Estrutura e Potência adequada.
2. O widget deve aparecer logo abaixo, com o iframe já carregado — confira no
   console do navegador a linha `[MeuBESS] prefill {...}` para ver os valores
   lidos e mapeados.
3. Dentro do iframe: adicione cargas de backup (se aplicável), confirme o
   frete, clique "Buscar kits", depois "Aplicar à proposta".
4. Confira se os 6 campos novos foram preenchidos na proposta — **sem
   precisar salvar antes**.
5. Teste o botão "↻ Recarregar com valores atuais" após mudar a Potência
   adequada manualmente — o iframe deve recarregar com o valor novo.

## O que ficou pendente

- `Micro Metal`, `Solo Fixo` (aproximado) e `Telhado Shingle` — revisar o
  de-para de Estrutura conforme mencionado.
- A integração antiga (Buscar Kit / Kit / Resposta API) segue nos campos do
  template original, não usada neste template duplicado — combinado que você
  faz a limpeza depois.
