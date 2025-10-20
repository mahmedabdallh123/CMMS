import streamlit as st
import pandas as pd
import re
import time
import json
import os
import streamlit.components.v1 as components
import requests
import shutil

# ===============================
# ⚙️ إعدادات أساسية
# ===============================
GITHUB_EXCEL_URL = "https://github.com/mahmedabdallh123/cmms/raw/refs/heads/main/Machine_Service_Lookup.xlsx"
TOKENS_FILE = "tokens.json"
TRIAL_SECONDS = 60
RENEW_HOURS = 24
PASSWORD = "1234"

# ===============================
# 📂 تحميل البيانات من GitHub مع تنظيف الأعمدة
# ===============================
@st.cache_data
def load_all_sheets():
    try:
        local_file = "Machine_Service_Lookup.xlsx"
        r = requests.get(GITHUB_EXCEL_URL, stream=True)
        with open(local_file, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
        sheets = pd.read_excel(local_file, sheet_name=None)
        for name, df in sheets.items():
            df.columns = df.columns.str.strip()
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الملف من GitHub: {e}")
        st.stop()

# ===============================
# 🔑 نظام التجربة المجانية
# ===============================
def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(TOKENS_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        with open(TOKENS_FILE, "w") as f:
            json.dump({}, f)
        return {}

def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=4, ensure_ascii=False)

def check_free_trial(user_id="default_user"):
    tokens = load_tokens()
    now_ts = int(time.time())

    if user_id not in tokens:
        tokens[user_id] = {"last_trial": 0}
        save_tokens(tokens)

    last_trial = tokens[user_id]["last_trial"]
    hours_since_last = (now_ts - last_trial) / 3600

    if "trial_start" in st.session_state:
        elapsed = now_ts - st.session_state["trial_start"]
        if elapsed < TRIAL_SECONDS:
            st.info(f"✅ التجربة المجانية مفعّلة — متبقي {TRIAL_SECONDS - elapsed:.0f} ثانية")
            return True
        else:
            st.warning("⏰ انتهت التجربة المجانية. يمكنك إعادة التجربة بعد 24 ساعة أو الدخول بالباسورد.")
            password = st.text_input("أدخل كلمة المرور للوصول:", type="password")
            if password == PASSWORD:
                st.session_state["access_granted"] = True
                st.success("✅ تم تسجيل الدخول بالباسورد.")
                return True
            return False

    if hours_since_last >= RENEW_HOURS:
        if st.button("تفعيل التجربة المجانية 60 ثانية"):
            tokens[user_id]["last_trial"] = now_ts
            save_tokens(tokens)
            st.session_state["trial_start"] = now_ts
            st.experimental_rerun()
        return False

    remaining_hours = max(0, RENEW_HOURS - hours_since_last)
    st.warning(f"🔒 انتهت التجربة المجانية. يمكنك إعادة التجربة بعد {remaining_hours:.1f} ساعة أو الدخول بالباسورد.")
    password = st.text_input("أدخل كلمة المرور للوصول:", type="password")
    if password == PASSWORD:
        st.session_state["access_granted"] = True
        st.success("✅ تم تسجيل الدخول بالباسورد.")
        return True
    return False

# ===============================
# 🔠 دوال مساعدة
# ===============================
def normalize_name(s):
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\n", "+")
    s = re.sub(r"[^0-9a-zA-Z\u0600-\u06FF\+\s_/.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def split_needed_services(needed_service_str):
    if not isinstance(needed_service_str, str) or needed_service_str.strip() == "":
        return []
    parts = re.split(r"\+|,|\n|;", needed_service_str)
    return [p.strip() for p in parts if p.strip() != ""]

# ===============================
# ⚙ دالة مقارنة الصيانة
# ===============================
def check_machine_status(card_num, current_tons, all_sheets):
    if "ServicePlan" not in all_sheets or "Machine" not in all_sheets:
        st.error("❌ الملف لازم يحتوي على شيتين: 'Machine' و 'ServicePlan'")
        return

    service_plan_df = all_sheets["ServicePlan"]
    card_sheet_name = f"Card{card_num}"
    if card_sheet_name not in all_sheets:
        st.warning(f"⚠ لا يوجد شيت باسم {card_sheet_name}")
        return

    card_df = all_sheets[card_sheet_name]
    current_slice = service_plan_df[
        (service_plan_df["Min_Tones"] <= current_tons) &
        (service_plan_df["Max_Tones"] >= current_tons)
    ]

    if current_slice.empty:
        st.warning("⚠ لم يتم العثور على شريحة تناسب عدد الأطنان الحالي.")
        return

    min_tons = current_slice["Min_Tones"].values[0]
    max_tons = current_slice["Max_Tones"].values[0]
    needed_service_raw = current_slice["Service"].values[0]
    needed_parts = split_needed_services(needed_service_raw)
    needed_norm = [normalize_name(p) for p in needed_parts]

    slice_df = card_df[
        (card_df["card"] == card_num) &
        (card_df["Tones"] >= min_tons) &
        (card_df["Tones"] <= max_tons)
    ]

    done_services, last_date, last_tons = [], "-", "-"
    status = "❌ لم يتم تنفيذ صيانة في هذه الشريحة"

    if not slice_df.empty:
        last_row = slice_df.iloc[-1]
        last_date = last_row.get("Date", "-")
        last_tons = last_row.get("Tones", "-")

        ignore_cols = ["card", "Tones", "Date", "Current_Tones", "Service Needed", "Min_Tones", "Max_Tones"]
        for col in card_df.columns:
            if col not in ignore_cols:
                val = str(last_row.get(col, "")).strip().lower()
                if val and val not in ["nan", "none", ""]:
                    done_services.append(col)
        if done_services:
            status = "✅ تم تنفيذ صيانة في هذه الشريحة"

    done_norm = [normalize_name(c) for c in done_services]
    not_done = [orig for orig, n in zip(needed_parts, needed_norm) if n not in done_norm]

    result = {
        "Card": card_num,
        "Current_Tons": current_tons,
        "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
        "Done Services": ", ".join(done_services) if done_services else "-",
        "Not Done Services": ", ".join(not_done) if not_done else "-",
        "Date": last_date,
        "Tones": last_tons,
        "Status": status,
    }

    result_df = pd.DataFrame([result])
    st.dataframe(result_df, use_container_width=True)

    if st.button("💾 حفظ النتيجة في Excel"):
        result_df.to_excel("Machine_Result.xlsx", index=False)
        st.success("✅ تم حفظ النتيجة في ملف 'Machine_Result.xlsx' بنجاح.")

# ===============================
# 🖥 واجهة Streamlit
# ===============================
st.title("🔧 نظام متابعة الصيانة التنبؤية")

# ===============================
# ✅ زر تحديث الكاش بطريقة آمنة على Cloud
# ===============================
if "refresh" not in st.session_state:
    st.session_state["refresh"] = False

if st.button("🔄 تحديث البيانات من GitHub"):
    st.cache_data.clear()
    st.session_state["refresh"] = True

if st.session_state["refresh"]:
    st.session_state["refresh"] = False
    all_sheets = load_all_sheets()  # تحميل البيانات بعد مسح الكاش
else:
    if check_free_trial(user_id="default_user") or st.session_state.get("access_granted", False):
        all_sheets = load_all_sheets()  # تحميل البيانات بعد التحقق من الوصول

# ===============================
# ✅ إدخال بيانات الماكينة
# ===============================
if 'all_sheets' in locals():
    st.write("أدخل رقم الماكينة وعدد الأطنان الحالية لمعرفة حالة الصيانة")
    
    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1)
    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100)
    
    if st.button("عرض الحالة"):
        check_machine_status(card_num, current_tons, all_sheets)
