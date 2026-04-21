#!/usr/bin/env python3
"""
backend/scripts/import_cargas_excel.py

Imports equipment catalog from Excel "Dados de Cargas" sheet into standard_loads.

Usage:
    cd backend
    SUPABASE_DB_URL=postgresql+asyncpg://... python scripts/import_cargas_excel.py \
        --excel /path/to/CALCULADORA\ BACKUP.xlsx

Requires: openpyxl, asyncpg, sqlalchemy
"""
import argparse
import asyncio
import sys

import openpyxl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Column indices in "Dados de Cargas" sheet (0-based)
COL_NOME       = 0   # A: EQUIPAMENTO
COL_IP_IN      = 1   # B: IP/IN
COL_FP         = 2   # C: FP (fator de potência)
COL_PNOM_W     = 3   # D: POT(W)
COL_FD         = 4   # E: FD (fator de demanda)
COL_TDIA       = 5   # F: Hora/d
COL_TRIFASICO  = 6   # G: 3F? (0=mono, 1=tri)
COL_CATEGORIA  = 32  # AG: CAT


def parse_row(row):
    """Return dict or None if row should be skipped."""
    nome = row[COL_NOME]
    if not nome or str(nome).startswith('['):
        return None  # header / empty placeholder

    def safe_float(v, default=1.0):
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def safe_bool(v):
        try:
            return bool(int(v)) if v is not None else False
        except (TypeError, ValueError):
            return False

    fase = 'trifasico' if safe_bool(row[COL_TRIFASICO]) else 'monofasico'
    cat = str(row[COL_CATEGORIA]).strip() if row[COL_CATEGORIA] else 'OUTRO'

    return {
        'nome': str(nome).strip(),
        'ip_in': safe_float(row[COL_IP_IN], 1.0),
        'fator_potencia': safe_float(row[COL_FP], 1.0),
        'potencia_w': safe_float(row[COL_PNOM_W], 0.0),
        'fator_demanda': safe_float(row[COL_FD], 1.0),
        'tdia_horas': safe_float(row[COL_TDIA], 4.0),
        'fase': fase,
        'categoria': cat,
        'tensao': '220',   # default; update manually if needed
        'ativo': True,
    }


async def run(db_url: str, excel_path: str, dry_run: bool):
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb['Dados de Cargas']

    rows_data = []
    for i, row in enumerate(ws.iter_rows(min_row=1, values_only=True)):
        if i == 0:
            continue  # header
        parsed = parse_row(row)
        if parsed:
            rows_data.append(parsed)

    print(f"Found {len(rows_data)} equipment rows to import.")
    if dry_run:
        for r in rows_data[:5]:
            print(" ", r)
        print("  ... (dry run, not inserting)")
        return

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from sqlalchemy import text
    async with async_session() as session:
        # Clear existing catalog entries (re-import is idempotent)
        await session.execute(text("DELETE FROM standard_loads WHERE true"))
        for r in rows_data:
            await session.execute(
                text("""
                    INSERT INTO standard_loads
                      (nome, categoria, potencia_w, fator_potencia,
                       tdia_horas, fator_demanda, ip_in, tensao, fase, ativo)
                    VALUES
                      (:nome, :categoria, :potencia_w, :fator_potencia,
                       :tdia_horas, :fator_demanda, :ip_in, :tensao, :fase, :ativo)
                """),
                r
            )
        await session.commit()
    print(f"Imported {len(rows_data)} rows into standard_loads.")
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Import Excel 'Dados de Cargas' into standard_loads")
    parser.add_argument('--excel', required=True, help='Path to CALCULADORA BACKUP.xlsx')
    parser.add_argument('--db-url', required=True,
                        help='Async DB URL, e.g. postgresql+asyncpg://user:pass@host/db')
    parser.add_argument('--dry-run', action='store_true', help='Preview first 5 rows, no DB changes')
    args = parser.parse_args()
    asyncio.run(run(args.db_url, args.excel, args.dry_run))
