"""
Generates frontend/src/data/irradiacao.json from the uploaded irradiacao.txt file.

Usage:
    python frontend/scripts/generate_irradiacao.py \
        --input /path/to/irradiacao.txt \
        --output frontend/src/data/irradiacao.json
"""
import argparse
import json
import re
import sys


def parse_irradiacao(input_path: str) -> list[dict]:
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract the JS array from the function body
    match = re.search(r'const Dados = (\[)', content)
    if not match:
        print("ERROR: Could not find 'const Dados = [' in input file", file=sys.stderr)
        sys.exit(1)

    # Find the matching closing bracket
    start = match.start(1)
    bracket_count = 0
    in_string = False
    escape = False

    for i in range(start, len(content)):
        char = content[i]

        if escape:
            escape = False
            continue

        if char == '\\':
            escape = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if not in_string:
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    raw_json = content[start:i+1]
                    break
    else:
        print("ERROR: Could not find closing bracket for array", file=sys.stderr)
        sys.exit(1)

    data = json.loads(raw_json)

    cities = []
    for item in data:
        mes_a_mes = item.get('Mês a mês', '')
        parts = mes_a_mes.split(';')
        if not parts:
            continue
        hsp_str = parts[-1].strip().replace(',', '.')
        try:
            hsp = float(hsp_str)
        except ValueError:
            continue

        sigla = item.get('Sigla', '').lstrip('-').strip()

        cities.append({
            'nome': item.get('Nome', '').strip(),
            'estado': item.get('Estado', '').strip(),
            'sigla': sigla,
            'hsp': hsp,
        })

    return cities


def main():
    parser = argparse.ArgumentParser(description='Generate irradiacao.json from irradiacao.txt')
    parser.add_argument('--input', required=True, help='Path to irradiacao.txt')
    parser.add_argument('--output', required=True, help='Path to output irradiacao.json')
    args = parser.parse_args()

    cities = parse_irradiacao(args.input)
    print(f"Parsed {len(cities)} cities")

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(cities, f, ensure_ascii=False, separators=(',', ':'))

    print(f"Written to {args.output}")


if __name__ == '__main__':
    main()
