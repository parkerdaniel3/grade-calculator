# grade_calculator_app.py
import streamlit as st

# ---------- Page setup ----------
st.set_page_config(page_title="Grade Calculator", page_icon="📘", layout="centered")
st.title("📘 Grade Calculator")
st.caption("Figure out what you need on the final to hit your target overall grade.")

# ---------- Helper functions ----------
def interpret_weight(value, unit):
    """Accept weight as Percent or Decimal -> return decimal in [0,1]."""
    if unit == "Percent":
        return value / 100.0
    return value

def avg_with_drops(scores, drop_n=0):
    """Average a list of 0–100 scores after dropping the lowest N."""
    if not scores:
        return None
    s = sorted(scores)
    drop_n = min(max(int(drop_n), 0), len(s))
    kept = s[drop_n:]
    return sum(kept) / len(kept) if kept else None

def compute_current_and_final(categories, final_name):
    """
    Returns (current, final_weight, final_found)
    current is the weighted contribution (0–100) from all non-final categories with scores.
    """
    current = 0.0
    final_w = 0.0
    final_found = False

    for c in categories:
        if c["name"].strip().lower() == final_name.strip().lower():
            final_w = c["weight"]
            final_found = True
            continue

        avg = avg_with_drops(c.get("scores", []), c.get("drop_n", 0))
        if avg is not None:
            # keep current on a 0–100 scale
            current += (avg / 100.0) * c["weight"] * 100.0

    return current, final_w, final_found

def required_final_score(current, final_weight, target):
    """Solve for needed final score (0–100 scale)."""
    if final_weight <= 0:
        return None
    return (target - current) / final_weight

def scenarios_table(current, final_w):
    """Return (labels, overall list) for quick what-if table."""
    labels = [50, 60, 70, 80, 90, 100]
    overalls = [current + final_w * f for f in labels]
    return labels, overalls

# ---------- UI ----------
with st.form("grade_form"):
    st.subheader("Course & Categories")

    course_name = st.text_input("Course name", value="My Course")

    num_categories = st.number_input(
        "How many grading categories?",
        min_value=1,
        step=1,
        value=3
    )

    # suggestions for category names (shown as faded placeholders)
    default_names = ["Homework", "Quizzes", "Exams", "Projects", "Participation", "Final Exam"]

    categories = []
    for i in range(int(num_categories)):
        with st.expander(f"Category {i+1}", expanded=(i < 2)):
            suggested = default_names[i] if i < len(default_names) else "e.g., Labs"

            # text input with faded placeholder instead of prefilled text
            cat_name_input = st.text_input(
                f"Name for category {i+1}",
                value="",                          # start empty
                placeholder=suggested,             # faded hint
                key=f"cat{i}_name"
            )
            cat_name = cat_name_input.strip() or suggested

            # weights
            c1, c2 = st.columns([2, 1])
            with c1:
                raw_weight = st.number_input(
                    f"Weight for {cat_name}",
                    help="If using Percent, enter 30 for 30%. If using Decimal, enter 0.3.",
                    min_value=0.0,
                    step=0.1,
                    value=30.0 if i < 2 else 10.0,
                    key=f"cat{i}_weight"
                )
            with c2:
                unit = st.selectbox(
                    "Unit",
                    ["Percent", "Decimal"],
                    key=f"cat{i}_unit"
                )
            weight = interpret_weight(raw_weight, unit)

            # drop lowest scores
            drop_n = st.number_input(
                f"Drop how many lowest scores in {cat_name}?",
                min_value=0,
                step=1,
                value=0,
                key=f"cat{i}_drop"
            )

            # individual scores
            num_items = st.number_input(
                f"How many items in {cat_name}?",
                min_value=0,
                step=1,
                value=0,
                key=f"cat{i}_items"
            )

            scores = []
            if num_items > 0:
                cols = st.columns(3)
                for j in range(int(num_items)):
                    with cols[j % 3]:
                        s = st.number_input(
                            f"{cat_name} item {j+1} (0–100)",
                            min_value=0.0,
                            max_value=100.0,
                            step=0.1,
                            key=f"cat{i}_score{j}"
                        )
                        scores.append(s)

            categories.append(
                {"name": cat_name, "weight": weight, "scores": scores, "drop_n": drop_n}
            )

    # Normalize weights if needed (this must be OUTSIDE the loop but INSIDE the form)
    total_weight = sum(c["weight"] for c in categories)
    normalized = False
    if total_weight > 0 and abs(total_weight - 1.0) > 1e-2:
        normalized = True
        for c in categories:
            c["weight"] = c["weight"] / total_weight

    # Final exam picker as a dropdown using the resolved names
    name_options = [c["name"] for c in categories] if categories else []
    default_index = (name_options.index("Final Exam")
                     if "Final Exam" in name_options else (len(name_options)-1 if name_options else 0))
    final_name = st.selectbox(
        "Which category is your final exam?",
        options=name_options,
        index=default_index,
        key="final_picker"
    )

    target = st.number_input(
        "Desired overall course grade (0–100)",
        min_value=0.0,
        max_value=100.0,
        step=0.1,
        value=90.0
    )

    # Submit button must be the LAST thing inside the form
    submitted = st.form_submit_button("Calculate")

# ---------- Results ----------
if submitted:
    if total_weight <= 0:
        st.error("Total weight is zero. Please enter valid weights.")
    elif not final_name.strip():
        st.error("Please specify the final exam category.")
    else:
        current, final_w, final_found = compute_current_and_final(categories, final_name)

        if not final_found:
            st.error("Final exam category not found. Check the name (must match exactly).")
        else:
            if normalized:
                st.info(f"Weights summed to {total_weight:.3f}. Normalized to 100%.")

            st.subheader("Results")
            st.write(f"**Course:** {course_name}")
            st.write(f"**Current grade (excluding final):** `{current:.2f}`")

            req_final = required_final_score(current, final_w, target)
            best = current + final_w * 100.0
            worst = current  # if final is 0

            st.write(f"**Final exam weight:** `{final_w*100:.2f}%`")
            st.write(f"**Best possible overall (100 on final):** `{best:.2f}`")
            st.write(f"**Worst possible overall (0 on final):** `{worst:.2f}`")

            if req_final is None:
                st.error("Error computing required final score (final weight is zero?).")
            elif req_final < 0:
                st.success(
                    f"✅ You’ve already secured at least `{target:.2f}`. "
                    f"Even a 0 on the final keeps you above your goal."
                )
            elif req_final > 100:
                st.warning(
                    f"❌ It’s not possible to reach `{target:.2f}`. "
                    f"You’d need `{req_final:.2f}` on the final (>100)."
                )
            else:
                st.info(
                    f"To achieve `{target:.2f}` overall, you need **`{req_final:.2f}`** on the final exam."
                )

            # What-if scenarios
            st.markdown("---")
            st.subheader("What-if Scenarios")
            labels, overalls = scenarios_table(current, final_w)
            st.table(
                {
                    "Final Score (%)": [f"{v}%" for v in labels],
                    "Overall Grade (%)": [f"{o:.2f}" for o in overalls],
                }
            )

# ---------- Footer ----------
st.caption("Tip: Use the expanders to enter scores, and choose Percent or Decimal for weights.")
