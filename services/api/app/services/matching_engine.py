"""
QuantifyU — 智能匹配引擎 v2

核心算法: 加权余弦相似度
  输入: 用户A评分向量 + 用户B评分向量 + B的自定义偏好权重
  输出: 兼容百分比(0-100%) + 人类可读解释文本

五维向量: [face, body, height, skin_hair, genital]
  各维度先归一化到 0-1, 再按对方偏好权重加权

匹配队列:
  每日计算每个活跃用户的 Top 50 候选, 写入 matches 表
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


# ================================================================
# 数据结构
# ================================================================
DIMENSION_NAMES = ["face", "body", "height", "skin_hair", "genital"]
DIMENSION_MAX = {"face": 40, "body": 25, "height": 15, "skin_hair": 10, "genital": 10}
DIMENSION_LABELS = {
    "face": "面部",
    "body": "身材",
    "height": "身高",
    "skin_hair": "皮肤/头发",
    "genital": "私密维度",
}

# 默认权重 (归一化后的偏好, 和=1)
DEFAULT_WEIGHTS = {
    "face": 0.40,
    "body": 0.25,
    "height": 0.15,
    "skin_hair": 0.10,
    "genital": 0.10,
}


@dataclass
class ScoreVector:
    """五维评分向量 (原始分)"""
    face: float = 0.0      # /40
    body: float = 0.0      # /25
    height: float = 0.0    # /15
    skin_hair: float = 0.0 # /10
    genital: float = 0.0   # /10

    def to_normalized(self) -> list[float]:
        """归一化到 [0, 1] 各维度"""
        return [
            self.face / DIMENSION_MAX["face"] if DIMENSION_MAX["face"] else 0,
            self.body / DIMENSION_MAX["body"] if DIMENSION_MAX["body"] else 0,
            self.height / DIMENSION_MAX["height"] if DIMENSION_MAX["height"] else 0,
            self.skin_hair / DIMENSION_MAX["skin_hair"] if DIMENSION_MAX["skin_hair"] else 0,
            self.genital / DIMENSION_MAX["genital"] if DIMENSION_MAX["genital"] else 0,
        ]

    @property
    def total(self) -> float:
        return self.face + self.body + self.height + self.skin_hair + self.genital

    @classmethod
    def from_dict(cls, d: dict) -> "ScoreVector":
        return cls(
            face=d.get("face_score", 0) or 0,
            body=d.get("body_score", 0) or 0,
            height=d.get("height_score", 0) or 0,
            skin_hair=d.get("skin_hair_score", 0) or 0,
            genital=d.get("genital_score", 0) or 0,
        )


@dataclass
class PreferenceWeights:
    """用户自定义偏好权重 (百分比, 和=100)"""
    face: int = 40
    body: int = 25
    height: int = 15
    skin_hair: int = 10
    genital: int = 10

    def to_normalized(self) -> list[float]:
        """归一化到 [0, 1] 且和=1"""
        total = self.face + self.body + self.height + self.skin_hair + self.genital
        if total == 0:
            return [0.2] * 5
        return [
            self.face / total,
            self.body / total,
            self.height / total,
            self.skin_hair / total,
            self.genital / total,
        ]

    @classmethod
    def from_dict(cls, d: dict) -> "PreferenceWeights":
        return cls(
            face=d.get("weight_face", 40) or 40,
            body=d.get("weight_body", 25) or 25,
            height=d.get("weight_height", 15) or 15,
            skin_hair=d.get("weight_skin_hair", 10) or 10,
            genital=d.get("weight_genital", 10) or 10,
        )


@dataclass
class CompatibilityResult:
    """兼容性计算结果"""
    # 总分
    compatibility_pct: float = 0.0

    # 各维度匹配度 (0-100)
    dimension_scores: dict[str, float] = field(default_factory=dict)

    # 非评分维度
    age_compatibility: float = 50.0
    distance_score: float = 50.0
    preference_match: float = 50.0

    # 中间值
    cosine_similarity: float = 0.0
    weighted_dot_product: float = 0.0

    # 人类可读解释
    explanation: str = ""
    highlights: list[str] = field(default_factory=list)

    # 元数据
    algorithm_version: str = "v2.0"


# ================================================================
# 核心算法
# ================================================================
class MatchingEngine:
    """
    智能匹配引擎 v2

    算法:
    1. 加权余弦相似度 (评分向量维度)     权重 40%
    2. 加权评分差异匹配 (对方在乎的维度)  权重 25%
    3. 偏好匹配度 (性别/年龄/looking_for) 权重 15%
    4. 年龄兼容性                         权重 10%
    5. 距离评分                           权重 10%
    """

    ALGORITHM_VERSION = "v2.0-weighted-cosine"

    # 各大类权重 (和=1)
    W_COSINE = 0.40
    W_DIM_MATCH = 0.25
    W_PREF = 0.15
    W_AGE = 0.10
    W_DISTANCE = 0.10

    def compute_compatibility(
        self,
        my_scores: ScoreVector,
        their_scores: ScoreVector,
        their_weights: PreferenceWeights,
        my_age: Optional[int] = None,
        their_age: Optional[int] = None,
        distance_km: Optional[float] = None,
        preference_match_pct: float = 50.0,
    ) -> CompatibilityResult:
        """
        计算两人的兼容性百分比 + 解释文本

        Args:
            my_scores: 我的五维评分向量
            their_scores: 对方的五维评分向量
            their_weights: 对方的偏好权重 (对方在乎什么)
            my_age / their_age: 年龄
            distance_km: 两人距离
            preference_match_pct: 偏好匹配度 (外部计算传入)

        Returns:
            CompatibilityResult 包含百分比 + 每维度得分 + 解释文本
        """
        result = CompatibilityResult()
        result.algorithm_version = self.ALGORITHM_VERSION

        # 归一化
        my_norm = my_scores.to_normalized()
        their_norm = their_scores.to_normalized()
        w = their_weights.to_normalized()

        # ---- 1. 加权余弦相似度 ----
        #   衡量两人评分"形状"的相似程度
        #   用对方的偏好权重加权 → 对方在乎面部, 则面部维度的方向匹配更重要
        cos_sim = self._weighted_cosine_similarity(my_norm, their_norm, w)
        cos_score = (cos_sim + 1) / 2 * 100  # [-1,1] → [0,100]
        result.cosine_similarity = round(cos_sim, 4)

        # ---- 2. 各维度匹配度 ----
        #   我在对方看重的维度上得分有多高?
        dim_scores = {}
        weighted_dim_total = 0.0

        for i, dim in enumerate(DIMENSION_NAMES):
            # 我在该维度的归一化分
            my_dim = my_norm[i]
            # 对方对该维度的权重
            dim_weight = w[i]
            # 该维度的匹配分 = 我的分 * 100 (越高越好)
            dim_match = my_dim * 100
            dim_scores[dim] = round(dim_match, 1)
            weighted_dim_total += dim_match * dim_weight

        result.dimension_scores = dim_scores
        result.weighted_dot_product = round(weighted_dim_total, 2)

        # ---- 3. 偏好匹配度 ----
        pref_score = preference_match_pct
        result.preference_match = pref_score

        # ---- 4. 年龄兼容性 ----
        age_score = self._age_compatibility(my_age, their_age)
        result.age_compatibility = age_score

        # ---- 5. 距离评分 ----
        dist_score = self._distance_score(distance_km)
        result.distance_score = dist_score

        # ---- 加权汇总 ----
        total = (
            cos_score * self.W_COSINE
            + weighted_dim_total * self.W_DIM_MATCH
            + pref_score * self.W_PREF
            + age_score * self.W_AGE
            + dist_score * self.W_DISTANCE
        )
        total = round(max(0, min(100, total)), 2)
        result.compatibility_pct = total

        # ---- 生成解释文本 ----
        result.explanation, result.highlights = self._generate_explanation(
            result, their_weights, my_scores, their_scores, distance_km
        )

        logger.debug(
            f"兼容性计算 | pct={total}% | cosine={cos_sim:.3f} | "
            f"dim_weighted={weighted_dim_total:.1f}"
        )

        return result

    # ================================================================
    # 加权余弦相似度
    # ================================================================
    @staticmethod
    def _weighted_cosine_similarity(
        a: list[float], b: list[float], weights: list[float]
    ) -> float:
        """
        加权余弦相似度

        cos_w(A, B) = Σ(w_i * a_i * b_i) / (√Σ(w_i * a_i²) * √Σ(w_i * b_i²))

        权重让对方看重的维度在方向匹配中占更大比例
        """
        dot = sum(weights[i] * a[i] * b[i] for i in range(len(a)))
        mag_a = math.sqrt(sum(weights[i] * a[i] ** 2 for i in range(len(a))))
        mag_b = math.sqrt(sum(weights[i] * b[i] ** 2 for i in range(len(b))))

        if mag_a < 1e-9 or mag_b < 1e-9:
            return 0.0

        return dot / (mag_a * mag_b)

    # ================================================================
    # 辅助评分
    # ================================================================
    @staticmethod
    def _age_compatibility(
        age_a: Optional[int], age_b: Optional[int]
    ) -> float:
        if age_a is None or age_b is None:
            return 50.0
        diff = abs(age_a - age_b)
        # 0岁差 → 100, 5岁差 → 70, 12+岁差 → 0
        return round(max(0, 100 - diff * diff * 0.7), 1)

    @staticmethod
    def _distance_score(distance_km: Optional[float]) -> float:
        if distance_km is None:
            return 50.0
        if distance_km <= 3:
            return 100.0
        if distance_km <= 10:
            return round(100 - (distance_km - 3) * 2, 1)
        if distance_km <= 50:
            return round(86 - (distance_km - 10) * 1.2, 1)
        return round(max(0, 38 - (distance_km - 50) * 0.5), 1)

    # ================================================================
    # 解释文本生成
    # ================================================================
    def _generate_explanation(
        self,
        result: CompatibilityResult,
        their_weights: PreferenceWeights,
        my_scores: ScoreVector,
        their_scores: ScoreVector,
        distance_km: Optional[float],
    ) -> tuple[str, list[str]]:
        """
        生成人类可读的匹配解释

        Returns: (summary_text, highlight_list)
        """
        dim_scores = result.dimension_scores
        w_norm = their_weights.to_normalized()
        highlights: list[str] = []

        # 找出对方最看重的维度 (权重Top 2)
        weighted_dims = sorted(
            zip(DIMENSION_NAMES, w_norm),
            key=lambda x: x[1],
            reverse=True,
        )
        top_dims = weighted_dims[:2]

        # ---- 分析各维度 ----
        strong_dims: list[str] = []   # 高匹配维度
        weak_dims: list[str] = []     # 低匹配维度
        neutral_dims: list[str] = []

        for dim in DIMENSION_NAMES:
            score = dim_scores.get(dim, 50)
            label = DIMENSION_LABELS[dim]
            weight_pct = dict(weighted_dims).get(dim, 0.2) * 100

            if score >= 75:
                strong_dims.append(dim)
                if weight_pct >= 20:
                    highlights.append(
                        f"{label}高度匹配 ({score:.0f}分) — 对方非常看重此项 ({weight_pct:.0f}%权重)"
                    )
            elif score < 45:
                weak_dims.append(dim)
                if weight_pct >= 20:
                    highlights.append(
                        f"{label}匹配度偏低 ({score:.0f}分) — 对方较看重此项 ({weight_pct:.0f}%权重)"
                    )
            else:
                neutral_dims.append(dim)

        # ---- 余弦相似度解读 ----
        cos = result.cosine_similarity
        if cos >= 0.9:
            highlights.append("评分轮廓高度相似 — 你们在各维度上的强弱项非常接近")
        elif cos >= 0.7:
            highlights.append("评分轮廓较为相似 — 整体趋势一致")
        elif cos < 0.4:
            highlights.append("评分轮廓差异较大 — 互补型匹配, 各有所长")

        # ---- 距离 ----
        if distance_km is not None:
            if distance_km <= 5:
                highlights.append(f"距离很近 ({distance_km:.1f}km) — 约会非常方便")
            elif distance_km > 50:
                highlights.append(f"距离较远 ({distance_km:.1f}km) — 可能需要考虑异地因素")

        # ---- 组装摘要 ----
        summary_parts = []

        if strong_dims:
            strong_labels = "、".join(DIMENSION_LABELS[d] for d in strong_dims[:3])
            summary_parts.append(f"{strong_labels}高度匹配")

        if weak_dims:
            # 只提及对方真正看重的弱维度
            important_weak = [
                d for d in weak_dims
                if dict(weighted_dims).get(d, 0) >= 0.15
            ]
            if important_weak:
                weak_labels = "、".join(DIMENSION_LABELS[d] for d in important_weak[:2])
                summary_parts.append(f"但{weak_labels}偏好略低")

        if not summary_parts:
            if result.compatibility_pct >= 75:
                summary_parts.append("各维度均衡匹配, 综合兼容度高")
            elif result.compatibility_pct >= 50:
                summary_parts.append("中等匹配度, 部分维度互补")
            else:
                summary_parts.append("匹配度较低, 偏好差异较大")

        summary = ", ".join(summary_parts)

        return summary, highlights

    # ================================================================
    # 偏好匹配度 (性别/年龄/looking_for)
    # ================================================================
    @staticmethod
    def calculate_preference_match(
        user_a_prefs: dict, user_b_profile: dict
    ) -> float:
        """
        计算偏好匹配度 (0-100)
        基于: gender, age, looking_for 的重叠程度
        """
        score = 0.0
        checks = 0

        # 性别偏好
        pref_genders = user_a_prefs.get("pref_gender") or []
        if pref_genders:
            checks += 1
            if user_b_profile.get("gender") in pref_genders:
                score += 100

        # 年龄范围
        b_age = user_b_profile.get("age")
        pref_age_min = user_a_prefs.get("pref_age_min")
        if b_age is not None and pref_age_min is not None:
            checks += 1
            pref_age_max = user_a_prefs.get("pref_age_max", 99)
            if pref_age_min <= b_age <= pref_age_max:
                # 越接近中间值越高分
                mid = (pref_age_min + pref_age_max) / 2
                half_range = max((pref_age_max - pref_age_min) / 2, 1)
                closeness = 1 - abs(b_age - mid) / half_range
                score += 70 + closeness * 30  # 70-100
            else:
                # 超出范围但接近边界还有部分分
                if b_age < pref_age_min:
                    overshoot = pref_age_min - b_age
                else:
                    overshoot = b_age - pref_age_max
                score += max(0, 50 - overshoot * 10)

        # looking_for 交集
        a_looking = set(user_a_prefs.get("pref_looking_for") or [])
        b_looking = set(user_b_profile.get("looking_for") or [])
        if a_looking and b_looking:
            checks += 1
            overlap = len(a_looking & b_looking) / len(a_looking | b_looking)
            score += overlap * 100

        # 距离偏好
        pref_dist = user_a_prefs.get("pref_distance_km")
        actual_dist = user_b_profile.get("distance_km")
        if pref_dist and actual_dist is not None:
            checks += 1
            if actual_dist <= pref_dist:
                score += 100
            else:
                overshoot = (actual_dist - pref_dist) / pref_dist
                score += max(0, 100 - overshoot * 100)

        if checks == 0:
            return 50.0

        return round(score / checks, 1)

    # ================================================================
    # 序列化结果 (写入DB)
    # ================================================================
    @staticmethod
    def result_to_db_row(result: CompatibilityResult) -> dict:
        """将结果转为matches表可存储的字段"""
        return {
            "compatibility_pct": result.compatibility_pct,
            "compatibility_breakdown": {
                "cosine_similarity": result.cosine_similarity,
                "weighted_dot_product": result.weighted_dot_product,
                "dimension_scores": result.dimension_scores,
                "age_compatibility": result.age_compatibility,
                "distance_score": result.distance_score,
                "preference_match": result.preference_match,
                "explanation": result.explanation,
                "highlights": result.highlights,
            },
            "algorithm_version": result.algorithm_version,
        }


# ================================================================
# 每日 Top 50 匹配队列
# ================================================================
class DailyMatchQueue:
    """
    每日匹配队列计算器

    流程:
    1. 获取所有活跃用户的评分向量和偏好
    2. 对每个用户, 计算其与所有候选人的兼容度
    3. 取 Top 50, 写入 matches 表 (status=pending)
    4. 跳过已存在的匹配对
    """

    def __init__(self):
        self.engine = MatchingEngine()

    async def compute_for_user(
        self,
        user_id: str,
        user_scores: ScoreVector,
        user_age: Optional[int],
        user_prefs: dict,
        user_location: Optional[tuple[float, float]],
        candidates: list[dict],
        existing_match_pairs: set[tuple[str, str]],
        top_n: int = 50,
    ) -> list[dict]:
        """
        为单个用户计算 Top N 候选

        Args:
            user_id: 当前用户ID
            user_scores: 当前用户评分向量
            user_age: 当前用户年龄
            user_prefs: 当前用户偏好 (from user_preferences表)
            user_location: 当前用户经纬度 (lat, lng)
            candidates: 候选用户列表, 每项包含:
                {id, face_score, body_score, ..., age, gender, looking_for,
                 weight_face, ..., lat, lng}
            existing_match_pairs: 已存在的匹配对集合 (避免重复)
            top_n: 返回前N个

        Returns:
            按兼容度降序排列的 top_n 结果列表
        """
        results: list[tuple[float, dict]] = []

        for cand in candidates:
            cand_id = cand["id"]
            if cand_id == user_id:
                continue

            # 检查是否已有匹配记录
            pair = tuple(sorted([user_id, cand_id]))
            if pair in existing_match_pairs:
                continue

            # 构建对方数据
            their_scores = ScoreVector.from_dict(cand)
            their_weights = PreferenceWeights.from_dict(cand)
            their_age = cand.get("age")

            # 计算距离
            distance_km = None
            if user_location and cand.get("lat") and cand.get("lng"):
                distance_km = self._haversine(
                    user_location[0], user_location[1],
                    cand["lat"], cand["lng"],
                )

            # 偏好匹配
            pref_pct = self.engine.calculate_preference_match(
                user_prefs,
                {
                    "gender": cand.get("gender"),
                    "age": their_age,
                    "looking_for": cand.get("looking_for", []),
                    "distance_km": distance_km,
                },
            )

            # 核心兼容度计算
            compat = self.engine.compute_compatibility(
                my_scores=user_scores,
                their_scores=their_scores,
                their_weights=their_weights,
                my_age=user_age,
                their_age=their_age,
                distance_km=distance_km,
                preference_match_pct=pref_pct,
            )

            results.append((
                compat.compatibility_pct,
                {
                    "user_a": min(user_id, cand_id),
                    "user_b": max(user_id, cand_id),
                    "candidate_id": cand_id,
                    **MatchingEngine.result_to_db_row(compat),
                },
            ))

        # 按兼容度降序, 取 Top N
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:top_n]]

    async def run_daily_batch(self, sb_client) -> dict:
        """
        每日批量计算 — 为所有活跃用户生成 Top 50

        Args:
            sb_client: Supabase admin client

        Returns:
            {"users_processed": int, "matches_created": int}
        """
        logger.info("[DailyMatch] 开始每日匹配批量计算")

        # 1. 获取所有有评分的活跃用户
        users_resp = (
            sb_client.table("users")
            .select("id, date_of_birth, gender, is_active")
            .eq("is_active", True)
            .execute()
        )
        active_users = {u["id"]: u for u in (users_resp.data or [])}

        if len(active_users) < 2:
            logger.info("[DailyMatch] 活跃用户不足2人, 跳过")
            return {"users_processed": 0, "matches_created": 0}

        # 2. 获取所有评分 (最新一条)
        scores_resp = (
            sb_client.table("ratings")
            .select("user_id, face_score, body_score, height_score, skin_hair_score, genital_score")
            .order("scored_at", desc=True)
            .execute()
        )
        # 每个用户只取最新评分
        user_scores_map: dict[str, dict] = {}
        for s in (scores_resp.data or []):
            uid = s["user_id"]
            if uid not in user_scores_map:
                user_scores_map[uid] = s

        # 3. 获取所有偏好
        prefs_resp = (
            sb_client.table("user_preferences")
            .select("*")
            .execute()
        )
        user_prefs_map = {p["user_id"]: p for p in (prefs_resp.data or [])}

        # 4. 获取所有资料 (位置)
        profiles_resp = (
            sb_client.table("profiles")
            .select("user_id, city, country, looking_for")
            .execute()
        )
        user_profiles_map = {p["user_id"]: p for p in (profiles_resp.data or [])}

        # 5. 获取已存在的匹配对
        existing_resp = (
            sb_client.table("matches")
            .select("user_a, user_b")
            .execute()
        )
        existing_pairs: set[tuple[str, str]] = set()
        for m in (existing_resp.data or []):
            existing_pairs.add((m["user_a"], m["user_b"]))

        # 6. 构建候选列表
        candidates = []
        for uid, user_data in active_users.items():
            scores = user_scores_map.get(uid)
            prefs = user_prefs_map.get(uid, {})
            prof = user_profiles_map.get(uid, {})
            if not scores:
                continue

            age = self._calculate_age(user_data.get("date_of_birth"))

            candidates.append({
                "id": uid,
                "face_score": scores.get("face_score", 0),
                "body_score": scores.get("body_score", 0),
                "height_score": scores.get("height_score", 0),
                "skin_hair_score": scores.get("skin_hair_score", 0),
                "genital_score": scores.get("genital_score", 0),
                "weight_face": prefs.get("weight_face", 40),
                "weight_body": prefs.get("weight_body", 25),
                "weight_height": prefs.get("weight_height", 15),
                "weight_skin_hair": prefs.get("weight_skin_hair", 10),
                "weight_genital": prefs.get("weight_genital", 10),
                "age": age,
                "gender": user_data.get("gender"),
                "looking_for": prof.get("looking_for", []),
                "lat": None,  # TODO: 从PostGIS提取
                "lng": None,
            })

        # 7. 对每个用户计算 Top 50
        total_created = 0
        users_processed = 0

        for cand in candidates:
            uid = cand["id"]
            my_scores = ScoreVector.from_dict(cand)
            my_age = cand.get("age")
            my_prefs = user_prefs_map.get(uid, {})

            top_matches = await self.compute_for_user(
                user_id=uid,
                user_scores=my_scores,
                user_age=my_age,
                user_prefs=my_prefs,
                user_location=None,
                candidates=candidates,
                existing_match_pairs=existing_pairs,
                top_n=50,
            )

            # 写入matches表
            for match_row in top_matches:
                pair = (match_row["user_a"], match_row["user_b"])
                if pair in existing_pairs:
                    continue

                try:
                    sb_client.table("matches").insert({
                        "user_a": match_row["user_a"],
                        "user_b": match_row["user_b"],
                        "status": "pending",
                        "compatibility_pct": match_row["compatibility_pct"],
                        "compatibility_breakdown": match_row["compatibility_breakdown"],
                        "algorithm_version": match_row["algorithm_version"],
                    }).execute()
                    existing_pairs.add(pair)
                    total_created += 1
                except Exception as e:
                    logger.warning(f"[DailyMatch] 写入匹配失败 | pair={pair} | error={e}")

            users_processed += 1

        logger.info(
            f"[DailyMatch] 完成 | users={users_processed} | "
            f"matches_created={total_created}"
        )

        return {
            "users_processed": users_processed,
            "matches_created": total_created,
        }

    # ================================================================
    # 工具函数
    # ================================================================
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine公式计算两点距离 (km)"""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _calculate_age(dob_str: Optional[str]) -> Optional[int]:
        if not dob_str:
            return None
        try:
            from datetime import date
            born = date.fromisoformat(str(dob_str))
            today = date.today()
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except (ValueError, TypeError):
            return None
