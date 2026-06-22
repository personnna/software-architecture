#!/usr/bin/env bash
# -------------------------------------------------------------------------
# Запусти этот файл из КОРНЯ репозитория:  bash make_commits.sh
# Он по очереди вносит изменения, прогоняет тесты и делает отдельный
# коммит на каждый шаг. Если тесты на каком-то шаге падают — скрипт
# останавливается, ничего не коммитит, и ты видишь, на чём встал.
# -------------------------------------------------------------------------
set -euo pipefail

SVC="services/tournament-service"
ROOT="$(pwd)"

# --- готовим временное окружение Python (вне репозитория, в коммиты не попадёт) ---
echo ">>> Создаю временное окружение Python и ставлю Flask + pytest..."
VENV="$(mktemp -d)/venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q Flask Flask-SQLAlchemy pytest
PYBIN="$VENV/bin/python"
echo ">>> Окружение готово."

run_tests () {
  ( cd "$SVC" && rm -f tournament.db && PYTHONPATH=. "$PYBIN" -m pytest -q -p no:cacheprovider ) \
    || { echo "!!! Тесты упали на шаге: $1 — коммит НЕ сделан"; exit 1; }
}

commit () {
  git add -A
  git commit -qm "$1"
  echo ">>> committed: $1"
}

py_edit () {  # py_edit <file> <python-snippet-that-uses var s and rewrites file>
  python3 - "$1" << PYEOF
import sys, pathlib
p = pathlib.Path(sys.argv[1])
s = p.read_text()
$2
p.write_text(s)
PYEOF
}

# =========================================================================
# STEP 1 — запретить повторный счёт уже сыгранного матча
# =========================================================================
py_edit "$SVC/app.py" '
old = """    m = Match.query.get_or_404(match_id)
    data = request.get_json(force=True) or {}

    if m.participant_a_id is None or m.participant_b_id is None:"""
new = """    m = Match.query.get_or_404(match_id)

    if m.status == \"finished\":
        return jsonify({\"error\": \"match already has a final score\"}), 409

    data = request.get_json(force=True) or {}

    if m.participant_a_id is None or m.participant_b_id is None:"""
assert old in s, "STEP1 anchor not found"
s = s.replace(old, new)
'
cat >> "$SVC/tests/test_app.py" << 'EOF'


def test_cannot_rescore_finished_match(client):
    res = client.post("/tournaments", json={"name": "Cup"})
    tid = res.get_json()["id"]
    for n in ["A", "B"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n})
    res = client.post(f"/tournaments/{tid}/generate-bracket")
    match_id = res.get_json()[0]["id"]
    res = client.post(f"/matches/{match_id}/score", json={"score_a": 10, "score_b": 3})
    assert res.status_code == 200
    res = client.post(f"/matches/{match_id}/score", json={"score_a": 5, "score_b": 1})
    assert res.status_code == 409
EOF
run_tests "1"
commit "fix: reject scoring a match that is already finished"

# =========================================================================
# STEP 2 — счёт и продвижение победителя в одной транзакции + блокировка строки
# =========================================================================
py_edit "$SVC/app.py" '
old = """    next_match = Match.query.filter_by(
        tournament_id=tournament_id, round_number=next_round, slot=next_slot
    ).first()"""
new = """    next_match = Match.query.filter_by(
        tournament_id=tournament_id, round_number=next_round, slot=next_slot
    ).with_for_update().first()"""
assert old in s, "STEP2 anchor A not found"
s = s.replace(old, new)
'
py_edit "$SVC/app.py" '
old = """    m.score_a = score_a
    m.score_b = score_b
    m.winner_id = m.participant_a_id if score_a > score_b else m.participant_b_id
    m.status = \"finished\"
    db.session.add(m)
    db.session.commit()

    advance_winner(m.tournament_id, m)
    db.session.commit()

    return jsonify(m.to_dict()), 200"""
new = """    try:
        m.score_a = score_a
        m.score_b = score_b
        m.winner_id = m.participant_a_id if score_a > score_b else m.participant_b_id
        m.status = \"finished\"
        db.session.add(m)
        advance_winner(m.tournament_id, m)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(m.to_dict()), 200"""
assert old in s, "STEP2 anchor B not found"
s = s.replace(old, new)
'
run_tests "2"
commit "fix: wrap score-and-advance in a transaction with row locking"

