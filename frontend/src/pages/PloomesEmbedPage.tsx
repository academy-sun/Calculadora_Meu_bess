import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * Página embed para o campo desenvolvedor do Ploomes (Fase 0 — spike).
 *
 * Carregada dentro de um iframe no formulário do Ploomes:
 *   Ploomes → campo desenvolvedor (sandbox) → <iframe src=".../embed/ploomes?deal_id=123">
 *
 * Objetivos do spike:
 *  1. Confirmar que a página renderiza dentro do sandbox (frame-ancestors ok).
 *  2. Confirmar que o deal_id chega via query string.
 *  3. Confirmar que postMessage atravessa de volta para o campo desenvolvedor
 *     (que então escreve num campo de teste do formulário).
 */
export function PloomesEmbedPage() {
  const [searchParams] = useSearchParams()
  const dealId = searchParams.get('deal_id')
  const [sent, setSent] = useState(false)
  const [ack, setAck] = useState<string | null>(null)

  // Escuta um eventual ACK do campo desenvolvedor (prova de comunicação bidirecional)
  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.data && typeof e.data === 'object' && e.data.type === 'ploomes:ack') {
        setAck(JSON.stringify(e.data))
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  function testarRetorno() {
    window.parent.postMessage(
      {
        type: 'meubess:test',
        deal_id: dealId,
        valor_teste: `Spike OK — ${new Date().toLocaleTimeString('pt-BR')}`,
      },
      '*',
    )
    setSent(true)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper p-6">
      <div className="w-full max-w-md rounded-2xl border border-ink/10 bg-white p-6 shadow-card">
        <h1 className="font-display text-lg font-bold text-ink">MeuBESS — Embed Ploomes</h1>
        <p className="mt-1 text-xs text-ink/50">Spike de validação (Fase 0)</p>

        <div className="mt-4 rounded-xl border border-ink/10 bg-paper/60 px-4 py-3 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink/45">deal_id recebido</p>
          <p className="mt-0.5 font-mono text-base font-bold text-primary">
            {dealId ?? <span className="text-red-500">— ausente na URL —</span>}
          </p>
        </div>

        <button
          onClick={testarRetorno}
          className="mt-4 w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-primary-dark"
        >
          Testar retorno (postMessage)
        </button>

        {sent && (
          <p className="mt-3 rounded-lg bg-green-50 px-3 py-2 text-xs text-green-700">
            Mensagem enviada ao campo desenvolvedor. Verifique se o campo de teste no
            formulário do Ploomes foi preenchido.
          </p>
        )}
        {ack && (
          <p className="mt-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-700 break-all">
            ACK recebido do Ploomes: <span className="font-mono">{ack}</span>
          </p>
        )}
      </div>
    </div>
  )
}
