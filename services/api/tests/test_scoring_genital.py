"""
QuantifyU — 生殖器官评分测试
测试 6.5 英寸 (16.5cm) 的完整评分流程

评分规则（来自 ai_scorer.py）：
  男性阴茎长度评分（勃起状态，全球平均 ~13.1cm）:
    - 16.5cm → 高于平均 ~2.6 个标准差 → ~8.5/10
  评分公式: score = 5.0 + (length - 13.1) / 1.3
    16.5cm → 5.0 + (16.5 - 13.1) / 1.3 = 5.0 + 2.6 = 7.6
  加上周长、修饰度等加权 → 最终 genital_score ≈ 7-8/10
"""

import pytest


class TestGenitalScoring:
    """生殖器官评分逻辑测试（纯数值，不依赖数据库）"""

    @staticmethod
    def calculate_penis_length_score(length_cm: float) -> float:
        """
        复现 ai_scorer.py 中的阴茎长度评分公式

        基于全球统计：
        - 平均勃起长度: 13.12cm (Veale et al. 2015 meta-analysis)
        - 标准差: ~1.66cm
        - 评分 0-10 scale

        评分逻辑:
        - 13cm (平均) → 5.0
        - 每多/少 1.3cm → +/- 1 分
        - 上限 10，下限 1
        """
        MEAN = 13.12
        STEP = 1.3  # 约 0.8 SD per point

        score = 5.0 + (length_cm - MEAN) / STEP
        return round(max(1.0, min(10.0, score)), 1)

    @staticmethod
    def calculate_girth_score(girth_cm: float) -> float:
        """
        阴茎周长评分
        平均勃起周长: ~11.66cm (Veale et al. 2015)
        """
        MEAN = 11.66
        STEP = 1.0
        score = 5.0 + (girth_cm - MEAN) / STEP
        return round(max(1.0, min(10.0, score)), 1)

    @staticmethod
    def compute_genital_total(
        length_cm: float = 13.12,
        girth_cm: float = 11.66,
        grooming: int = 3,
        self_rating: int = 5,
    ) -> float:
        """
        加权计算 genital 总分 (/10)

        权重:
        - 长度: 35%
        - 周长: 25%
        - 修饰度: 15% (1-5 → 映射到 0-10)
        - 自评: 25%
        """
        length_score = TestGenitalScoring.calculate_penis_length_score(length_cm)
        girth_score = TestGenitalScoring.calculate_girth_score(girth_cm)
        grooming_score = grooming * 2.0  # 1-5 → 2-10
        self_score = float(self_rating)

        total = (
            length_score * 0.35
            + girth_score * 0.25
            + grooming_score * 0.15
            + self_score * 0.25
        )
        return round(max(0, min(10, total)), 1)

    # ----------------------------------------------------------------
    # 测试用例
    # ----------------------------------------------------------------

    def test_65_inch_length_score(self):
        """
        6.5 英寸 = 16.51cm
        score = 5.0 + (16.51 - 13.12) / 1.3 = 5.0 + 2.61 = 7.6
        """
        score = self.calculate_penis_length_score(16.51)
        assert score == pytest.approx(7.6, abs=0.2)
        assert score > 7.0  # 明显高于平均
        print(f"\n6.5 inch (16.51cm) 长度评分: {score}/10")

    def test_65_inch_full_scoring(self):
        """
        完整 6.5 inch 评分:
        - 勃起长度: 16.51cm → ~7.6
        - 勃起周长: 13.0cm (略粗于平均) → ~6.3
        - 修饰度: 4/5 (良好) → 8.0
        - 自评: 8/10

        加权: 7.6*0.35 + 6.3*0.25 + 8.0*0.15 + 8.0*0.25
             = 2.66 + 1.575 + 1.2 + 2.0
             = 7.435 → 7.4/10
        """
        total = self.compute_genital_total(
            length_cm=16.51,    # 6.5 inches
            girth_cm=13.0,      # ~5.1 inches
            grooming=4,         # 良好修饰
            self_rating=8,      # 自评 8/10
        )

        assert total > 7.0
        assert total < 8.5
        print(f"\n6.5 inch 完整评分: {total}/10")
        print(f"  长度分: {self.calculate_penis_length_score(16.51)}")
        print(f"  周长分: {self.calculate_girth_score(13.0)}")
        print(f"  修饰分: 8.0")
        print(f"  自评分: 8.0")

    def test_average_male(self):
        """平均男性: 5.2 inch (13.1cm)"""
        total = self.compute_genital_total(
            length_cm=13.12, girth_cm=11.66, grooming=3, self_rating=5
        )
        assert total == pytest.approx(5.0, abs=0.5)
        print(f"\n平均值评分: {total}/10")

    def test_below_average(self):
        """低于平均: 4.0 inch (10.2cm)"""
        score = self.calculate_penis_length_score(10.2)
        assert score < 4.0
        print(f"\n4.0 inch (10.2cm) 长度评分: {score}/10")

    def test_well_above_average(self):
        """高于平均: 7.5 inch (19.05cm)"""
        score = self.calculate_penis_length_score(19.05)
        assert score >= 9.0
        print(f"\n7.5 inch (19.05cm) 长度评分: {score}/10")

    def test_score_bounds(self):
        """评分不超出 1-10 范围"""
        assert self.calculate_penis_length_score(5.0) >= 1.0   # 极小
        assert self.calculate_penis_length_score(25.0) <= 10.0  # 极大

    def test_female_breast_scoring(self):
        """
        女性胸部评分（罩杯 + 身材协调性）

        罩杯基础分映射:
          A → 4, B → 5.5, C → 7, D → 8, DD → 8.5
        """
        CUP_SCORES = {
            "A": 4.0, "B": 5.5, "C": 7.0, "D": 8.0,
            "DD": 8.5, "E": 8.0, "F": 7.0,
        }

        # C 罩杯 + 修饰度 3 + 自评 7
        cup_score = CUP_SCORES["C"]
        grooming_score = 3 * 2.0  # → 6.0
        self_score = 7.0

        total = cup_score * 0.40 + grooming_score * 0.25 + self_score * 0.35
        total = round(max(0, min(10, total)), 1)

        assert total > 5.5
        assert total < 8.0
        print(f"\nC 罩杯评分: {total}/10")

    def test_genital_score_in_overall_context(self):
        """
        genital_score 在总分中的权重 (10/100)

        6.5 inch → genital_score ≈ 7.4/10
        总分贡献: 7.4 分 (在 100 分中占 7.4%)
        """
        genital = self.compute_genital_total(
            length_cm=16.51, girth_cm=13.0, grooming=4, self_rating=8
        )

        # 模拟完整评分
        face = 30.0       # /40
        body = 18.0       # /25
        height = 12.0     # /15
        skin_hair = 7.0   # /10
        genital_weighted = genital  # /10

        total = face + body + height + skin_hair + genital_weighted
        assert 60 < total < 90

        print(f"\n完整评分 (含 6.5 inch genital):")
        print(f"  面部:      {face}/40")
        print(f"  身材:      {body}/25")
        print(f"  身高:      {height}/15")
        print(f"  皮肤头发:  {skin_hair}/10")
        print(f"  生殖器官:  {genital_weighted}/10 (6.5 inch)")
        print(f"  ──���──────────────")
        print(f"  总分:      {total}/100")
        print(f"  评级:      {'优秀' if total >= 80 else '良好' if total >= 65 else '一般'}")
