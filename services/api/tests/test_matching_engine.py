"""
QuantifyU — 匹配引擎测试
加权余弦相似度 + 五维兼容度计算
"""

import pytest

from app.services.matching_engine import (
    CompatibilityResult,
    DailyMatchQueue,
    DIMENSION_MAX,
    DIMENSION_NAMES,
    MatchingEngine,
    PreferenceWeights,
    ScoreVector,
)


@pytest.fixture
def engine():
    return MatchingEngine()


# ================================================================
# ScoreVector 测试
# ================================================================
class TestScoreVector:

    def test_normalization(self):
        """归一化到 [0, 1]"""
        sv = ScoreVector(face=32, body=20, height=12, skin_hair=8, genital=7)
        norm = sv.to_normalized()

        assert norm[0] == pytest.approx(32 / 40, abs=0.01)  # face
        assert norm[1] == pytest.approx(20 / 25, abs=0.01)  # body
        assert norm[2] == pytest.approx(12 / 15, abs=0.01)  # height
        assert norm[3] == pytest.approx(8 / 10, abs=0.01)   # skin_hair
        assert norm[4] == pytest.approx(7 / 10, abs=0.01)   # genital

    def test_total(self):
        sv = ScoreVector(face=32, body=20, height=12, skin_hair=8, genital=7)
        assert sv.total == 79

    def test_from_dict(self):
        d = {
            "face_score": 28,
            "body_score": 18,
            "height_score": 10,
            "skin_hair_score": 7,
            "genital_score": 6.5,
        }
        sv = ScoreVector.from_dict(d)
        assert sv.face == 28
        assert sv.genital == 6.5
        assert sv.total == pytest.approx(69.5)

    def test_from_dict_missing_fields(self):
        """缺失字段默认 0"""
        sv = ScoreVector.from_dict({"face_score": 30})
        assert sv.face == 30
        assert sv.body == 0
        assert sv.genital == 0


# ================================================================
# PreferenceWeights 测试
# ================================================================
class TestPreferenceWeights:

    def test_default_weights_sum_100(self):
        pw = PreferenceWeights()
        assert pw.face + pw.body + pw.height + pw.skin_hair + pw.genital == 100

    def test_normalized_sum_1(self):
        pw = PreferenceWeights(face=40, body=25, height=15, skin_hair=10, genital=10)
        norm = pw.to_normalized()
        assert sum(norm) == pytest.approx(1.0)

    def test_custom_weights(self):
        """用户自定义：更看重面部和身材"""
        pw = PreferenceWeights(face=50, body=30, height=5, skin_hair=5, genital=10)
        norm = pw.to_normalized()
        assert norm[0] == pytest.approx(0.5)  # face
        assert norm[4] == pytest.approx(0.1)  # genital


