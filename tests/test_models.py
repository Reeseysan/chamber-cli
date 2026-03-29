from chamber.models import Persona, Message, ConsensusResult, Session


def test_persona_creation():
    p = Persona(
        name="Alice Chen",
        role="Constitutional Lawyer",
        expertise="First Amendment case law",
        avatar_emoji="⚖️",
        system_prompt="You are Alice Chen, a Constitutional Lawyer.",
    )
    assert p.name == "Alice Chen"
    assert p.role == "Constitutional Lawyer"
    assert p.system_prompt.startswith("You are Alice Chen")


def test_persona_default_system_prompt():
    p = Persona(name="Bob", role="Engineer", expertise="Systems", avatar_emoji="🔧")
    assert p.system_prompt == ""


def test_message_creation():
    m = Message(agent_name="Alice Chen", role="expert", content="My analysis is...", round_number=1)
    assert m.agent_name == "Alice Chen"
    assert m.role == "expert"
    assert m.round_number == 1
    assert m.id  # auto-generated


def test_message_defaults():
    m = Message(agent_name="User", role="user", content="topic")
    assert m.round_number == 0
    assert m.session_id == ""


def test_consensus_result_defaults():
    c = ConsensusResult()
    assert c.reached is False
    assert c.summary == ""
    assert c.key_points == []
    assert c.dissenting_views == []


def test_consensus_result_populated():
    c = ConsensusResult(
        reached=True,
        summary="Experts agree on X.",
        key_points=["point 1", "point 2"],
        dissenting_views=["dissent 1"],
    )
    assert c.reached is True
    assert len(c.key_points) == 2


def test_session_creation():
    s = Session()
    assert s.id
    assert s.topic == ""
    assert s.personas == []
    assert s.messages == []
    assert s.current_round == 0
    assert s.status == "idle"


def test_session_with_data():
    p = Persona(name="A", role="R", expertise="E", avatar_emoji="🧑")
    s = Session(topic="Test topic", personas=[p])
    assert s.topic == "Test topic"
    assert len(s.personas) == 1
