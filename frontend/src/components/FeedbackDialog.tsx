import { useState } from 'react'
import { MessageSquarePlus, X } from 'lucide-react'
import { apiPost } from '@/lib/api'

const TIPOS = [
  { v: 'dimensionamento', label: 'Problema no dimensionamento' },
  { v: 'erro', label: 'Erro / algo quebrado' },
  { v: 'melhoria', label: 'Sugestão de melhoria' },
] as const

interface Props {
  origem: 'embed' | 'interna'
  /** Entradas do cálculo e kit na tela. Vai junto com o relato porque
   *  "o dimensionamento está errado" sem os números não dá para reproduzir. */
  contexto?: Record<string, unknown>
  autorNome?: string
  autorEmail?: string
  /** Embed autentica por API key; a calculadora interna, por sessão. */
  porApiKey?: boolean
}

export function FeedbackDialog({ origem, contexto, autorNome, autorEmail, porApiKey = false }: Props) {
  const [aberto, setAberto] = useState(false)
  const [tipo, setTipo] = useState<string>('dimensionamento')
  const [mensagem, setMensagem] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<{ ok: boolean; email: boolean } | null>(null)

  async function enviar() {
    if (mensagem.trim().length < 3) return
    setEnviando(true)
    try {
      const r = await apiPost<{ id: string; email_enviado: boolean }>('/feedback', {
        origem, tipo, mensagem,
        autor_nome: autorNome || null,
        autor_email: autorEmail || null,
        contexto: contexto ?? null,
        url: window.location.href,
      }, porApiKey)
      setResultado({ ok: true, email: r.email_enviado })
      setMensagem('')
    } catch {
      setResultado({ ok: false, email: false })
    } finally {
      setEnviando(false)
    }
  }

  function fechar() {
    setAberto(false)
    setResultado(null)
  }

  return (
    <>
      <button type="button" onClick={() => setAberto(true)}
        className="flex items-center gap-1.5 rounded-lg border border-ink/15 px-3 py-1.5
                   text-xs font-medium text-ink/60 transition hover:border-primary hover:text-primary">
        <MessageSquarePlus size={14} /> Relatar problema
      </button>

      {aberto && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-card ring-1 ring-ink/10">
            <div className="flex items-center justify-between border-b border-ink/10 px-5 py-4">
              <h3 className="font-display text-base font-semibold">Relatar problema ou sugestão</h3>
              <button onClick={fechar} className="text-ink/40 hover:text-ink"><X size={18} /></button>
            </div>

            {resultado?.ok ? (
              <div className="space-y-3 px-5 py-6">
                <p className="text-sm font-medium text-green-700">Recebido. Obrigado!</p>
                <p className="text-xs text-ink/50">
                  {/* O registro é a fonte da verdade: dizer "enviamos por e-mail"
                      quando o SMTP falhou seria mentir para quem escreveu. */}
                  {resultado.email
                    ? 'O relato foi enviado por e-mail para a equipe.'
                    : 'O relato foi registrado e aparece na caixa de entrada da equipe.'}
                </p>
                <button onClick={fechar}
                  className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-dark">
                  Fechar
                </button>
              </div>
            ) : (
              <div className="space-y-3 px-5 py-4">
                <div>
                  <label className="mb-1 block text-xs font-semibold text-ink/60">Tipo</label>
                  <select value={tipo} onChange={e => setTipo(e.target.value)}
                    className="w-full rounded-lg border border-ink/15 px-2 py-1.5 text-sm focus:border-primary focus:outline-none">
                    {TIPOS.map(t => <option key={t.v} value={t.v}>{t.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-semibold text-ink/60">O que aconteceu?</label>
                  <textarea value={mensagem} onChange={e => setMensagem(e.target.value)} rows={6}
                    autoFocus maxLength={5000}
                    placeholder="Descreva o que você esperava e o que apareceu."
                    className="w-full rounded-lg border border-ink/15 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
                </div>
                {contexto && (
                  <p className="rounded-lg bg-paper/60 px-3 py-2 text-[11px] text-ink/50">
                    As entradas e o kit desta tela vão junto, para a equipe reproduzir o caso.
                  </p>
                )}
                {resultado && !resultado.ok && (
                  <p className="text-xs text-red-600">
                    Não foi possível enviar. Tente novamente em instantes.
                  </p>
                )}
                <button onClick={enviar} disabled={enviando || mensagem.trim().length < 3}
                  className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white
                             transition hover:bg-primary-dark disabled:opacity-50">
                  {enviando ? 'Enviando…' : 'Enviar'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