# ================================================================
# 核心兼容度计算
# ================================================================
class TestMatchingEngine:

    def test_identical_scores_high_compatibility(self, engine):
        """完全相同的评分 → 高兼容度"""
        sv = ScoreVector(face=32, body=20, height=12, skin_hair=8, genital=7)
        weights = PreferenceWeights()

        result = engine.compute_compatibility(
            my_scores=sv,
            their_scores=sv,
            their_weights=weights,
        )

        # 完全相同 → cosine = 1.0
        assert result.cosine_similarity == pytest.approx(1.0, abs=0.01)
        assert result.compatibility_pct > 70

    def test_opposite_scores_lower_compatibility(self, engine):
        """截然不同的评分 → 较低兼容度"""
        user_a = ScoreVector(face=38, body=5, height=3, skin_hair=2, genital=2)
        user_b = ScoreVector(face=5, body=23, height=14, skin_hair=9, genital=9)
        weights = PreferenceWeights()

        result = engine.compute_compatibility(
            my_scores=user_a,
            their_scores=user_b,
            their_weights=weights,
        )

        assert result.compatibility_pct < 70
        assert result.cosine_similarity < 0.9

    def test_genital_65_inch_scoring_example(self, engine):
        """
        🎯 测试用例：6.5英寸生殖器官评分

        场景：
        - 用户A：面部 30/40, 身材 18/25, 身高 12/15, 皮肤 7/10, 生殖器官 7.5/10
          (6.5 inch ≈ 16.5cm, 高于平均 → ~7.5/10)
        - 用户B：面部 28/40, 身材 20/25, 身高 10/15, 皮肤 8/10, 生殖器官 5/10
          (平均水平 → 5/10)
        - B 的偏好权重：面部 35%, 身材 30%, 身高 10%, 皮肤 10%, 生殖器官 15%
          (B 较看重生殖器官维度)
        """
        user_a = ScoreVector(
            face=30, body=18, height=12, skin_hair=7, genital=7.5
        )
        user_b = ScoreVector(
            face=28, body=20, height=10, skin_hair=8, genital=5
        )
        # B 的偏好：genital 权重提高到 15%
        b_weights = PreferenceWeights(
            face=35, body=30, height=10, skin_hair=10, genital=15
        )

        result = engine.compute_compatibility(
            my_scores=user_a,
            their_scores=user_b,
            their_weights=b_weights,
            my_age=25,
            their_age=27,
        )

        # 验证基本结构
        assert 0 <= result.compatibility_pct <= 100
        assert result.algorithm_version == "v2.0-weighted-cosine"
        assert len(result.dimension_scores) == 5
        assert result.explanation != ""
        assert isinstance(result.highlights, list)

        # A 的 genital 维度得分较高 (7.5/10 = 75%)
        assert result.dimension_scores["genital"] == pytest.approx(75.0)

        # A 的 face 维度得分也不错 (30/40 = 75%)
        assert result.dimension_scores["face"] == pytest.approx(75.0)

        # 年龄差 2 岁 → 高年龄兼容
        assert result.age_compatibility > 90

        # 综合兼容度应该不错（相似分布 + 高 genital 匹配 B 的偏好）
        assert result.compatibility_pct > 55

        print(f"\n{'='*60}")
        print(f"6.5 inch (16.5cm) 生殖器官评分测试结果:")
        print(f"{'='*60}")
        print(f"  兼容度: {result.compatibility_pct}%")
        print(f"  余弦相似度: {result.cosine_similarity}")
        print(f"  各维度匹配:")
        for dim, score in result.dimension_scores.items():
            print(f"    {dim}: {score}")
        print(f"  解释: {result.explanation}")
        print(f"  亮点:")
        for h in result.highlights:
            print(f"    - {h}")
        print(f"{'='*60}")

    def test_high_genital_weight_preference(self, engine):
        """用户极度看重生殖器官维度的场景"""
        # A: genital 高分
        user_a = ScoreVector(face=20, body=15, height=10, skin_hair=5, genital=9)
        # B: genital 低分
        user_b = ScoreVector(face=35, body=22, height=13, skin_hair=9, genital=3)
        # B 的偏好：genital 占 40%!
        b_weights = PreferenceWeights(
            face=20, body=15, height=10, skin_hair=15, genital=40
        )

        result = engine.compute_compatibility(
            my_scores=user_a,
            their_scores=user_b,
            their_weights=b_weights,
        )

        # A 在 B 最看重的 genital 维度得分高 (9/10 = 90%)
        assert result.dimension_scores["genital"] == pytest.approx(90.0)

        # 这应该拉高 A 对 B 的兼容度
        assert result.weighted_dot_product > 50

    def test_explanation_text_generated(self, engine):
        """确保生成了解释文本"""
        sv = ScoreVector(face=35, body=22, height=13, skin_hair=9, genital=8)
        result = engine.compute_compatibility(
            my_scores=sv,
            their_scores=sv,
            their_weights=PreferenceWeights(),
        )

        assert len(result.explanation) > 0
        assert len(result.highlights) > 0

    def test_age_compatibility(self):
        """年龄兼容度计算"""
        assert MatchingEngine._age_compatibility(25, 25) == 100.0
        assert MatchingEngine._age_compatibility(25, 27) > 90
        assert MatchingEngine._age_compatibility(20, 35) < 30
        assert MatchingEngine._age_compatibility(None, 25) == 50.0

    def test_distance_score(self):
        """距离评分"""
        assert MatchingEngine._distance_score(1.0) == 100.0
        assert MatchingEngine._distance_score(5.0) > 90
        assert MatchingEngine._distance_score(100.0) < 20
        assert MatchingEngine._distance_score(None) == 50.0

    def test_preference_match(self):
        """偏好匹配度（性别、年龄、looking_for）"""
        prefs = {
            "pref_gender": ["female"],
            "pref_age_min": 22,
            "pref_age_max": 30,
            "pref_looking_for": ["relationship"],
        }
        profile = {
            "gender": "female",
            "age": 25,
            "looking_for": ["relationship", "casual"],
        }

        score = MatchingEngine.calculate_preference_match(prefs, profile)
        assert score > 70  # 性别匹配 + 年龄在范围 + looking_for 有交集

    def test_result_to_db_row(self, engine):
        """结果序列化为 DB 行"""
        result = CompatibilityResult(
            compatibility_pct=78.5,
            cosine_similarity=0.92,
            explanation="面部高度匹配",
            highlights=["面部高度匹配 (75分)"],
        )
        row = MatchingEngine.result_to_db_row(result)

        assert row["compatibility_pct"] == 78.5
        assert row["compatibility_breakdown"]["cosine_similarity"] == 0.92
        assert row["compatibility_breakdown"]["explanation"] == "面部高度匹配"


# ================================================================
# 加权余弦相似度单元测试
# ================================================================
class TestWeightedCosine:

    def test_identical_vectors(self):
        """相同向量 → cos = 1.0"""
        a = [0.8, 0.7, 0.6, 0.5, 0.4]
        w = [0.4, 0.25, 0.15, 0.1, 0.1]
        cos = MatchingEngine._weighted_cosine_similarity(a, a, w)
        assert cos == pytest.approx(1.0, abs=0.001)

    def test_orthogonal_vectors(self):
        """正交向量 → cos ≈ 0"""
        a = [1.0, 0.0, 0.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0, 0.0, 0.0]
        w = [0.2, 0.2, 0.2, 0.2, 0.2]
        cos = MatchingEngine._weighted_cosine_similarity(a, b, w)
        assert cos == pytest.approx(0.0, abs=0.001)

    def test_zero_vector(self):
        """零向量 → cos = 0"""
        a = [0.0, 0.0, 0.0, 0.0, 0.0]
        b = [0.8, 0.7, 0.6, 0.5, 0.4]
        w = [0.2, 0.2, 0.2, 0.2, 0.2]
        cos = MatchingEngine._weighted_cosine_similarity(a, b, w)
        assert cos == 0.0
