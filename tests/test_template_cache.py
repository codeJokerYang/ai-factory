from orchestration.schemas import ProductSpec, UserStory
from orchestration.template_cache import match_templates, render_template_context


def _spec(**overrides):
    values = {
        "project_name": "demo",
        "one_liner": "一个轻量工具",
        "target_users": "个人用户",
    }
    values.update(overrides)
    return ProductSpec(**values)


def test_matches_and_ranks_templates_by_distinct_keywords():
    spec = _spec(
        one_liner="带登录的 analytics dashboard",
        core_features=["用户注册", "数据看板"],
    )

    matches = match_templates(spec)

    assert [match.template.id for match in matches] == ["dashboard", "auth"]
    assert matches[0].score == 3
    assert matches[1].score == 2


def test_matches_user_story_and_normalises_full_width_english():
    spec = _spec(
        user_stories=[UserStory(as_a="会员", i_want="完成 ＰＡＹＭＥＮＴ", so_that="开通服务")]
    )

    assert [match.template.id for match in match_templates(spec)] == ["payment"]


def test_ascii_keywords_require_word_boundaries():
    spec = _spec(one_liner="An authoring tool for technical writers")

    assert match_templates(spec) == []


def test_empty_null_and_zero_limit_do_not_match():
    assert match_templates(None) == []
    assert match_templates(_spec(one_liner="", target_users="")) == []
    assert match_templates(_spec(one_liner="登录"), limit=0) == []


def test_out_of_scope_features_do_not_trigger_templates():
    spec = _spec(mvp_out_of_scope=["用户登录", "支付与订阅"])

    assert match_templates(spec) == []


def test_match_limit_cannot_exceed_prompt_safety_cap():
    spec = _spec(core_features=["登录", "支付", "CRUD", "Dashboard"])

    assert len(match_templates(spec, limit=99)) == 2


def test_rendered_context_contains_only_selected_template_guidance():
    context = render_template_context(match_templates(_spec(core_features=["CRUD", "支付"]), limit=1))

    assert "### payment:" in context
    assert "客户端暴露密钥" in context
    assert "### crud:" not in context