# =========================================================================
# STEP 3 — турнир автоматически становится finished после финала
# =========================================================================
py_edit "$SVC/app.py" '
old = "    db.session.add(next_match)\n"
new = """    db.session.add(next_match)


def maybe_finish_tournament(tournament_id):
    \"\"\"If the final match is finished, move the tournament to finished.\"\"\"
    last = (
        Match.query.filter_by(tournament_id=tournament_id)
        .order_by(Match.round_number.desc(), Match.slot.desc())
        .first()
    )
    if last and last.status == \"finished\":
        t = Tournament.query.get(tournament_id)
        if t and t.status != \"finished\":
            t.status = \"finished\"
            db.session.add(t)
"""
assert old in s, "STEP3 anchor A not found"
s = s.replace(old, new, 1)
'
py_edit "$SVC/app.py" '
old = """        advance_winner(m.tournament_id, m)
        db.session.commit()"""
new = """        advance_winner(m.tournament_id, m)
        maybe_finish_tournament(m.tournament_id)
        db.session.commit()"""
assert old in s, "STEP3 anchor B not found"
s = s.replace(old, new)
'
cat >> "$SVC/tests/test_app.py" << 'EOF'


def test_tournament_finishes_after_final(client):
    res = client.post("/tournaments", json={"name": "Cup"})
    tid = res.get_json()["id"]
    for n in ["A", "B"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n})
    res = client.post(f"/tournaments/{tid}/generate-bracket")
    final_id = res.get_json()[0]["id"]
    client.post(f"/matches/{final_id}/score", json={"score_a": 10, "score_b": 3})
    res = client.get(f"/tournaments/{tid}")
    assert res.get_json()["status"] == "finished"
EOF
run_tests "3"
commit "feat: auto-finish tournament when the final match completes"

# =========================================================================
# STEP 4 — запретить разрушительную перегенерацию сетки при наличии результатов
# =========================================================================
py_edit "$SVC/app.py" '
old = """    t = Tournament.query.get_or_404(tournament_id)

    Match.query.filter_by(tournament_id=tournament_id).delete()"""
new = """    t = Tournament.query.get_or_404(tournament_id)

    force = request.args.get(\"force\", \"\").lower() in (\"1\", \"true\", \"yes\")
    has_results = (
        Match.query.filter_by(tournament_id=tournament_id, status=\"finished\")
        .filter(Match.winner_id.isnot(None))
        .filter(Match.participant_a_id.isnot(None))
        .first()
        is not None
    )
    if has_results and not force:
        return jsonify({\"error\": \"bracket already has played matches; pass ?force=true to wipe\"}), 409

    Match.query.filter_by(tournament_id=tournament_id).delete()"""
assert old in s, "STEP4 anchor not found"
s = s.replace(old, new)
'
cat >> "$SVC/tests/test_app.py" << 'EOF'


def test_regenerate_blocked_after_results(client):
    res = client.post("/tournaments", json={"name": "Cup"})
    tid = res.get_json()["id"]
    for n in ["A", "B"]:
        client.post(f"/tournaments/{tid}/participants", json={"name": n})
    res = client.post(f"/tournaments/{tid}/generate-bracket")
    final_id = res.get_json()[0]["id"]
    client.post(f"/matches/{final_id}/score", json={"score_a": 10, "score_b": 3})
    res = client.post(f"/tournaments/{tid}/generate-bracket")
    assert res.status_code == 409
    res = client.post(f"/tournaments/{tid}/generate-bracket?force=true")
    assert res.status_code == 201
EOF
run_tests "4"
commit "fix: block destructive bracket regeneration when results exist"

# =========================================================================
# STEP 5 — пагинация на списках турниров и участников
# =========================================================================
py_edit "$SVC/app.py" '
old = """    tournaments = Tournament.query.order_by(Tournament.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tournaments]), 200"""
new = """    limit = min(int(request.args.get(\"limit\", 50)), 200)
    offset = int(request.args.get(\"offset\", 0))
    tournaments = (
        Tournament.query.order_by(Tournament.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return jsonify([t.to_dict() for t in tournaments]), 200"""
assert old in s, "STEP5 anchor A not found"
s = s.replace(old, new)
'
py_edit "$SVC/app.py" '
old = """    participants = Participant.query.filter_by(tournament_id=tournament_id).all()
    return jsonify([p.to_dict() for p in participants]), 200"""
new = """    limit = min(int(request.args.get(\"limit\", 50)), 200)
    offset = int(request.args.get(\"offset\", 0))
    participants = (
        Participant.query.filter_by(tournament_id=tournament_id)
        .limit(limit)
        .offset(offset)
        .all()
    )
    return jsonify([p.to_dict() for p in participants]), 200"""
