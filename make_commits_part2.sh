#!/usr/bin/env bash
# -------------------------------------------------------------------------
# ЧАСТЬ 2 (шаги 4-7). Запускай из КОРНЯ репозитория: bash make_commits_part2.sh
# Продолжает с того места, где остановилась часть 1 (после шага 3).
# -------------------------------------------------------------------------
set -euo pipefail

SVC="services/tournament-service"
ROOT="$(pwd)"

echo ">>> Готовлю временное окружение Python (Flask + pytest)..."
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
commit () { git add -A; git commit -qm "$1"; echo ">>> committed: $1"; }
py_edit () {
python3 - "$1" << PYEOF
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
$2
p.write_text(s)
PYEOF
}

# === STEP 4 — запрет разрушительной перегенерации сетки при наличии результатов ===
py_edit "$SVC/app.py" '
old = "    Match.query.filter_by(tournament_id=tournament_id).delete()"
new = """    force = request.args.get(\"force\", \"\").lower() in (\"1\", \"true\", \"yes\")
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
assert s.count(old) == 1, "STEP4 anchor not unique/found"
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
run_tests "4"; commit "fix: block destructive bracket regeneration when results exist"

# === STEP 5 — пагинация списков ===
py_edit "$SVC/app.py" '
old = """    tournaments = Tournament.query.order_by(Tournament.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tournaments]), 200"""
new = """    limit = min(int(request.args.get(\"limit\", 50)), 200)
    offset = int(request.args.get(\"offset\", 0))
    tournaments = (
        Tournament.query.order_by(Tournament.created_at.desc())
        .limit(limit).offset(offset).all()
    )
    return jsonify([t.to_dict() for t in tournaments]), 200"""
assert old in s, "STEP5a not found"
s = s.replace(old, new)
old2 = """    participants = Participant.query.filter_by(tournament_id=tournament_id).all()
    return jsonify([p.to_dict() for p in participants]), 200"""
new2 = """    limit = min(int(request.args.get(\"limit\", 50)), 200)
    offset = int(request.args.get(\"offset\", 0))
    participants = (
        Participant.query.filter_by(tournament_id=tournament_id)
        .limit(limit).offset(offset).all()
    )
    return jsonify([p.to_dict() for p in participants]), 200"""
assert old2 in s, "STEP5b not found"
s = s.replace(old2, new2)
'
cat >> "$SVC/tests/test_app.py" << 'EOF'


def test_tournament_list_pagination(client):
    for i in range(5):
        client.post("/tournaments", json={"name": f"T{i}"})
    res = client.get("/tournaments?limit=2")
    assert res.status_code == 200
    assert len(res.get_json()) == 2
EOF
run_tests "5"; commit "feat: add pagination to tournament and participant lists"

# === STEP 6 — вынести чистую математику сетки в bracket.py ===
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
    """Pad with byes (None) to a power of two; return round-1 (a, b) pairs."""
    size = bracket_size(len(participant_ids))
    padded = list(participant_ids) + [None] * (size - len(participant_ids))
    return [(padded[i * 2], padded[i * 2 + 1]) for i in range(size // 2)]
EOF
py_edit "$SVC/app.py" '
imp = "from flask_sqlalchemy import SQLAlchemy\n"
assert imp in s, "STEP6 import anchor not found"
s = s.replace(imp, imp + "\nfrom bracket import bracket_size, total_rounds, first_round_pairings\n", 1)

old = """    n = len(participant_ids)
    if n < 2:
        raise ValueError(\"Need at least 2 participants to generate a bracket\")

    size = 2 ** math.ceil(math.log2(n))
    padded = participant_ids + [None] * (size - n)

    total_rounds = int(math.log2(size))"""
new = """    size = bracket_size(len(participant_ids))
    padded = list(participant_ids) + [None] * (size - len(participant_ids))
    rounds = total_rounds(len(participant_ids))"""
assert old in s, "STEP6 compute-block anchor not found"
s = s.replace(old, new)

loop = "    for r in range(2, total_rounds + 1):"
assert loop in s, "STEP6 loop anchor not found"
s = s.replace(loop, "    for r in range(2, rounds + 1):")
'
run_tests "6"; commit "refactor: extract pure bracket math into bracket.py"

# === STEP 7 — юнит-тесты на чистую логику сетки ===
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
    assert len(pairings) == 2
    flat = [p for pair in pairings for p in pair]
    assert flat.count(None) == 1


def test_no_byes_for_power_of_two():
    pairings = first_round_pairings(["A", "B", "C", "D"])
    flat = [p for pair in pairings for p in pair]
    assert None not in flat
EOF
run_tests "7"; commit "test: cover bracket engine edge cases (byes, odd counts)"

echo
echo "================ ГОТОВО: ещё 4 коммита (шаги 4-7) ================"
git log --oneline | head -8
