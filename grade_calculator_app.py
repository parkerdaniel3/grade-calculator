# grade_calculator_app.py
import math
import pandas as pd
import streamlit as st

# ---------- Page setup ----------
st.set_page_config(page_title="Grade Calculator", page_icon="📘", layout="centered")
st.title("📘 Grade Calculator")
st.caption("Figure out what you need on the final to hit your target overall grade.")

# Quick reset if session state ever gets weird
if st.sidebar.button("🔄 Reset all"):
    st.session_state.clear()
    st.rerun()

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
    Returns (current, final_weight, final_found).
    'current' is the weighted contribution (0–100) from all non-final categories with scores.
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
            current += (avg / 100.0) * c["weight"] * 100.0  # keep current on 0–100 scale

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

# ---------- UI (Form) ----------
with st.form("grade_form"):
    st.subheader("Course & Categories")

    course_name = st.text_input("Course name", value="My Course")

    num_categories = st.number_input(
        "How many grading categories?",
        min_value=1,
        step=1,
        value=3
    )

    # Placeholder suggestions for names (faded hints)
    default_names = ["Homework", "Quizzes", "Exams", "Projects", "Participation", "Final Exam"]

    categories = []
    for i in range(int(num_categories)):
        with st.expander(f"Category {i+1}", expanded=(i < 2)):
            suggested = default_names[i] if i < len(default_names) else "e.g., Labs"

            # Category name input with a placeholder (faded suggestion)
            cat_name_input = st.text_input(
                f"Name for category {i+1}",
                value="",
                placeholder=suggested,
                key=f"cat{i}_name"
            )
            entered = bool(cat_name_input.strip())
            resolved_name = cat_name_input.strip() or suggested

            # Weights
            c1, c2 = st.columns([2, 1])
            with c1:
                raw_weight = st.number_input(
                    f"Weight for {resolved_name}",
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

            # Drop lowest scores
            drop_n = st.number_input(
                f"Drop how many lowest scores in {resolved_name}?",
                min_value=0,
                step=1,
                value=0,
                key=f"cat{i}_drop"
            )

            # --- Editable scores table (add/remove rows) ---
            st.markdown(f"**Scores for {resolved_name}**")
            df_key = f"cat{i}_df"

            # Load from session or initialize with correct dtypes
            df = st.session_state.get(df_key)
            if df is None:
                df = pd.DataFrame(
                    {
                        "Item": pd.Series([""], dtype="object"),             # text
                        "Score": pd.Series([float("nan")], dtype="float64"), # numeric
                    }
                )
            else:
                # Ensure required columns exist and have the right dtypes
                if "Item" not in df.columns or "Score" not in df.columns:
                    df = pd.DataFrame(
                        {
                            "Item": pd.Series([""], dtype="object"),
                            "Score": pd.Series([float("nan")], dtype="float64"),
                        }
                    )
                else:
                    df["Item"] = df["Item"].astype("object", copy=False)
                    df["Score"] = pd.to_numeric(df["Score"], errors="coerce")

            st.session_state[df_key] = df

            edited_df = st.data_editor(
                df,
                num_rows="dynamic",       # enables the “Add row” button
                width="stretch",          # replaces deprecated use_container_width
                key=f"cat{i}_editor",
                column_config={
                    "Item": st.column_config.TextColumn("Item (optional)", width="medium"),
                    "Score": st.column_config.NumberColumn(
                        "Score (0–100)", min_value=0.0, max_value=100.0, step=0.1, format="%.1f"
                    ),
                },
            )

            # Persist edits
            st.session_state[df_key] = edited_df

            # Extract numeric scores (ignore blanks)
            scores = [float(x) for x in pd.to_numeric(edited_df["Score"], errors="coerce").dropna().tolist()]

            # Live average display
            avg_now = avg_with_drops(scores, drop_n)
            if avg_now is not None:
                st.caption(f"Current average (after drops): **{avg_now:.2f}%**")

            categories.append({
                "name": resolved_name,
                "entered": entered,
                "weight": weight,
                "scores": scores,
                "drop_n": drop_n
            })

    # Normalize weights if needed (outside loop, still inside form)
    total_weight = sum(c["weight"] for c in categories)
    normalized = False
    if total_weight > 0 and abs(total_weight - 1.0) > 1e-2:
        normalized = True
        for c in categories:
            c["weight"] = c["weight"] / total_weight

    # Final exam picker: prefer only names the user typed (fallback to all names)
    typed_options = [c["name"] for c in categories if c.get("entered")]
    name_options = typed_options if typed_options else [c["name"] for c in categories]

    if name_options:
        default_index = (
            name_options.index("Final Exam")
            if "Final Exam" in name_options
            else len(name_options) - 1
        )
        final_name = st.selectbox(
            "Which category is your final exam?",
            options=name_options,
            index=default_index,
            key="final_picker"
        )
    else:
        st.warning("Add at least one category to choose a final exam.")
        final_name = ""

    target = st.number_input(
        "Desired overall course grade (0–100)",
        min_value=0.0,
        max_value=100.0,
        step=0.1,
        value=90.0
    )

    # Submit must be the last line inside the form
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
            st.error("Final exam category not found among your categories.")
        else:
            if normalized:
                st.info(f"Weights summed to {total_weight:.3f}. Normalized to 100%.")

            st.subheader("Results")
            st.write(f"**Course:** {course_name}")
            st.write(f"**Current grade (excluding final):** `{current:.2f}`")

            req_final = required_final_score(current, final_w, target)
            best = current + final_w * 100.0
            worst = current  # final = 0

            st.write(f"**Final exam weight:** `{final_w*100:.2f}%`")
            st.write(f"**Best possible overall (100 on final):** `{best:.2f}`")
            st.write(f"**Worst possible overall (0 on final):** `{worst:.2f}`")

            if req_final is None or math.isnan(req_final) or math.isinf(req_final):
                st.error("Error computing required final score (check final weight and inputs).")
            elif req_final < 0:
                st.success(
                    f"✅ You already meet `{target:.2f}` overall. "
                    f"Even a 0 on the final stays ≥ target."
                )
            elif req_final > 100:
                st.warning(
                    f"❌ Reaching `{target:.2f}` isn’t possible. "
                    f"You’d need `{req_final:.2f}` on the final (> 100)."
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
