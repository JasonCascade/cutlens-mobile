import base64
import io
import json
import os
import re
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st
from PIL import Image
from openai import OpenAI

st.set_page_config(
    page_title="CutLens - AI Meal Macros",
    page_icon="📸",
    layout="centered",
    initial_sidebar_state="collapsed",
)

MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-5.6-terra")
USDA_API_KEY = os.getenv("USDA_API_KEY", "DEMO_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

st.markdown(
    """
<style>
/* Mobile-first shell */
.block-container {
    max-width: 720px;
    padding-top: 0.75rem;
    padding-left: 0.85rem;
    padding-right: 0.85rem;
    padding-bottom: 5rem;
}
header { visibility: hidden; height: 0; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

.hero {
    padding: 0.25rem 0 0.6rem 0;
}
.hero h1 {
    font-size: 2.0rem;
    margin: 0;
    line-height: 1.05;
}
.hero p {
    margin: 0.35rem 0 0 0;
    opacity: 0.72;
    font-size: 0.96rem;
}

.step-card {
    border: 1px solid rgba(128,128,128,0.25);
    border-radius: 18px;
    padding: 0.95rem;
    margin: 0.55rem 0 0.8rem 0;
}

.macro-card {
    border: 1px solid rgba(128,128,128,0.22);
    border-radius: 18px;
    padding: 0.9rem 0.65rem;
    text-align: center;
    min-height: 92px;
}
.macro-number {
    font-size: 1.42rem;
    font-weight: 750;
    line-height: 1.05;
}
.macro-label {
    font-size: 0.78rem;
    opacity: 0.68;
    margin-top: 0.3rem;
}

.food-card {
    border: 1px solid rgba(128,128,128,0.20);
    border-radius: 16px;
    padding: 0.8rem;
    margin-bottom: 0.55rem;
}
.food-title { font-weight: 700; font-size: 1rem; }
.food-sub { opacity: 0.7; font-size: 0.82rem; margin-top: 0.15rem; }

div.stButton > button {
    width: 100%;
    min-height: 3.25rem;
    border-radius: 16px;
    font-size: 1.06rem;
    font-weight: 700;
}

[data-testid="stCameraInput"] {
    border-radius: 18px;
    overflow: hidden;
}

[data-testid="stFileUploader"] {
    border-radius: 16px;
}

[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 16px;
    padding: 0.7rem;
}

@media (max-width: 480px) {
    .block-container {
        padding-left: 0.7rem;
        padding-right: 0.7rem;
        padding-top: 0.45rem;
    }
    .hero h1 { font-size: 1.8rem; }
    div.stButton > button { min-height: 3.5rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

NUTRIENT_IDS = {
    "calories": {1008, 2047, 2048},
    "protein": {1003},
    "fat": {1004},
    "carbs": {1005},
}


def img_to_data_url(image: Image.Image) -> str:
    image = image.convert("RGB")
    max_side = 1600
    if max(image.size) > max_side:
        ratio = max_side / max(image.size)
        image = image.resize((int(image.width * ratio), int(image.height * ratio)))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=88, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def safe_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise ValueError("The AI response was not valid JSON.")
        return json.loads(m.group(0))


def load_image(file_obj) -> Optional[Image.Image]:
    if file_obj is None:
        return None
    return Image.open(file_obj).convert("RGB")


def analyze_images(
    images: List[Image.Image],
    plate_diameter_cm: Optional[float],
    notes: str,
    oil_info: str,
) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured on the server.")

    calibration = (
        f"Known plate/bowl diameter: {plate_diameter_cm:.1f} cm. Use it as a scale reference."
        if plate_diameter_cm
        else "No exact plate diameter is known. Increase uncertainty accordingly."
    )

    prompt = f"""
You are CutLens, a careful food portion estimator for a user tracking fat loss.
All attached images show the SAME meal from different angles.

Your job:
- Identify each distinct edible component.
- Estimate READY-TO-EAT / COOKED grams for each component.
- Give realistic low and high gram bounds.
- Return a USDA-searchable English food query for each component.
- Explicitly consider hidden calories such as oil, butter, dressing, creamy sauce, cheese, nuts, sugar, glaze.
- Do not double count oil/sauce if it is already intrinsic to a prepared mixed-dish name.
- Use visual geometry, plate scale, thickness, food density, count, and consistency across views.
- Be conservative against underestimating calories, but do not intentionally inflate the estimate.
- If the meal is visually ambiguous, say so and widen the range rather than pretending certainty.
- For rice/pasta/meat, distinguish cooked vs raw whenever possible.
- If a visible item is a mixed dish that cannot be reliably decomposed, identify it as the mixed dish.

Calibration: {calibration}
User meal notes: {notes or 'None'}
Known oil/sauce info: {oil_info or 'None'}

Return JSON only:
{{
  "meal_summary": "short meal name",
  "overall_confidence": 0.0,
  "items": [
    {{
      "name": "USDA-searchable English food query",
      "display_name": "short human-friendly name",
      "grams": 0,
      "grams_low": 0,
      "grams_high": 0,
      "confidence": 0.0,
      "cooked_state": "cooked/raw/unknown",
      "notes": "one brief reason for the estimate"
    }}
  ],
  "visual_warnings": ["short warning if needed"]
}}
"""

    content = [{"type": "input_text", "text": prompt}]
    for image in images:
        content.append({"type": "input_image", "image_url": img_to_data_url(image)})

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.responses.create(
        model=MODEL,
        input=[{"role": "user", "content": content}],
    )
    return safe_json(response.output_text)


@st.cache_data(show_spinner=False, ttl=86400)
def usda_search(query: str) -> Optional[Dict[str, Any]]:
    endpoint = "https://api.nal.usda.gov/fdc/v1/foods/search"
    payload = {
        "query": query,
        "pageSize": 12,
        "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)", "Branded"],
    }
    r = requests.post(
        endpoint,
        params={"api_key": USDA_API_KEY},
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    foods = r.json().get("foods", [])
    if not foods:
        return None

    q = query.lower().strip()

    def score(food: Dict[str, Any]) -> float:
        desc = (food.get("description") or "").lower()
        dtype = food.get("dataType", "")
        s = 0.0
        if q == desc:
            s += 10
        if q in desc:
            s += 4
        for token in [x for x in q.split() if len(x) > 2]:
            if token in desc:
                s += 0.8
        if dtype in ("Foundation", "Survey (FNDDS)", "SR Legacy"):
            s += 2
        elif dtype == "Branded":
            s -= 1
        return s

    return max(foods, key=score)


def nutrient_per_100g(food: Optional[Dict[str, Any]]) -> Dict[str, float]:
    out = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    if not food:
        return out

    for n in food.get("foodNutrients", []):
        nutrient_id = n.get("nutrientId")
        value = n.get("value", n.get("amount"))
        try:
            value = float(value)
        except Exception:
            continue
        for key, ids in NUTRIENT_IDS.items():
            if nutrient_id in ids:
                if key == "calories" and out[key] != 0:
                    continue
                out[key] = value

    # Fallback by nutrient name for records with atypical identifiers.
    for n in food.get("foodNutrients", []):
        name = (n.get("nutrientName") or "").lower()
        value = n.get("value", n.get("amount"))
        try:
            value = float(value)
        except Exception:
            continue
        if "energy" in name and out["calories"] == 0 and "kcal" in (n.get("unitName") or "kcal").lower():
            out["calories"] = value
        elif name == "protein" and out["protein"] == 0:
            out["protein"] = value
        elif ("total lipid" in name or name == "fat") and out["fat"] == 0:
            out["fat"] = value
        elif "carbohydrate" in name and out["carbs"] == 0:
            out["carbs"] = value
    return out


def calculate_nutrition(item_rows: pd.DataFrame) -> pd.DataFrame:
    result_rows = []
    for _, row in item_rows.iterrows():
        query = str(row["USDA query"]).strip()
        grams = max(0.0, float(row["Grams"]))
        food = usda_search(query)
        p = nutrient_per_100g(food)
        factor = grams / 100.0
        result_rows.append(
            {
                "Food": row["Food"],
                "USDA query": query,
                "USDA match": food.get("description", "No match") if food else "No match",
                "Grams": round(grams, 1),
                "Calories": round(p["calories"] * factor),
                "Protein g": round(p["protein"] * factor, 1),
                "Carbs g": round(p["carbs"] * factor, 1),
                "Fat g": round(p["fat"] * factor, 1),
            }
        )
    return pd.DataFrame(result_rows)


def range_calories(items: List[Dict[str, Any]]) -> tuple[float, float]:
    low = 0.0
    high = 0.0
    for item in items:
        food = usda_search(item["name"])
        p = nutrient_per_100g(food)
        low += p["calories"] * float(item.get("grams_low", item["grams"])) / 100.0
        high += p["calories"] * float(item.get("grams_high", item["grams"])) / 100.0
    return low, high


def reset_analysis() -> None:
    st.session_state.pop("analysis_result", None)


if "capture_round" not in st.session_state:
    st.session_state["capture_round"] = 0
round_id = st.session_state["capture_round"]


st.markdown(
    """
<div class="hero">
  <h1>📸 CutLens</h1>
  <p>拍照估分量 · Calories · Protein · Carbs · Fat</p>
</div>
""",
    unsafe_allow_html=True,
)

if not OPENAI_API_KEY:
    st.warning("服务器还没有配置 OPENAI_API_KEY。先按 README 部署并添加 Secrets，手机端即可使用。")

st.markdown("### 1. 拍主照片")
st.caption("建议正上方拍，完整保留餐盘边缘。手机会优先调用摄像头。")
photo1 = st.camera_input("拍摄主照片", key=f"camera_main_{round_id}", label_visibility="collapsed", on_change=reset_analysis)

with st.expander("＋ 再拍一个角度（推荐，提高估重准确度）"):
    st.caption("建议约 45° 侧上方，让 AI 看见食物厚度。")
    photo2 = st.camera_input("拍摄第二角度", key=f"camera_second_{round_id}", label_visibility="collapsed", on_change=reset_analysis)
    photo3 = st.camera_input("可选：第三角度", key=f"camera_third_{round_id}", label_visibility="collapsed", on_change=reset_analysis)

with st.expander("从相册上传 / 补充信息"):
    gallery = st.file_uploader(
        "也可以从相册补充照片",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        help="最多会使用前三张有效照片。",
        on_change=reset_analysis,
    )
    plate = st.number_input(
        "餐盘/碗直径（cm，可选但很有帮助）",
        min_value=0.0,
        max_value=60.0,
        value=0.0,
        step=0.5,
    )
    oil_info = st.text_input("油 / 酱汁（如果知道）", placeholder="例如：1 tsp olive oil / no sauce")
    notes = st.text_area(
        "其他信息",
        placeholder="例如：鸡胸是熟重；米饭没加油；这是 Chipotle bowl",
        height=90,
    )

images: List[Image.Image] = []
for obj in [photo1, photo2, photo3]:
    img = load_image(obj)
    if img is not None:
        images.append(img)

if gallery:
    for obj in gallery:
        if len(images) >= 3:
            break
        img = load_image(obj)
        if img is not None:
            images.append(img)

if images:
    st.caption(f"已准备 {len(images)} 张照片用于同一餐分析。")

analyze_clicked = st.button(
    "✨ 分析这顿饭",
    type="primary",
    use_container_width=True,
    disabled=(len(images) == 0),
)

if analyze_clicked:
    with st.spinner("正在识别食物、估算克重并匹配 USDA 营养数据…"):
        try:
            st.session_state["analysis_result"] = analyze_images(
                images=images,
                plate_diameter_cm=(plate if plate > 0 else None),
                notes=notes,
                oil_info=oil_info,
            )
        except Exception as exc:
            st.error(f"分析失败：{exc}")

if "analysis_result" in st.session_state:
    result = st.session_state["analysis_result"]
    items = result.get("items", [])

    st.divider()
    st.markdown(f"## {result.get('meal_summary', 'Meal result')}")

    confidence = float(result.get("overall_confidence", 0.0))
    st.caption(f"视觉估重置信度约 {confidence * 100:.0f}% · 建议优先看区间，不要把图片估重当成电子秤。")

    if not items:
        st.warning("没有可靠识别到食物，请重新拍摄。")
    else:
        edit_rows = []
        for item in items:
            edit_rows.append(
                {
                    "Food": item.get("display_name") or item["name"],
                    "USDA query": item["name"],
                    "Grams": float(item["grams"]),
                    "AI low": float(item.get("grams_low", item["grams"])),
                    "AI high": float(item.get("grams_high", item["grams"])),
                    "Confidence %": round(float(item.get("confidence", 0.0)) * 100),
                }
            )

        st.markdown("### 2. 确认分量")
        st.caption("如果某项你知道更准确的克重，直接改 Grams。营养会按修改后的数值计算。")
        edited = st.data_editor(
            pd.DataFrame(edit_rows),
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Food": st.column_config.TextColumn("Food", disabled=True),
                "USDA query": st.column_config.TextColumn("USDA food"),
                "Grams": st.column_config.NumberColumn("Grams", min_value=0.0, step=5.0, format="%.0f g"),
                "AI low": st.column_config.NumberColumn("Low", disabled=True, format="%.0f g"),
                "AI high": st.column_config.NumberColumn("High", disabled=True, format="%.0f g"),
                "Confidence %": st.column_config.NumberColumn("Conf.", disabled=True, format="%d%%"),
            },
            key="portion_editor_mobile",
        )

        with st.spinner("计算营养…"):
            nutrition = calculate_nutrition(edited)

        totals = nutrition[["Calories", "Protein g", "Carbs g", "Fat g"]].sum()

        st.markdown("### 3. 本餐 P / C / F")
        a, b = st.columns(2)
        c, d = st.columns(2)
        with a:
            st.markdown(f'<div class="macro-card"><div class="macro-number">{totals["Calories"]:.0f}</div><div class="macro-label">kcal</div></div>', unsafe_allow_html=True)
        with b:
            st.markdown(f'<div class="macro-card"><div class="macro-number">{totals["Protein g"]:.1f}g</div><div class="macro-label">Protein</div></div>', unsafe_allow_html=True)
        with c:
            st.markdown(f'<div class="macro-card"><div class="macro-number">{totals["Carbs g"]:.1f}g</div><div class="macro-label">Carbs</div></div>', unsafe_allow_html=True)
        with d:
            st.markdown(f'<div class="macro-card"><div class="macro-number">{totals["Fat g"]:.1f}g</div><div class="macro-label">Fat</div></div>', unsafe_allow_html=True)

        try:
            kcal_low, kcal_high = range_calories(items)
            st.info(f"📊 仅按视觉克重的不确定性，这餐约 **{kcal_low:.0f}–{kcal_high:.0f} kcal**。隐藏油脂/酱汁仍可能让实际范围更宽。")
        except Exception:
            pass

        st.markdown("### 食物明细")
        for _, row in nutrition.iterrows():
            st.markdown(
                f"""
<div class="food-card">
  <div class="food-title">{row['Food']} · {row['Grams']:.0f} g</div>
  <div class="food-sub">{row['Calories']:.0f} kcal · P {row['Protein g']:.1f}g · C {row['Carbs g']:.1f}g · F {row['Fat g']:.1f}g</div>
  <div class="food-sub">USDA: {row['USDA match']}</div>
</div>
""",
                unsafe_allow_html=True,
            )

        warnings = result.get("visual_warnings") or []
        if warnings:
            with st.expander("⚠️ AI 认为可能影响准确度的地方"):
                for warning in warnings:
                    st.write("•", warning)

        csv = nutrition.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "导出本餐 CSV",
            data=csv,
            file_name="cutlens_meal.csv",
            mime="text/csv",
            use_container_width=True,
        )

        if st.button("📷 拍下一餐", use_container_width=True):
            st.session_state.pop("analysis_result", None)
            st.session_state["capture_round"] += 1
            st.rerun()

st.divider()
st.caption("CutLens 是视觉估算工具，不是电子秤。自己做饭时称重仍然最准；餐厅、外卖、旅行时它最有价值。")

