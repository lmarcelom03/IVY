from otree.api import *
import random


doc = """
Sección D: cada ítem de probabilidad es precedido por un quiz de conocimiento general (múltiple opción).
Si se acierta el quiz, la urna del ítem correspondiente recibe +1 bola azul.
No se muestra feedback; el ajuste ocurre sólo en servidor.
"""


class C(BaseConstants):
    NAME_IN_URL = 'Seccion_D'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1

    # Urnas base por ítem (P1..P4)
    URNAS = [
        dict(rojas=3, azules=7, condicion=None),
        dict(rojas=2, azules=5, condicion=None),
        dict(rojas=1, azules=8, condicion='ya se extrajeron 2 bolas azules'),
        dict(rojas=3, azules=17, condicion='ya se extrajeron 2 bolas azules'),
    ]

    BONUS_AZUL = 1

    # Pool de preguntas (múltiple opción). 'correcta' es el índice 0..3
    GK_POOL = [
        dict(texto='¿Cuál es la capital de Marruecos?',
             opciones=['Dirham', 'Rabat', 'Casablanca', 'Aziz'], correcta=1),
        dict(texto='¿Qué elemento tiene el símbolo químico Pt?',
             opciones=['Plutonio', 'Platino', 'Paladio', 'Paterón'], correcta=1),
        dict(texto='¿En qué país habitan más musulmanes?',
             opciones=['Emiratos Árabes Unidos', 'Arabia Saudita', 'Indonesia', 'Marruecos'], correcta=2),
        dict(texto='¿Qué mamífero pone huevos?',
             opciones=['Murciélago', 'Pato', 'Ornitorrinco', 'Los mamíferos no ponen huevos'], correcta=2),
        dict(texto='¿En qué parte del cuerpo se produce la insulina?',
             opciones=['Páncreas', 'Hígado', 'Riñones', 'Vejiga'], correcta=0),
        dict(texto='¿Quién pintó "El Grito"?',
             opciones=['Dalí', 'Munch', 'Van Gogh', 'Da Vinci'], correcta=1),
    ]


class Subsession(BaseSubsession):
    def creating_session(subsession):
        pool_n = len(C.GK_POOL)
        if pool_n < 4:
            raise ValueError('GK_POOL debe contener al menos 4 preguntas.')
        for p in subsession.get_players():
            sel = random.sample(range(pool_n), 4)  # sin reemplazo
            p.gk_idx_1, p.gk_idx_2, p.gk_idx_3, p.gk_idx_4 = sel


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    # Probabilidades subjetivas (0–1)
    p_blue_1 = models.FloatField(min=0, max=1, label='')
    p_blue_2 = models.FloatField(min=0, max=1, label='')
    p_blue_3 = models.FloatField(min=0, max=1, label='')
    p_blue_4 = models.FloatField(min=0, max=1, label='')

    # Índices del quiz: inicializamos con -1 (nunca None)
    gk_idx_1 = models.IntegerField(initial=-1)
    gk_idx_2 = models.IntegerField(initial=-1)
    gk_idx_3 = models.IntegerField(initial=-1)
    gk_idx_4 = models.IntegerField(initial=-1)

    # Respuestas del quiz (0..3) -> radios con choices dinámicas
    gk_1_resp = models.IntegerField(label='', widget=widgets.RadioSelect)
    gk_2_resp = models.IntegerField(label='', widget=widgets.RadioSelect)
    gk_3_resp = models.IntegerField(label='', widget=widgets.RadioSelect)
    gk_4_resp = models.IntegerField(label='', widget=widgets.RadioSelect)

    # Flags de acierto (servidor)
    gk_1_ok = models.BooleanField(initial=False)
    gk_2_ok = models.BooleanField(initial=False)
    gk_3_ok = models.BooleanField(initial=False)
    gk_4_ok = models.BooleanField(initial=False)

    # Helpers
    def _gk_ok(self, i: int) -> bool:
        return getattr(self, f'gk_{i + 1}_ok')

    def urna_ajustada(self, i: int) -> dict:
        base = C.URNAS[i]
        rojas = base['rojas']
        azules = base['azules'] + (C.BONUS_AZUL if self._gk_ok(i) else 0)
        total = rojas + azules
        return dict(rojas=rojas, azules=azules, total=total, condicion=base.get('condicion'))

    def _ensure_indices(self) -> None:
        ensure_gk_indices(self)

    def _gk_question(self, i: int) -> dict:
        self._ensure_indices()
        idx = getattr(self, f'gk_idx_{i + 1}')
        return C.GK_POOL[idx]

    # Dynamic choices for quiz questions
    def gk_1_resp_choices(self):
        q = self._gk_question(0)
        return [(i, opt) for i, opt in enumerate(q['opciones'])]

    def gk_2_resp_choices(self):
        q = self._gk_question(1)
        return [(i, opt) for i, opt in enumerate(q['opciones'])]

    def gk_3_resp_choices(self):
        q = self._gk_question(2)
        return [(i, opt) for i, opt in enumerate(q['opciones'])]

    def gk_4_resp_choices(self):
        q = self._gk_question(3)
        return [(i, opt) for i, opt in enumerate(q['opciones'])]


