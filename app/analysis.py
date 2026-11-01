"""Firestore에서 조회한 현재 데이터로 통계를 계산합니다."""

from collections import defaultdict
from statistics import mean


def summarize(records):
    if not records:
        return {"city": "대전", "count": 0, "period": None, "unit": "°C",
                "metric": "일평균기온", "metrics": {}, "monthly": [], "trend": None,
                "warmest_dates": [], "coldest_dates": [], "storage": "firestore"}
    records = sorted(records, key=lambda row: row["date"])
    values = [row["value"] for row in records]
    groups = defaultdict(list)
    for row in records:
        groups[row["date"][:7]].append(row["value"])
    monthly = [{"month": month, "count": len(items), "average": round(mean(items), 2)}
               for month, items in sorted(groups.items())]
    trend = None
    if len(monthly) >= 2:
        previous, latest = monthly[-2:]
        difference = round(latest["average"] - previous["average"], 2)
        trend = {"comparison": f"{latest['month']} 평균 - {previous['month']} 평균",
                 "difference_celsius": difference,
                 "direction": "상승" if difference > 0 else "하락" if difference < 0 else "유지"}
    return {
        "city": "대전", "period": f"{records[0]['date']} ~ {records[-1]['date']}",
        "count": len(records), "unit": "°C", "metric": "일평균기온", "storage": "firestore",
        "metrics": {"average": round(mean(values), 2), "max": max(values), "min": min(values)},
        "warmest_dates": sorted({r["date"] for r in records if r["value"] == max(values)}),
        "coldest_dates": sorted({r["date"] for r in records if r["value"] == min(values)}),
        "monthly": monthly, "trend": trend,
        "interpretation": "최대·최소는 일평균기온의 비교이며, 추세는 저장된 최근 두 달의 비교입니다.",
    }
