import { useState } from 'react'
import { X } from 'lucide-react'

export function SaveQuoteDialog({ onConfirm, onClose, isPending, initialTitulo, isEdicao }: {
  onConfirm: (titulo: string) => void
  onClose: () => void
  isPending?: boolean
  initialTitulo?: string
  isEdicao?: boolean
}) {
  const [titulo, setTitulo] = useState(initialTitulo ?? '')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!titulo.trim()) return
    onConfirm(titulo.trim())
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-card ring-1 ring-ink/10">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-display text-base font-semibold">{isEdicao ? 'Salvar nova versão' : 'Salvar cotação'}</h3>
          <button type="button" onClick={onClose} className="text-ink/40 hover:text-ink"><X size={18} /></button>
        </div>
        <label className="mb-1.5 block text-sm font-medium text-ink/70">Título da cotação</label>
        <input autoFocus value={titulo} onChange={e => setTitulo(e.target.value)}
          placeholder="ex: Residência João — Backup 2 dias"
          className="w-full rounded-xl border border-ink/15 px-3 py-2.5 text-sm focus:border-primary focus:outline-none" />
        <div className="mt-5 flex gap-2">
          <button type="button" onClick={onClose}
            className="flex-1 rounded-xl border border-ink/15 px-4 py-2.5 text-sm font-medium text-ink/60 hover:bg-paper">
            Cancelar
          </button>
          <button type="submit" disabled={!titulo.trim() || isPending}
            className="flex-1 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-dark disabled:opacity-50">
            {isPending ? 'Salvando…' : 'Confirmar'}
          </button>
        </div>
      </form>
    </div>
  )
}