# ---------- Failsafe: asigna índices si siguen en -1 ----------
def ensure_gk_indices(player: Player):
    if player.gk_idx_1 != -1:
        return
    pool_n = len(C.GK_POOL)
    sel = random.sample(range(pool_n), 4)
    player.gk_idx_1, player.gk_idx_2, player.gk_idx_3, player.gk_idx_4 = sel


# =================== PAGES ===================


class Introduction(Page):
    @staticmethod
    def vars_for_template(player: Player):
        return dict(total=len(C.URNAS))

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        ensure_gk_indices(player)


# ---- QUIZ + ÍTEM 1 ----


class Quiz1(Page):
    form_model = 'player'
    form_fields = ['gk_1_resp']

    @staticmethod
    def vars_for_template(player: Player):
        ensure_gk_indices(player)
        q = C.GK_POOL[player.gk_idx_1]
        return dict(numero=1, pregunta_gk=q['texto'], opciones=q['opciones'])

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        q = C.GK_POOL[player.gk_idx_1]
        player.gk_1_ok = player.gk_1_resp == q['correcta']


class Pregunta1(Page):
    form_model = 'player'
    form_fields = ['p_blue_1']

    @staticmethod
    def vars_for_template(player: Player):
        u = player.urna_ajustada(0)
        return dict(numero=1, rojas=u['rojas'], azules=u['azules'], total=u['total'], condicion=u.get('condicion'))


# ---- QUIZ + ÍTEM 2 ----


class Quiz2(Page):
    form_model = 'player'
    form_fields = ['gk_2_resp']

    @staticmethod
    def vars_for_template(player: Player):
        ensure_gk_indices(player)
        q = C.GK_POOL[player.gk_idx_2]
        return dict(numero=2, pregunta_gk=q['texto'], opciones=q['opciones'])

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        q = C.GK_POOL[player.gk_idx_2]
        player.gk_2_ok = player.gk_2_resp == q['correcta']


class Pregunta2(Page):
    form_model = 'player'
    form_fields = ['p_blue_2']

    @staticmethod
    def vars_for_template(player: Player):
        u = player.urna_ajustada(1)
        return dict(numero=2, rojas=u['rojas'], azules=u['azules'], total=u['total'], condicion=u.get('condicion'))


# ---- QUIZ + ÍTEM 3 ----


class Quiz3(Page):
    form_model = 'player'
    form_fields = ['gk_3_resp']

    @staticmethod
    def vars_for_template(player: Player):
        ensure_gk_indices(player)
        q = C.GK_POOL[player.gk_idx_3]
        return dict(numero=3, pregunta_gk=q['texto'], opciones=q['opciones'])

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        q = C.GK_POOL[player.gk_idx_3]
        player.gk_3_ok = player.gk_3_resp == q['correcta']


class Pregunta3(Page):
    form_model = 'player'
    form_fields = ['p_blue_3']

    @staticmethod
    def vars_for_template(player: Player):
        u = player.urna_ajustada(2)
        return dict(numero=3, rojas=u['rojas'], azules=u['azules'], total=u['total'], condicion=u.get('condicion'))


# ---- QUIZ + ÍTEM 4 ----


class Quiz4(Page):
    form_model = 'player'
    form_fields = ['gk_4_resp']

    @staticmethod
    def vars_for_template(player: Player):
        ensure_gk_indices(player)
        q = C.GK_POOL[player.gk_idx_4]
        return dict(numero=4, pregunta_gk=q['texto'], opciones=q['opciones'])

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        q = C.GK_POOL[player.gk_idx_4]
        player.gk_4_ok = player.gk_4_resp == q['correcta']


class Pregunta4(Page):
    form_model = 'player'
    form_fields = ['p_blue_4']

    @staticmethod
    def vars_for_template(player: Player):
        u = player.urna_ajustada(3)
        return dict(numero=4, rojas=u['rojas'], azules=u['azules'], total=u['total'], condicion=u.get('condicion'))


page_sequence = [
    Introduction,
    Quiz1, Pregunta1,
    Quiz2, Pregunta2,
    Quiz3, Pregunta3,
    Quiz4, Pregunta4,
]
