

class TestConexoesRede:
    """As tensões de conexão vêm do padrão de entrada, não das cargas.

    Cada tipo de inversor tem um CONJUNTO de conexões possíveis, não uma só.
    Numa rede trifásica o monofásico pode ir fase-neutro (tensão de fase) ou
    entre duas fases (tensão de linha) — as duas são conexões reais, e o
    engenheiro confirmou na revisão da matriz que um híbrido monofásico 220 V
    atende uma rede 127/220. Numa rede monofásica só existe uma tensão.
    """
    def test_padrao_trifasico_oferece_as_duas_conexoes(self):
        from app.calculate.service import _conexoes_rede
        assert _conexoes_rede("tri_220_380") == {
            "monofasico": {"220", "380"},   # fase-neutro ou entre fases
            "trifasico": {"380"},           # entre fases
        }
        assert _conexoes_rede("tri_127_220") == {
            "monofasico": {"127", "220"},
            "trifasico": {"220"},
        }

    def test_padrao_monofasico_tem_uma_tensao_so(self):
        from app.calculate.service import _conexoes_rede
        assert _conexoes_rede("mono_127") == {"monofasico": {"127"}}
        assert _conexoes_rede("mono_220") == {"monofasico": {"220"}}

    def test_padrao_monofasico_nao_aceita_inversor_trifasico(self):
        from app.calculate.service import _conexoes_rede
        assert "trifasico" not in _conexoes_rede("mono_220")

    def test_sem_padrao_assume_mono_220(self):
        from app.calculate.service import _conexoes_rede
        assert _conexoes_rede(None) == {"monofasico": {"220"}}


class TestPrecoDefasado:
    """Dois sintomas diferentes, com causas e destinatários diferentes.

    Catálogo velho = o sync parou (plataforma fora, chave revogada, agendador
    morto). Afeta tudo, o consultor precisa saber antes de enviar a proposta.

    Produto congelado = o sync roda bem, mas aquele item saiu da listagem da
    plataforma e ficou com o último preço. Medido em produção: o SIW400H T030
    passou 55 dias assim enquanto os outros 679 atualizavam. A idade do
    catálogo não pega isso, porque ela olha o registro MAIS RECENTE.
    """
    def _prod(self, titulo, horas_atras):
        from datetime import datetime, timedelta, timezone

        class P:
            title = titulo
            last_synced_at = datetime.now(timezone.utc) - timedelta(hours=horas_atras)
        return P()

    def _diag(self, produtos):
        from app.calculate.schemas import CalculateRequest
        from app.calculate.service import _montar_diagnostico
        req = CalculateRequest(
            origem_info={"origem": "interno", "solicitante_id": "t",
                         "solicitante_nome": "t",
                         "solicitado_em": "2026-01-01T00:00:00Z"},
            tipo_calculo="backup", powerpeak_kwp=5.0,
        )
        return _montar_diagnostico([], req, produtos, False)

    def test_catalogo_fresco_nao_avisa(self):
        d = self._diag([self._prod("A", 0.5), self._prod("B", 0.5)])
        assert not any("sincronizado há" in a for a in d.avisos), d.avisos

    def test_sync_parado_avisa_o_consultor(self):
        d = self._diag([self._prod("A", 9), self._prod("B", 9)])
        assert any("sincronizado há" in a for a in d.avisos), d.avisos

    def test_produto_congelado_com_catalogo_fresco(self):
        """O caso real: 679 produtos frescos e um parado há semanas."""
        d = self._diag([self._prod("SIW400H T030", 24 * 55), self._prod("M050", 0.5)])
        assert not any("sincronizado há" in a for a in d.avisos), \
            "catálogo está fresco — não é caso de avisar o consultor"
        assert any("T030" in a and "55 dia" in a for a in d.avisos_internos), \
            d.avisos_internos

    def test_congelado_e_interno_nao_vai_para_o_consultor(self):
        d = self._diag([self._prod("SIW400H T030", 24 * 55), self._prod("M050", 0.5)])
        assert not any("congelado" in a for a in d.avisos), d.avisos
