
import streamlit as st
import pandas as pd
import io
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpInteger

st.set_page_config(page_title="Transport Optimizer - Min Company Trips", page_icon="🚛")

st.title("🚛 Transport Route Optimizer (Min Company Trips Constraint)")
st.markdown("Upload your demand data, define fleet size, min company trips and conditions.")

uploaded_file = st.file_uploader("📂 Upload Excel File", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, sheet_name="Routes")
    expected_columns = ["From", "To", "Demand", "Company_Final_Cost", "3PL_Final_Cost"]
    if not all(col in df.columns for col in expected_columns):
        st.error(f"❌ The file must contain columns: {expected_columns}")
    else:
        total_trucks = st.number_input("🚛 Enter total company trucks available:", min_value=1, value=10)
        min_company_trips = st.number_input("📌 Minimum company trips to run:", min_value=1, value=5)
        min_trips = st.number_input("📌 Minimum trips per route per month:", min_value=1, value=6)

        df["Route"] = df["From"] + " ➡ " + df["To"]
        selected_routes = st.multiselect("✅ Select routes to include", df["Route"].tolist(), default=df["Route"].tolist())

        route_inputs = {}
        for _, row in df.iterrows():
            route = row["Route"]
            if route in selected_routes:
                col1, col2, col3 = st.columns(3)
                with col1:
                    comp_cost = st.number_input(f"Company Final Cost ({route})", value=float(row["Company_Final_Cost"]))
                with col2:
                    pl3_cost = st.number_input(f"3PL Final Cost ({route})", value=float(row["3PL_Final_Cost"]))
                with col3:
                    return_empty = st.checkbox(f"Return empty? ({route})", value=True)
                route_inputs[route] = {
                    "Company_Final_Cost": comp_cost * (2 if return_empty else 1),
                    "3PL_Final_Cost": pl3_cost,
                    "Demand": row["Demand"],
                    "From": row["From"],
                    "To": row["To"]
                }

        prob = LpProblem("Transport_Optimization", LpMinimize)
        company_vars = {}
        pl3_vars = {}

        for route, info in route_inputs.items():
            key = route.replace(" ", "_").replace("➡", "to")
            company_vars[route] = LpVariable(f"Company_{key}", 0, cat=LpInteger)
            pl3_vars[route] = LpVariable(f"PL3_{key}", 0, cat=LpInteger)
            prob += company_vars[route] + pl3_vars[route] == info["Demand"]
            prob += company_vars[route] + pl3_vars[route] >= min_trips

        prob += lpSum(company_vars.values()) <= total_trucks
        prob += lpSum(company_vars.values()) >= min_company_trips

        prob += lpSum([
            company_vars[route] * info["Company_Final_Cost"] +
            pl3_vars[route] * info["3PL_Final_Cost"]
            for route, info in route_inputs.items()
        ])

        prob.solve()

        results = []
        total_cost = 0
        for route, info in route_inputs.items():
            comp_trips = int(company_vars[route].varValue)
            pl3_trips = int(pl3_vars[route].varValue)
            comp_cost = comp_trips * info["Company_Final_Cost"]
            pl3_cost = pl3_trips * info["3PL_Final_Cost"]
            total = comp_cost + pl3_cost
            total_cost += total

            results.append({
                "From": info["From"],
                "To": info["To"],
                "Company_Trips": comp_trips,
                "3PL_Trips": pl3_trips,
                "Company_Cost": comp_cost,
                "3PL_Cost": pl3_cost,
                "Total_Cost": total
            })

        result_df = pd.DataFrame(results)
        st.subheader("📊 Optimized Distribution Result")
        st.dataframe(result_df)
        st.info(f"✅ Grand Total Cost: {total_cost} SAR")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            result_df.to_excel(writer, index=False)
        output.seek(0)

        st.download_button(
            label="⬇️ Download Optimized Plan as Excel",
            data=output,
            file_name="Route_Optimized_MinCompany.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("📌 Please upload a file to start.")

company_total_trips = sum(result_df["Company_Trips"])
pl3_total_trips = sum(result_df["3PL_Trips"])
if company_total_trips > pl3_total_trips:
    st.success("🚀 Distribution effectively utilizes company fleet with minimal 3PL dependency.")
elif pl3_total_trips > company_total_trips * 2:
    st.warning("⚠️ High dependency on 3PL detected. Consider increasing company fleet or revising costs.")
else:
    st.info("💡 Balanced distribution achieved. You may review cost structure for further savings.")

