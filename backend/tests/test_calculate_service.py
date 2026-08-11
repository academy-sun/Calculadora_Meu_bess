

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
