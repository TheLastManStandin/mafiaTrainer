from dataclasses import replace
from pathlib import Path
import json
import random

import pytest
from mafia_trainer.core import (
    ASSETS, CATEGORIES, Library, Question, Session, load_builtin, normalize, select_questions,
)


def sample(**kwargs):
    values=dict(id='custom-test',level=2,topics=['roles'],kind='short',prompt='Кто?',answer='Шериф',explanation='Проверяет цвет.',aliases=['комиссар'])
    values.update(kwargs)
    return Question(**values)


def test_curated_bank_is_complete_and_every_level_covers_all_topics():
    questions=load_builtin()
    assert len(questions)==180
    assert len({q.id for q in questions})==180
    for level in (1,2,3):
        assert sum(q.level==level for q in questions)==60
        for topic in CATEGORIES:
            assert sum(q.level==level and topic in q.topics for q in questions)>=5
    for q in questions:
        assert q.check(q.answer)
        for alias in q.aliases:
            assert q.check(alias)
        if q.source=='Правила Школы 21':assert 3<=q.page<=14


def test_answers_normalize_punctuation_and_yo_but_do_not_guess():
    assert normalize('  ЧЁРНЫЙ! ')=='черный'
    q=sample()
    assert q.check('  КОМИССАР! ')
    assert not q.check('не комиссар')
    assert not q.check('шериф или мафия')
    assert not q.check('')


def test_numeric_set_order_and_duplicate_protection():
    q=sample(answer='2, 5',aliases=[],numeric_set=True)
    assert q.check('№5 и №2')
    assert q.check('5; 2')
    assert not q.check('2, 5, 9')
    assert not q.check('2, 2, 5')
    assert not q.check('2 или 5')
    assert not q.check('5')


def test_filtering_no_duplicates_and_balanced_topics():
    bank=load_builtin()
    picked=select_questions(bank,2,['roles','night','voting'],12,random.Random(1))
    assert len(picked)==12
    assert len({q.id for q in picked})==12
    assert all(q.level==2 and set(q.topics)&{'roles','night','voting'} for q in picked)
    assert {t:sum(t in q.topics for q in picked) for t in ['roles','night','voting']}=={'roles':4,'night':4,'voting':4}
    assert len(select_questions(bank,1,['roles'],30))==6
    assert select_questions(bank,1,[],20)==[]


def test_multiple_tags_do_not_duplicate_questions():
    q=sample(topics=['roles','night'])
    assert select_questions([q],2,['roles','night'],20)==[q]


def test_all_available_and_shuffling():
    bank=load_builtin()
    one=select_questions(bank,3,list(CATEGORIES),0,random.Random(1))
    two=select_questions(bank,3,list(CATEGORIES),0,random.Random(2))
    assert len(one)==60 and len(two)==60
    assert {q.id for q in one}=={q.id for q in two}
    assert one!=two


def test_custom_and_deletion_survive_relaunch_without_saving_results(tmp_path):
    lib=Library(tmp_path);original=lib.active()[0]
    lib.add(sample());lib.delete(original)
    fresh=Library(tmp_path)
    assert len(fresh.active())==180
    assert sample().id in {q.id for q in fresh.active()}
    assert original.id not in {q.id for q in fresh.active()}
    fresh.restore(original.id)
    assert len(Library(tmp_path).active())==181
    assert set(json.loads(fresh.path.read_text()))=={'version','custom','deleted'}


def test_stale_library_instances_preserve_changes_from_both_interfaces(tmp_path):
    desktop = Library(tmp_path)
    browser = Library(tmp_path)
    first, second = desktop.builtin[:2]

    browser.add(sample())
    desktop.delete(first)
    browser.delete(second)
    desktop.restore(first.id)

    saved = Library(tmp_path)
    assert [q.id for q in saved.custom] == [sample().id]
    assert saved.deleted == {second.id}


def test_custom_attachment_is_copied_and_does_not_depend_on_original(tmp_path):
    original=tmp_path/'original.jpg';original.write_bytes((ASSETS/'media/g01.jpg').read_bytes())
    library=Library(tmp_path/'data');q=sample();library.add(q,original)
    assert Path(q.media).is_file() and Path(q.media)!=original
    original.unlink()
    assert Path(Library(tmp_path/'data').custom[0].media).is_file()


def test_invalid_question_never_mutates_disk(tmp_path):
    library=Library(tmp_path)
    with pytest.raises(ValueError):library.add(sample(topics=[]))
    with pytest.raises(ValueError):library.add(sample(kind='choice',options=['A','A','B','C'],answer='A'))
    assert not library.path.exists() and library.custom==[]


def test_save_failure_rolls_back_memory(tmp_path,monkeypatch):
    lib=Library(tmp_path)
    def fail():raise OSError('disk full')
    monkeypatch.setattr(lib,'save',fail)
    with pytest.raises(OSError):lib.delete(lib.builtin[0])
    assert not lib.deleted
    with pytest.raises(OSError):lib.add(sample())
    assert not lib.custom


def test_corrupted_storage_is_preserved(tmp_path):
    path=tmp_path/'library.json';path.write_text('{broken',encoding='utf-8')
    with pytest.raises(ValueError):Library(tmp_path)
    assert path.read_text()=='{broken'


def test_library_initialization_is_read_only(tmp_path):
    Library(tmp_path/'absent')
    assert not (tmp_path/'absent').exists()


def test_session_pending_delete_and_scoring():
    a=sample(id='a');b=sample(id='b',kind='review');s=Session([a,b])
    r=s.submit('комиссар',hinted=True)
    assert r.status=='correct' and r.hinted
    with pytest.raises(ValueError):s.submit('мафия')
    s.delete_current()
    assert s.total==1 and s.current is b and s.results==[] and s.pending is None
    s.submit('Моё объяснение')
    with pytest.raises(ValueError):s.advance()
    s.pending.status='review_repeat';s.advance()
    assert s.current is None and len(s.results)==1


def test_session_skips_and_wrong_answers():
    s=Session([sample(),sample(id='second')])
    assert s.submit('',skip=True).status=='skipped';s.advance()
    assert s.submit('мафия').status=='wrong';s.advance()
    assert len(s.results)==2


def test_delete_last_unanswered_question_yields_no_fake_error():
    s=Session([sample()]);s.delete_current()
    assert not s.current and s.total==0 and s.results==[]
