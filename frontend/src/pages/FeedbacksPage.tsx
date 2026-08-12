import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, Mail, MailX } from 'lucide-react'
import { apiGet, apiPatch } from '@/lib/api'

interface Feedback {
  id: string
  criado_em: string
  origem: string
  tipo: string | null
  mensagem: string
  autor_nome: string | null
  autor_email: string | null
  contexto: Record<string, unknown> | null
  url: string | null
  email_enviado: boolean
  email_erro: string | null
  lido: boolean
}

const ROTULO_TIPO: Record<string, string> = {
  dimensionamento: 'Dimensionamento',
  erro: 'Erro',
  melhoria: 'Melhoria',
}

const COR_TIPO: Record<string, string> = {
  dimensionamento: 'bg-amber-100 text-amber-700',
  erro: 'bg-red-100 text-red-700',
  melhoria: 'bg-sky-100 text-sky-700',
}

export function FeedbacksPage() {
  const [soNaoLidos, setSoNaoLidos] = useState(false)
  const [aberto, setAberto] = useState<string | null>(null)
  const qc = useQueryClient()

  const { data: feedbacks = [], isLoading } = useQuery({
    queryKey: ['feedbacks', soNaoLidos],
    queryFn: () => apiGet<Feedback[]>(`/feedback${soNaoLidos ? '?apenas_nao_lidos=true' : ''}`),
  })

  const marcar = useMutation({
    mutationFn: ({ id, lido }: { id: string; lido: boolean }) =>
      apiPatch<Feedback>(`/feedback/${id}/lido?lido=${lido}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['feedbacks'] }),
  })

  const naoLidos = feedbacks.filter(f => !f.lido).length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink">Feedback</h1>
          <p className="text-sm text-ink/50">
            Relatos de quem usa a calculadora — {naoLidos} não lido(s)
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink/70">
          <input type="checkbox" checked={soNaoLidos} onChange={e => setSoNaoLidos(e.target.checked)}
            className="rounded border-ink/30 text-primary focus:ring-primary" />
          Só não lidos
        </label>
      </div>

      {isLoading ? (
        <p className="py-8 text-center text-sm text-ink/40">Carregando…</p>
      ) : feedbacks.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-ink/15 px-4 py-10 text-center text-sm text-ink/40">
          Nenhum feedback {soNaoLidos ? 'não lido' : 'registrado'}.
        </p>
      ) : (
        <div className="space-y-2">
          {feedbacks.map(f => (
            <div key={f.id}
              className={`rounded-2xl border bg-white p-4 shadow-card transition
                ${f.lido ? 'border-ink/10 opacity-70' : 'border-primary/30'}`}>
              <div className="flex flex-wrap items-center gap-2">
                {f.tipo && (
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${COR_TIPO[f.tipo] ?? 'bg-ink/10 text-ink/60'}`}>
                    {ROTULO_TIPO[f.tipo] ?? f.tipo}
                  </span>
                )}
                <span className="rounded-full bg-ink/[0.06] px-2 py-0.5 text-[11px] font-medium text-ink/60">
                  {f.origem === 'embed' ? 'Ploomes' : 'Calculadora'}
                </span>
                <span className="text-xs text-ink/45">
                  {new Date(f.criado_em).toLocaleString('pt-BR')}
                </span>
                {f.autor_nome && <span className="text-xs text-ink/60">· {f.autor_nome}</span>}

                {/* Estado do e-mail à vista: um SMTP quebrado fica invisível se
                    o único sinal for a ausência de mensagem na caixa. */}
                <span className="ml-auto flex items-center gap-1 text-[11px]"
                  title={f.email_erro ?? undefined}>
                  {f.email_enviado
                    ? <><Mail size={13} className="text-green-600" /><span className="text-green-700">enviado</span></>
                    : <><MailX size={13} className="text-ink/30" /><span className="text-ink/40">não enviado</span></>}
                </span>
                <button onClick={() => marcar.mutate({ id: f.id, lido: !f.lido })}
                  className="flex items-center gap-1 rounded-lg border border-ink/15 px-2 py-1 text-[11px]
                             font-medium text-ink/60 hover:border-primary hover:text-primary">
                  <Check size={12} /> {f.lido ? 'Marcar não lido' : 'Marcar lido'}
                </button>
              </div>

              <p className="mt-3 whitespace-pre-wrap text-sm text-ink">{f.mensagem}</p>

              {f.email_erro && (
                <p className="mt-2 flex items-start gap-1.5 text-[11px] text-amber-700">
                  <AlertTriangle size={13} className="mt-px shrink-0" /> {f.email_erro}
                </p>
              )}

              {f.contexto && (
                <div className="mt-3">
                  <button onClick={() => setAberto(aberto === f.id ? null : f.id)}
                    className="text-xs font-medium text-primary hover:underline">
                    {aberto === f.id ? 'Ocultar' : 'Ver'} contexto do cálculo
                  </button>
                  {aberto === f.id && (
                    <pre className="mt-2 max-h-80 overflow-auto rounded-lg bg-paper/70 p-3 text-[11px] leading-relaxed text-ink/70">
                      {JSON.stringify(f.contexto, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
