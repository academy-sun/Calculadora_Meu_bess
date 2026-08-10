

class TestConexoesRede:
    """As tensões de conexão vêm do padrão de entrada, não das cargas.

    Um padrão trifásico oferece DUAS conexões: a de linha (entre fases) e a
    de fase (fase-neutro). Numa rede 220/380 cabe tanto um inversor trifásico
    em 380 V quanto monofásicos em 220 V entre fase e neutro — e essa segunda
    opção costuma ser a mais barata. Modelar como valor único descartava ela.
    """
    def test_padrao_trifasico_oferece_as_duas_conexoes(self):
        from app.calculate.service import _conexoes_rede
        assert _conexoes_rede("tri_220_380") == {
            "monofasico": "220",    # fase-neutro
            "trifasico": "380",     # entre fases
        }
        assert _conexoes_rede("tri_127_220") == {
            "monofasico": "127",
            "trifasico": "220",
        }

    def test_padrao_monofasico_nao_aceita_inversor_trifasico(self):
        from app.calculate.service import _conexoes_rede
        assert _conexoes_rede("mono_127") == {"monofasico": "127"}
        assert _conexoes_rede("mono_220") == {"monofasico": "220"}
        assert "trifasico" not in _conexoes_rede("mono_220")

    def test_sem_padrao_assume_mono_220(self):
        from app.calculate.service import _conexoes_rede
        assert _conexoes_rede(None) == {"monofasico": "220"}
        assert _conexoes_rede("") == {"monofasico": "220"}
