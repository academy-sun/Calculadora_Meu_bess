"""Perfil de visualização: o que cada origem pode ver da resposta do cálculo.

A separação é feita AQUI, no servidor, e não na tela. Esconder no frontend
deixaria os valores na resposta HTTP, visíveis na aba Network do navegador —
seria aparência de confidencialidade. Com o filtro no servidor, o dado
confidencial não sai daqui.

Como o perfil é resolvido hoje: pela chave de API que assinou a requisição.
O campo desenvolvedor de admin no Ploomes carrega a chave de admin, o campo
do usuário final carrega a chave restrita, e o Ploomes esconde o campo de
admin dos demais perfis. Editar o JavaScript do campo não escala privilégio,
porque a resposta completa exige uma chave que o usuário final não tem.

Como vai ser resolvido quando houver alçada na calculadora interna: pelo
papel no JWT, mapeado para o mesmo enum. Só a função `resolver` muda — o
filtro, a URL do embed e os scripts do Ploomes ficam intocados.
"""

from typing import Literal

from app.calculate.schemas import CalculateResponse, Diagnostico
from app.config import settings

Perfil = Literal["completo", "restrito"]


def resolver(api_key: str | None) -> Perfil:
    """Perfil de quem fez a requisição.

    Fecha em "restrito" quando não reconhece a chave: uma chave nova, ou uma
    variável de ambiente esquecida no deploy, não pode virar acesso completo
    por omissão.
    """
    if api_key and api_key == settings.api_key_embed_restrito:
        return "restrito"
    if api_key and api_key in {settings.api_key_ploomes, settings.api_key_embed}:
        return "completo"
    return "restrito"


def _limpar_kit(kit) -> None:
    """Tira do kit tudo que é valor em reais, menos o total com frete."""
    if kit is None:
        return
    kit.preco_total = 0.0          # o campo é obrigatório no schema; zera o valor
    kit.frete_valor = None
    kit.economia_mensal_rs = None
    kit.payback_anos = None
    # Vocabulário interno do motor ("dc" / "split" / "scaled") — só confunde
    # quem não conhece o algoritmo.
    kit.rotulo_caminho = None
    # Os alertas são de engenharia (desequilíbrio entre fases, confirmação de
    # carga bifásica) e o usuário final não tem como respondê-los. Os casos
    # perigosos de verdade já são BLOQUEIO no motor (R7/R8), não dependem de
    # alguém ler aviso. Continuam visíveis no perfil completo.
    kit.alertas = None
    for item in kit.itens or []:
        item.preco_unitario = 0.0
        item.preco_total = 0.0


def aplicar(resp: CalculateResponse, perfil: Perfil) -> CalculateResponse:
    """Devolve a resposta filtrada para o perfil. 'completo' passa intacta."""
    resp.perfil = perfil
    if perfil == "completo":
        return resp

    _limpar_kit(resp.kit_selecionado)
    for alt in resp.alternativas:
        _limpar_kit(alt)

    # Do diagnóstico sai o que é catálogo: `descartados` lista todo produto
    # avaliado com marca e motivo, e `avisos_internos` aponta buraco de
    # cadastro nosso.
    #
    # Os `avisos` FICAM. São eles que dizem "preço sincronizado há N horas,
    # confira antes de enviar" e "a carga veio sem tensão, a compatibilidade
    # não foi verificada" — falam da cotação que a pessoa está prestes a
    # mandar para o cliente. Justamente quem só tem o campo restrito é quem
    # mais precisa vê-los.
    if resp.diagnostico:
        resp.diagnostico = Diagnostico(avisos=resp.diagnostico.avisos)

    # Frete detalhado: valor separado, percentual por UF e piso mínimo. O que
    # sobra do frete é a modalidade e a UF, que a proposta precisa exibir.
    if resp.frete:
        resp.frete = {
            k: v for k, v in resp.frete.items()
            if k in ("uf", "tipo", "modalidade")
        } or None

    resp.economia_mensal_rs = None
    resp.economia_anual_rs = None
    resp.payback_meses = None

    if resp.solar_dimensionamento:
        resp.solar_dimensionamento.preco_modulos_total = 0.0

    return resp
