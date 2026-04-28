// frontend/src/components/CityCombobox.tsx
import { useState, useRef, useEffect } from 'react'
import irradiacaoData from '@/data/irradiacao.json'

interface City {
  nome: string
  estado: string
  sigla: string
  hsp: number
}

const CITIES = irradiacaoData as City[]

interface Props {
  value: string
  onSelect: (city: City) => void
  placeholder?: string
}

export function CityCombobox({ value, onSelect, placeholder = 'Buscar cidade...' }: Props) {
  const [query, setQuery] = useState(value)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => { setQuery(value) }, [value])

  const filtered = query.length < 2
    ? []
    : CITIES.filter(c => {
        const q = query.toLowerCase()
        return (
          c.nome.toLowerCase().includes(q) ||
          c.sigla.toLowerCase().includes(q) ||
          c.estado.toLowerCase().includes(q)
        )
      }).slice(0, 30)

  function handleSelect(city: City) {
    setQuery(`${city.nome} - ${city.sigla}`)
    setOpen(false)
    onSelect(city)
  }

  return (
    <div ref={ref} className="relative">
      <input
        type="text"
        value={query}
        onChange={e => { setQuery(e.target.value); setOpen(true) }}
        onFocus={() => { if (query.length >= 2) setOpen(true) }}
        placeholder={placeholder}
        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
        autoComplete="off"
      />
      {open && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
          {filtered.map(city => (
            <li
              key={`${city.nome}-${city.sigla}`}
              onMouseDown={() => handleSelect(city)}
              className="cursor-pointer px-3 py-2 text-sm hover:bg-primary/5"
            >
              <span className="font-medium">{city.nome}</span>
              <span className="ml-1 text-gray-400 text-xs">— {city.sigla} · {city.hsp} HSP</span>
            </li>
          ))}
        </ul>
      )}
      {open && query.length >= 2 && filtered.length === 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-400 shadow-lg">
          Nenhuma cidade encontrada
        </div>
      )}
    </div>
  )
}
