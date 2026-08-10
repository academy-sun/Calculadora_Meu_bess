

class TestTensaoRede:
    """A tensão de conexão vem do padrão de entrada declarado, não das cargas.

    Os dois caminhos que precisavam dela derivavam por conta própria e cada
    um errava metade dos casos: `"220" in padrao` mandava 380 V para rede
    mono 127; `padrao.startswith("tri")` mandava 380 V para rede 127/220.
    """
    def test_mapeia_os_quatro_padroes(self):
        from app.calculate.service import _tensao_rede
        assert _tensao_rede("mono_127") == "127"
        assert _tensao_rede("mono_220") == "220"
        assert _tensao_rede("tri_127_220") == "220"   # 220 V entre fases
        assert _tensao_rede("tri_220_380") == "380"   # 380 V entre fases

    def test_sem_padrao_assume_220(self):
        from app.calculate.service import _tensao_rede
        assert _tensao_rede(None) == "220"
        assert _tensao_rede("") == "220"