assert old in s, "STEP5 anchor B not found"
s = s.replace(old, new)
'
cat >> "$SVC/tests/test_app.py" << 'EOF'


def test_tournament_list_pagination(client):
    for i in range(5):
        client.post("/tournaments", json={"name": f"T{i}"})
    res = client.get("/tournaments?limit=2")
    assert res.status_code == 200
    assert len(res.get_json()) == 2
EOF
run_tests "5"
commit "feat: add pagination to tournament and participant lists"

# =========================================================================
# STEP 6 — вынести чистую математику сетки в отдельный модуль bracket.py
# =========================================================================
cat > "$SVC/bracket.py" << 'EOF'
"""
Pure bracket math, decoupled from Flask and the database so it can be
unit-tested on its own (see tests/test_bracket.py).
"""
import math


def bracket_size(n):
    """Next power of two >= n (the padded field size)."""
    if n < 2:
        raise ValueError("Need at least 2 participants to generate a bracket")
    return 2 ** math.ceil(math.log2(n))


def total_rounds(n):
    return int(math.log2(bracket_size(n)))


def first_round_pairings(participant_ids):
    """
    Pad the field with byes (None) to a power of two and return the list of
    (participant_a, participant_b) pairs for round 1.
    """
    size = bracket_size(len(participant_ids))
    padded = list(participant_ids) + [None] * (size - len(participant_ids))
    return [(padded[i * 2], padded[i * 2 + 1]) for i in range(size // 2)]
EOF
py_edit "$SVC/app.py" '
old = """def generate_single_elimination(tournament_id, participant_ids):
    n = len(participant_ids)
    if n < 2:
        raise ValueError(\"Need at least 2 participants to generate a bracket\")

    size = 2 ** math.ceil(math.log2(n))
    padded = participant_ids + [None] * (size - n)

    total_rounds = int(math.log2(size))
    matches = []

    round1 = []
    for slot in range(size // 2):
        a = padded[slot * 2]
        b = padded[slot * 2 + 1]
        m = Match("""
new = """def generate_single_elimination(tournament_id, participant_ids):
    pairings = first_round_pairings(participant_ids)
    size = bracket_size(len(participant_ids))
    rounds = total_rounds(len(participant_ids))
    matches = []

    round1 = []
    for slot, (a, b) in enumerate(pairings):
        m = Match("""
assert old in s, "STEP6 anchor A not found"
s = s.replace(old, new)

old2 = """    matches_per_round = size // 2
    for r in range(2, total_rounds + 1):"""
new2 = """    matches_per_round = size // 2
    for r in range(2, rounds + 1):"""
assert old2 in s, "STEP6 anchor B not found"
s = s.replace(old2, new2)

old3 = "from flask_sqlalchemy import SQLAlchemy\n"
new3 = "from flask_sqlalchemy import SQLAlchemy\n\nfrom bracket import first_round_pairings, bracket_size, total_rounds\n"
assert old3 in s, "STEP6 anchor C not found"
s = s.replace(old3, new3)
'
run_tests "6"
commit "refactor: extract pure bracket math into bracket.py"

# =========================================================================
# STEP 7 — юнит-тесты на чистую логику сетки (баи, нечётное число участников)
# =========================================================================
cat > "$SVC/tests/test_bracket.py" << 'EOF'
import pytest
from bracket import bracket_size, total_rounds, first_round_pairings


def test_power_of_two_field():
    assert bracket_size(2) == 2
    assert bracket_size(4) == 4
    assert bracket_size(5) == 8
    assert bracket_size(8) == 8


def test_rounds_count():
    assert total_rounds(2) == 1
    assert total_rounds(4) == 2
    assert total_rounds(8) == 3


def test_fewer_than_two_raises():
    with pytest.raises(ValueError):
        bracket_size(1)


def test_byes_for_three_participants():
    pairings = first_round_pairings(["A", "B", "C"])
    assert len(pairings) == 2  # padded to 4 -> 2 first-round matches
    flat = [p for pair in pairings for p in pair]
    assert flat.count(None) == 1  # exactly one bye


def test_no_byes_for_power_of_two():
    pairings = first_round_pairings(["A", "B", "C", "D"])
    flat = [p for pair in pairings for p in pair]
    assert None not in flat
EOF
run_tests "7"
commit "test: cover bracket engine edge cases (byes, odd counts)"

echo
echo "================ ГОТОВО: 7 коммитов ================"
git log --oneline | head -8
